"""Failure investigation and approval routes — Slice 6.

Both routers live here because they are two halves of one slice and share
their error translation. They are mounted at separate prefixes.

**Permissions, checked against migration 002 before writing:**

    failure.view              Chemist, Engineer, Lead, Director, QA
    failure.create            Chemist, Engineer
    failure.investigate       Chemist, Engineer     hypotheses and evidence
    failure.accept_root_cause **Lead alone**
    failure.close             **Lead alone**

🔴 `failure.accept_root_cause` IS THE WHOLE POINT OF THE SPLIT.

`CLAUDE.md` §7: an AI hypothesis is not an accepted root cause, and only a
human moves it. The Chemist and Engineer who investigate hold
`failure.investigate` and NOT `failure.accept_root_cause` — so the people
generating hypotheses are structurally unable to conclude one, and MSD
(Slice 7) inherits that boundary by having no permissions at all.

The administrator holds neither, deliberately: migration 002 says
"administering the system is not the same authority as making a technical
decision".
"""

from __future__ import annotations

import datetime as dt
import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.security import PermissionDenied, Principal, get_db, require_permission
from app.core.tenancy import CrossTenantReferenceError
from app.domains.approvals.service import (
    ApprovalError,
    ApprovalNotFoundError,
    ApprovalStateError,
    IncompatibleDutyError,
    decide_step,
    get_route,
    open_route,
    pending_steps_for,
    route_for_entity,
)
from app.domains.approvals.service import DecisionInput as ApprovalDecisionInput
from app.domains.failures.service import (
    ActionInput,
    DriverInput,
    EvidenceInput,
    FailureError,
    FailureInput,
    FailureNotFoundError,
    FailureStateError,
    HypothesisInput,
    accept_root_cause,
    close_failure,
    get_failure,
    link_evidence,
    list_failures,
    open_failure,
    raise_action,
    record_driver,
    record_evidence,
    record_hypothesis,
    reject_hypothesis,
)

router = APIRouter()
approvals_router = APIRouter()

__all__ = ["approvals_router", "router"]


class FailureCreate(BaseModel):
    project_id: uuid.UUID
    failure_code: str = Field(min_length=3, max_length=50)
    title: str = Field(min_length=3, max_length=200)
    description: str | None = None
    severity: str = Field(default="major", pattern="^(critical|major|minor)$")
    test_id: uuid.UUID | None = None
    formula_version_id: uuid.UUID | None = None
    batch_id: uuid.UUID | None = None


class HypothesisCreate(BaseModel):
    possible_cause: str = Field(min_length=3, max_length=2000)
    mechanism: str | None = Field(default=None, max_length=2000)
    confidence: str = Field(default="medium", pattern="^(low|medium|high)$")
    source: str | None = Field(default=None, max_length=500)
    # An MSD-proposed hypothesis must SAY it is one. §7 rests on the
    # distinction, and a default of `human` means the label can only be
    # wrong by a caller asserting it.
    origin: str = Field(default="human", pattern="^(human|msd)$")


class EvidenceCreate(BaseModel):
    evidence_type: str = Field(
        pattern="^(previous_experiment|literature|batch_deviation|material_lot_issue|"
        "test_trend|photograph|other)$"
    )
    summary: str = Field(min_length=3, max_length=2000)
    detail: str | None = None
    referenced_entity_type: str | None = Field(
        default=None, pattern="^(test|batch|material_lot|formula_version|document)$"
    )
    referenced_entity_id: uuid.UUID | None = None
    source_reference: str | None = Field(default=None, max_length=500)
    origin: str = Field(default="human", pattern="^(human|msd)$")


class EvidenceLink(BaseModel):
    evidence_id: uuid.UUID
    relationship: str = Field(default="supports", pattern="^(supports|contradicts|inconclusive)$")
    note: str | None = Field(default=None, max_length=1000)


