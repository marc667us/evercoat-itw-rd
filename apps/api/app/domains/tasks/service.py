"""Tasks and the My Work inbox.

My Work is the single place a user is told what the system needs from
them. Every other module -- formula approval, test review, failure
investigation, stage gates -- creates tasks through :func:`create_task`
rather than growing its own queue. CLAUDE.md §12 names this as shared
infrastructure specifically so that Pilot, Validation, Stability, Quality
and Qualification add zero new task machinery.

Two design points carry real weight.

**A task may be addressed to a ROLE rather than a person.** "A lab
technician must run this" is a true statement before anyone has been
picked, and forcing an assignee at creation time would mean the creating
module has to know the org chart. The DB constraint ``tasks_has_an_owner``
requires one of the two, never neither.

**Sidebar counts are actionable items, not row counts** (CLAUDE.md §11).
:func:`my_work_counts` therefore counts what the user can act on now --
open and in-progress work addressed to them or to a role they hold --
and excludes blocked, completed, delegated and cancelled. A badge that
counts rows the user cannot act on trains them to ignore the badge.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.audit import AuditEvent, write_audit
from app.core.logging import log_audit

# Cross-domain, and it cannot cycle: `messaging` imports only `app.core.*`.
# §12 names NotificationService as shared infrastructure -- a module that
# grows its own notification table is the duplication that rule forbids.
from app.core.notifications import notify
from app.core.tenancy import require_active_member

__all__ = [
    "TaskError",
    "TaskInput",
    "TaskNotFoundError",
    "TaskStateError",
    "claim_task",
    "complete_task",
    "create_task",
    "my_work",
    "my_work_counts",
    "project_tasks",
    "reassign_task",
]

# Statuses a user can still act on. Kept as one definition because the
# inbox query, the count query and the completion guard must agree -- if
# the badge counts a status the list hides, the user sees "3" beside an
# empty inbox and stops trusting both.
_ACTIONABLE = ("open", "in_progress")

# Statuses from which completion is legal. Completing a cancelled task
# would resurrect work somebody deliberately stopped.
_COMPLETABLE = {"open", "in_progress", "blocked"}


class TaskError(RuntimeError):
    """Base for refusals that are business rules, not bugs."""


class TaskNotFoundError(TaskError):
    pass


class TaskStateError(TaskError):
    pass


@dataclass(frozen=True, slots=True)
class TaskInput:
    task_type: str
    title: str
    description: str | None = None
    priority: str = "medium"
    assigned_user_id: uuid.UUID | None = None
    assigned_role: str | None = None
    project_id: uuid.UUID | None = None
    due_date: date | None = None
    source_event: str | None = None
    entity_type: str | None = None
    entity_id: uuid.UUID | None = None
    required_action: str | None = None


def create_task(
    session: Session,
    *,
    data: TaskInput,
    actor_id: uuid.UUID,
    organization_id: uuid.UUID,
) -> uuid.UUID:
    """Raise a task. The one entry point every module uses.

    Validated here rather than relying on the CHECK constraint alone, so
    the caller gets a domain error naming the problem instead of an
    IntegrityError naming a constraint. Both fire; the constraint is the
    backstop for anything that reaches the table another way.
    """
    if data.assigned_user_id is None and not data.assigned_role:
        raise TaskStateError("a task needs an owner: give it an assigned user or an assigned role")
    if not data.title.strip():
        raise TaskStateError("a task needs a title")

    # The assignee must belong to THIS organization. `tasks.assigned_user_id`
    # is a plain REFERENCES core.users(id) -- users are not tenant-scoped --
    # so the FK happily accepts a user who exists only in another tenant.
    # Referential integrity bypasses RLS even under FORCE, so nothing else
    # in this function would have caught it (Codex C1).
    if data.assigned_user_id is not None:
        require_active_member(
            session,
            user_id=data.assigned_user_id,
            organization_id=organization_id,
            role_description="assignee",
        )

    task_id: uuid.UUID = session.execute(
        text(
            """
            INSERT INTO workflow.tasks
                (organization_id, project_id, task_type, title, description,
                 priority, assigned_user_id, assigned_role, due_date,
                 source_event, entity_type, entity_id, required_action)
            VALUES (:org, :pid, :ttype, :title, :description, :priority,
                    :user, :role, :due, :source, :etype, :eid, :action)
            RETURNING id
            """
        ),
        {
            "org": organization_id,
            "pid": data.project_id,
            "ttype": data.task_type,
            "title": data.title.strip(),
            "description": data.description,
            "priority": data.priority,
            "user": data.assigned_user_id,
            "role": data.assigned_role,
            "due": data.due_date,
            "source": data.source_event,
            "etype": data.entity_type,
            "eid": data.entity_id,
            "action": data.required_action,
        },
    ).scalar_one()

    write_audit(
        session,
        AuditEvent(
            action="task.created",
            entity_type="task",
            entity_id=str(task_id),
            organization_id=organization_id,
            user_id=actor_id,
            new_state={
                "task_type": data.task_type,
                "title": data.title.strip(),
                "priority": data.priority,
                "assigned_role": data.assigned_role,
                "assigned_user_id": str(data.assigned_user_id) if data.assigned_user_id else None,
            },
            reason=data.source_event or "task created",
        ),
    )
    # 🔴 I8 -- A TASK NOBODY IS TOLD ABOUT IS NOT AN ASSIGNMENT.
    #
    # `notify()` had exactly ONE caller in the whole application
    # (`_resolve_mentions`), so §11's sidebar badge -- which counts ACTIONABLE
    # items -- read zero for everything except being @-mentioned. A chemist
    # could be assigned every task in the project and see no indication at all.
    #
    # `is_actionable=True` deliberately: an assigned task is the definition of
    # something the recipient must do, and §11 requires that distinction to
    # exist in the data or every count is just a row total.
    #
    # NOT sent to the person who created it. Being told you did the thing you
    # just did trains people to ignore the badge, which costs more than the
    # notification is worth.
    #
    # A ROLE assignment notifies nobody here on purpose: the task is unclaimed,
    # `my_work` surfaces it to every holder of that role, and fanning a
    # notification out to all of them would make one task look like several.
    #
    # 🔴 AND ONLY IF THE ASSIGNEE CAN SEE WHAT IT IS ABOUT. §7: a notification
    # must not disclose what its recipient cannot reach. `require_active_member`
    # above proves ORGANIZATION membership, which is not the same thing -- a
    # task on a RESTRICTED project can be assigned to an organization member
    # who is not on that project, and the notification's title would name work
    # they have no access to. The notification becomes the leak.
    #
    # The same predicate `_resolve_mentions` uses for a project channel, plus
    # the project LEAD, whom migration 006 already grants read access on the
    # strength of `lead_user_id` alone.
    #
    # A task with NO project is organization-wide and reaches any member.
    #
    # The TASK IS STILL CREATED either way. Refusing the assignment would be a
    # different and larger decision; withholding the notification is the narrow
    # thing §7 actually requires.
    reachable = True
    if data.assigned_user_id is not None and data.project_id is not None:
        reachable = bool(
            session.execute(
                text(
                    """
                    SELECT EXISTS (
                        SELECT 1 FROM projects.projects p
                        WHERE p.id = :pid AND p.organization_id = :org
                          AND (
                                p.confidentiality = 'normal'
                                OR p.lead_user_id = :uid
                                OR EXISTS (
                                    SELECT 1 FROM projects.project_members pm
                                    WHERE pm.project_id = p.id
                                      AND pm.organization_id = p.organization_id
                                      AND pm.user_id = :uid
                                      AND pm.status = 'active'
                                )
                          )
                    )
                    """
                ),
                {"pid": data.project_id, "org": organization_id, "uid": data.assigned_user_id},
            ).scalar_one()
        )

    if data.assigned_user_id is not None and data.assigned_user_id != actor_id and reachable:
        notify(
            session,
            organization_id=organization_id,
            recipient_id=data.assigned_user_id,
            notification_type="task_assigned",
            title=data.title.strip(),
            body=data.description,
            entity_type="task",
            entity_id=task_id,
            is_actionable=True,
        )

    log_audit("task_created", task_id=str(task_id), task_type=data.task_type)
    return task_id


def my_work(
    session: Session,
    *,
    user_id: uuid.UUID,
    organization_id: uuid.UUID,
    role_codes: frozenset[str] | set[str],
    include_done: bool = False,
) -> list[dict[str, Any]]:
    """The caller's inbox: their tasks and their roles' unclaimed tasks.

    Ordered by urgency rather than by creation, because an inbox sorted
    newest-first buries the overdue critical item under today's routine
    ones. Overdue first, then priority, then due date.

    ``organization_id`` is filtered EXPLICITLY. RLS is the backstop, not
    the scoping mechanism -- the policy is permissive while the GUC is
    unset and the owner role bypasses it entirely, so a query that leans
    on RLS for correctness returns every tenant's rows under exactly the
    conditions a migration or a background job runs in.

    A role-addressed task is included only while ``assigned_user_id`` is
    NULL: once somebody claims it, it is theirs and must leave everyone
    else's inbox, or five people work the same item.
    """
    statuses = (
        list(_ACTIONABLE)
        if not include_done
        else [
            "open",
            "in_progress",
            "blocked",
            "completed",
            "delegated",
            "cancelled",
        ]
    )

    rows = session.execute(
        text(
            """
            SELECT t.id, t.task_type, t.title, t.description, t.priority,
                   t.status, t.due_date, t.required_action, t.entity_type,
                   t.entity_id, t.project_id, t.assigned_user_id,
                   t.assigned_role, t.created_at,
                   p.project_code, p.name AS project_name,
                   (t.due_date IS NOT NULL AND t.due_date < CURRENT_DATE) AS is_overdue
            FROM workflow.tasks t
            LEFT JOIN projects.projects p
                   ON p.id = t.project_id AND p.organization_id = t.organization_id
            WHERE t.organization_id = :org
              AND t.status = ANY(:statuses)
              AND (
                    t.assigned_user_id = :uid
                    -- Unclaimed role work. Once claimed it belongs to the
                    -- claimant and disappears from everyone else's inbox.
                 OR (t.assigned_user_id IS NULL AND t.assigned_role = ANY(:roles))
              )
            ORDER BY
                (t.due_date IS NOT NULL AND t.due_date < CURRENT_DATE) DESC,
                CASE t.priority WHEN 'critical' THEN 1 WHEN 'high' THEN 2
                                WHEN 'medium' THEN 3 ELSE 4 END,
                t.due_date NULLS LAST,
                t.created_at
            """
        ),
        {
            "org": organization_id,
            "uid": user_id,
            "roles": list(role_codes) or [""],
            "statuses": statuses,
        },
    ).mappings()
    return [dict(r) for r in rows]


def my_work_counts(
    session: Session,
    *,
    user_id: uuid.UUID,
    organization_id: uuid.UUID,
    role_codes: frozenset[str] | set[str],
) -> dict[str, int]:
    """Sidebar badge numbers -- ACTIONABLE items only.

    Deliberately built from the same predicate as :func:`my_work`. The two
    were written together because a count and a list that disagree is a
    defect users notice immediately and developers never do.
    """
    row = (
        session.execute(
            text(
                """
            SELECT
                COUNT(*) AS total,
                COUNT(*) FILTER (
                    WHERE t.due_date IS NOT NULL AND t.due_date < CURRENT_DATE
                ) AS overdue,
                COUNT(*) FILTER (WHERE t.priority IN ('critical','high')) AS urgent,
                COUNT(*) FILTER (WHERE t.assigned_user_id IS NULL) AS unclaimed
            FROM workflow.tasks t
            WHERE t.organization_id = :org
              AND t.status = ANY(:statuses)
              AND (
                    t.assigned_user_id = :uid
                 OR (t.assigned_user_id IS NULL AND t.assigned_role = ANY(:roles))
              )
            """
            ),
            {
                "org": organization_id,
                "uid": user_id,
                "roles": list(role_codes) or [""],
                "statuses": list(_ACTIONABLE),
            },
        )
        .mappings()
        .one()
    )
    return {k: int(v) for k, v in row.items()}


def claim_task(
    session: Session,
    *,
    task_id: uuid.UUID,
    user_id: uuid.UUID,
    organization_id: uuid.UUID,
    role_codes: frozenset[str] | set[str],
) -> None:
    """Take ownership of a role-addressed task.

    The claim is a conditional UPDATE rather than a read-then-write.
    Two technicians hitting Claim on the same task within the same second
    is not a hypothetical on a shared queue; the ``assigned_user_id IS
    NULL`` predicate in the WHERE clause means the second one updates zero
    rows and is told so, instead of silently stealing the first one's work.
    """
    updated = session.execute(
        text(
            """
            UPDATE workflow.tasks
            SET assigned_user_id = :uid,
                status = CASE WHEN status = 'open' THEN 'in_progress' ELSE status END,
                updated_at = now()
            WHERE id = :tid
              AND organization_id = :org
              AND assigned_user_id IS NULL
              AND assigned_role = ANY(:roles)
              AND status = ANY(:statuses)
            RETURNING id
            """
        ),
        {
            "tid": task_id,
            "org": organization_id,
            "uid": user_id,
            "roles": list(role_codes) or [""],
            "statuses": list(_ACTIONABLE),
        },
    ).scalar_one_or_none()

    if updated is None:
        # One message for "does not exist", "already claimed" and "not
        # addressed to your role". Distinguishing them would tell a caller
        # that a task they may not see exists.
        raise TaskStateError("task is not available to claim")

    write_audit(
        session,
        AuditEvent(
            action="task.claimed",
            entity_type="task",
            entity_id=str(task_id),
            organization_id=organization_id,
            user_id=user_id,
            new_state={"assigned_user_id": str(user_id)},
            reason="claimed from role queue",
        ),
    )


def complete_task(
    session: Session,
    *,
    task_id: uuid.UUID,
    actor_id: uuid.UUID,
    organization_id: uuid.UUID,
    outcome_note: str | None = None,
) -> None:
    """Mark a task done. Only its assignee may, **at write time**.

    ``completed_at`` and ``completed_by`` are written together because the
    ``tasks_completion_complete`` CHECK requires both -- a half-written
    completion is not a state this table permits.

    **The ownership and status tests live in the UPDATE's WHERE clause,
    not in a preceding SELECT.** An earlier version read the row, checked
    ``assigned_user_id == actor_id``, then issued an unconditional UPDATE.
    Between those two statements a concurrent reassignment or cancellation
    can land, and the former assignee completes a task they no longer own
    -- so "only the assignee may complete" was true at read time and false
    at write time (Codex C3). That is precisely the guarantee the route
    relies on to justify carrying no permission dependency, which made it
    load-bearing rather than incidental.

    The follow-up SELECT exists only to produce a specific error message
    when the UPDATE matches nothing. It cannot re-introduce the race: by
    then the write has already either happened or not.
    """
    updated = (
        session.execute(
            text(
                """
            UPDATE workflow.tasks
            SET status = 'completed', completed_at = now(),
                completed_by = :uid, updated_at = now()
            WHERE id = :tid
              AND organization_id = :org
              AND assigned_user_id = :uid
              AND status = ANY(:completable)
            RETURNING status
            """
            ),
            {
                "tid": task_id,
                "org": organization_id,
                "uid": actor_id,
                "completable": sorted(_COMPLETABLE),
            },
        )
        .mappings()
        .one_or_none()
    )

    if updated is None:
        # Diagnose only. The write has already been decided.
        current = (
            session.execute(
                text(
                    """
                SELECT status, assigned_user_id FROM workflow.tasks
                WHERE id = :tid AND organization_id = :org
                """
                ),
                {"tid": task_id, "org": organization_id},
            )
            .mappings()
            .one_or_none()
        )
        if current is None:
            raise TaskNotFoundError("task not found")
        if current["assigned_user_id"] != actor_id:
            raise TaskStateError("only the assignee may complete a task")
        raise TaskStateError(f"a {current['status']} task cannot be completed")

    write_audit(
        session,
        AuditEvent(
            action="task.completed",
            entity_type="task",
            entity_id=str(task_id),
            organization_id=organization_id,
            user_id=actor_id,
            new_state={"status": "completed"},
            reason=outcome_note or "task completed",
        ),
    )
    log_audit("task_completed", task_id=str(task_id))


def reassign_task(
    session: Session,
    *,
    task_id: uuid.UUID,
    to_user_id: uuid.UUID,
    actor_id: uuid.UUID,
    organization_id: uuid.UUID,
    reason: str,
) -> None:
    """Delegate a task to somebody else.

    A reason is required. "Why is this suddenly mine" is the first thing
    the new assignee asks, and the audit record is the only place that
    answer can survive.

    The target must be an active member of this organization. Without
    that check a task could be delegated to a user id from another tenant
    -- the FK to core.users would permit it, because referential
    integrity bypasses RLS even under FORCE. See `app.core.tenancy`.

    Like :func:`complete_task`, the status test is in the UPDATE's WHERE
    clause. Checked in a preceding SELECT it could be overtaken by a
    concurrent completion, and the result was a *completed* task whose
    ``assigned_user_id`` named somebody other than its ``completed_by``
    -- two columns disagreeing about who did the work (Codex C6).
    """
    if not reason or not reason.strip():
        raise TaskStateError("a reassignment reason is required")

    require_active_member(
        session,
        user_id=to_user_id,
        organization_id=organization_id,
        role_description="target user",
    )

    updated = (
        session.execute(
            text(
                """
            UPDATE workflow.tasks
            SET assigned_user_id = :to, updated_at = now()
            WHERE id = :tid
              AND organization_id = :org
              AND status <> ALL(:terminal)
            -- The pre-update assignee is deliberately NOT returned here.
            -- RETURNING yields post-update values, so reading it back
            -- would record the new assignee as the previous one -- an
            -- audit entry that is worse than none because it looks
            -- authoritative. The audit records who it moved TO; who it
            -- moved FROM is the previous task.reassigned/claimed event.
            RETURNING id
            """
            ),
            {
                "tid": task_id,
                "org": organization_id,
                "to": to_user_id,
                "terminal": ["completed", "cancelled"],
            },
        )
        .mappings()
        .one_or_none()
    )

    if updated is None:
        current = (
            session.execute(
                text(
                    """
                SELECT status FROM workflow.tasks
                WHERE id = :tid AND organization_id = :org
                """
                ),
                {"tid": task_id, "org": organization_id},
            )
            .mappings()
            .one_or_none()
        )
        if current is None:
            raise TaskNotFoundError("task not found")
        raise TaskStateError(f"a {current['status']} task cannot be reassigned")

    write_audit(
        session,
        AuditEvent(
            action="task.reassigned",
            entity_type="task",
            entity_id=str(task_id),
            organization_id=organization_id,
            user_id=actor_id,
            new_state={"assigned_user_id": str(to_user_id)},
            reason=reason,
        ),
    )


def project_tasks(
    session: Session, *, project_id: uuid.UUID, organization_id: uuid.UUID
) -> list[dict[str, Any]]:
    """Every task on a project, for the project workspace.

    Unlike :func:`my_work` this is not filtered by assignee -- the project
    view answers "what is outstanding here", which includes other people's
    work. RLS still restricts it to project members.
    """
    rows = session.execute(
        text(
            """
            SELECT t.id, t.task_type, t.title, t.priority, t.status,
                   t.due_date, t.assigned_role, t.required_action,
                   u.display_name AS assignee,
                   (t.due_date IS NOT NULL AND t.due_date < CURRENT_DATE
                    AND t.status = ANY(:statuses)) AS is_overdue
            FROM workflow.tasks t
            -- The assignee's name through the MEMBERSHIP (052): the global
            -- identity's name belongs to whichever tenant created it, and
            -- the runtime role can no longer read it. Scoped explicitly, not
            -- by RLS, so an unset org GUC cannot fan this out.
            LEFT JOIN core.organization_members u
                   ON u.user_id = t.assigned_user_id AND u.organization_id = :org
            WHERE t.project_id = :pid AND t.organization_id = :org
            ORDER BY
                CASE t.status WHEN 'blocked' THEN 1 WHEN 'in_progress' THEN 2
                              WHEN 'open' THEN 3 ELSE 4 END,
                CASE t.priority WHEN 'critical' THEN 1 WHEN 'high' THEN 2
                                WHEN 'medium' THEN 3 ELSE 4 END,
                t.due_date NULLS LAST
            """
        ),
        {"pid": project_id, "org": organization_id, "statuses": list(_ACTIONABLE)},
    ).mappings()
    return [dict(r) for r in rows]
