"""Project, pipeline and requirement routes.

Every route carries BOTH a permission dependency and, where it touches a
project, a resource-scope dependency. They answer different questions —
"may this person ever do this" and "may they do it here" — and conflating
them is how F32 happened.

Domain errors are translated to HTTP here and nowhere else. The services
raise business exceptions (`TransitionNotPermittedError`,
`RequirementInvalidError`); turning those into status codes is a
transport concern, and a service that imported `HTTPException` could not
be called from the Celery worker.
"""

from __future__ import annotations

import datetime as dt
import uuid
from decimal import Decimal
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.security import Principal, get_db, require_permission, require_project_member
from app.core.tenancy import CrossTenantReferenceError
from app.domains.pipeline.service import (
    StageNotFoundError,
    StageTransitionError,
    advance_stage,
    project_pipeline,
    stage_history,
)
from app.domains.projects.dashboard import project_dashboard
from app.domains.projects.members import (
    MemberNotFoundError,
    ProjectLeadNotRemovableError,
    add_member,
    list_members,
    remove_member,
)
from app.domains.projects.planning import (
    MilestoneError,
    MilestoneInput,
    MilestoneNotFoundError,
    RiskDuplicateError,
    RiskInput,
    RiskInvalidError,
    RiskNotFoundError,
    create_milestone,
    create_risk,
    list_milestones,
    list_risks,
    set_milestone_status,
    update_risk,
)
from app.domains.requirements.service import (
    RequirementError,
    RequirementImmutableError,
    RequirementInput,
    RequirementInvalidError,
    approve_requirement,
    create_requirement,
    revise_requirement,
    verification_matrix,
)

router = APIRouter()

__all__ = ["router"]


# ---------------------------------------------------------------------------
# Schemas — one per operation, so server-owned fields are unreachable
# ---------------------------------------------------------------------------


class ProjectSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_code: str
    name: str
    product_family: str | None
    status: str
    priority: str
    current_stage: str | None
    confidentiality: str
    target_release_date: object | None = None
    # When this project was opened. A Pydantic model DROPS what it does not
    # declare, so projecting the column in SQL is only half the change —
    # without this line the query returns it and the response omits it.
    created_at: object | None = None


class ProjectCreate(BaseModel):
    project_code: str = Field(min_length=3, max_length=50)
    name: str = Field(min_length=1, max_length=200)
    product_family: str | None = None
    description: str | None = None
    technical_objective: str | None = None
    commercial_objective: str | None = None
    priority: str = Field(default="medium", pattern="^(low|medium|high|critical)$")
    # Members-only visibility. Chosen at creation because retro-fitting
    # confidentiality after people have already seen the project does not
    # un-see it.
    confidentiality: str = Field(default="normal", pattern="^(normal|restricted)$")


class StageAdvance(BaseModel):
    to_stage_code: str = Field(min_length=1, max_length=50)
    # Required by the service too. Declared here so the API contract shows
    # it rather than surfacing as a 500 from a domain exception.
    reason: str = Field(min_length=3, max_length=500)
    force: bool = False


class RequirementCreate(BaseModel):
    requirement_code: str = Field(min_length=3, max_length=50)
    name: str = Field(min_length=1, max_length=200)
    category: str = Field(default="technical")
    description: str | None = None
    target_value: Decimal | None = None
    minimum_value: Decimal | None = None
    maximum_value: Decimal | None = None
    canonical_unit: str | None = None
    warning_threshold: Decimal | None = None
    criticality: str = Field(default="major", pattern="^(critical|major|minor|informational)$")
    verification_method: str = Field(default="test")
    test_method_code: str | None = None
    source: str | None = None

    def to_input(self) -> RequirementInput:
        return RequirementInput(**self.model_dump())


class RequirementRevise(RequirementCreate):
    reason: str = Field(min_length=3, max_length=500)

    def to_input(self) -> RequirementInput:
        data = self.model_dump()
        data.pop("reason")
        return RequirementInput(**data)