class RootCauseAcceptance(BaseModel):
    hypothesis_id: uuid.UUID
    # Required. Accepting a root cause is a technical decision and an
    # unexplained one cannot be reviewed later.
    rationale: str = Field(min_length=3, max_length=2000)


class HypothesisRejection(BaseModel):
    reason: str = Field(min_length=3, max_length=2000)


class ActionCreate(BaseModel):
    action_type: str = Field(
        pattern="^(formula_revision|repeat_test|process_change|material_change|start_doe|other)$"
    )
    description: str = Field(min_length=3, max_length=2000)
    assigned_to: uuid.UUID | None = None
    due_date: dt.date | None = None


class ClosureCreate(BaseModel):
    summary: str = Field(min_length=3, max_length=2000)


class DriverCreate(BaseModel):
    driver_type: str = Field(
        pattern="^(failure|requirement|optimization|cost|regulatory|customer_request|other)$"
    )
    reason: str = Field(min_length=3, max_length=2000)
    failure_id: uuid.UUID | None = None
    requirement_id: uuid.UUID | None = None


class RouteOpen(BaseModel):
    project_id: uuid.UUID
    entity_type: str = Field(
        pattern="^(test|formula_version|validation|pilot|qualification|product_release)$"
    )
    entity_id: uuid.UUID
    authority_level: str = Field(
        pattern="^(preliminary|development|controlled|validation|qualification|release)$"
    )


class StepDecision(BaseModel):
    decision: str = Field(
        pattern="^(approve|approve_with_condition|return_for_correction|"
        "request_retest|reject|escalate|request_additional_test)$"
    )
    condition_text: str | None = Field(default=None, max_length=2000)
    rationale: str | None = Field(default=None, max_length=2000)


def _missing(exc: Exception) -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


def _conflict(exc: Exception) -> HTTPException:
    return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))


def _invalid(exc: Exception) -> HTTPException:
    return HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))


# ---------------------------------------------------------------------------
# Failures
# ---------------------------------------------------------------------------


@router.get("", tags=["failures"])
def get_failures(
    project_id: uuid.UUID | None = Query(default=None),
    status_filter: str | None = Query(default=None, alias="status"),
    principal: Principal = Depends(require_permission("failure.view")),
    session: Session = Depends(get_db),
) -> list[dict[str, Any]]:
    """The investigation queue.

    `open_actions` and `has_root_cause` come back on every row because
    they are what makes it actionable — §11 requires counts to represent
    items needing action, not total rows.
    """
    return list_failures(
        session,
        organization_id=principal.organization_id,
        project_id=project_id,
        status=status_filter,
    )


@router.post("", status_code=status.HTTP_201_CREATED, tags=["failures"])
def post_failure(
    payload: FailureCreate,
    principal: Principal = Depends(require_permission("failure.create")),
    session: Session = Depends(get_db),
) -> dict[str, Any]:
    try:
        return open_failure(
            session,
            project_id=payload.project_id,
            organization_id=principal.organization_id,
            actor_id=principal.user_id,
            spec=FailureInput(
                failure_code=payload.failure_code,
                title=payload.title,
                description=payload.description,
                severity=payload.severity,
                test_id=payload.test_id,
                formula_version_id=payload.formula_version_id,
                batch_id=payload.batch_id,
            ),
        )
    except FailureNotFoundError as exc:
        raise _missing(exc) from exc
    except (FailureError, CrossTenantReferenceError) as exc:
        raise _invalid(exc) from exc


@router.get("/{failure_id}", tags=["failures"])
def get_one_failure(
    failure_id: uuid.UUID,
    principal: Principal = Depends(require_permission("failure.view")),
    session: Session = Depends(get_db),
) -> dict[str, Any]:
    """One investigation: hypotheses with their evidence, and how each
    piece bears on each hypothesis.

    `accepted_root_cause` is returned separately, and is `null` until a
    Lead accepts one. A screen must be able to show "no root cause yet"
    as distinct from "here are some ideas".
    """
    try:
        return get_failure(
            session, failure_id=failure_id, organization_id=principal.organization_id
        )
    except FailureNotFoundError as exc:
        raise _missing(exc) from exc


