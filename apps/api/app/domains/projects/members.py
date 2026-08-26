"""Project membership — the write half of `project.assign_member`.

The permission `project.assign_member` has existed since migration 002
and was granted to `product_development_lead`. No route used it. Members
could only ever be created as a side effect of two operations: creating a
project (the creator is enrolled as lead) and converting an opportunity
(the lead is enrolled). There was no way to add a second person to a
project, and no way to remove anyone.

That matters more here than it would in most systems, because membership
is not a convenience list. It is the RLS predicate: `core.is_project_member`
gates every project-scoped table, so "add a colleague to this project" and
"let this colleague see any of this project's data" are the same action.

**Removal deactivates; it does not DELETE.** `project_members.status`
already carries `active`/`inactive`, `core.is_project_member` already
filters on `status = 'active'`, and CLAUDE.md §5 says to retire rather
than delete R&D history. Deleting the row would also destroy the record
that the person ever had access, which is the first thing anyone asks
after an incident.
"""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.audit import AuditEvent, write_audit
from app.core.tenancy import require_active_member

__all__ = [
    "MemberError",
    "MemberNotFoundError",
    "ProjectLeadNotRemovableError",
    "add_member",
    "list_members",
    "remove_member",
]


class MemberError(RuntimeError):
    """Base for refusals that are business rules, not bugs."""


class MemberNotFoundError(MemberError):
    pass


class ProjectLeadNotRemovableError(MemberError):
    """The project's own lead may not be removed from its member list."""


def add_member(
    session: Session,
    *,
    project_id: uuid.UUID,
    organization_id: uuid.UUID,
    actor_id: uuid.UUID,
    user_id: uuid.UUID,
    project_role: str,
) -> uuid.UUID:
    """Add someone to the project, or restore and re-role a past member.

    `require_active_member` is what stops this becoming a cross-tenant
    hole. `project_members.user_id` is a plain `REFERENCES core.users(id)`
    -- users are not tenant-scoped -- and referential integrity bypasses
    RLS even under FORCE. Without this check any user id in the entire
    system could be enrolled into this project, and enrolment is precisely
    what grants read access to it.

    The write is an UPSERT because `project_members_unique (project_id,
    user_id)` means a previously removed member still has a row. A plain
    INSERT would fail with a duplicate-key error on the most ordinary
    action there is -- re-adding someone who was taken off the project
    last month.
    """
    require_active_member(
        session,
        user_id=user_id,
        organization_id=organization_id,
        role_description="project member",
    )

    member_id: uuid.UUID = session.execute(
        text(
            """
            INSERT INTO projects.project_members
                (organization_id, project_id, user_id, project_role, status)
            VALUES (:org, :pid, :uid, :role, 'active')
            ON CONFLICT (project_id, user_id) DO UPDATE
                SET status = 'active',
                    project_role = EXCLUDED.project_role
            RETURNING id
            """
        ),
        {"org": organization_id, "pid": project_id, "uid": user_id, "role": project_role},
    ).scalar_one()

    write_audit(
        session,
        AuditEvent(
            action="project.member_added",
            entity_type="project_member",
            entity_id=str(member_id),
            organization_id=organization_id,
            user_id=actor_id,
            new_state={
                "project_id": str(project_id),
                "user_id": str(user_id),
                "project_role": project_role,
            },
            reason="member added to project",
        ),
    )
    return member_id