# ---------------------------------------------------------------------------
# Projects
# ---------------------------------------------------------------------------

# The same 200 every other collection in this codebase uses (materials,
# suppliers, formulations, batches, tests, failures, messages). Kept
# identical on purpose: a second, different bound would be one more pair
# of literals nothing can check against each other.
COLLECTION_LIMIT = 200


@router.get("", response_model=list[ProjectSummary], tags=["projects"])
def list_projects(
    principal: Principal = Depends(require_permission("project.view")),
    session: Session = Depends(get_db),
) -> list[ProjectSummary]:
    """Projects the caller may see.

    No organization or confidentiality filter in the SQL: RLS applies
    both, and a restricted project the caller is not a member of simply
    does not appear. The application-side check is the resource-scope
    dependency on the detail routes.

    **Bounded.** This returned every visible row. Materials, suppliers,
    formulations, batches, tests, failures and messages all cap at 200 in
    their service functions; projects and opportunities were the two that
    did not, so a large tenant — or a caller repeating the request —
    could make the database, the API process and the response body grow
    without limit. Raised by Codex in the 2026-08-20 API security audit.

    The cap is a hard SQL `LIMIT` rather than a client-supplied page size,
    matching the convention already in use. Cursor pagination is the
    right long-term answer and is recorded in `TODO.md`; a bound that
    exists now is worth more than a design that does not.
    """
    rows = session.execute(
        text(
            """
            -- `created_at` is projected because the pipeline views show WHEN
            -- each step happened. The column has always existed; it was
            -- simply never returned, so a screen could say what stage a
            -- project was at and not when it got there.
            SELECT id, project_code, name, product_family, status, priority,
                   current_stage, confidentiality, target_release_date,
                   created_at
            FROM projects.projects
            ORDER BY
                CASE priority WHEN 'critical' THEN 1 WHEN 'high' THEN 2
                              WHEN 'medium' THEN 3 ELSE 4 END,
                project_code
            LIMIT :limit
            """
        ),
        {"limit": COLLECTION_LIMIT},
    ).mappings()
    _ = principal
    return [ProjectSummary(**r) for r in rows]


@router.post(
    "", response_model=ProjectSummary, status_code=status.HTTP_201_CREATED, tags=["projects"]
)
def create_project(
    payload: ProjectCreate,
    principal: Principal = Depends(require_permission("project.create")),
    session: Session = Depends(get_db),
) -> ProjectSummary:
    existing = session.execute(
        text("SELECT 1 FROM projects.projects WHERE project_code = :c"),
        {"c": payload.project_code},
    ).scalar_one_or_none()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"project code {payload.project_code} already exists",
        )

    row = (
        session.execute(
            text(
                """
            INSERT INTO projects.projects
                (organization_id, project_code, name, product_family, description,
                 technical_objective, commercial_objective, priority,
                 confidentiality, lead_user_id)
            VALUES (:org, :code, :name, :family, :description, :tech, :comm,
                    :priority, :confidentiality, :lead)
            -- 🔴 `created_at` HERE TOO, AND ITS ABSENCE WAS INVISIBLE.
            -- `ProjectSummary` DEFAULTS this field to None, so omitting it
            -- from RETURNING does not fail — the route answers 201 with
            -- `created_at: null`, and the grid renders "—" beside a project
            -- created one second earlier. A default and a missing column
            -- cancel each other out exactly where nothing can see it.
            RETURNING id, project_code, name, product_family, status, priority,
                      current_stage, confidentiality, target_release_date,
                      created_at
            """
            ),
            {
                "org": principal.organization_id,
                "code": payload.project_code,
                "name": payload.name,
                "family": payload.product_family,
                "description": payload.description,
                "tech": payload.technical_objective,
                "comm": payload.commercial_objective,
                "priority": payload.priority,
                "confidentiality": payload.confidentiality,
                "lead": principal.user_id,
            },
        )
        .mappings()
        .one()
    )

    # The creator becomes a member immediately. Without this, creating a
    # restricted project makes it invisible to its own creator on the
    # next request -- RLS is doing exactly what it should, and the result
    # looks like the save silently failed.
    session.execute(
        text(
            """
            INSERT INTO projects.project_members
                (organization_id, project_id, user_id, project_role)
            VALUES (:org, :pid, :uid, 'lead')
            """
        ),
        {"org": principal.organization_id, "pid": row["id"], "uid": principal.user_id},
    )

    return ProjectSummary(**row)