@router.post("/{failure_id}/hypotheses", status_code=status.HTTP_201_CREATED, tags=["failures"])
def post_hypothesis(
    failure_id: uuid.UUID,
    payload: HypothesisCreate,
    principal: Principal = Depends(require_permission("failure.investigate")),
    session: Session = Depends(get_db),
) -> dict[str, str]:
    """Propose a possible cause. Always `proposed` — never accepted.

    `failure.investigate` deliberately does NOT carry
    `failure.accept_root_cause`: whoever generates hypotheses must not be
    able to conclude one.
    """
    try:
        hypothesis_id = record_hypothesis(
            session,
            failure_id=failure_id,
            organization_id=principal.organization_id,
            actor_id=principal.user_id,
            spec=HypothesisInput(**payload.model_dump()),
        )
    except FailureNotFoundError as exc:
        raise _missing(exc) from exc
    except FailureStateError as exc:
        raise _conflict(exc) from exc
    return {"id": str(hypothesis_id)}


@router.post("/{failure_id}/evidence", status_code=status.HTTP_201_CREATED, tags=["failures"])
def post_evidence(
    failure_id: uuid.UUID,
    payload: EvidenceCreate,
    principal: Principal = Depends(require_permission("failure.investigate")),
    session: Session = Depends(get_db),
) -> dict[str, str]:
    try:
        evidence_id = record_evidence(
            session,
            failure_id=failure_id,
            organization_id=principal.organization_id,
            actor_id=principal.user_id,
            spec=EvidenceInput(**payload.model_dump()),
        )
    except FailureNotFoundError as exc:
        raise _missing(exc) from exc
    return {"id": str(evidence_id)}


@router.post(
    "/{failure_id}/hypotheses/{hypothesis_id}/evidence",
    status_code=status.HTTP_201_CREATED,
    tags=["failures"],
)
def post_evidence_link(
    failure_id: uuid.UUID,
    hypothesis_id: uuid.UUID,
    payload: EvidenceLink,
    principal: Principal = Depends(require_permission("failure.investigate")),
    session: Session = Depends(get_db),
) -> dict[str, str]:
    """Attach an observation to a hypothesis, saying HOW it bears on it.

    `contradicts` is an ordinary value here. An investigation that could
    only record confirming evidence cannot rule anything out.
    """
    try:
        link_id = link_evidence(
            session,
            hypothesis_id=hypothesis_id,
            evidence_id=payload.evidence_id,
            organization_id=principal.organization_id,
            actor_id=principal.user_id,
            relationship=payload.relationship,
            note=payload.note,
        )
    except FailureNotFoundError as exc:
        raise _missing(exc) from exc
    except FailureError as exc:
        raise _invalid(exc) from exc
    return {"id": str(link_id)}


@router.post("/{failure_id}/root-cause", tags=["failures"])
def post_root_cause(
    failure_id: uuid.UUID,
    payload: RootCauseAcceptance,
    principal: Principal = Depends(require_permission("failure.accept_root_cause")),
    session: Session = Depends(get_db),
) -> dict[str, Any]:
    """🔴 Promote a hypothesis to THE accepted root cause.

    The Lead alone. §7: only a human moves a hypothesis to `accepted`,
    and the people who propose them cannot.
    """
    try:
        return accept_root_cause(
            session,
            failure_id=failure_id,
            hypothesis_id=payload.hypothesis_id,
            organization_id=principal.organization_id,
            actor_id=principal.user_id,
            rationale=payload.rationale,
        )
    except FailureNotFoundError as exc:
        raise _missing(exc) from exc
    except FailureStateError as exc:
        raise _conflict(exc) from exc
    except FailureError as exc:
        raise _invalid(exc) from exc


