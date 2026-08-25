"""Laboratory routes — the guided batch flow.

**Each step is guarded by the permission that names it**, and those
permissions were checked against migration 002 before this module was
written rather than invented to fit it:

    batch.create    Chemist            create the batch, issue the sheet
    batch.execute   Technician         start it, weigh, capture process data
    batch.complete  Engineer, Tech     close execution
    batch.reject    Engineer           reject at review
    sample.create   Chemist, Eng, Tech take a sample

There is deliberately no `batch.authorize`: no such permission exists, and
inventing one would have produced a control no role holds — the defect
migration 016 had to close for `material.approve_production`. The
authorising act is the Lead's `formula.approve_lab`, without which the
batch cannot be created at all.

**Review is one endpoint, two permissions.** Accepting needs
`batch.complete`; rejecting needs `batch.reject`, which only the Engineer
holds. Guarding the endpoint with either alone would have handed the
Technician a rejection right the permission model withholds, or blocked
the Engineer from accepting. Resolved from the decision in the body, the
same shape as the material status route.
"""

from __future__ import annotations

import uuid
from decimal import Decimal
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

# 🔴 THE READS GO THROUGH THE ORCHESTRATOR (§0.2, I103).
#
# This module called its domain service directly, and the department
# conductor written for it had NO CALLERS -- a layer nothing reaches is the
# same defect as a route nothing calls, which is a rule this repository
# already has. `app/api/dashboards.py` was wired first; this is the same
# move.
#
# ⚠️ THE WRITES DELIBERATELY DO NOT. §4: humans approve, and AI must not
# authorize a batch, confirm a test or move a result from YELLOW to GREEN.
# So the orchestrator exposes no write-side entry point at all, and every
# mutation below still calls the domain service directly. The asymmetry is
# the rule, not an omission -- if a write ever appears on that door, it is a
# §4 violation and not a convenience.
#
# ⚠️ `require_permission(...)` ON EACH ROUTE STAYS. The conductor asserts the
# same permission; that is defence in depth. The dependency refuses an
# unauthenticated caller before any handler runs, and the conductor refuses on
# the paths that have no route.
from app.agents.orchestrators.root_orchestrator import (
    laboratory_batch,
    laboratory_batches,
)
from app.core.security import (
    PermissionDenied,
    Principal,
    get_db,
    get_principal,
    require_permission,
)
from app.core.tenancy import CrossTenantReferenceError
from app.domains.laboratory.service import (
    BatchError,
    BatchInput,
    BatchNotFoundError,
    BatchStateError,
    DeviationInput,
    LaboratoryError,
    ProcessParameterInput,
    SampleInput,
    authorize_batch,
    complete_batch,
    create_batch,
    create_sample,
    raise_deviation,
    record_process_parameter,
    record_weighing,
    review_batch,
    start_batch,
)

router = APIRouter()

__all__ = ["router"]

# Which permission each review decision requires. A table for the same
# reason the material lifecycle has one: the mapping IS the authorization
# model for this step and must be readable without following control flow.
REVIEW_PERMISSION: dict[str, str] = {
    "accept": "batch.complete",
    "reject": "batch.reject",
}


class BatchCreate(BaseModel):
    formula_version_id: uuid.UUID
    batch_number: str = Field(min_length=3, max_length=50)
    # `Decimal`, never `float`. A batch quantity is a controlled mass and
    # the engine refuses a float at its boundary; declaring it as a float
    # here would undo that at the one point a number enters the system.
    planned_quantity_kg: Decimal = Field(gt=0)
    tolerance_percent: Decimal | None = Field(default=None, ge=0, le=100)
    purpose: str | None = Field(default=None, max_length=500)
    mixing_procedure: str | None = None
    notes: str | None = None


class WeighingCreate(BaseModel):
    actual_mass_kg: Decimal = Field(ge=0)
    material_lot_id: uuid.UUID | None = None


class ProcessParameterCreate(BaseModel):
    parameter_code: str = Field(min_length=1, max_length=50)
    value: Decimal
    # Required, not optional. A bare number labelled `temperature` cannot
    # be compared against another batch, and CLAUDE.md §5 requires
    # measurements stored as value + unit.
    unit: str = Field(min_length=1, max_length=20)
    stage: str | None = Field(default=None, max_length=50)
    notes: str | None = None


class DeviationCreate(BaseModel):
    description: str = Field(min_length=3, max_length=2000)
    severity: str = Field(default="minor", pattern="^(minor|major|critical)$")
    batch_component_id: uuid.UUID | None = None


class SampleCreate(BaseModel):
    sample_number: str = Field(min_length=3, max_length=50)
    quantity_g: Decimal | None = Field(default=None, gt=0)
    purpose: str | None = Field(default=None, max_length=500)
    storage_location: str | None = Field(default=None, max_length=200)
    notes: str | None = None