@router.get("/{project_id}", response_model=ProjectSummary, tags=["projects"])
def get_project(
    project_id: uuid.UUID,
    principal: Principal = Depends(require_project_member()),
    session: Session = Depends(get_db),
) -> ProjectSummary:
    row = (
        session.execute(
            text(
                """
            -- `created_at` is projected because the pipeline views show WHEN
            -- each step happened. The column has always existed; it was
            -- simply never returned, so a screen could say what stage a
            -- project was at and not when it got there.
            SELECT id, project_code, name, product_family, status, priority,
                   current_stage, confidentiality, target_release_date,
                   created_at
            FROM projects.projects WHERE id = :pid
            """
            ),
            {"pid": project_id},
        )
        .mappings()
        .one_or_none()
    )
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="not found")
    _ = principal
    return ProjectSummary(**row)


@router.get("/{project_id}/dashboard", tags=["projects"])
def get_dashboard(
    project_id: uuid.UUID,
    principal: Principal = Depends(require_project_member()),
    session: Session = Depends(get_db),
) -> dict[str, Any]:
    """The project workspace, shaped to CLAUDE.md §11's five questions.

    Returns one key per question rather than whatever the first screen
    needed, so a missing answer shows up as a missing key instead of as a
    panel somebody forgot. Every count ships with the records behind it --
    a KPI tile that cannot say *which* four are overdue is a number the
    user has to re-derive by hand.
    """
    data = project_dashboard(
        session, project_id=project_id, organization_id=principal.organization_id
    )
    if data["context"] is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="not found")
    return data


# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------


@router.get("/{project_id}/pipeline", tags=["pipeline"])
def get_pipeline(
    project_id: uuid.UUID,
    principal: Principal = Depends(require_project_member()),
    session: Session = Depends(get_db),
) -> dict[str, Any]:
    return {
        "project_id": project_id,
        "stages": project_pipeline(session, project_id, principal.organization_id),
    }


@router.get("/{project_id}/pipeline/history", tags=["pipeline"])
def get_pipeline_history(
    project_id: uuid.UUID,
    principal: Principal = Depends(require_project_member()),
    session: Session = Depends(get_db),
) -> dict[str, Any]:
    """The append-only transition log.

    Includes every backwards move, which is the part a `current_stage`
    column cannot express at all.
    """
    _ = principal
    return {"project_id": project_id, "history": stage_history(session, project_id)}


@router.post("/{project_id}/pipeline/advance", tags=["pipeline"])
def post_stage_advance(
    project_id: uuid.UUID,
    payload: StageAdvance,
    principal: Principal = Depends(require_permission("project.advance_stage")),
    _member: Principal = Depends(require_project_member()),
    session: Session = Depends(get_db),
) -> dict[str, Any]:
    """Advance the pipeline.

    Both dependencies are required: holding `project.advance_stage` does
    not grant advancing a project you are not a member of.
    """
    try:
        result = advance_stage(
            session,
            project_id=project_id,
            to_stage_code=payload.to_stage_code,
            actor_id=principal.user_id,
            organization_id=principal.organization_id,
            reason=payload.reason,
            force=payload.force,
        )
    except StageNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc
    except StageTransitionError as exc:
        # 409, not 400: the request is well-formed and the refusal is a
        # state conflict. A client can retry it after the stage changes.
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc

    return {
        "project_stage_id": result.project_stage_id,
        "from_stage": result.from_stage_code,
        "to_stage": result.to_stage_code,
        "is_rework": result.is_rework,
    }


# ---------------------------------------------------------------------------
# Requirements
# ---------------------------------------------------------------------------