def remove_member(
    session: Session,
    *,
    project_id: uuid.UUID,
    organization_id: uuid.UUID,
    actor_id: uuid.UUID,
    user_id: uuid.UUID,
    reason: str,
) -> None:
    """Deactivate a membership, refusing to strand the project's own lead.

    **Why the lead is protected.** Migration 006 lets `lead_user_id` read
    the project row without a membership, so removing the lead looks
    harmless -- they can still open the project. But that escape exists
    only on `projects.projects`. Every child policy (milestones, risks,
    requirements, project_stages, stage_transitions, tasks) tests
    `core.is_project_member` and nothing else. On a restricted project the
    lead would therefore keep the project header and lose every record
    inside it, which presents as "the project is empty" rather than as a
    permission error.

    Reassigning the lead is a different operation and must happen first.

    The guard is in the UPDATE's own WHERE clause rather than in a
    preceding SELECT, so a concurrent lead change cannot slip between the
    check and the write.
    """
    row = (
        session.execute(
            text(
                """
                WITH target AS (
                    SELECT pm.id, pm.status, pm.project_role,
                           (p.lead_user_id = pm.user_id) AS is_project_lead
                    FROM projects.project_members pm
                    JOIN projects.projects p
                      ON p.id = pm.project_id AND p.organization_id = pm.organization_id
                    WHERE pm.project_id = :pid
                      AND pm.user_id = :uid
                      AND pm.organization_id = :org
                      -- Only an ACTIVE membership can be removed. Without
                      -- this, removing an already-inactive member reports
                      -- success and writes an audit row claiming a
                      -- transition from 'active' that never happened
                      -- (Codex review, finding 10).
                      AND pm.status = 'active'
                    -- BOTH rows are locked. `FOR UPDATE OF pm` alone left
                    -- p.lead_user_id read from an unlocked row, so a
                    -- concurrent transaction could make this user the lead
                    -- while we deactivated them -- defeating the very
                    -- guard below (Codex review, finding 6).
                    FOR UPDATE OF pm, p
                )
                UPDATE projects.project_members m
                SET status = 'inactive'
                FROM target
                WHERE m.id = target.id
                  AND target.is_project_lead IS NOT TRUE
                RETURNING m.id AS member_id, target.project_role AS project_role
                """
            ),
            {"pid": project_id, "uid": user_id, "org": organization_id},
        )
        .mappings()
        .one_or_none()
    )

    if row is None:
        # The UPDATE matched nothing. Two causes, and they need different
        # answers, so ask which one -- but only now, after the write has
        # already failed to apply. This read cannot race the write into
        # doing the wrong thing; it only chooses the message.
        is_lead = session.execute(
            text(
                """
                SELECT EXISTS (
                    SELECT 1 FROM projects.projects
                    WHERE id = :pid AND organization_id = :org AND lead_user_id = :uid
                )
                """
            ),
            {"pid": project_id, "org": organization_id, "uid": user_id},
        ).scalar_one()

        if is_lead:
            raise ProjectLeadNotRemovableError(
                "this user is the project lead; on a restricted project removing "
                "them would leave them the project header and none of its "
                "records. Reassign the lead first."
            )
        raise MemberNotFoundError("membership not found")

    write_audit(
        session,
        AuditEvent(
            action="project.member_removed",
            entity_type="project_member",
            entity_id=str(row["member_id"]),
            organization_id=organization_id,
            user_id=actor_id,
            previous_state={"status": "active", "project_role": row["project_role"]},
            new_state={"status": "inactive"},
            reason=reason,
        ),
    )


def list_members(
    session: Session, *, project_id: uuid.UUID, organization_id: uuid.UUID
) -> list[dict[str, Any]]:
    """Who is on the project, including who used to be.

    Inactive members are returned rather than filtered out. "Who has ever
    had access to this project" is the question asked after an incident,
    and a list that silently drops them cannot answer it.
    """
    rows = session.execute(
        text(
            """
            SELECT pm.id, pm.user_id, pm.project_role, pm.status, pm.created_at,
                   u.display_name, u.email::text AS email,
                   (p.lead_user_id = pm.user_id) AS is_project_lead
            FROM projects.project_members pm
            -- 🔴 THE ORGANIZATION'S OWN VIEW OF THE PERSON (052).
            --
            -- This joined `core.users`, whose address and name belong to
            -- whichever tenant first created the identity — so "who has ever
            -- had access to this project" could name somebody by another
            -- company's address. `evercoat_app` can no longer read those
            -- columns at all (I106). The membership is not filtered by
            -- status: a departed colleague is deactivated, never deleted, so
            -- the row that answers the post-incident question is still here.
            JOIN core.organization_members u
              ON u.user_id = pm.user_id AND u.organization_id = :org
            JOIN projects.projects p
              ON p.id = pm.project_id AND p.organization_id = pm.organization_id
            WHERE pm.project_id = :pid AND pm.organization_id = :org
            ORDER BY
                CASE pm.status WHEN 'active' THEN 0 ELSE 1 END,
                u.display_name
            """
        ),
        {"pid": project_id, "org": organization_id},
    ).mappings()
    return [dict(r) for r in rows]
