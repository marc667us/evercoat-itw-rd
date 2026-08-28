"""Material Safety Data, over HTTP.

🔴 `compliance.review_sds` GETS ITS FIRST ENFORCEMENT POINT HERE.

It has been in the catalogue since `002:127` — *"Review SDS and safety
documentation"* — granted to `qa_compliance_officer` since `002:275`, and read
by nothing in this application. It is one of 29 permissions measured in that
state. This module does not mint `safety.review` beside it: a synonym for a
permission the catalogue already carries is the "two literals in two files"
defect this project keeps finding, and §30 of the specification asks for a
capability, not for a particular string.

🔴 PERMISSION AND RESOURCE SCOPE ARE SEPARATE GATES (SECURITY.md §3).

Holding `compliance.review_sds` says a role may review safety documentation. It
does not say they may see a restricted project's work. The routes below apply
the permission; RLS applies the project predicate on `safety_alerts` and
`safety_reviews`, so a compliance officer who is not a member of a restricted
project gets that project's alerts filtered out by PostgreSQL rather than by
anything here.

⚠️ THIS MODULE REPORTS RECORD STATE. IT DOES NOT ASSESS HAZARD. The rule comes
from `agents/tools/safety.py` and binds the whole capability: *"'RM-104 is
restricted, its SDS is missing' are facts read out of columns. 'RM-104 is safe
to use at 4%' is a compliance determination."* Every response here is counts,
statuses, stated absences and what changed between two revisions. The judgement
is the reviewer's, and it is recorded through the approval engine.
"""

from __future__ import annotations

import uuid
from datetime import date
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.security import Principal, get_db, require_permission
from app.core.tenancy import CrossTenantReferenceError
from app.domains.material_safety.service import (
    ComponentInput,
    HazardInput,
    MaterialSafetyError,
    MaterialSafetyNotFoundError,
    MaterialSafetyStateError,
    SdsInterpretation,
    SectionInput,
    acknowledge_alert,
    compare_revisions,
    confirm_interpretation,
    current_safety_position,
    impact_of_revision,
    interpret_sds,
    list_alerts,
    list_comparable_revisions,
    list_interpretable_documents,
    list_interpretations_for_material,
    list_pending_interpretations,
    open_safety_review,
    raise_alerts_for_revision,
)

router = APIRouter()

__all__ = ["router"]


class SectionPayload(BaseModel):
    section_number: int = Field(ge=1, le=16)
    heading: str = Field(min_length=1, max_length=200)
    body: str | None = Field(default=None, max_length=20000)


class HazardPayload(BaseModel):
    hazard_class: str = Field(min_length=1, max_length=200)
    hazard_category: str | None = Field(default=None, max_length=100)
    # Shape only. The GHS code list changes with each revision of the standard,
    # and a hard-coded enum here would refuse a real code from a newer sheet --
    # which, for hazard data, is the worse failure.
    hazard_code: str | None = Field(default=None, pattern=r"^[HP][0-9]{3}[A-Za-z+]*$")
    signal_word: str | None = Field(default=None, pattern=r"^(Danger|Warning)$")
    statement: str | None = Field(default=None, max_length=2000)


class ComponentPayload(BaseModel):
    component_name: str = Field(min_length=1, max_length=300)
    cas_number: str | None = Field(default=None, pattern=r"^[0-9]{2,7}-[0-9]{2}-[0-9]$")
    ec_number: str | None = Field(default=None, max_length=50)
    # 🔴 STRINGS, NOT FLOATS, ALL THE WAY TO POSTGRES.
    # CLAUDE.md §5: NUMERIC never float for a percentage on a controlled
    # record. Binding a Python float here would round before the database ever
    # saw the value, and the column's NUMERIC(7,4) would then be storing a
    # number nobody typed.
    concentration_low: str | None = Field(default=None, pattern=r"^[0-9]{1,3}(\.[0-9]{1,4})?$")
    concentration_high: str | None = Field(default=None, pattern=r"^[0-9]{1,3}(\.[0-9]{1,4})?$")


class InterpretationCreate(BaseModel):
    document_id: uuid.UUID
    material_id: uuid.UUID
    supplier_revision: str | None = Field(default=None, max_length=100)
    manufacturer: str | None = Field(default=None, max_length=300)
    effective_date: date | None = None
    sections: list[SectionPayload] = Field(default_factory=list, max_length=16)
    hazards: list[HazardPayload] = Field(default_factory=list, max_length=100)
    components: list[ComponentPayload] = Field(default_factory=list, max_length=200)


