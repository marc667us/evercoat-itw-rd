"""The one shared approval engine.

`CLAUDE.md` §9: "One shared approval engine. Never re-implement approval
inside Formula, Test, Validation, Pilot, Qualification or Release." This
module is that engine, and it is polymorphic over `(entity_type,
entity_id)` so the later modules add zero approval infrastructure.

**A route is a SNAPSHOT.** `open_route` copies the template's steps onto
the route. Editing the template afterwards changes nothing about
approvals in flight — without which an administrator adding a QA step
would retroactively make every completed qualification incomplete.

**Groups, not booleans.** Steps sharing a `parallel_group` may be decided
in any order; the next group opens only when every MANDATORY step in the
current one has been decided. A group of one is a sequential step. One
mechanism expresses both, and it can say which steps are parallel *with
each other* — which a boolean cannot.

**Incompatible duties come off the step, not out of code.**
`must_differ_from_group` was snapshotted with the route, so the rule that
applied when the route opened is the rule that governs it. ADR-019's
constraint depends on per-record identity, so it is checked against who
has already decided rather than against role names.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any

from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.audit import AuditEvent, write_audit
from app.core.db import guarded_write

__all__ = [
    "ApprovalError",
    "ApprovalNotFoundError",
    "ApprovalStateError",
    "DecisionInput",
    "IncompatibleDutyError",
    "decide_step",
    "get_route",
    "next_step_for",
    "open_route",
    "pending_steps_for",
    "route_for_entity",
    "route_outcome",
]

# Decisions that advance a step. Everything else stops the route.
_APPROVING = frozenset({"approve", "approve_with_condition"})
_REFUSING = frozenset({"reject"})


class ApprovalError(RuntimeError):
    """Base for refusals that are business rules, not bugs."""


class ApprovalNotFoundError(ApprovalError):
    pass


class ApprovalStateError(ApprovalError):
    """The step is not open, or its group has not been reached."""


class IncompatibleDutyError(ApprovalError):
    """The caller may not decide THIS step, though they hold the permission.

    A distinct type because the answer is not "you may never" but "not
    here": §9's segregation of duties and ADR-019 both depend on who has
    already decided on this particular record. The route answers 403 and
    says which involvement disqualified them.
    """


@dataclass(frozen=True, slots=True)
class DecisionInput:
    decision: str
    condition_text: str | None = None
    rationale: str | None = None


def open_route(
    session: Session,
    *,
    organization_id: uuid.UUID,
    project_id: uuid.UUID,
    entity_type: str,
    entity_id: uuid.UUID,
    authority_level: str,
    actor_id: uuid.UUID,
) -> dict[str, Any]:
    """Open an approval route by SNAPSHOTTING the template for an authority.

    The template is found by `authority_level`, and at most one active
    template may claim each level — an exclusion constraint enforces
    that, because two would make "which route applies?" ambiguous and the
    engine would pick one silently.

    Returns the route and its steps. Raises if a route is already open
    for this entity: one open route, or a result could be approved twice
    by different routes and nothing could say which governed.
    """
    template = (
        session.execute(
            text(
                """
                SELECT id, template_code, name
                FROM workflow.approval_templates
                WHERE organization_id = :org
                  AND authority_level = :authority
                  AND is_active
                """
            ),
            {"org": organization_id, "authority": authority_level},
        )
        .mappings()
        .one_or_none()
    )
    if template is None:
        raise ApprovalNotFoundError(
            f"no active approval template is configured for {authority_level} "
            "authority; an approval cannot be routed without one"
        )

    try:
        with guarded_write(session):
            route_id: uuid.UUID = session.execute(
                text(
                    """
                    INSERT INTO workflow.approval_routes
                        (organization_id, project_id, entity_type, entity_id,
                         template_id, template_code)
                    VALUES (:org, :pid, :etype, :eid, :tid, :tcode)
                    RETURNING id
                    """
                ),
                {
                    "org": organization_id,
                    "pid": project_id,
                    "etype": entity_type,
                    "eid": entity_id,
                    "tid": template["id"],
                    "tcode": template["template_code"],
                },
            ).scalar_one()
    except IntegrityError as exc:
        if "one_open_per_entity" in str(exc.orig):
            raise ApprovalStateError(
                "an approval route is already open for this record; close it before opening another"
            ) from exc
        raise ApprovalError(str(exc.orig)) from exc

    # 🔴 THE SNAPSHOT. INSERT ... SELECT, so the copy is atomic with
    # respect to anything editing the template, and so no step can be
    # missed by a loop that reads and writes separately.
    copied = session.execute(
        text(
            """
            WITH copied AS (
                INSERT INTO workflow.approval_route_steps
                    (organization_id, route_id, step_number, parallel_group,
                     permission_required, step_label, is_mandatory,
                     must_differ_from_group)
                SELECT s.organization_id, :route, s.step_number, s.parallel_group,
                       s.permission_required, s.step_label, s.is_mandatory,
                       s.must_differ_from_group
                FROM workflow.approval_template_steps s
                WHERE s.template_id = :tid AND s.organization_id = :org
                RETURNING id
            )
            SELECT count(*) FROM copied
            """
        ),
        {"route": route_id, "tid": template["id"], "org": organization_id},
    ).scalar_one()

    if copied == 0:
        raise ApprovalStateError(
            f"template {template['template_code']} has no steps; a route copied from "
            "it would be approved the moment it opened"
        )

    write_audit(
        session,
        AuditEvent(
            action="approval.route_opened",
            entity_type=entity_type,
            entity_id=str(entity_id),
            organization_id=organization_id,
            user_id=actor_id,
            new_state={"template": template["template_code"], "steps": copied},
            reason=f"approval route opened at {authority_level} authority",
        ),
    )
    return {"route_id": route_id, "template_code": template["template_code"], "steps": copied}


def decide_step(
    session: Session,
    *,
    route_id: uuid.UUID,
    step_id: uuid.UUID,
    organization_id: uuid.UUID,
    actor_id: uuid.UUID,
    held_permissions: frozenset[str],
    spec: DecisionInput,
) -> dict[str, Any]:
    """Decide one step, and advance or stop the route.

    Four things are checked before anything is written, and each one is a
    rule the route itself carries rather than something this code knows:

    1. the step is undecided — a decision is a signature and is not
       revisited;
    2. its group has been reached — every mandatory step in every earlier
       group has been decided;
    3. the caller holds the permission the STEP requires, not one this
       module chose;
    4. the caller is not disqualified by `must_differ_from_group`.
    """
    step = (
        session.execute(
            text(
                """
                SELECT s.id, s.route_id, s.step_number, s.parallel_group,
                       s.permission_required, s.step_label, s.is_mandatory,
                       s.must_differ_from_group, s.decision,
                       r.status AS route_status, r.entity_type, r.entity_id,
                       r.project_id
                FROM workflow.approval_route_steps s
                JOIN workflow.approval_routes r
                  ON r.id = s.route_id AND r.organization_id = s.organization_id
                WHERE s.id = :sid AND s.route_id = :rid AND s.organization_id = :org
                """
            ),
            {"sid": step_id, "rid": route_id, "org": organization_id},
        )
        .mappings()
        .one_or_none()
    )
    if step is None:
        raise ApprovalNotFoundError("no such step on this route")

    if step["route_status"] != "open":
        raise ApprovalStateError(
            f"this route is {step['route_status']} and takes no further decisions"
        )
    if step["decision"] is not None:
        raise ApprovalStateError(
            f"step {step['step_number']} has already been decided; a decision is a "
            "signature and is not revisited"
        )

    # 2 — has this group been reached?
    blocking = session.execute(
        text(
            """
            SELECT count(*) FROM workflow.approval_route_steps
            WHERE route_id = :rid AND organization_id = :org
              AND parallel_group < :group
              AND is_mandatory
              AND decision IS NULL
            """
        ),
        {"rid": route_id, "org": organization_id, "group": step["parallel_group"]},
    ).scalar_one()
    if blocking:
        raise ApprovalStateError(
            f"{blocking} earlier mandatory step(s) have not been decided; this step's "
            "turn has not come"
        )

    # 3 — the permission the STEP names, not one chosen here.
    if step["permission_required"] not in held_permissions:
        raise IncompatibleDutyError(f"this step requires {step['permission_required']}")

    # 4 — incompatible duties, from the snapshot.
    if step["must_differ_from_group"] is not None:
        conflicted = session.execute(
            text(
                """
                SELECT count(*) FROM workflow.approval_route_steps
                WHERE route_id = :rid AND organization_id = :org
                  AND parallel_group = :group
                  AND decided_by = :actor
                """
            ),
            {
                "rid": route_id,
                "org": organization_id,
                "group": step["must_differ_from_group"],
                "actor": actor_id,
            },
        ).scalar_one()
        if conflicted:
            raise IncompatibleDutyError(
                "you decided an earlier step this approval must be independent of; "
                "an independent approval from the same person is one signature twice "
                "(ADR-019)"
            )

    if spec.decision == "approve_with_condition" and not spec.condition_text:
        raise ApprovalError(
            "a conditional approval must state its limitation; §9 requires the "
            "condition preserved and displayed with the result"
        )
    if spec.decision in {"reject", "return_for_correction", "request_retest", "escalate"} and (
        not spec.rationale
    ):
        raise ApprovalError(f"a decision of '{spec.decision}' must say why")

    session.execute(
        text(
            """
            UPDATE workflow.approval_route_steps
            SET decision = :decision,
                condition_text = :condition,
                rationale = :rationale,
                decided_by = :actor,
                decided_at = now()
            WHERE id = :sid AND organization_id = :org AND decision IS NULL
            """
        ),
        {
            "decision": spec.decision,
            "condition": spec.condition_text,
            "rationale": spec.rationale,
            "actor": actor_id,
            "sid": step_id,
            "org": organization_id,
        },
    )

    route_status = _settle_route(session, route_id=route_id, organization_id=organization_id)

    write_audit(
        session,
        AuditEvent(
            action=f"approval.{spec.decision}",
            entity_type=step["entity_type"],
            entity_id=str(step["entity_id"]),
            organization_id=organization_id,
            user_id=actor_id,
            new_state={
                "step": step["step_number"],
                "label": step["step_label"],
                "route_status": route_status,
            },
            reason=spec.rationale or spec.condition_text or step["step_label"],
        ),
    )
    return {
        "route_id": route_id,
        "step_number": step["step_number"],
        "decision": spec.decision,
        "route_status": route_status,
    }


def _settle_route(session: Session, *, route_id: uuid.UUID, organization_id: uuid.UUID) -> str:
    """Close the route when its outcome is determined; otherwise leave it open.

    A single REJECT closes it. Otherwise it completes only when every
    MANDATORY step has an approving decision — optional steps (the
    escalation rung in OVERSIGHT_STANDARD) never hold a route open,
    which is what makes them optional rather than merely labelled so.
    """
    counts = (
        session.execute(
            text(
                """
                SELECT
                    count(*) FILTER (WHERE decision = 'reject') AS rejected,
                    count(*) FILTER (WHERE is_mandatory AND decision IS NULL) AS outstanding,
                    count(*) FILTER (
                        WHERE is_mandatory
                          AND decision IS NOT NULL
                          AND decision NOT IN ('approve','approve_with_condition')
                    ) AS stopped
                FROM workflow.approval_route_steps
                WHERE route_id = :rid AND organization_id = :org
                """
            ),
            {"rid": route_id, "org": organization_id},
        )
        .mappings()
        .one()
    )

    if counts["rejected"]:
        status = "rejected"
    elif counts["outstanding"] == 0 and counts["stopped"] == 0:
        status = "approved"
    else:
        # Still open. A `return_for_correction` or `request_retest` on a
        # mandatory step leaves the route open deliberately: the work
        # comes back, and the route is where it comes back TO.
        return "open"

    session.execute(
        text(
            """
            UPDATE workflow.approval_routes
            SET status = :status, closed_at = now()
            WHERE id = :rid AND organization_id = :org AND status = 'open'
            """
        ),
        {"status": status, "rid": route_id, "org": organization_id},
    )
    return status


def get_route(
    session: Session, *, route_id: uuid.UUID, organization_id: uuid.UUID
) -> dict[str, Any]:
    """One route, its steps, and which step is next.

    `next_steps` is DERIVED, not stored. A stored "current step" column
    would be a second statement of something the steps already say, and
    it would go stale the moment a parallel step was decided out of
    order.
    """
    route = (
        session.execute(
            text(
                """
                SELECT id, entity_type, entity_id, template_code, status,
                       project_id, opened_at, closed_at
                FROM workflow.approval_routes
                WHERE id = :rid AND organization_id = :org
                """
            ),
            {"rid": route_id, "org": organization_id},
        )
        .mappings()
        .one_or_none()
    )
    if route is None:
        raise ApprovalNotFoundError("no such approval route in this organization")

    steps = [
        dict(r)
        for r in session.execute(
            text(
                """
                SELECT id, step_number, parallel_group, permission_required, step_label,
                       is_mandatory, must_differ_from_group, decision, condition_text,
                       rationale, decided_by, decided_at
                FROM workflow.approval_route_steps
                WHERE route_id = :rid AND organization_id = :org
                ORDER BY parallel_group, step_number
                """
            ),
            {"rid": route_id, "org": organization_id},
        ).mappings()
    ]

    result = dict(route)
    result["steps"] = steps

    open_groups = sorted(
        {s["parallel_group"] for s in steps if s["is_mandatory"] and s["decision"] is None}
    )
    current = open_groups[0] if open_groups else None
    result["current_group"] = current
    result["next_steps"] = [
        s for s in steps if s["decision"] is None and s["parallel_group"] == current
    ]
    # What rule 12 of the traffic light needs: WHO is being waited on.
    result["awaiting"] = sorted({s["step_label"] for s in result["next_steps"]})
    return result


def route_for_entity(
    session: Session,
    *,
    organization_id: uuid.UUID,
    entity_type: str,
    entity_id: uuid.UUID,
) -> dict[str, Any] | None:
    """The open route for a record, or None.

    Returns None rather than raising: "this record has no approval route"
    is an ordinary state, not a fault — a test still in execution has
    nothing to approve.
    """
    row = (
        session.execute(
            text(
                """
                SELECT id FROM workflow.approval_routes
                WHERE organization_id = :org AND entity_type = :etype
                  AND entity_id = :eid AND status = 'open'
                """
            ),
            {"org": organization_id, "etype": entity_type, "eid": entity_id},
        )
        .mappings()
        .one_or_none()
    )
    if row is None:
        return None
    return get_route(session, route_id=row["id"], organization_id=organization_id)


def next_step_for(
    session: Session,
    *,
    route_id: uuid.UUID,
    organization_id: uuid.UUID,
    held_permissions: frozenset[str],
) -> dict[str, Any] | None:
    """The step on THIS route that this caller may decide next, or None.

    `pending_steps_for` answers "what is in my queue?" across the whole
    organization. This answers "I am deciding on this record — which step is
    that?", which is what a domain module needs when its own endpoint takes a
    decision on a record rather than on a step id.

    🔴 WHY A DOMAIN MODULE MUST NOT PICK THE STEP ITSELF. The ordering rules —
    earlier mandatory groups first, the permission the STEP names rather than
    one the caller chose, incompatible duties from the snapshot — are the
    route's, and §9 says they are implemented once. A module that resolved
    "the next step" with its own query would be re-implementing the engine's
    sequencing, which is the defect this function exists to avoid.

    Returns the LOWEST-numbered undecided step in the earliest reachable group
    whose required permission the caller holds. Returns None when the caller
    has nothing to decide here — which is not an error, because "it is not
    your turn" and "this is not your approval" are ordinary states.

    Selecting a step does NOT authorize deciding it: `decide_step` re-checks
    every rule, including ADR-019's independence, which cannot be evaluated
    without knowing who is deciding.
    """
    if not held_permissions:
        return None

    row = (
        session.execute(
            text(
                """
                SELECT s.id AS step_id, s.step_number, s.parallel_group,
                       s.step_label, s.permission_required, s.is_mandatory
                FROM workflow.approval_route_steps s
                JOIN workflow.approval_routes r
                  ON r.id = s.route_id AND r.organization_id = s.organization_id
                WHERE s.route_id = :rid
                  AND s.organization_id = :org
                  AND r.status = 'open'
                  AND s.decision IS NULL
                  AND s.permission_required = ANY(CAST(:permissions AS TEXT[]))
                  AND NOT EXISTS (
                        SELECT 1 FROM workflow.approval_route_steps earlier
                        WHERE earlier.route_id = s.route_id
                          AND earlier.parallel_group < s.parallel_group
                          AND earlier.is_mandatory
                          AND earlier.decision IS NULL
                  )
                ORDER BY s.parallel_group, s.step_number
                LIMIT 1
                """
            ),
            {
                "rid": route_id,
                "org": organization_id,
                "permissions": sorted(held_permissions),
            },
        )
        .mappings()
        .one_or_none()
    )
    return dict(row) if row is not None else None


def route_outcome(
    session: Session, *, route_id: uuid.UUID, organization_id: uuid.UUID
) -> dict[str, Any]:
    """The route's status, and whether any approval carried a condition.

    §9: "Conditional approval yields YELLOW, and the stated limitation is
    preserved." A route that is `approved` with a conditional step among its
    decisions is NOT a clean approval, and a caller mapping route status onto
    its own axis needs to know the difference — otherwise the condition is
    silently discarded at exactly the point it starts to matter.
    """
    row = (
        session.execute(
            text(
                """
                SELECT r.status,
                       count(*) FILTER (
                           WHERE s.decision = 'approve_with_condition'
                       ) AS conditional_steps,
                       max(s.condition_text) FILTER (
                           WHERE s.decision = 'approve_with_condition'
                       ) AS condition_text
                FROM workflow.approval_routes r
                LEFT JOIN workflow.approval_route_steps s
                  ON s.route_id = r.id AND s.organization_id = r.organization_id
                WHERE r.id = :rid AND r.organization_id = :org
                GROUP BY r.status
                """
            ),
            {"rid": route_id, "org": organization_id},
        )
        .mappings()
        .one_or_none()
    )
    if row is None:
        raise ApprovalNotFoundError("no such approval route in this organization")
    return dict(row)


def pending_steps_for(
    session: Session,
    *,
    organization_id: uuid.UUID,
    held_permissions: frozenset[str],
    limit: int = 100,
) -> list[dict[str, Any]]:
    """The approval queue: steps this caller could decide right now.

    "Right now" is the load-bearing part. A queue that listed every
    undecided step would show work whose turn has not come, and §11
    requires a count to represent items needing action BY THE HOLDER —
    not total rows. So steps in groups still blocked by earlier ones are
    excluded here rather than left for a screen to filter.
    """
    if not held_permissions:
        return []

    rows = session.execute(
        text(
            """
            SELECT s.id AS step_id, s.step_number, s.step_label, s.permission_required,
                   r.id AS route_id, r.entity_type, r.entity_id, r.template_code,
                   r.project_id, r.opened_at
            FROM workflow.approval_route_steps s
            JOIN workflow.approval_routes r
              ON r.id = s.route_id AND r.organization_id = s.organization_id
            WHERE s.organization_id = :org
              AND r.status = 'open'
              AND s.decision IS NULL
              AND s.permission_required = ANY(CAST(:permissions AS TEXT[]))
              AND NOT EXISTS (
                    SELECT 1 FROM workflow.approval_route_steps earlier
                    WHERE earlier.route_id = s.route_id
                      AND earlier.parallel_group < s.parallel_group
                      AND earlier.is_mandatory
                      AND earlier.decision IS NULL
              )
            ORDER BY r.opened_at
            LIMIT :limit
            """
        ),
        {
            "org": organization_id,
            "permissions": sorted(held_permissions),
            "limit": limit,
        },
    ).mappings()
    return [dict(r) for r in rows]
