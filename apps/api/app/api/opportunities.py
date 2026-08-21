"""Opportunity routes — the innovation funnel and its gate.

`opportunity.decide` and `opportunity.create` are separate permissions on
purpose. Anyone in R&D may propose; deciding is a Director/Lead act, and
the separation is the whole point of a gate. Granting both to the same
role in a deployment is a staffing choice; collapsing them into one
permission would remove the choice.

Rule 4 -- humans approve -- is enforced by these permissions being
reachable only through an authenticated Principal. No agent path exists
to this router.
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
from app.domains.opportunities.service import (
    OpportunityDecision,
    OpportunityInput,
    OpportunityNotFoundError,
    OpportunityStateError,
    convert_to_project,
    create_opportunity,
    decide_opportunity,
    list_opportunities,
    opportunity_detail,
    submit_opportunity,
)

router = APIRouter()

__all__ = ["router"]


class OpportunityCreate(BaseModel):
    opportunity_code: str = Field(min_length=3, max_length=50)
    title: str = Field(min_length=1, max_length=200)
    market_need: str | None = None
    product_family: str | None = None
    target_application: str | None = None
    technical_concept: str | None = None
    priority: str = Field(default="medium", pattern="^(low|medium|high|critical)$")


class DecisionCreate(BaseModel):
    decision: str = Field(pattern="^(approve|reject|hold|more_information)$")
    # Required. A rejected opportunity with no stated reason gets
    # re-proposed every year by somebody who was not in the room.
    rationale: str = Field(min_length=3, max_length=2000)


class ConversionCreate(BaseModel):
    project_code: str = Field(min_length=3, max_length=50)
    name: str = Field(min_length=1, max_length=200)
    lead_user_id: uuid.UUID
    target_release_date: date | None = None
    confidentiality: str = Field(default="normal", pattern="^(normal|restricted)$")


def _refuse(exc: OpportunityStateError) -> HTTPException:
    return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))


def _missing(exc: OpportunityNotFoundError) -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


@router.get("", tags=["opportunities"])
def get_opportunities(
    status_filter: str | None = Query(default=None, alias="status"),
    principal: Principal = Depends(require_permission("opportunity.view")),
    session: Session = Depends(get_db),
) -> list[dict[str, Any]]:
    """The funnel. Optionally filtered to one status."""
    return list_opportunities(
        session, organization_id=principal.organization_id, status=status_filter
    )


@router.post("", status_code=status.HTTP_201_CREATED, tags=["opportunities"])
def post_opportunity(
    payload: OpportunityCreate,
    principal: Principal = Depends(require_permission("opportunity.create")),
    session: Session = Depends(get_db),
) -> dict[str, str]:
    try:
        opportunity_id = create_opportunity(
            session,
            data=OpportunityInput(**payload.model_dump()),
            actor_id=principal.user_id,
            organization_id=principal.organization_id,
        )
    except OpportunityStateError as exc:
        raise _refuse(exc) from exc
    return {"id": str(opportunity_id)}


@router.get("/{opportunity_id}", tags=["opportunities"])
def get_opportunity(
    opportunity_id: uuid.UUID,
    principal: Principal = Depends(require_permission("opportunity.view")),
    session: Session = Depends(get_db),
) -> dict[str, Any]:
    try:
        return opportunity_detail(
            session,
            opportunity_id=opportunity_id,
            organization_id=principal.organization_id,
        )
    except OpportunityNotFoundError as exc:
        raise _missing(exc) from exc


@router.post("/{opportunity_id}/submission", tags=["opportunities"])
def post_submission(
    opportunity_id: uuid.UUID,
    principal: Principal = Depends(require_permission("opportunity.create")),
    session: Session = Depends(get_db),
) -> dict[str, str]:
    """Submit a draft opportunity for a gate decision.

    🔴 THE ROUTE THAT DID NOT EXIST. `create_opportunity` writes `draft`,
    `decide_opportunity` refuses anything outside
    {feasibility, awaiting_decision, on_hold}, and NOTHING wrote those -- so
    an opportunity could be created and never decided, and therefore never
    become a project. §44's golden scenario begins with exactly that
    transition, and the whole digital thread hangs off it.

    Behind `opportunity.create`, not `opportunity.decide`: submitting is the
    AUTHOR saying their draft is ready to be judged. Requiring the deciding
    permission would mean only a Director could put work in their own queue.

    No body: there is nothing for the caller to state. The target status is
    the one the decision gate reads, and letting a client name it would let
    somebody skip straight past feasibility.
    """
    try:
        new_status = submit_opportunity(
            session,
            opportunity_id=opportunity_id,
            organization_id=principal.organization_id,
            actor_id=principal.user_id,
        )
    except OpportunityNotFoundError as exc:
        raise _missing(exc) from exc
    except OpportunityStateError as exc:
        raise _refuse(exc) from exc
    return {"status": new_status}


@router.post("/{opportunity_id}/decision", tags=["opportunities"])
def post_decision(
    opportunity_id: uuid.UUID,
    payload: DecisionCreate,
    principal: Principal = Depends(require_permission("opportunity.decide")),
    session: Session = Depends(get_db),
) -> dict[str, str]:
    """Record the gate decision. Returns the resulting status.

    A second decision is refused rather than overwriting the first --
    "rejected in March, approved in April" is history a governance audit
    asks for, and an UPDATE would destroy it.
    """
    try:
        new_status = decide_opportunity(
            session,
            opportunity_id=opportunity_id,
            decision=OpportunityDecision(decision=payload.decision, rationale=payload.rationale),
            actor_id=principal.user_id,
            organization_id=principal.organization_id,
        )
    except OpportunityNotFoundError as exc:
        raise _missing(exc) from exc
    except OpportunityStateError as exc:
        raise _refuse(exc) from exc
    return {"status": new_status}


@router.post(
    "/{opportunity_id}/convert",
    status_code=status.HTTP_201_CREATED,
    tags=["opportunities"],
)
def post_conversion(
    opportunity_id: uuid.UUID,
    payload: ConversionCreate,
    # Creating the project is the act being authorized, so this is
    # project.create rather than an opportunity permission. Someone who
    # may decide but may not create projects hands over at this point,
    # which is the correct separation.
    principal: Principal = Depends(require_permission("project.create")),
    session: Session = Depends(get_db),
) -> dict[str, str]:
    """Turn an approved opportunity into a project, keeping the link.

    One transaction. An approved opportunity with no project, or a
    project pointing at an undecided opportunity, are both states the
    digital thread cannot explain.
    """
    try:
        project_id = convert_to_project(
            session,
            opportunity_id=opportunity_id,
            project_code=payload.project_code,
            name=payload.name,
            lead_user_id=payload.lead_user_id,
            actor_id=principal.user_id,
            organization_id=principal.organization_id,
            target_release_date=payload.target_release_date,
            confidentiality=payload.confidentiality,
        )
    except CrossTenantReferenceError as exc:
        # 400, not 403/404: the caller named a lead who is not a member of
        # this organization. Any status that distinguishes "not real" from
        # "not yours" leaks the existence of another tenant's user.
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except OpportunityNotFoundError as exc:
        raise _missing(exc) from exc
    except OpportunityStateError as exc:
        raise _refuse(exc) from exc
    return {"project_id": str(project_id)}