class ReviewDecision(BaseModel):
    accept: bool


class AlertsRequest(BaseModel):
    previous_version_id: uuid.UUID


class SafetyReviewCreate(BaseModel):
    project_id: uuid.UUID
    reason: str = Field(min_length=1, max_length=2000)


def _refuse(exc: MaterialSafetyError) -> HTTPException:
    """Map a domain error onto a status a client can act on.

    `NotFound` and `State` are different answers and must stay different: one
    means "you are asking about something that is not there", the other means
    "it is there and this is not a thing you may do to it now".
    """
    if isinstance(exc, MaterialSafetyNotFoundError):
        return HTTPException(status.HTTP_404_NOT_FOUND, str(exc))
    if isinstance(exc, MaterialSafetyStateError):
        return HTTPException(status.HTTP_409_CONFLICT, str(exc))
    return HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc))


@router.get("/materials/{material_id}", summary="The safety position for one material")
def get_material_safety(
    material_id: uuid.UUID,
    principal: Principal = Depends(require_permission("material.view")),
    session: Session = Depends(get_db),
) -> dict[str, Any]:
    """What is on file now.

    Gated on `material.view` rather than a new `safety.view`: safety data is
    information ABOUT a material, and the nine roles that may look at a
    material are the nine that need to know what its sheet says. Inventing a
    permission here would produce the defect this project has caught five
    times — a permission nobody holds, gating a feature nobody can then use.

    `current` is `null` when no USABLE SDS is interpreted, and that is a real
    answer the screen must state plainly rather than render as an empty panel:
    "no current safety data on file" is the actionable fact.
    """
    return current_safety_position(
        session, organization_id=principal.organization_id, material_id=material_id
    )


@router.post(
    "/interpretations",
    status_code=status.HTTP_201_CREATED,
    summary="Record what one Safety Data Sheet says",
)
def post_interpretation(
    payload: InterpretationCreate,
    principal: Principal = Depends(require_permission("material.edit")),
    session: Session = Depends(get_db),
) -> dict[str, Any]:
    """Transcribe a sheet into structured safety data.

    ⚠️ IT LANDS AS `pending_review`, ALWAYS. The specification: *"Where a
    document cannot be reliably interpreted automatically, the information
    shall remain pending technical review rather than being treated as
    confirmed safety data."* Recording is `material.edit`; confirming is
    `compliance.review_sds`, and they are deliberately different acts held by
    different roles.

    The database refuses a document that is not usable, is not an SDS, or does
    not belong to the named material. That is a trigger rather than a check
    here, because a rule enforced only in Python is not a rule the database
    has.
    """
    try:
        result = interpret_sds(
            session,
            organization_id=principal.organization_id,
            actor_id=principal.user_id,
            document_id=payload.document_id,
            material_id=payload.material_id,
            spec=SdsInterpretation(
                supplier_revision=payload.supplier_revision,
                manufacturer=payload.manufacturer,
                effective_date=payload.effective_date.isoformat()
                if payload.effective_date
                else None,
                sections=tuple(
                    SectionInput(s.section_number, s.heading, s.body) for s in payload.sections
                ),
                hazards=tuple(
                    HazardInput(
                        h.hazard_class, h.hazard_category, h.hazard_code, h.signal_word, h.statement
                    )
                    for h in payload.hazards
                ),
                components=tuple(
                    ComponentInput(
                        c.component_name,
                        c.cas_number,
                        c.ec_number,
                        c.concentration_low,
                        c.concentration_high,
                    )
                    for c in payload.components
                ),
            ),
        )
    except MaterialSafetyError as exc:
        raise _refuse(exc) from exc
    except CrossTenantReferenceError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc
    # 🔴 ON THE SUCCESS PATH ONLY, AND IT HAS TO BE HERE.
    #
    # An earlier draft of this function had no commit at all, hidden behind a
    # `finally` block whose condition was `... or True`. Every interpretation
    # would have been rolled back by `get_db` on the way out, the route would
    # have returned 201 with a real id, and the row would not have existed.
    # Nothing would have failed: not the type checker, not the linter, and not
    # a test that only asserts the status code.
    session.commit()
    return result