@router.get("/{project_id}/requirements/matrix", tags=["requirements"])
def get_verification_matrix(
    project_id: uuid.UUID,
    principal: Principal = Depends(require_project_member()),
    session: Session = Depends(get_db),
) -> dict[str, Any]:
    return verification_matrix(
        session, project_id=project_id, organization_id=principal.organization_id
    )


@router.post(
    "/{project_id}/requirements", status_code=status.HTTP_201_CREATED, tags=["requirements"]
)
def post_requirement(
    project_id: uuid.UUID,
    payload: RequirementCreate,
    principal: Principal = Depends(require_permission("requirement.create")),
    _member: Principal = Depends(require_project_member()),
    session: Session = Depends(get_db),
) -> dict[str, Any]:
    try:
        requirement_id = create_requirement(
            session,
            project_id=project_id,
            organization_id=principal.organization_id,
            actor_id=principal.user_id,
            spec=payload.to_input(),
        )
    except RequirementInvalidError as exc:
        # 422: the payload is syntactically valid and semantically wrong.
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from exc

    return {"requirement_id": requirement_id}


@router.post(
    "/{project_id}/requirements/{requirement_id}/approve",
    status_code=status.HTTP_204_NO_CONTENT,
    tags=["requirements"],
)
def post_requirement_approval(
    project_id: uuid.UUID,
    requirement_id: uuid.UUID,
    principal: Principal = Depends(require_permission("requirement.approve")),
    _member: Principal = Depends(require_project_member()),
    session: Session = Depends(get_db),
) -> None:
    try:
        approve_requirement(
            session,
            requirement_id=requirement_id,
            organization_id=principal.organization_id,
            actor_id=principal.user_id,
        )
    except RequirementImmutableError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
    except RequirementError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc


@router.post(
    "/{project_id}/requirements/{requirement_id}/revise",
    status_code=status.HTTP_201_CREATED,
    tags=["requirements"],
)
def post_requirement_revision(
    project_id: uuid.UUID,
    requirement_id: uuid.UUID,
    payload: RequirementRevise,
    principal: Principal = Depends(require_permission("requirement.create")),
    _member: Principal = Depends(require_project_member()),
    session: Session = Depends(get_db),
) -> dict[str, Any]:
    """Supersede a requirement with a new revision.

    Deliberately POST /revise rather than PUT /requirements/{id}. A PUT
    implies replacing the resource in place, which is exactly what must
    not happen — the old revision remains as the criterion existing tests
    were measured against.
    """
    try:
        new_id = revise_requirement(
            session,
            requirement_id=requirement_id,
            organization_id=principal.organization_id,
            actor_id=principal.user_id,
            spec=payload.to_input(),
            reason=payload.reason,
        )
    except RequirementInvalidError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from exc
    except RequirementError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc

    return {"requirement_id": new_id}


# ---------------------------------------------------------------------------
# Milestones and risks
# ---------------------------------------------------------------------------
# Both tables, their indexes, their RLS policies and their dashboard
# counters shipped in Slice 2. Neither had a writer, so both counters were
# structurally incapable of showing anything but zero. These are the
# missing halves.


class MilestoneCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    planned_date: dt.date
    description: str | None = None


class MilestoneStatus(BaseModel):
    status: str = Field(pattern="^(planned|in_progress|met|missed|cancelled)$")
    # Optional: the service records today when a milestone is closed
    # without one. Supplying it is for back-dating a milestone that was
    # actually met last week.
    actual_date: dt.date | None = None
    reason: str = Field(min_length=3, max_length=500)


class RiskCreate(BaseModel):
    risk_code: str = Field(min_length=2, max_length=50)
    title: str = Field(min_length=1, max_length=200)
    probability: str = Field(pattern="^(low|medium|high)$")
    impact: str = Field(pattern="^(low|medium|high)$")
    category: str = Field(
        default="technical",
        pattern="^(technical|material|process|schedule|commercial|regulatory|supply)$",
    )
    description: str | None = None
    mitigation: str | None = None
    owner_user_id: uuid.UUID | None = None


