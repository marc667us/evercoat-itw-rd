"""Opportunities — the first link in the digital thread.

    Opportunity -> Project -> Requirement -> ... -> Released Product

An opportunity is a market need before anyone has committed R&D money to
it. It carries a gate decision, and on approval it becomes a project that
keeps a permanent link back here. That link is the reason this module
exists at all: CLAUDE.md §2 forbids isolated data islands, and "why are
we spending eight months on this product" is answerable only if the
originating opportunity and its decision rationale survive.

**The conversion is one transaction.** An approved opportunity with no
project, or a project whose `opportunity_id` points at an opportunity
still marked `awaiting_decision`, are both states the thread cannot
explain. They are created together or not at all.

**A decision is never just a status change.** The DB constraint
`opportunities_decision_complete` requires `decision`, `decided_by` and
`decided_at` to arrive together; the rationale is required here on top of
that, because a rejected opportunity with no stated reason gets
re-proposed every year by somebody who was not in the room.
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
from app.core.tenancy import require_active_member

__all__ = [
    "OpportunityDecision",
    "OpportunityError",
    "OpportunityInput",
    "OpportunityNotFoundError",
    "OpportunityStateError",
    "convert_to_project",
    "create_opportunity",
    "decide_opportunity",
    "list_opportunities",
    "opportunity_detail",
]

# Only an opportunity that has been worked up can be decided. Deciding a
# draft means deciding on an idea nobody has assessed, which is how the
# feasibility stage becomes optional in practice.
#
# `on_hold` is in this set deliberately. Without it, `hold` would be a
# one-way door: the status existed in the table from migration 003 and
# nothing could ever leave it, so "revisit next quarter" meant "never".
# See migration 008.
_DECIDABLE = {"feasibility", "awaiting_decision", "on_hold"}

_DECISIONS = {"approve", "reject", "hold", "more_information"}

# Which decisions move the opportunity where.
#
# `more_information` returns it to feasibility -- there is more work to
# do and somebody must do it. `hold` parks it in `on_hold`, which is a
# different statement: the work is understood and the timing is wrong.
# Collapsing the two would lose the distinction the funnel report needs.
_STATUS_AFTER = {
    "approve": "approved",
    "reject": "rejected",
    "hold": "on_hold",
    "more_information": "feasibility",
}


class OpportunityError(RuntimeError):
    """Base for refusals that are business rules, not bugs."""


class OpportunityNotFoundError(OpportunityError):
    pass


class OpportunityStateError(OpportunityError):
    pass


@dataclass(frozen=True, slots=True)
class OpportunityInput:
    opportunity_code: str
    title: str
    market_need: str | None = None
    product_family: str | None = None
    target_application: str | None = None
    technical_concept: str | None = None
    priority: str = "medium"


@dataclass(frozen=True, slots=True)
class OpportunityDecision:
    decision: str
    rationale: str


def create_opportunity(
    session: Session,
    *,
    data: OpportunityInput,
    actor_id: uuid.UUID,
    organization_id: uuid.UUID,
) -> uuid.UUID:
    """Register a market need.

    The code is unique per organization, never globally
    (``opportunities_org_code_key``). A global constraint would stop Org B
    creating ``OPP-2026-001`` because Org A has one, and the violation
    message itself would disclose that another tenant holds that code.
    """
    if not data.title.strip():
        raise OpportunityStateError("an opportunity needs a title")

    clash = session.execute(
        text(
            """
            SELECT 1 FROM innovation.opportunities
            WHERE organization_id = :org AND opportunity_code = :code
            """
        ),
        {"org": organization_id, "code": data.opportunity_code},
    ).scalar_one_or_none()
    if clash:
        raise OpportunityStateError(f"opportunity code {data.opportunity_code} already exists")

    opportunity_id: uuid.UUID = session.execute(
        text(
            """
            INSERT INTO innovation.opportunities
                (organization_id, opportunity_code, title, market_need,
                 product_family, target_application, technical_concept,
                 priority, created_by)
            VALUES (:org, :code, :title, :need, :family, :application,
                    :concept, :priority, :actor)
            RETURNING id
            """
        ),
        {
            "org": organization_id,
            "code": data.opportunity_code,
            "title": data.title.strip(),
            "need": data.market_need,
            "family": data.product_family,
            "application": data.target_application,
            "concept": data.technical_concept,
            "priority": data.priority,
            "actor": actor_id,
        },
    ).scalar_one()

    write_audit(
        session,
        AuditEvent(
            action="opportunity.created",
            entity_type="opportunity",
            entity_id=str(opportunity_id),
            organization_id=organization_id,
            user_id=actor_id,
            new_state={
                "opportunity_code": data.opportunity_code,
                "title": data.title.strip(),
                "status": "draft",
                "priority": data.priority,
            },
            reason="opportunity registered",
        ),
    )
    log_audit("opportunity_created", opportunity_code=data.opportunity_code)
    return opportunity_id


def decide_opportunity(
    session: Session,
    *,
    opportunity_id: uuid.UUID,
    decision: OpportunityDecision,
    actor_id: uuid.UUID,
    organization_id: uuid.UUID,
) -> str:
    """Record the gate decision. Returns the resulting status.

    Humans approve (rule 4). Nothing in this function may be reached by an
    agent -- it is behind ``opportunity.decide``, which is granted to the
    Director and Lead roles only.

    A second decision on an already-decided opportunity is refused rather
    than overwritten. Overwriting would destroy the first decision and its
    rationale, and "it was rejected in March and approved in April" is
    exactly the history a governance audit asks for.
    """
    if decision.decision not in _DECISIONS:
        raise OpportunityStateError(
            f"unknown decision '{decision.decision}'; expected one of {sorted(_DECISIONS)}"
        )
    if not decision.rationale or not decision.rationale.strip():
        raise OpportunityStateError("a decision rationale is required")

    new_status = _STATUS_AFTER[decision.decision]

    # The decidable-status test is in the WHERE clause, not in a preceding
    # SELECT.
    #
    # Read-then-write here is not a theoretical race: two Directors
    # clicking Approve and Reject on the same gate both observed a
    # decidable status, both wrote, both reported success, and only the
    # LAST decision and rationale survived -- while both audit events
    # claimed to be the decision (Codex C5). That is exactly the history
    # loss the "a second decision is refused" rule exists to prevent, so
    # the rule has to hold at write time to mean anything.
    #
    # decision, decided_by and decided_at are set in ONE statement because
    # opportunities_decision_complete requires all three or none.
    updated = (
        session.execute(
            text(
                """
            UPDATE innovation.opportunities
            SET status = :status,
                decision = :decision,
                decided_by = :actor,
                decided_at = now(),
                decision_rationale = :rationale,
                updated_at = now()
            WHERE id = :oid
              AND organization_id = :org
              AND status = ANY(:decidable)
            RETURNING opportunity_code
            """
            ),
            {
                "oid": opportunity_id,
                "org": organization_id,
                "status": new_status,
                "decision": decision.decision,
                "actor": actor_id,
                "rationale": decision.rationale.strip(),
                "decidable": sorted(_DECIDABLE),
            },
        )
        .mappings()
        .one_or_none()
    )

    if updated is None:
        # Diagnose only -- the write has already been decided either way.
        current = (
            session.execute(
                text(
                    """
                SELECT status FROM innovation.opportunities
                WHERE id = :oid AND organization_id = :org
                """
                ),
                {"oid": opportunity_id, "org": organization_id},
            )
            .mappings()
            .one_or_none()
        )
        if current is None:
            raise OpportunityNotFoundError("opportunity not found")
        raise OpportunityStateError(
            f"an opportunity in '{current['status']}' cannot be decided; "
            f"it must be in {sorted(_DECIDABLE)}"
        )

    write_audit(
        session,
        AuditEvent(
            action="opportunity.decided",
            entity_type="opportunity",
            entity_id=str(opportunity_id),
            organization_id=organization_id,
            user_id=actor_id,
            new_state={"status": new_status, "decision": decision.decision},
            reason=decision.rationale.strip(),
        ),
    )
    log_audit(
        "opportunity_decided",
        opportunity_code=updated["opportunity_code"],
        decision=decision.decision,
    )
    return new_status


def convert_to_project(
    session: Session,
    *,
    opportunity_id: uuid.UUID,
    project_code: str,
    name: str,
    lead_user_id: uuid.UUID,
    actor_id: uuid.UUID,
    organization_id: uuid.UUID,
    target_release_date: date | None = None,
    confidentiality: str = "normal",
) -> uuid.UUID:
    """Turn an APPROVED opportunity into a project, keeping the link.

    Refused unless the opportunity is approved. Converting a rejected or
    undecided opportunity would create a project whose justification does
    not exist, and the digital thread would then contain a link that
    contradicts itself.

    One opportunity yields one project. A second conversion is refused
    rather than creating a sibling, because two projects claiming the same
    origin makes "what did this opportunity produce" unanswerable.

    The lead is enrolled as a project member in the same transaction. A
    restricted project whose own lead is not a member is invisible to its
    lead on the very next request -- RLS behaving correctly, looking
    exactly like a failed save.

    **That enrolment is why `lead_user_id` must be validated first.**
    `projects.lead_user_id` and `project_members.user_id` are both plain
    `REFERENCES core.users(id)`; referential integrity bypasses RLS even
    under FORCE, so a user id belonging only to another tenant is
    accepted by the FK. Unchecked, this function did not merely store a
    foreign id -- it went on to enrol that user as a member of the new
    project, handing them access (Codex C2).
    """
    require_active_member(
        session,
        user_id=lead_user_id,
        organization_id=organization_id,
        role_description="project lead",
    )

    current = (
        session.execute(
            text(
                """
            SELECT o.status, o.opportunity_code, o.title, o.product_family,
                   o.technical_concept, o.priority,
                   EXISTS (
                       SELECT 1 FROM projects.projects p
                       WHERE p.opportunity_id = o.id
                         AND p.organization_id = o.organization_id
                   ) AS already_converted
            FROM innovation.opportunities o
            WHERE o.id = :oid AND o.organization_id = :org
            """
            ),
            {"oid": opportunity_id, "org": organization_id},
        )
        .mappings()
        .one_or_none()
    )
    if current is None:
        raise OpportunityNotFoundError("opportunity not found")
    if current["status"] != "approved":
        raise OpportunityStateError(
            f"only an approved opportunity becomes a project; this one is '{current['status']}'"
        )
    if current["already_converted"]:
        raise OpportunityStateError("this opportunity has already been converted to a project")

    clash = session.execute(
        text("SELECT 1 FROM projects.projects WHERE project_code = :c AND organization_id = :org"),
        {"c": project_code, "org": organization_id},
    ).scalar_one_or_none()
    if clash:
        raise OpportunityStateError(f"project code {project_code} already exists")

    project_id: uuid.UUID = session.execute(
        text(
            """
            INSERT INTO projects.projects
                (organization_id, project_code, name, product_family,
                 description, technical_objective, priority, confidentiality,
                 lead_user_id, opportunity_id, target_release_date)
            VALUES (:org, :code, :name, :family, :description, :concept,
                    :priority, :confidentiality, :lead, :oid, :target)
            RETURNING id
            """
        ),
        {
            "org": organization_id,
            "code": project_code,
            "name": name,
            "family": current["product_family"],
            "description": f"Converted from opportunity {current['opportunity_code']}: "
            f"{current['title']}",
            "concept": current["technical_concept"],
            "priority": current["priority"],
            "confidentiality": confidentiality,
            "lead": lead_user_id,
            "oid": opportunity_id,
            "target": target_release_date,
        },
    ).scalar_one()

    session.execute(
        text(
            """
            INSERT INTO projects.project_members
                (organization_id, project_id, user_id, project_role)
            VALUES (:org, :pid, :uid, 'lead')
            ON CONFLICT DO NOTHING
            """
        ),
        {"org": organization_id, "pid": project_id, "uid": lead_user_id},
    )

    session.execute(
        text(
            """
            UPDATE innovation.opportunities
            SET status = 'converted', updated_at = now()
            WHERE id = :oid AND organization_id = :org
            """
        ),
        {"oid": opportunity_id, "org": organization_id},
    )

    write_audit(
        session,
        AuditEvent(
            action="opportunity.converted",
            entity_type="opportunity",
            entity_id=str(opportunity_id),
            organization_id=organization_id,
            user_id=actor_id,
            previous_state={"status": "approved"},
            new_state={"status": "converted", "project_id": str(project_id)},
            reason=f"converted to project {project_code}",
        ),
    )
    log_audit(
        "opportunity_converted",
        opportunity_code=current["opportunity_code"],
        project_code=project_code,
    )
    return project_id


def list_opportunities(
    session: Session, *, organization_id: uuid.UUID, status: str | None = None, limit: int = 200
) -> list[dict[str, Any]]:
    """The innovation funnel, most urgent first.

    **Bounded.** This returned every visible row. Every other collection
    in this codebase caps at 200 in its service function; opportunities
    and projects were the two that did not, so a large tenant — or a
    caller repeating the request — could make the database, the API
    process and the response body grow without limit. Raised by Codex in
    the 2026-08-20 API security audit.

    The ordering is already deterministic (priority, then `created_at`
    descending), which is what makes a bare `LIMIT` safe to apply: an
    unordered truncation returns an arbitrary subset and reads as missing
    records.
    """
    rows = session.execute(
        text(
            """
            SELECT o.id, o.opportunity_code, o.title, o.product_family,
                   o.target_application, o.status, o.priority, o.decision,
                   o.decided_at, o.created_at,
                   u.display_name AS created_by_name,
                   p.id AS project_id, p.project_code
            FROM innovation.opportunities o
            JOIN core.users u ON u.id = o.created_by
            LEFT JOIN projects.projects p
                   ON p.opportunity_id = o.id
                  AND p.organization_id = o.organization_id
            WHERE o.organization_id = :org
              -- CAST is required, not cosmetic. An untyped NULL bind
              -- appearing only in `:status IS NULL` gives the planner no
              -- context to infer a type from, and PostgreSQL refuses the
              -- whole statement with "could not determine data type of
              -- parameter $2" -- but only on the unfiltered call, so a
              -- test that always passed a status would never see it.
              AND (CAST(:status AS TEXT) IS NULL OR o.status = CAST(:status AS TEXT))
            ORDER BY
                CASE o.priority WHEN 'critical' THEN 1 WHEN 'high' THEN 2
                                WHEN 'medium' THEN 3 ELSE 4 END,
                o.created_at DESC
            LIMIT :limit
            """
        ),
        {"org": organization_id, "status": status, "limit": limit},
    ).mappings()
    return [dict(r) for r in rows]


def opportunity_detail(
    session: Session, *, opportunity_id: uuid.UUID, organization_id: uuid.UUID
) -> dict[str, Any]:
    """One opportunity with its decision and resulting project."""
    row = (
        session.execute(
            text(
                """
            SELECT o.*, u.display_name AS created_by_name,
                   d.display_name AS decided_by_name,
                   p.id AS project_id, p.project_code, p.name AS project_name
            FROM innovation.opportunities o
            JOIN core.users u ON u.id = o.created_by
            LEFT JOIN core.users d ON d.id = o.decided_by
            LEFT JOIN projects.projects p
                   ON p.opportunity_id = o.id
                  AND p.organization_id = o.organization_id
            WHERE o.id = :oid AND o.organization_id = :org
            """
            ),
            {"oid": opportunity_id, "org": organization_id},
        )
        .mappings()
        .one_or_none()
    )
    if row is None:
        raise OpportunityNotFoundError("opportunity not found")
    return dict(row)