class ReviewCreate(BaseModel):
    decision: str = Field(pattern="^(accept|reject)$")
    note: str | None = Field(default=None, max_length=2000)


def _missing(exc: Exception) -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


def _conflict(exc: Exception) -> HTTPException:
    return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))


def _invalid(exc: Exception) -> HTTPException:
    return HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))


@router.get("", tags=["laboratory"])
def get_batches(
    project_id: uuid.UUID | None = Query(default=None),
    status_filter: str | None = Query(default=None, alias="status"),
    principal: Principal = Depends(require_permission("batch.view")),
    session: Session = Depends(get_db),
) -> list[dict[str, Any]]:
    """The batch queue.

    `unweighed_count` comes back on every row because it is what makes the
    queue actionable — CLAUDE.md §11 requires counts to represent items
    needing action, not total rows.
    """
    return laboratory_batches(
        session,
        organization_id=principal.organization_id,
        permissions=principal.permissions,
        project_id=project_id,
        status=status_filter,
    )


@router.post("", status_code=status.HTTP_201_CREATED, tags=["laboratory"])
def post_batch(
    payload: BatchCreate,
    principal: Principal = Depends(require_permission("batch.create")),
    session: Session = Depends(get_db),
) -> dict[str, Any]:
    """Create a batch and calculate its weigh-up sheet.

    A 409 means the formula version exists but has not been approved for
    laboratory trial. That distinction matters to the caller: the first is
    a mistake, the second is a step somebody still has to take.
    """
    try:
        return create_batch(
            session,
            formula_version_id=payload.formula_version_id,
            organization_id=principal.organization_id,
            actor_id=principal.user_id,
            spec=BatchInput(
                batch_number=payload.batch_number,
                planned_quantity_kg=payload.planned_quantity_kg,
                tolerance_percent=payload.tolerance_percent,
                purpose=payload.purpose,
                mixing_procedure=payload.mixing_procedure,
                notes=payload.notes,
            ),
        )
    except BatchNotFoundError as exc:
        raise _missing(exc) from exc
    except BatchStateError as exc:
        raise _conflict(exc) from exc
    except (BatchError, CrossTenantReferenceError) as exc:
        raise _invalid(exc) from exc


@router.get("/{batch_id}", tags=["laboratory"])
def get_one_batch(
    batch_id: uuid.UUID,
    principal: Principal = Depends(require_permission("batch.view")),
    session: Session = Depends(get_db),
) -> dict[str, Any]:
    """The sheet, what was weighed against it, process data, deviations,
    samples — and each line's deviation computed at read time."""
    try:
        return laboratory_batch(
            session,
            batch_id=batch_id,
            organization_id=principal.organization_id,
            permissions=principal.permissions,
        )
    except BatchNotFoundError as exc:
        raise _missing(exc) from exc


@router.post("/{batch_id}/authorization", tags=["laboratory"])
def post_authorization(
    batch_id: uuid.UUID,
    principal: Principal = Depends(require_permission("batch.create")),
    session: Session = Depends(get_db),
) -> dict[str, Any]:
    """Issue the weigh-up sheet. Planned quantities freeze here."""
    try:
        return authorize_batch(
            session,
            batch_id=batch_id,
            organization_id=principal.organization_id,
            actor_id=principal.user_id,
        )
    except BatchNotFoundError as exc:
        raise _missing(exc) from exc
    except BatchStateError as exc:
        raise _conflict(exc) from exc


@router.post("/{batch_id}/start", tags=["laboratory"])
def post_start(
    batch_id: uuid.UUID,
    principal: Principal = Depends(require_permission("batch.execute")),
    session: Session = Depends(get_db),
) -> dict[str, Any]:
    try:
        return start_batch(
            session,
            batch_id=batch_id,
            organization_id=principal.organization_id,
            actor_id=principal.user_id,
        )
    except BatchNotFoundError as exc:
        raise _missing(exc) from exc
    except BatchStateError as exc:
        raise _conflict(exc) from exc


@router.post("/{batch_id}/components/{component_id}/weighing", tags=["laboratory"])
def post_weighing(
    batch_id: uuid.UUID,
    component_id: uuid.UUID,
    payload: WeighingCreate,
    principal: Principal = Depends(require_permission("batch.execute")),
    session: Session = Depends(get_db),
) -> dict[str, Any]:
    """Record what was actually weighed, and from which lot.

    Returns the deviation immediately — delta, percentage and whether it
    is within the batch's tolerance — because a technician needs to know
    at the bench, while the material is still in front of them, not at
    review a day later.
    """
    try:
        return record_weighing(
            session,
            batch_id=batch_id,
            component_id=component_id,
            organization_id=principal.organization_id,
            actor_id=principal.user_id,
            actual_mass_kg=payload.actual_mass_kg,
            material_lot_id=payload.material_lot_id,
        )
    except BatchNotFoundError as exc:
        raise _missing(exc) from exc
    except BatchStateError as exc:
        raise _conflict(exc) from exc
    except LaboratoryError as exc:
        raise _invalid(exc) from exc


