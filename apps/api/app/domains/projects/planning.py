"""Project plan — milestones and risks.

**Why this module exists.** `projects.milestones` and `projects.risks`
have had tables since migration 003, indexes, RLS policies, and counters
on the project dashboard. They had no writer. Not a route, not a service;
`milestones` did not even have a test fixture. Every counter the dashboard
rendered for them was structurally incapable of being anything but zero,
and a confident zero is worse than a blank: the reader cannot tell "this
project has no open risks" from "this product cannot record risks".

Found by asking of each entity the question that keeps finding this class
of hole -- *which production path WRITES it?*

Two rules shape everything below.

**No read-then-write.** Every mutation is a single statement whose guard
lives in its own WHERE clause, with the prior state captured by a CTE in
the same statement. A rule checked in a SELECT and enforced in a later
UPDATE is unknown at write time: between the two, another transaction can
change exactly the thing that was checked. Four instances of that pattern
were found in review last session; none are reintroduced here.

**References are not reads.** `risks.owner_user_id` is a plain
`REFERENCES core.users(id)`, because users are not tenant-scoped.
Referential integrity bypasses RLS even under FORCE, so RLS gives no
protection at all here: without an explicit check, a risk could be
assigned to an owner in another organization. Every path that accepts a
user id calls `require_active_member`.
"""

from __future__ import annotations

import datetime as dt
import uuid
from dataclasses import dataclass

from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.audit import AuditEvent, write_audit
from app.core.tenancy import require_active_member

__all__ = [
    "MilestoneError",
    "MilestoneInput",
    "MilestoneNotFoundError",
    "PlanningError",
    "RiskDuplicateError",
    "RiskError",
    "RiskInput",
    "RiskInvalidError",
    "RiskNotFoundError",
    "create_milestone",
    "create_risk",
    "list_milestones",
    "list_risks",
    "set_milestone_status",
    "update_risk",
]

# Statuses that mean the milestone is finished, one way or the other.
# Migration 012 requires an actual_date for exactly these and forbids one
# for the rest.
_MILESTONE_CLOSED = frozenset({"met", "missed"})


class PlanningError(RuntimeError):
    """Base for refusals that are business rules, not bugs."""


class MilestoneError(PlanningError):
    pass


class MilestoneNotFoundError(MilestoneError):
    pass


class RiskError(PlanningError):
    pass


class RiskNotFoundError(RiskError):
    pass


class RiskDuplicateError(RiskError):
    """The risk code is already used in this organization.

    Codes are unique per organization, not globally, so this says nothing
    about any other tenant.
    """


class RiskInvalidError(RiskError):
    """The resulting risk would violate a database invariant.

    Distinct from "not found" so the route can answer 422 rather than 404.
    The canonical case is moving a risk to `mitigating` while neither the
    request nor the stored row states a mitigation.
    """


@dataclass(frozen=True, slots=True)
class MilestoneInput:
    name: str
    planned_date: dt.date
    description: str | None = None


@dataclass(frozen=True, slots=True)
class RiskInput:
    risk_code: str
    title: str
    probability: str
    impact: str
    category: str = "technical"
    description: str | None = None
    mitigation: str | None = None
    owner_user_id: uuid.UUID | None = None


# ---------------------------------------------------------------------------
# Milestones
# ---------------------------------------------------------------------------


def create_milestone(
    session: Session,
    *,
    project_id: uuid.UUID,
    organization_id: uuid.UUID,
    actor_id: uuid.UUID,
    spec: MilestoneInput,
) -> uuid.UUID:
    """Add a milestone to the project plan.

    Always created as ``planned`` with no ``actual_date``. A milestone
    that could be created already 'met' would let the plan be written
    after the fact, which is precisely the record the dashboard's overdue
    count is supposed to make impossible to hide.
    """
    milestone_id = session.execute(
        text(
            """
            INSERT INTO projects.milestones
                (organization_id, project_id, name, description, planned_date, status)
            VALUES (:org, :pid, :name, :description, :planned, 'planned')
            RETURNING id
            """
        ),
        {
            "org": organization_id,
            "pid": project_id,
            "name": spec.name,
            "description": spec.description,
            "planned": spec.planned_date,
        },
    ).scalar_one()

    write_audit(
        session,
        AuditEvent(
            action="milestone.created",
            entity_type="milestone",
            entity_id=str(milestone_id),
            organization_id=organization_id,
            user_id=actor_id,
            new_state={"name": spec.name, "planned_date": str(spec.planned_date)},
            reason="milestone added to the project plan",
        ),
    )
    return milestone_id