@router.post("/{failure_id}/hypotheses/{hypothesis_id}/rejection", tags=["failures"])
def post_hypothesis_rejection(
    failure_id: uuid.UUID,
    hypothesis_id: uuid.UUID,
    payload: HypothesisRejection,
    principal: Principal = Depends(require_permission("failure.investigate")),
    session: Session = Depends(get_db),
) -> dict[str, Any]:
    """Rule a hypothesis out, with the reason the next investigator needs."""
    try:
        return reject_hypothesis(
            session,
            hypothesis_id=hypothesis_id,
            organization_id=principal.organization_id,
            actor_id=principal.user_id,
            reason=payload.reason,
        )
    except FailureStateError as exc:
        raise _conflict(exc) from exc
    except FailureError as exc:
        raise _invalid(exc) from exc


@router.post("/{failure_id}/actions", status_code=status.HTTP_201_CREATED, tags=["failures"])
def post_action(
    failure_id: uuid.UUID,
    payload: ActionCreate,
    principal: Principal = Depends(require_permission("failure.investigate")),
    session: Session = Depends(get_db),
) -> dict[str, str]:
    try:
        action_id = raise_action(
            session,
            failure_id=failure_id,
            organization_id=principal.organization_id,
            actor_id=principal.user_id,
            spec=ActionInput(**payload.model_dump()),
        )
    except FailureNotFoundError as exc:
        raise _missing(exc) from exc
    except CrossTenantReferenceError as exc:
        raise _invalid(exc) from exc
    return {"id": str(action_id)}


@router.post("/{failure_id}/closure", tags=["failures"])
def post_closure(
    failure_id: uuid.UUID,
    payload: ClosureCreate,
    principal: Principal = Depends(require_permission("failure.close")),
    session: Session = Depends(get_db),
) -> dict[str, Any]:
    """Close the investigation, with its conclusion.

    Refused while corrective actions are outstanding: closing would leave
    them where no queue will surface them again.
    """
    try:
        return close_failure(
            session,
            failure_id=failure_id,
            organization_id=principal.organization_id,
            actor_id=principal.user_id,
            summary=payload.summary,
        )
    except FailureNotFoundError as exc:
        raise _missing(exc) from exc
    except FailureStateError as exc:
        raise _conflict(exc) from exc
    except FailureError as exc:
        raise _invalid(exc) from exc


# ---------------------------------------------------------------------------
# Approvals — the shared engine
# ---------------------------------------------------------------------------


@approvals_router.get("/queue", tags=["approvals"])
def get_approval_queue(
    principal: Principal = Depends(require_permission("test.view")),
    session: Session = Depends(get_db),
) -> list[dict[str, Any]]:
    """Steps this caller can decide RIGHT NOW.

    Not every undecided step — only those whose turn has come. A queue
    listing work that is still blocked by an earlier group would show
    items the holder cannot act on, and §11 requires a count to mean
    items needing action BY THE HOLDER.

    The caller's own permission set does the filtering, so this endpoint
    needs no permission of its own beyond being able to see tests at all.
    """
    return pending_steps_for(
        session,
        organization_id=principal.organization_id,
        held_permissions=principal.permissions,
    )


@approvals_router.post("", status_code=status.HTTP_201_CREATED, tags=["approvals"])
def post_route(
    payload: RouteOpen,
    principal: Principal = Depends(require_permission("test.plan", "formula.submit")),
    session: Session = Depends(get_db),
) -> dict[str, Any]:
    """Open an approval route by snapshotting the template for an authority."""
    try:
        return open_route(
            session,
            organization_id=principal.organization_id,
            project_id=payload.project_id,
            entity_type=payload.entity_type,
            entity_id=payload.entity_id,
            authority_level=payload.authority_level,
            actor_id=principal.user_id,
        )
    except ApprovalNotFoundError as exc:
        raise _missing(exc) from exc
    except ApprovalStateError as exc:
        raise _conflict(exc) from exc
    except ApprovalError as exc:
        raise _invalid(exc) from exc


@approvals_router.get("/{route_id}", tags=["approvals"])
def get_one_route(
    route_id: uuid.UUID,
    principal: Principal = Depends(require_permission("test.view")),
    session: Session = Depends(get_db),
) -> dict[str, Any]:
    """One route, its snapshotted steps, and who is being waited on.

    `awaiting` is what rule 12 of the traffic light needs in order to
    name the actual approver, rather than saying only "awaiting the next
    approver".
    """
    try:
        return get_route(session, route_id=route_id, organization_id=principal.organization_id)
    except ApprovalNotFoundError as exc:
        raise _missing(exc) from exc


@approvals_router.get("/entity/{entity_type}/{entity_id}", tags=["approvals"])
def get_route_for_entity(
    entity_type: str,
    entity_id: uuid.UUID,
    principal: Principal = Depends(require_permission("test.view")),
    session: Session = Depends(get_db),
) -> dict[str, Any] | None:
    """The open route for a record, or null.

    Null is an ordinary answer, not a 404: a test still in execution has
    nothing to approve, and that is not a missing resource.
    """
    return route_for_entity(
        session,
        organization_id=principal.organization_id,
        entity_type=entity_type,
        entity_id=entity_id,
    )


@approvals_router.post("/{route_id}/steps/{step_id}/decision", tags=["approvals"])
def post_step_decision(
    route_id: uuid.UUID,
    step_id: uuid.UUID,
    payload: StepDecision,
    principal: Principal = Depends(require_permission("test.view")),
    session: Session = Depends(get_db),
) -> dict[str, Any]:
    """Decide one step.

    🔴 THE PERMISSION IS THE STEP'S, NOT THIS ENDPOINT'S.

    `require_permission("test.view")` here is only a floor — the engine
    checks the permission the SNAPSHOTTED STEP names, which is the
    template's decision and not the router's. Hard-coding a permission
    here would mean the route's own definition of who may sign was
    advisory, and a template could never introduce a step this endpoint
    had not anticipated.

    403 covers two different refusals and says which: the caller lacks
    the step's permission, or holds it and is disqualified by their own
    earlier involvement (ADR-019).
    """
    try:
        return decide_step(
            session,
            route_id=route_id,
            step_id=step_id,
            organization_id=principal.organization_id,
            actor_id=principal.user_id,
            held_permissions=principal.permissions,
            spec=ApprovalDecisionInput(
                decision=payload.decision,
                condition_text=payload.condition_text,
                rationale=payload.rationale,
            ),
        )
    except ApprovalNotFoundError as exc:
        raise _missing(exc) from exc
    except IncompatibleDutyError as exc:
        raise PermissionDenied(str(exc)) from exc
    except ApprovalStateError as exc:
        raise _conflict(exc) from exc
    except ApprovalError as exc:
        raise _invalid(exc) from exc


@approvals_router.post(
    "/versions/{formula_version_id}/drivers",
    status_code=status.HTTP_201_CREATED,
    tags=["approvals"],
)
def post_version_driver(
    formula_version_id: uuid.UUID,
    payload: DriverCreate,
    principal: Principal = Depends(require_permission("formula.clone", "formula.create")),
    session: Session = Depends(get_db),
) -> dict[str, str]:
    """Record WHY a formula version exists. §29.

    Several drivers per version are expected: a revision may answer a
    failure and chase a requirement at once, and a single column would
    force somebody to pick one and lose the rest.
    """
    try:
        driver_id = record_driver(
            session,
            formula_version_id=formula_version_id,
            organization_id=principal.organization_id,
            actor_id=principal.user_id,
            spec=DriverInput(**payload.model_dump()),
        )
    except FailureNotFoundError as exc:
        raise _missing(exc) from exc
    except FailureError as exc:
        raise _invalid(exc) from exc
    return {"id": str(driver_id)}