class RiskUpdate(BaseModel):
    """Every field optional; None means "leave unchanged".

    A PATCH that silently blanked the mitigation because the client did
    not resend it is how a risk stops being tracked without anyone
    deciding that.
    """

    status: str | None = Field(default=None, pattern="^(open|mitigating|closed|accepted|realised)$")
    mitigation: str | None = None
    probability: str | None = Field(default=None, pattern="^(low|medium|high)$")
    impact: str | None = Field(default=None, pattern="^(low|medium|high)$")
    owner_user_id: uuid.UUID | None = None
    reason: str = Field(min_length=3, max_length=500)


@router.get("/{project_id}/milestones", tags=["projects"])
def get_milestones(
    project_id: uuid.UUID,
    principal: Principal = Depends(require_project_member()),
    session: Session = Depends(get_db),
) -> dict[str, Any]:
    return {
        "project_id": project_id,
        "milestones": list_milestones(
            session, project_id=project_id, organization_id=principal.organization_id
        ),
    }


@router.post("/{project_id}/milestones", status_code=status.HTTP_201_CREATED, tags=["projects"])
def post_milestone(
    project_id: uuid.UUID,
    payload: MilestoneCreate,
    principal: Principal = Depends(require_permission("milestone.manage")),
    _member: Principal = Depends(require_project_member()),
    session: Session = Depends(get_db),
) -> dict[str, Any]:
    milestone_id = create_milestone(
        session,
        project_id=project_id,
        organization_id=principal.organization_id,
        actor_id=principal.user_id,
        spec=MilestoneInput(
            name=payload.name,
            planned_date=payload.planned_date,
            description=payload.description,
        ),
    )
    return {"milestone_id": milestone_id}


@router.patch("/{project_id}/milestones/{milestone_id}/status", tags=["projects"])
def patch_milestone_status(
    project_id: uuid.UUID,
    milestone_id: uuid.UUID,
    payload: MilestoneStatus,
    principal: Principal = Depends(require_permission("milestone.manage")),
    _member: Principal = Depends(require_project_member()),
    session: Session = Depends(get_db),
) -> dict[str, Any]:
    try:
        return set_milestone_status(
            session,
            milestone_id=milestone_id,
            # The project from the PATH, which is what
            # require_project_member() authorised. Without it the service
            # would accept a milestone belonging to a different project in
            # the same organization.
            project_id=project_id,
            organization_id=principal.organization_id,
            actor_id=principal.user_id,
            status=payload.status,
            actual_date=payload.actual_date,
            reason=payload.reason,
        )
    except MilestoneNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc
    except MilestoneError as exc:
        # Well-formed request, incoherent combination -- an in-flight
        # status carrying a completion date.
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from exc


@router.get("/{project_id}/risks", tags=["projects"])
def get_risks(
    project_id: uuid.UUID,
    principal: Principal = Depends(require_project_member()),
    session: Session = Depends(get_db),
) -> dict[str, Any]:
    return {
        "project_id": project_id,
        "risks": list_risks(
            session, project_id=project_id, organization_id=principal.organization_id
        ),
    }


@router.post("/{project_id}/risks", status_code=status.HTTP_201_CREATED, tags=["projects"])
def post_risk(
    project_id: uuid.UUID,
    payload: RiskCreate,
    principal: Principal = Depends(require_permission("risk.create")),
    _member: Principal = Depends(require_project_member()),
    session: Session = Depends(get_db),
) -> dict[str, Any]:
    try:
        risk_id = create_risk(
            session,
            project_id=project_id,
            organization_id=principal.organization_id,
            actor_id=principal.user_id,
            spec=RiskInput(
                risk_code=payload.risk_code,
                title=payload.title,
                probability=payload.probability,
                impact=payload.impact,
                category=payload.category,
                description=payload.description,
                mitigation=payload.mitigation,
                owner_user_id=payload.owner_user_id,
            ),
        )
    except RiskDuplicateError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
    except CrossTenantReferenceError as exc:
        # Explicitly caught. This is NOT a subclass of RiskError, and the
        # last time that was overlooked the exception escaped the handler
        # and surfaced as a 500 -- a fix introducing its own defect.
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from exc

    return {"risk_id": risk_id}