@router.get(
    "/interpretations/comparable",
    summary="Materials whose newest reading has a predecessor to compare against",
)
def get_comparable(
    principal: Principal = Depends(require_permission("compliance.review_sds")),
    session: Session = Depends(get_db),
    limit: int = Query(default=100, ge=1, le=500),
) -> list[dict[str, Any]]:
    """What the "raise alerts" control offers.

    🔴 WITHOUT IT THAT ROUTE HAD NO CALLER. Raising alerts needs two
    interpretation ids of the same material, and no browser could supply that
    pair without a person pasting UUIDs. A hook with no button is the same
    defect as no hook.
    """
    return list_comparable_revisions(
        session, organization_id=principal.organization_id, limit=limit
    )


@router.get(
    "/interpretations/candidates",
    summary="Usable Safety Data Sheets that have not been read yet",
)
def get_candidates(
    principal: Principal = Depends(require_permission("material.edit")),
    session: Session = Depends(get_db),
    limit: int = Query(default=200, ge=1, le=500),
) -> list[dict[str, Any]]:
    """What the "record a reading" form offers.

    🔴 IT EXISTS SO THE WRITE IS PRESSABLE. `POST /interpretations` takes a
    document id and a material id; without this the only way to call it from a
    browser would be to paste two UUIDs, which this project has already logged
    as a defect on the add-a-project-member screen. A control nobody can
    realistically operate is not a caller.
    """
    return list_interpretable_documents(
        session, organization_id=principal.organization_id, limit=limit
    )


@router.get(
    "/materials/{material_id}/interpretations",
    summary="Every reading recorded for a material, history included",
)
def get_material_interpretations(
    material_id: uuid.UUID,
    principal: Principal = Depends(require_permission("material.view")),
    session: Session = Depends(get_db),
) -> list[dict[str, Any]]:
    """The list a reviewer picks two entries from in order to compare them.

    Includes superseded readings, which is the point: the previous revision has
    left `materials.usable_documents` by the time there is anything to compare
    it with. `is_current` says which one the view still returns.
    """
    return list_interpretations_for_material(
        session, organization_id=principal.organization_id, material_id=material_id
    )


@router.get("/interpretations/pending", summary="Interpretations awaiting technical review")
def get_pending(
    principal: Principal = Depends(require_permission("compliance.review_sds")),
    session: Session = Depends(get_db),
    limit: int = Query(default=100, ge=1, le=500),
) -> list[dict[str, Any]]:
    """The compliance officer's queue."""
    return list_pending_interpretations(
        session, organization_id=principal.organization_id, limit=limit
    )


# 🔴 `confirm`, NOT `review`. The route below this one opens a controlled
# SAFETY REVIEW, and two POST routes differing only by a plural "s" is a
# trap for whoever writes the client: one confirms a transcription, the
# other opens an approval route on a project. Different acts, different
# consequences, names that cannot be confused.
@router.post("/interpretations/{sds_version_id}/confirm", summary="Confirm or reject a reading")
def post_review(
    sds_version_id: uuid.UUID,
    payload: ReviewDecision,
    principal: Principal = Depends(require_permission("compliance.review_sds")),
    session: Session = Depends(get_db),
) -> dict[str, Any]:
    """The act `compliance.review_sds` was seeded for, five slices ago."""
    try:
        result = confirm_interpretation(
            session,
            organization_id=principal.organization_id,
            reviewer_id=principal.user_id,
            sds_version_id=sds_version_id,
            accept=payload.accept,
        )
    except MaterialSafetyError as exc:
        raise _refuse(exc) from exc
    session.commit()
    return result


@router.get("/interpretations/{sds_version_id}/impact", summary="What this revision reaches")
def get_impact(
    sds_version_id: uuid.UUID,
    principal: Principal = Depends(require_permission("material.view")),
    session: Session = Depends(get_db),
) -> dict[str, Any]:
    """Formulas, projects and open laboratory batches containing the material.

    ⚠️ THIS IS THE CALLER'S ANSWER, NOT THE ORGANIZATION'S. The underlying
    `material_usage` is RLS-scoped, so a restricted project the caller is not
    in is absent. That is intended and documented there: a bare count RLS had
    silently reduced would look like a fact.
    """
    try:
        return impact_of_revision(
            session, organization_id=principal.organization_id, sds_version_id=sds_version_id
        )
    except MaterialSafetyError as exc:
        raise _refuse(exc) from exc