def set_milestone_status(
    session: Session,
    *,
    milestone_id: uuid.UUID,
    project_id: uuid.UUID,
    organization_id: uuid.UUID,
    actor_id: uuid.UUID,
    status: str,
    actual_date: dt.date | None = None,
    reason: str,
) -> dict:
    """Move a milestone's status, keeping ``actual_date`` consistent.

    The date is derived rather than trusted from the caller, because the
    two must agree: migration 012 requires a date for ``met``/``missed``
    and forbids one otherwise. Letting the client send both invites the
    combination the constraint would reject, surfacing as a 500 from an
    integrity error rather than as a comprehensible refusal.

    Closing a milestone with no supplied date records today. That is a
    statement of fact -- it is being closed now -- not a default standing
    in for a missing value.
    """
    if status in _MILESTONE_CLOSED:
        effective_date: dt.date | None = actual_date or dt.date.today()
    else:
        if actual_date is not None:
            raise MilestoneError(
                f"status '{status}' means the milestone is still in flight, "
                "so it cannot carry a completion date"
            )
        effective_date = None

    # Single statement. `prev` captures the before-state under FOR UPDATE
    # in the same statement that writes the after-state, so no other
    # transaction can move the milestone between the two.
    #
    # `project_id` is in the predicate, not merely in the URL. The route's
    # `require_project_member()` authorises the project in the PATH; if
    # this query matched on milestone id alone, a member of project X
    # could pass project X in the URL and a milestone id belonging to
    # project Y and have it accepted. RLS does not repair that: the child
    # policy admits rows from any `normal` project in the organization, so
    # every non-restricted project would be mutable by any colleague.
    # Found by Codex review (finding 3).
    row = (
        session.execute(
            text(
                """
                WITH prev AS (
                    SELECT id, status, actual_date, name
                    FROM projects.milestones
                    WHERE id = :mid
                      AND project_id = :pid
                      AND organization_id = :org
                    FOR UPDATE
                )
                UPDATE projects.milestones m
                SET status = :status,
                    actual_date = CAST(:actual AS DATE)
                FROM prev
                WHERE m.id = prev.id
                RETURNING prev.status AS old_status,
                          prev.actual_date AS old_actual_date,
                          m.status AS new_status,
                          m.actual_date AS new_actual_date,
                          m.name AS name
                """
            ),
            {
                "mid": milestone_id,
                "pid": project_id,
                "org": organization_id,
                "status": status,
                "actual": effective_date,
            },
        )
        .mappings()
        .one_or_none()
    )

    if row is None:
        # Same answer for "no such milestone" and "not yours". The
        # difference is itself information about another tenant.
        raise MilestoneNotFoundError("milestone not found")

    write_audit(
        session,
        AuditEvent(
            action="milestone.status_changed",
            entity_type="milestone",
            entity_id=str(milestone_id),
            organization_id=organization_id,
            user_id=actor_id,
            previous_state={
                "status": row["old_status"],
                "actual_date": str(row["old_actual_date"]) if row["old_actual_date"] else None,
            },
            new_state={
                "status": row["new_status"],
                "actual_date": str(row["new_actual_date"]) if row["new_actual_date"] else None,
            },
            reason=reason,
        ),
    )
    return dict(row)