@router.post(
    "/{batch_id}/process-parameters", status_code=status.HTTP_201_CREATED, tags=["laboratory"]
)
def post_process_parameter(
    batch_id: uuid.UUID,
    payload: ProcessParameterCreate,
    principal: Principal = Depends(require_permission("batch.execute")),
    session: Session = Depends(get_db),
) -> dict[str, str]:
    """Capture mixing RPM, mixing time, temperature, vacuum — value + unit."""
    try:
        parameter_id = record_process_parameter(
            session,
            batch_id=batch_id,
            organization_id=principal.organization_id,
            actor_id=principal.user_id,
            spec=ProcessParameterInput(**payload.model_dump()),
        )
    except BatchNotFoundError as exc:
        raise _missing(exc) from exc
    except BatchStateError as exc:
        raise _conflict(exc) from exc
    return {"id": str(parameter_id)}


@router.post("/{batch_id}/deviations", status_code=status.HTTP_201_CREATED, tags=["laboratory"])
def post_deviation(
    batch_id: uuid.UUID,
    payload: DeviationCreate,
    # Either the person at the bench or the one reviewing may raise one.
    # A deviation noticed at review is the evidence the review exists to
    # act on, and refusing it there would push it onto paper.
    principal: Principal = Depends(require_permission("batch.execute", "batch.complete")),
    session: Session = Depends(get_db),
) -> dict[str, str]:
    try:
        deviation_id = raise_deviation(
            session,
            batch_id=batch_id,
            organization_id=principal.organization_id,
            actor_id=principal.user_id,
            spec=DeviationInput(**payload.model_dump()),
        )
    except BatchNotFoundError as exc:
        raise _missing(exc) from exc
    return {"id": str(deviation_id)}


@router.post("/{batch_id}/samples", status_code=status.HTTP_201_CREATED, tags=["laboratory"])
def post_sample(
    batch_id: uuid.UUID,
    payload: SampleCreate,
    principal: Principal = Depends(require_permission("sample.create")),
    session: Session = Depends(get_db),
) -> dict[str, str]:
    """Take a sample. This is the record every future test result cites."""
    try:
        sample_id = create_sample(
            session,
            batch_id=batch_id,
            organization_id=principal.organization_id,
            actor_id=principal.user_id,
            spec=SampleInput(**payload.model_dump()),
        )
    except BatchNotFoundError as exc:
        raise _missing(exc) from exc
    except BatchStateError as exc:
        raise _conflict(exc) from exc
    except BatchError as exc:
        raise _invalid(exc) from exc
    return {"id": str(sample_id)}


@router.post("/{batch_id}/completion", tags=["laboratory"])
def post_completion(
    batch_id: uuid.UUID,
    principal: Principal = Depends(require_permission("batch.complete")),
    session: Session = Depends(get_db),
) -> dict[str, Any]:
    """Close execution. Refused while any line is unweighed."""
    try:
        return complete_batch(
            session,
            batch_id=batch_id,
            organization_id=principal.organization_id,
            actor_id=principal.user_id,
        )
    except BatchNotFoundError as exc:
        raise _missing(exc) from exc
    except BatchStateError as exc:
        raise _conflict(exc) from exc


@router.post("/{batch_id}/review", tags=["laboratory"])
def post_review(
    batch_id: uuid.UUID,
    payload: ReviewCreate,
    principal: Principal = Depends(get_principal),
    session: Session = Depends(get_db),
) -> dict[str, Any]:
    """Chemist Review: Accept for Testing, or Reject for Process Deviation.

    Depends on `get_principal` because the required permission depends on
    the DECISION: only the Engineer holds `batch.reject`. A single
    permission on the endpoint would either hand the Technician a
    rejection right the model withholds, or stop the Engineer accepting.
    """
    required = REVIEW_PERMISSION[payload.decision]
    if not principal.has(required):
        raise PermissionDenied()

    try:
        return review_batch(
            session,
            batch_id=batch_id,
            organization_id=principal.organization_id,
            actor_id=principal.user_id,
            decision=payload.decision,
            note=payload.note,
        )
    except BatchNotFoundError as exc:
        raise _missing(exc) from exc
    except BatchStateError as exc:
        raise _conflict(exc) from exc
    except LaboratoryError as exc:
        # Segregation of duties: the executor may not review their own
        # batch. 403, because it is an authorization refusal about WHO,
        # not a malformed request.
        raise PermissionDenied(str(exc)) from exc