@router.patch("/{project_id}/risks/{risk_id}", tags=["projects"])
def patch_risk(
    project_id: uuid.UUID,
    risk_id: uuid.UUID,
    payload: RiskUpdate,
    principal: Principal = Depends(require_permission("risk.manage")),
    _member: Principal = Depends(require_project_member()),
    session: Session = Depends(get_db),
) -> dict[str, Any]:
    try:
        return update_risk(
            session,
            risk_id=risk_id,
            project_id=project_id,
            organization_id=principal.organization_id,
            actor_id=principal.user_id,
            reason=payload.reason,
            status=payload.status,
            mitigation=payload.mitigation,
            probability=payload.probability,
            impact=payload.impact,
            owner_user_id=payload.owner_user_id,
        )
    except RiskNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc
    except RiskInvalidError as exc:
        # A database CHECK that reaches the client as a 500 is a defect
        # even when the refusal itself is correct.
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from exc
    except CrossTenantReferenceError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from exc


# ---------------------------------------------------------------------------
# Project members
# ---------------------------------------------------------------------------
# `project.assign_member` was seeded in migration 002 and granted to the
# Lead. No route used it, so a project could never gain a second member.
# Membership is the RLS predicate for every project-scoped table, which
# makes this the difference between a colleague seeing the project's data
# and not.


class MemberAdd(BaseModel):
    user_id: uuid.UUID
    project_role: str = Field(pattern="^(lead|chemist|engineer|technician|qa|director|observer)$")


class MemberRemove(BaseModel):
    reason: str = Field(min_length=3, max_length=500)


@router.get("/{project_id}/members", tags=["projects"])
def get_members(
    project_id: uuid.UUID,
    principal: Principal = Depends(require_project_member()),
    session: Session = Depends(get_db),
) -> dict[str, Any]:
    return {
        "project_id": project_id,
        "members": list_members(
            session, project_id=project_id, organization_id=principal.organization_id
        ),
    }


@router.post("/{project_id}/members", status_code=status.HTTP_201_CREATED, tags=["projects"])
def post_member(
    project_id: uuid.UUID,
    payload: MemberAdd,
    principal: Principal = Depends(require_permission("project.assign_member")),
    _member: Principal = Depends(require_project_member()),
    session: Session = Depends(get_db),
) -> dict[str, Any]:
    try:
        member_id = add_member(
            session,
            project_id=project_id,
            organization_id=principal.organization_id,
            actor_id=principal.user_id,
            user_id=payload.user_id,
            project_role=payload.project_role,
        )
    except CrossTenantReferenceError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from exc

    return {"member_id": member_id}


@router.post(
    "/{project_id}/members/{user_id}/remove",
    status_code=status.HTTP_204_NO_CONTENT,
    tags=["projects"],
)
def post_member_removal(
    project_id: uuid.UUID,
    user_id: uuid.UUID,
    payload: MemberRemove,
    principal: Principal = Depends(require_permission("project.assign_member")),
    _member: Principal = Depends(require_project_member()),
    session: Session = Depends(get_db),
) -> None:
    """POST /remove rather than DELETE /members/{user_id}.

    Removal takes a mandatory reason, and a DELETE with a required body is
    both awkward for clients and, per RFC 9110, of undefined semantics --
    several proxies and HTTP clients drop the body. The same reasoning
    already applies to requirement revision, which is POST /revise rather
    than PUT.

    It is also not a deletion: the membership row survives as `inactive`,
    so the record of who once had access remains.
    """
    try:
        remove_member(
            session,
            project_id=project_id,
            organization_id=principal.organization_id,
            actor_id=principal.user_id,
            user_id=user_id,
            reason=payload.reason,
        )
    except ProjectLeadNotRemovableError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
    except MemberNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc
