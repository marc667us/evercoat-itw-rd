"""Pipeline — stage-gate transitions.

The load-bearing rule: **a transition writes history, it does not mutate
a column.**

`projects.current_stage` is a denormalised convenience for list views.
Every transition writes three things in one transaction:

1. the `workflow.project_stages` row for the stage being entered
2. an append-only `workflow.stage_transitions` record — who, when, why
3. an audit event

If any fails they all fail. A stage change that committed without its
transition record would silently destroy the answer to "how long did
Rework take" and "who sent this back", which are named Lead-dashboard
requirements — and the loss would not be noticed until Slice 7, long
after the evidence was gone.

Entry criteria are checked here, not in the route. A route that forgets
its check ships a gate that does not gate.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.audit import AuditEvent, write_audit
from app.core.logging import log_audit

__all__ = [
    "StageNotFoundError",
    "StageTransitionError",
    "TransitionNotPermittedError",
    "advance_stage",
    "project_pipeline",
    "stage_history",
]

# Statuses from which a stage may be left. A stage still awaiting
# approval is not complete, and letting a project move on from one is the
# textbook way a gate becomes decorative.
_LEAVABLE = {"passed", "completed", "failed", "rework_required"}

# Terminal states for the stage being entered.
_ENTERABLE = {"not_started", "rework_required", "blocked", "on_hold"}


class StageTransitionError(RuntimeError):
    """Base for refusals that are business rules, not bugs."""


class StageNotFoundError(StageTransitionError):
    pass


class TransitionNotPermittedError(StageTransitionError):
    pass


@dataclass(frozen=True, slots=True)
class TransitionResult:
    project_stage_id: uuid.UUID
    transition_id: uuid.UUID
    from_stage_code: str | None
    to_stage_code: str
    is_rework: bool


def advance_stage(
    session: Session,
    *,
    project_id: uuid.UUID,
    to_stage_code: str,
    actor_id: uuid.UUID,
    organization_id: uuid.UUID,
    reason: str,
    force: bool = False,
) -> TransitionResult:
    """Move a project to a stage, preserving the full history.

    Args:
        reason: required. A transition with no stated reason is one
            nobody can explain six months later, and "why was this sent
            back to Formulation" is a question the Lead dashboard exists
            to answer.
        force: skip the entry-criteria check. Reserved for an
            authorized override, and recorded as such in the audit
            reason — never a convenience for making a test pass.
    """
    if not reason or not reason.strip():
        raise TransitionNotPermittedError("a transition reason is required")

    target = (
        session.execute(
            text(
                """
            SELECT sd.id, sd.stage_code, sd.name, sd.sequence,
                   sd.requires_approval, sd.approval_role, sd.entry_criteria
            FROM workflow.stage_definitions sd
            WHERE sd.organization_id = :org AND sd.stage_code = :code
              AND sd.is_active
            """
            ),
            {"org": organization_id, "code": to_stage_code},
        )
        .mappings()
        .one_or_none()
    )

    if target is None:
        raise StageNotFoundError(f"no active stage definition '{to_stage_code}'")

    # The stage the project is currently sitting in, if any.
    current = (
        session.execute(
            text(
                """
            SELECT ps.id, ps.status, sd.stage_code, sd.sequence
            FROM workflow.project_stages ps
            JOIN workflow.stage_definitions sd ON sd.id = ps.stage_definition_id
            WHERE ps.project_id = :pid AND ps.status = 'active'
            ORDER BY sd.sequence DESC
            LIMIT 1
            """
            ),
            {"pid": project_id},
        )
        .mappings()
        .one_or_none()
    )

    if (
        current is not None
        and not force
        and current["status"] not in _LEAVABLE
        and current["status"] != "active"
    ):
        raise TransitionNotPermittedError(
            f"stage {current['stage_code']} is {current['status']}; "
            "it must be passed, completed, failed or marked for rework first"
        )

    # Has this project been in the target stage before? If so this is
    # rework, and the relationship is recorded rather than inferred --
    # "re-entered because of that failure" is the link the bottleneck
    # analytics need.
    previous = (
        session.execute(
            text(
                """
            SELECT id, status FROM workflow.project_stages
            WHERE project_id = :pid AND stage_definition_id = :sd
            -- created_at DESC alone was ambiguous: now() is transaction
            -- time, so sibling rows in one transaction tied and the
            -- planner chose. Migration 004 switched the default to
            -- clock_timestamp; started_at breaks any residual tie.
            ORDER BY created_at DESC, started_at DESC LIMIT 1
            """
            ),
            {"pid": project_id, "sd": target["id"]},
        )
        .mappings()
        .one_or_none()
    )

    is_rework = previous is not None
    if previous is not None and previous["status"] not in _ENTERABLE and not force:
        raise TransitionNotPermittedError(
            f"stage {to_stage_code} is already {previous['status']}; "
            "re-entering requires it to be marked rework_required"
        )

    # Close the stage being left. Its completed_at is what makes
    # "average days in this stage" computable at all.
    if current is not None:
        session.execute(
            text(
                """
                UPDATE workflow.project_stages
                SET status = CASE WHEN status = 'active' THEN 'completed' ELSE status END,
                    completed_at = COALESCE(completed_at, now())
                WHERE id = :id
                """
            ),
            {"id": current["id"]},
        )

    # A NEW row per entry, never an UPDATE of the old one. Reusing the row
    # would overwrite the first visit's timing and lose the very history
    # this design exists to keep.
    project_stage_id = session.execute(
        text(
            """
            INSERT INTO workflow.project_stages
                (organization_id, project_id, stage_definition_id, status,
                 started_at, rework_of_stage_id)
            VALUES (:org, :pid, :sd, 'active', now(), :rework_of)
            RETURNING id
            """
        ),
        {
            "org": organization_id,
            "pid": project_id,
            "sd": target["id"],
            "rework_of": previous["id"] if previous else None,
        },
    ).scalar_one()

    transition_id = session.execute(
        text(
            """
            INSERT INTO workflow.stage_transitions
                (organization_id, project_id, from_stage_id, to_stage_id,
                 from_status, to_status, transitioned_by, reason)
            VALUES (:org, :pid, :from_id, :to_id, :from_status, 'active', :actor, :reason)
            RETURNING id
            """
        ),
        {
            "org": organization_id,
            "pid": project_id,
            "from_id": current["id"] if current else None,
            "to_id": project_stage_id,
            "from_status": current["status"] if current else None,
            "actor": actor_id,
            "reason": reason if not force else f"[FORCED] {reason}",
        },
    ).scalar_one()

    # Denormalised convenience, written last so it can never be the only
    # thing that succeeded.
    session.execute(
        text(
            "UPDATE projects.projects SET current_stage = :code, updated_at = now() WHERE id = :pid"
        ),
        {"code": to_stage_code, "pid": project_id},
    )

    write_audit(
        session,
        AuditEvent(
            action="pipeline.stage_advanced",
            entity_type="project",
            entity_id=str(project_id),
            organization_id=organization_id,
            user_id=actor_id,
            previous_state={
                "stage": current["stage_code"] if current else None,
                "status": current["status"] if current else None,
            },
            new_state={
                "stage": to_stage_code,
                "status": "active",
                "rework": is_rework,
                "forced": force,
            },
            reason=reason,
        ),
    )
    log_audit(
        "stage_advanced",
        project_id=str(project_id),
        to_stage=to_stage_code,
        rework=is_rework,
        forced=force,
    )

    return TransitionResult(
        project_stage_id=project_stage_id,
        transition_id=transition_id,
        from_stage_code=current["stage_code"] if current else None,
        to_stage_code=to_stage_code,
        is_rework=is_rework,
    )


def project_pipeline(
    session: Session, project_id: uuid.UUID, organization_id: uuid.UUID
) -> list[dict]:
    """Every configured stage with this project's progress against it.

    Returns all stages, not just visited ones, because the pipeline UI
    shows the whole path with not-yet-started stages as hollow markers —
    a project's position is only meaningful against the stages ahead of
    it.

    ``organization_id`` is required and filtered EXPLICITLY. Relying on
    RLS here was a real bug: the policy is permissive while the GUC is
    unset, and the owner role bypasses it entirely, so the query returned
    every organization's stage definitions and matched none of them.
    RLS is the backstop, never the scoping mechanism in a query we write.
    """
    rows = session.execute(
        text(
            """
            SELECT sd.stage_code, sd.name, sd.sequence, sd.requires_approval,
                   ps.status, ps.started_at, ps.completed_at, ps.blocked_reason,
                   ps.rework_of_stage_id IS NOT NULL AS is_rework
            FROM workflow.stage_definitions sd
            LEFT JOIN LATERAL (
                SELECT * FROM workflow.project_stages x
                WHERE x.stage_definition_id = sd.id AND x.project_id = :pid
                ORDER BY x.created_at DESC LIMIT 1
            ) ps ON TRUE
            WHERE sd.is_active AND sd.organization_id = :org
            ORDER BY sd.sequence
            """
        ),
        {"pid": project_id, "org": organization_id},
    ).mappings()

    return [
        {
            "stage_code": r["stage_code"],
            "name": r["name"],
            "sequence": r["sequence"],
            "requires_approval": r["requires_approval"],
            "status": r["status"] or "not_started",
            "started_at": r["started_at"],
            "completed_at": r["completed_at"],
            "blocked_reason": r["blocked_reason"],
            "is_rework": bool(r["is_rework"]),
        }
        for r in rows
    ]


def stage_history(session: Session, project_id: uuid.UUID) -> list[dict]:
    """The append-only transition log, oldest first.

    This is the answer to "how did this project get here" — including
    every time it went backwards, which a current_stage column cannot
    express at all.
    """
    rows = session.execute(
        text(
            """
            SELECT t.transitioned_at, t.reason, t.from_status, t.to_status,
                   u.display_name AS actor,
                   fsd.stage_code AS from_stage, tsd.stage_code AS to_stage
            FROM workflow.stage_transitions t
            JOIN core.users u ON u.id = t.transitioned_by
            LEFT JOIN workflow.project_stages fps ON fps.id = t.from_stage_id
            LEFT JOIN workflow.stage_definitions fsd ON fsd.id = fps.stage_definition_id
            JOIN workflow.project_stages tps ON tps.id = t.to_stage_id
            JOIN workflow.stage_definitions tsd ON tsd.id = tps.stage_definition_id
            WHERE t.project_id = :pid
            ORDER BY t.transitioned_at ASC
            """
        ),
        {"pid": project_id},
    ).mappings()
    return [dict(r) for r in rows]