@router.get("/interpretations/compare", summary="What changed between two readings")
def get_comparison(
    previous_version_id: uuid.UUID,
    current_version_id: uuid.UUID,
    principal: Principal = Depends(require_permission("material.view")),
    session: Session = Depends(get_db),
) -> dict[str, Any]:
    """Components added and removed, ranges changed, hazards added and removed.

    Works across a supersession, which is the whole point: the previous
    revision has left `materials.usable_documents` by the time there is
    anything to compare it with, and its interpretation is kept precisely so
    this question can still be answered.
    """
    try:
        return compare_revisions(
            session,
            organization_id=principal.organization_id,
            previous_version_id=previous_version_id,
            current_version_id=current_version_id,
        )
    except MaterialSafetyError as exc:
        raise _refuse(exc) from exc


@router.post(
    "/interpretations/{sds_version_id}/alerts",
    status_code=status.HTTP_201_CREATED,
    summary="Raise safety alerts for what this revision changed",
)
def post_alerts(
    sds_version_id: uuid.UUID,
    payload: AlertsRequest,
    principal: Principal = Depends(require_permission("compliance.review_sds")),
    session: Session = Depends(get_db),
) -> list[dict[str, Any]]:
    """§23's chain: compare, find the affected work, tell the project leads.

    Returns an empty list when nothing substantive changed — deliberately.
    An alert saying "nothing changed" trains people to close alerts without
    reading them, and the next one will be the one that mattered.
    """
    try:
        raised = raise_alerts_for_revision(
            session,
            organization_id=principal.organization_id,
            actor_id=principal.user_id,
            sds_version_id=sds_version_id,
            previous_version_id=payload.previous_version_id,
        )
    except MaterialSafetyError as exc:
        raise _refuse(exc) from exc
    session.commit()
    return raised


@router.get("/alerts", summary="Safety alerts this caller can reach")
def get_alerts(
    principal: Principal = Depends(require_permission("material.view")),
    session: Session = Depends(get_db),
    unacknowledged_only: bool = Query(default=False),
    limit: int = Query(default=100, ge=1, le=500),
) -> list[dict[str, Any]]:
    return list_alerts(
        session,
        organization_id=principal.organization_id,
        unacknowledged_only=unacknowledged_only,
        limit=limit,
    )


@router.post("/alerts/{alert_id}/acknowledge", summary="Mark an alert as seen")
def post_acknowledge(
    alert_id: uuid.UUID,
    principal: Principal = Depends(require_permission("material.view")),
    session: Session = Depends(get_db),
) -> dict[str, Any]:
    """Acknowledging is not clearing.

    The alert stays, with a name and a time on it. `material.view` rather than
    a compliance permission because the person who must act is usually the
    project lead, and RLS has already limited this to alerts on projects the
    caller can reach.
    """
    try:
        result = acknowledge_alert(
            session,
            organization_id=principal.organization_id,
            actor_id=principal.user_id,
            alert_id=alert_id,
        )
    except MaterialSafetyError as exc:
        raise _refuse(exc) from exc
    session.commit()
    return result


@router.post(
    "/interpretations/{sds_version_id}/safety-reviews",
    status_code=status.HTTP_201_CREATED,
    summary="Open a controlled safety review on a project",
)
def post_safety_review(
    sds_version_id: uuid.UUID,
    payload: SafetyReviewCreate,
    principal: Principal = Depends(require_permission("compliance.review_sds")),
    session: Session = Depends(get_db),
) -> dict[str, Any]:
    """Opens the review AND its approval route, through the one shared engine.

    The route lands in `/approvals` beside every other pending signature —
    there is no second queue. Step 1 requires `compliance.review_sds`, step 2
    requires `safety.approve` and must be decided by somebody who did not
    decide step 1 (migration 055).
    """
    try:
        result = open_safety_review(
            session,
            organization_id=principal.organization_id,
            actor_id=principal.user_id,
            sds_version_id=sds_version_id,
            project_id=payload.project_id,
            reason=payload.reason,
        )
    except MaterialSafetyError as exc:
        raise _refuse(exc) from exc
    except CrossTenantReferenceError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc
    session.commit()
    return result