def list_milestones(
    session: Session, *, project_id: uuid.UUID, organization_id: uuid.UUID
) -> list[dict]:
    """The plan, in the order it is meant to happen.

    Includes `is_overdue` computed the same way the dashboard counts it.
    Two places deriving 'overdue' from the same columns with different SQL
    is how a list and its own KPI tile come to disagree.
    """
    rows = session.execute(
        text(
            """
            SELECT id, name, description, planned_date, actual_date, status,
                   (status IN ('planned','in_progress')
                    AND planned_date < CURRENT_DATE) AS is_overdue
            FROM projects.milestones
            WHERE project_id = :pid AND organization_id = :org
            ORDER BY planned_date, name
            """
        ),
        {"pid": project_id, "org": organization_id},
    ).mappings()
    return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# Risks
# ---------------------------------------------------------------------------


def create_risk(
    session: Session,
    *,
    project_id: uuid.UUID,
    organization_id: uuid.UUID,
    actor_id: uuid.UUID,
    spec: RiskInput,
) -> uuid.UUID:
    """Raise a risk against the project.

    The owner check is not optional politeness. `owner_user_id` is a plain
    FK to `core.users`, users are not tenant-scoped, and referential
    integrity bypasses RLS -- so without this call a risk could be owned
    by a user in another organization, whose name would then render on
    this organization's dashboard.
    """
    if spec.owner_user_id is not None:
        require_active_member(
            session,
            user_id=spec.owner_user_id,
            organization_id=organization_id,
            role_description="risk owner",
        )

    duplicate = session.execute(
        text(
            """
            SELECT 1 FROM projects.risks
            WHERE organization_id = :org AND risk_code = :code
            """
        ),
        {"org": organization_id, "code": spec.risk_code},
    ).scalar_one_or_none()
    if duplicate:
        # Checked for the MESSAGE, not for the guarantee. risks_org_code_key
        # is the guarantee, and it still fires if two requests race past
        # this SELECT -- so the insert below translates it too. Leaving
        # only this check would turn an ordinary race into a 500, which is
        # exactly the read-then-write gap this codebase keeps closing
        # (Codex review, finding 7).
        raise RiskDuplicateError(f"risk code {spec.risk_code} already exists")

    try:
        risk_id = session.execute(
            text(
                """
                INSERT INTO projects.risks
                    (organization_id, project_id, risk_code, title, description,
                     category, probability, impact, mitigation, owner_user_id)
                VALUES (:org, :pid, :code, :title, :description, :category,
                        :probability, :impact, :mitigation, :owner)
                RETURNING id
                """
            ),
            {
                "org": organization_id,
                "pid": project_id,
                "code": spec.risk_code,
                "title": spec.title,
                "description": spec.description,
                "category": spec.category,
                "probability": spec.probability,
                "impact": spec.impact,
                "mitigation": spec.mitigation,
                "owner": spec.owner_user_id,
            },
        ).scalar_one()
    except IntegrityError as exc:
        constraint = getattr(getattr(exc.orig, "diag", None), "constraint_name", None)
        if constraint == "risks_org_code_key":
            raise RiskDuplicateError(f"risk code {spec.risk_code} already exists") from exc
        raise

    write_audit(
        session,
        AuditEvent(
            action="risk.raised",
            entity_type="risk",
            entity_id=str(risk_id),
            organization_id=organization_id,
            user_id=actor_id,
            new_state={
                "risk_code": spec.risk_code,
                "probability": spec.probability,
                "impact": spec.impact,
            },
            reason="risk raised",
        ),
    )
    return risk_id


def update_risk(
    session: Session,
    *,
    risk_id: uuid.UUID,
    project_id: uuid.UUID,
    organization_id: uuid.UUID,
    actor_id: uuid.UUID,
    reason: str,
    status: str | None = None,
    mitigation: str | None = None,
    probability: str | None = None,
    impact: str | None = None,
    owner_user_id: uuid.UUID | None = None,
) -> dict:
    """Re-assess or progress a risk.

    Every argument is optional and ``None`` means "leave unchanged", so a
    caller updating only the status cannot accidentally blank the
    mitigation.

    Note the explicit CASTs on every bind. psycopg cannot infer the type
    of a bare NULL inside `COALESCE(:x, column)`, and the failure is an
    "could not determine data type" error at execution -- the same
    untyped-NULL defect review caught in this codebase once already.
    """
    if owner_user_id is not None:
        require_active_member(
            session,
            user_id=owner_user_id,
            organization_id=organization_id,
            role_description="risk owner",
        )

    # The `mitigating` invariant is checked by the database, against the
    # values that RESULT from this update -- which depend on both the
    # request and the stored row. Reading the stored mitigation here to
    # pre-check it would be a read-then-write: another transaction could
    # clear it between the check and the UPDATE. So the constraint is
    # allowed to fire and its violation is translated.
    try:
        row = (
            session.execute(
                text(
                    """
                WITH prev AS (
                    SELECT id, status, mitigation, probability, impact, owner_user_id
                    FROM projects.risks
                    WHERE id = :rid
                      AND project_id = :pid
                      AND organization_id = :org
                    FOR UPDATE
                )
                UPDATE projects.risks r
                SET status        = COALESCE(CAST(:status AS TEXT),      r.status),
                    mitigation    = COALESCE(CAST(:mitigation AS TEXT),  r.mitigation),
                    probability   = COALESCE(CAST(:probability AS TEXT), r.probability),
                    impact        = COALESCE(CAST(:impact AS TEXT),      r.impact),
                    owner_user_id = COALESCE(CAST(:owner AS UUID),       r.owner_user_id),
                    updated_at    = now()
                FROM prev
                WHERE r.id = prev.id
                RETURNING prev.status AS old_status,
                          prev.probability AS old_probability,
                          prev.impact AS old_impact,
                          r.status AS new_status,
                          r.probability AS new_probability,
                          r.impact AS new_impact,
                          r.risk_code AS risk_code
                """
                ),
                {
                    "rid": risk_id,
                    "pid": project_id,
                    "org": organization_id,
                    "status": status,
                    "mitigation": mitigation,
                    "probability": probability,
                    "impact": impact,
                    "owner": owner_user_id,
                },
            )
            .mappings()
            .one_or_none()
        )
    except IntegrityError as exc:
        constraint = getattr(getattr(exc.orig, "diag", None), "constraint_name", None)
        if constraint == "risks_mitigating_states_the_mitigation":
            raise RiskInvalidError(
                "a risk moved to 'mitigating' must state its mitigation — "
                "supply one, or leave the status as it was"
            ) from exc
        # Any other integrity failure is not something this layer
        # understands. Swallowing it into a 422 would report a database
        # inconsistency as a client mistake.
        raise

    if row is None:
        raise RiskNotFoundError("risk not found")

    write_audit(
        session,
        AuditEvent(
            action="risk.updated",
            entity_type="risk",
            entity_id=str(risk_id),
            organization_id=organization_id,
            user_id=actor_id,
            previous_state={
                "status": row["old_status"],
                "probability": row["old_probability"],
                "impact": row["old_impact"],
            },
            new_state={
                "status": row["new_status"],
                "probability": row["new_probability"],
                "impact": row["new_impact"],
            },
            reason=reason,
        ),
    )
    return dict(row)


def list_risks(
    session: Session, *, project_id: uuid.UUID, organization_id: uuid.UUID
) -> list[dict]:
    """Open risks first, worst first.

    Ordered by the same probability x impact the dashboard's `high_high`
    counter singles out, so the top of this list is the tile's contents.
    """
    rows = session.execute(
        text(
            """
            SELECT id, risk_code, title, description, category, probability,
                   impact, status, mitigation, owner_user_id, updated_at
            FROM projects.risks
            WHERE project_id = :pid AND organization_id = :org
            ORDER BY
                CASE WHEN status IN ('open','mitigating') THEN 0 ELSE 1 END,
                CASE probability WHEN 'high' THEN 0 WHEN 'medium' THEN 1 ELSE 2 END,
                CASE impact      WHEN 'high' THEN 0 WHEN 'medium' THEN 1 ELSE 2 END,
                risk_code
            """
        ),
        {"pid": project_id, "org": organization_id},
    ).mappings()
    return [dict(r) for r in rows]
