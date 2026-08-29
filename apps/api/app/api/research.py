"""The Research Center, over HTTP.

🔴 EVERY WRITE ROUTE HERE HAS A CONTROL SOMEBODY CAN PRESS, IN THIS COMMIT.

§10's phase rule, and the defect this project has counted twenty-five of: a
route with no caller, a permission with no enforcement point and a table with no
writer are one defect wearing three hats. `tests/e2e/shell/research.spec.ts`
presses each of these from a browser, and
`tests/auth/test_research_routes.py::test_every_write_route_names_a_write_permission`
parses this file so a route added later cannot quietly skip the gate.

🔴 ACCEPTING A PROPOSAL REQUIRES THE FORMULA PERMISSIONS TOO.

`POST /proposals/{id}/accept` produces a formula version through
`formulations.revise_version` — the same service `/formulations/.../revise`
calls, which is gated on `formula.clone` AND `formula.modify_draft`. If this
route required only `experiment.accept`, it would be a second door to a
controlled act with a weaker lock, which is exactly the shape of the
authorization bypass found on 2026-08-26 (I104). All three are required
together.

🔴 A FINDING'S APPROVAL STATUS IS READ FROM THE ROUTE, NOT FROM A COLUMN.

There is no "approve finding" endpoint here, and that is deliberate. Approval
happens in the one approval engine, through `/approvals`, where the queue,
the segregation-of-duties rule and the decision record already live. A second
approve button would be a second notion of "signed off" — `CLAUDE.md` §12
forbids one, and Phase 2 shipped a table that claimed a status nothing
maintained before Codex measured it.
"""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.embedding import EmbeddingUnavailableError, build_embedder
from app.core.security import Principal, get_db, require_permission
from app.core.tenancy import CrossTenantReferenceError
from app.domains.formulations.service import FormulationError
from app.domains.research.service import (
    EvidenceInput,
    FindingInput,
    InvestigationInput,
    ProposalInput,
    ResearchError,
    ResearchNotFoundError,
    ResearchStateError,
    SourceInput,
    accept_experiment_proposal,
    close_investigation,
    decide_hypothesis,
    finding_approval_status,
    list_evidence,
    list_findings,
    list_hypotheses,
    list_investigations,
    list_knowledge_gaps,
    list_proposals,
    list_questions,
    list_sources,
    open_investigation,
    promote_finding,
    propose_experiment,
    record_evidence,
    record_finding,
    record_hypothesis,
    record_knowledge_gap,
    record_question,
    record_source,
    reject_experiment_proposal,
    resolve_knowledge_gap,
    settle_question,
    submit_finding,
)

router = APIRouter()

# The vocabularies, in one place each, so a route and its client cannot drift
# into two spellings of the same enum.
SOURCE_KINDS = (
    "document | manual_observation | laboratory | literature | patent | inference | model"
)
GRADES = "A | B | C | D | X"
CONFIDENCES = "high | moderate | low | unknown"


class InvestigationCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=300)
    research_question: str = Field(..., min_length=1)
    project_id: uuid.UUID | None = None
    search_strategy: str | None = None
    formula_version_id: uuid.UUID | None = None
    material_id: uuid.UUID | None = None
    test_id: uuid.UUID | None = None
    failure_id: uuid.UUID | None = None
    owner_user_id: uuid.UUID | None = None


class QuestionCreate(BaseModel):
    question: str = Field(..., min_length=1)


class QuestionSettle(BaseModel):
    status: str = Field(..., description="answered | unanswerable")


class SourceCreate(BaseModel):
    source_kind: str = Field(..., description=SOURCE_KINDS)
    evidence_grade: str = Field(..., description=GRADES)
    title: str = Field(..., min_length=1, max_length=300)
    source_locator: str | None = None
    document_id: uuid.UUID | None = None


class EvidenceCreate(BaseModel):
    summary: str = Field(..., min_length=1)
    stance: str = Field(default="supports", description="supports | related | contradicts")
    question_id: uuid.UUID | None = None
    source_id: uuid.UUID | None = None
    formula_version_id: uuid.UUID | None = None
    test_id: uuid.UUID | None = None
    failure_id: uuid.UUID | None = None


class FindingCreate(BaseModel):
    subject: str = Field(..., min_length=1, max_length=300)
    statement: str = Field(..., min_length=1)
    applicability: str = Field(..., min_length=1)
    confidence: str = Field(..., description=CONFIDENCES)
    limitations: str | None = None


class HypothesisCreate(BaseModel):
    statement: str = Field(..., min_length=1)
    rationale: str | None = None
    finding_id: uuid.UUID | None = None


class HypothesisDecide(BaseModel):
    status: str = Field(..., description="supported | refuted | withdrawn")


class GapCreate(BaseModel):
    description: str = Field(..., min_length=1)
    impact: str = Field(default="moderate", description="high | moderate | low")
    question_id: uuid.UUID | None = None


class ProposalCreate(BaseModel):
    objective: str = Field(..., min_length=1)
    basis: str = Field(..., min_length=1)
    variables: str = Field(..., min_length=1)
    expected_direction: str = Field(..., min_length=1)
    required_tests: str = Field(..., min_length=1)
    confidence: str = Field(..., description=CONFIDENCES)
    controlled_variables: str | None = None
    risks: str | None = None
    hypothesis_id: uuid.UUID | None = None


class ProposalAccept(BaseModel):
    version_id: uuid.UUID = Field(..., description="The formula version to revise.")
    change_reason: str = Field(..., min_length=1)
    technical_hypothesis: str = Field(..., min_length=1)
    decision_note: str | None = None


class ProposalReject(BaseModel):
    decision_note: str = Field(..., min_length=1)


def _refuse(exc: ResearchError) -> HTTPException:
    if isinstance(exc, ResearchNotFoundError):
        return HTTPException(status.HTTP_404_NOT_FOUND, str(exc))
    if isinstance(exc, ResearchStateError):
        return HTTPException(status.HTTP_409_CONFLICT, str(exc))
    return HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc))


# ---------------------------------------------------------------------------
# Workspaces
# ---------------------------------------------------------------------------


@router.get("", summary="Research workspaces this caller can reach")
def get_investigations(
    principal: Principal = Depends(require_permission("research.view")),
    session: Session = Depends(get_db),
    investigation_status: str | None = Query(default=None, alias="status"),
    limit: int = Query(default=200, ge=1, le=500),
) -> list[dict[str, Any]]:
    return list_investigations(
        session,
        organization_id=principal.organization_id,
        status=investigation_status,
        limit=limit,
    )


@router.post("", status_code=status.HTTP_201_CREATED, summary="Open a research workspace")
def post_investigation(
    payload: InvestigationCreate,
    principal: Principal = Depends(require_permission("research.create")),
    session: Session = Depends(get_db),
) -> dict[str, Any]:
    try:
        result = open_investigation(
            session,
            organization_id=principal.organization_id,
            actor_id=principal.user_id,
            spec=InvestigationInput(
                title=payload.title,
                research_question=payload.research_question,
                project_id=payload.project_id,
                search_strategy=payload.search_strategy,
                formula_version_id=payload.formula_version_id,
                material_id=payload.material_id,
                test_id=payload.test_id,
                failure_id=payload.failure_id,
                owner_user_id=payload.owner_user_id,
            ),
        )
    except ResearchError as exc:
        raise _refuse(exc) from exc
    except CrossTenantReferenceError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc
    session.commit()
    return result


@router.post("/{investigation_id}/close", summary="Close a research workspace")
def post_close_investigation(
    investigation_id: uuid.UUID,
    principal: Principal = Depends(require_permission("research.create")),
    session: Session = Depends(get_db),
) -> dict[str, Any]:
    """Closing is not deleting. §5 forbids removing investigation history."""
    try:
        result = close_investigation(
            session,
            investigation_id=investigation_id,
            organization_id=principal.organization_id,
            actor_id=principal.user_id,
        )
    except ResearchError as exc:
        raise _refuse(exc) from exc
    session.commit()
    return result


# ---------------------------------------------------------------------------
# Questions, sources, evidence
# ---------------------------------------------------------------------------


@router.get("/{investigation_id}/questions", summary="Questions in a workspace")
def get_questions(
    investigation_id: uuid.UUID,
    principal: Principal = Depends(require_permission("research.view")),
    session: Session = Depends(get_db),
) -> list[dict[str, Any]]:
    try:
        return list_questions(
            session,
            investigation_id=investigation_id,
            organization_id=principal.organization_id,
        )
    except ResearchError as exc:
        raise _refuse(exc) from exc


@router.post(
    "/{investigation_id}/questions",
    status_code=status.HTTP_201_CREATED,
    summary="Add a research question",
)
def post_question(
    investigation_id: uuid.UUID,
    payload: QuestionCreate,
    principal: Principal = Depends(require_permission("research.create")),
    session: Session = Depends(get_db),
) -> dict[str, Any]:
    try:
        result = record_question(
            session,
            investigation_id=investigation_id,
            organization_id=principal.organization_id,
            actor_id=principal.user_id,
            question=payload.question,
        )
    except ResearchError as exc:
        raise _refuse(exc) from exc
    session.commit()
    return result


@router.post("/questions/{question_id}/settle", summary="Answer or close a question")
def post_settle_question(
    question_id: uuid.UUID,
    payload: QuestionSettle,
    principal: Principal = Depends(require_permission("research.create")),
    session: Session = Depends(get_db),
) -> dict[str, Any]:
    try:
        result = settle_question(
            session,
            question_id=question_id,
            organization_id=principal.organization_id,
            actor_id=principal.user_id,
            status=payload.status,
        )
    except ResearchError as exc:
        raise _refuse(exc) from exc
    session.commit()
    return result


@router.get("/{investigation_id}/sources", summary="Graded sources on file")
def get_sources(
    investigation_id: uuid.UUID,
    principal: Principal = Depends(require_permission("research.view")),
    session: Session = Depends(get_db),
) -> list[dict[str, Any]]:
    try:
        return list_sources(
            session,
            investigation_id=investigation_id,
            organization_id=principal.organization_id,
        )
    except ResearchError as exc:
        raise _refuse(exc) from exc


@router.post(
    "/{investigation_id}/sources",
    status_code=status.HTTP_201_CREATED,
    summary="Register and grade a source",
)
def post_source(
    investigation_id: uuid.UUID,
    payload: SourceCreate,
    principal: Principal = Depends(require_permission("research.create")),
    session: Session = Depends(get_db),
) -> dict[str, Any]:
    """§6's A-X ranking. The grade describes the SOURCE, not the conclusion."""
    try:
        result = record_source(
            session,
            investigation_id=investigation_id,
            organization_id=principal.organization_id,
            actor_id=principal.user_id,
            spec=SourceInput(
                source_kind=payload.source_kind,
                evidence_grade=payload.evidence_grade,
                title=payload.title,
                source_locator=payload.source_locator,
                document_id=payload.document_id,
            ),
        )
    except ResearchError as exc:
        raise _refuse(exc) from exc
    except CrossTenantReferenceError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc
    session.commit()
    return result


@router.get("/{investigation_id}/evidence", summary="Evidence cards")
def get_evidence(
    investigation_id: uuid.UUID,
    principal: Principal = Depends(require_permission("research.view")),
    session: Session = Depends(get_db),
) -> list[dict[str, Any]]:
    try:
        return list_evidence(
            session,
            investigation_id=investigation_id,
            organization_id=principal.organization_id,
        )
    except ResearchError as exc:
        raise _refuse(exc) from exc


@router.post(
    "/{investigation_id}/evidence",
    status_code=status.HTTP_201_CREATED,
    summary="Record an evidence card",
)
def post_evidence(
    investigation_id: uuid.UUID,
    payload: EvidenceCreate,
    principal: Principal = Depends(require_permission("research.create")),
    session: Session = Depends(get_db),
) -> dict[str, Any]:
    """§28. `stance` includes `contradicts`, which is the honest case."""
    try:
        result = record_evidence(
            session,
            investigation_id=investigation_id,
            organization_id=principal.organization_id,
            actor_id=principal.user_id,
            spec=EvidenceInput(
                summary=payload.summary,
                stance=payload.stance,
                question_id=payload.question_id,
                source_id=payload.source_id,
                formula_version_id=payload.formula_version_id,
                test_id=payload.test_id,
                failure_id=payload.failure_id,
            ),
        )
    except ResearchError as exc:
        raise _refuse(exc) from exc
    except CrossTenantReferenceError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc
    session.commit()
    return result


# ---------------------------------------------------------------------------
# Hypotheses and knowledge gaps
# ---------------------------------------------------------------------------


@router.post(
    "/{investigation_id}/hypotheses",
    status_code=status.HTTP_201_CREATED,
    summary="State a hypothesis",
)
def post_hypothesis(
    investigation_id: uuid.UUID,
    payload: HypothesisCreate,
    principal: Principal = Depends(require_permission("research.create")),
    session: Session = Depends(get_db),
) -> dict[str, Any]:
    try:
        result = record_hypothesis(
            session,
            investigation_id=investigation_id,
            organization_id=principal.organization_id,
            actor_id=principal.user_id,
            statement=payload.statement,
            rationale=payload.rationale,
            finding_id=payload.finding_id,
        )
    except ResearchError as exc:
        raise _refuse(exc) from exc
    session.commit()
    return result


@router.get("/{investigation_id}/hypotheses", summary="Hypotheses in a workspace")
def get_hypotheses(
    investigation_id: uuid.UUID,
    principal: Principal = Depends(require_permission("research.view")),
    session: Session = Depends(get_db),
) -> list[dict[str, Any]]:
    """The reader that `record_hypothesis` needed and did not have."""
    try:
        return list_hypotheses(
            session,
            investigation_id=investigation_id,
            organization_id=principal.organization_id,
        )
    except ResearchError as exc:
        raise _refuse(exc) from exc


@router.post("/hypotheses/{hypothesis_id}/decide", summary="Settle a hypothesis")
def post_decide_hypothesis(
    hypothesis_id: uuid.UUID,
    payload: HypothesisDecide,
    principal: Principal = Depends(require_permission("research.create")),
    session: Session = Depends(get_db),
) -> dict[str, Any]:
    try:
        result = decide_hypothesis(
            session,
            hypothesis_id=hypothesis_id,
            organization_id=principal.organization_id,
            actor_id=principal.user_id,
            status=payload.status,
        )
    except ResearchError as exc:
        raise _refuse(exc) from exc
    session.commit()
    return result


@router.get("/{investigation_id}/gaps", summary="Knowledge gaps")
def get_gaps(
    investigation_id: uuid.UUID,
    principal: Principal = Depends(require_permission("research.view")),
    session: Session = Depends(get_db),
) -> list[dict[str, Any]]:
    try:
        return list_knowledge_gaps(
            session,
            investigation_id=investigation_id,
            organization_id=principal.organization_id,
        )
    except ResearchError as exc:
        raise _refuse(exc) from exc


@router.post(
    "/{investigation_id}/gaps",
    status_code=status.HTTP_201_CREATED,
    summary="Record a knowledge gap",
)
def post_gap(
    investigation_id: uuid.UUID,
    payload: GapCreate,
    principal: Principal = Depends(require_permission("research.create")),
    session: Session = Depends(get_db),
) -> dict[str, Any]:
    try:
        result = record_knowledge_gap(
            session,
            investigation_id=investigation_id,
            organization_id=principal.organization_id,
            actor_id=principal.user_id,
            description=payload.description,
            impact=payload.impact,
            question_id=payload.question_id,
        )
    except ResearchError as exc:
        raise _refuse(exc) from exc
    session.commit()
    return result


@router.post("/gaps/{gap_id}/resolve", summary="Close a knowledge gap")
def post_resolve_gap(
    gap_id: uuid.UUID,
    principal: Principal = Depends(require_permission("research.create")),
    session: Session = Depends(get_db),
) -> dict[str, Any]:
    try:
        result = resolve_knowledge_gap(
            session,
            gap_id=gap_id,
            organization_id=principal.organization_id,
            actor_id=principal.user_id,
        )
    except ResearchError as exc:
        raise _refuse(exc) from exc
    session.commit()
    return result


# ---------------------------------------------------------------------------
# The findings register
# ---------------------------------------------------------------------------


@router.get("/findings", summary="The research findings register")
def get_findings(
    principal: Principal = Depends(require_permission("research.view")),
    session: Session = Depends(get_db),
    investigation_id: uuid.UUID | None = Query(default=None),
    finding_status: str | None = Query(default=None, alias="status"),
    limit: int = Query(default=200, ge=1, le=500),
) -> list[dict[str, Any]]:
    """`approval_status` on each row is the ROUTE's status, not a stored copy."""
    return list_findings(
        session,
        organization_id=principal.organization_id,
        investigation_id=investigation_id,
        status=finding_status,
        limit=limit,
    )


@router.post(
    "/{investigation_id}/findings",
    status_code=status.HTTP_201_CREATED,
    summary="Draft a research finding",
)
def post_finding(
    investigation_id: uuid.UUID,
    payload: FindingCreate,
    principal: Principal = Depends(require_permission("research.create")),
    session: Session = Depends(get_db),
) -> dict[str, Any]:
    try:
        result = record_finding(
            session,
            investigation_id=investigation_id,
            organization_id=principal.organization_id,
            actor_id=principal.user_id,
            spec=FindingInput(
                subject=payload.subject,
                statement=payload.statement,
                applicability=payload.applicability,
                confidence=payload.confidence,
                limitations=payload.limitations,
            ),
        )
    except ResearchError as exc:
        raise _refuse(exc) from exc
    session.commit()
    return result


@router.post("/findings/{finding_id}/submit", summary="Submit a finding for approval")
def post_submit_finding(
    finding_id: uuid.UUID,
    principal: Principal = Depends(require_permission("research.create")),
    session: Session = Depends(get_db),
) -> dict[str, Any]:
    """Opens a route in the ONE approval engine; it is decided in `/approvals`.

    Gated on `research.create` — submitting your own work for review is part of
    doing the work. `research.review` and `research.approve` gate the two steps
    of the route itself, which is where the decision actually happens.
    """
    try:
        result = submit_finding(
            session,
            finding_id=finding_id,
            organization_id=principal.organization_id,
            actor_id=principal.user_id,
        )
    except ResearchError as exc:
        raise _refuse(exc) from exc
    session.commit()
    return result


@router.get("/findings/{finding_id}/approval", summary="Where a finding's approval stands")
def get_finding_approval(
    finding_id: uuid.UUID,
    principal: Principal = Depends(require_permission("research.view")),
    session: Session = Depends(get_db),
) -> dict[str, Any] | None:
    return finding_approval_status(
        session, finding_id=finding_id, organization_id=principal.organization_id
    )


@router.post(
    "/findings/{finding_id}/promote",
    summary="Promote an approved finding into the Knowledge Library",
)
def post_promote_finding(
    finding_id: uuid.UUID,
    principal: Principal = Depends(require_permission("knowledge.promote")),
    session: Session = Depends(get_db),
) -> dict[str, Any]:
    """🔴 `knowledge.promote`'s FIRST ENFORCEMENT POINT.

    Seeded in migration 002, held by three roles, and read by nothing in the
    product until this route. One of the 29 orphaned permissions; this is the
    28th remaining.

    ⚠️ `build_embedder()` IS CALLED HERE, NOT DECLARED AS A DEPENDENCY. It takes
    a keyword argument with a default, so `Depends(build_embedder)` would make
    FastAPI publish `prefer_neural` as a QUERY PARAMETER on this route --
    letting a caller choose the embedder over HTTP. `/knowledge` calls it
    inline for the same reason.
    """
    embedder = build_embedder()
    try:
        result = promote_finding(
            session,
            finding_id=finding_id,
            organization_id=principal.organization_id,
            actor_id=principal.user_id,
            embedder=embedder,
        )
    except ResearchError as exc:
        raise _refuse(exc) from exc
    except ValueError as exc:
        # `ingest_document` raises this for a body with no text and for the
        # chunk cap. Neither is reachable from a finding today -- statement and
        # applicability are NOT NULL and short -- but the handler is here
        # because the service can raise it, not because a test drove it.
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from exc
    except EmbeddingUnavailableError as exc:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            f"the finding could not be embedded: {exc}",
        ) from exc
    session.commit()
    return result


# ---------------------------------------------------------------------------
# Experiment proposals
# ---------------------------------------------------------------------------


@router.get("/proposals", summary="Experiment proposals this caller can reach")
def get_proposals(
    principal: Principal = Depends(require_permission("research.view")),
    session: Session = Depends(get_db),
    investigation_id: uuid.UUID | None = Query(default=None),
    proposal_status: str | None = Query(default=None, alias="status"),
    limit: int = Query(default=200, ge=1, le=500),
) -> list[dict[str, Any]]:
    return list_proposals(
        session,
        organization_id=principal.organization_id,
        investigation_id=investigation_id,
        status=proposal_status,
        limit=limit,
    )


@router.post(
    "/{investigation_id}/proposals",
    status_code=status.HTTP_201_CREATED,
    summary="Propose an experiment",
)
def post_proposal(
    investigation_id: uuid.UUID,
    payload: ProposalCreate,
    principal: Principal = Depends(require_permission("experiment.propose")),
    session: Session = Depends(get_db),
) -> dict[str, Any]:
    """§20's structured proposal. It changes nothing until somebody accepts it."""
    try:
        result = propose_experiment(
            session,
            investigation_id=investigation_id,
            organization_id=principal.organization_id,
            actor_id=principal.user_id,
            spec=ProposalInput(
                objective=payload.objective,
                basis=payload.basis,
                variables=payload.variables,
                expected_direction=payload.expected_direction,
                required_tests=payload.required_tests,
                confidence=payload.confidence,
                controlled_variables=payload.controlled_variables,
                risks=payload.risks,
                hypothesis_id=payload.hypothesis_id,
            ),
        )
    except ResearchError as exc:
        raise _refuse(exc) from exc
    session.commit()
    return result


@router.post(
    "/proposals/{proposal_id}/accept",
    summary="Accept a proposal, revising the named formula version",
)
def post_accept_proposal(
    proposal_id: uuid.UUID,
    payload: ProposalAccept,
    principal: Principal = Depends(
        require_permission(
            "experiment.accept", "formula.clone", "formula.modify_draft", require_all=True
        )
    ),
    session: Session = Depends(get_db),
) -> dict[str, Any]:
    """🔴 THREE PERMISSIONS, ALL OF THEM, AND THAT IS THE POINT.

    This produces a formula version through the same service
    `/formulations/versions/{id}/revise` calls, which requires `formula.clone`
    and `formula.modify_draft`. Requiring only `experiment.accept` here would
    make this a second door to a controlled act with a weaker lock. §20 gives
    the DECISION to the chemist; it does not give them a way round the formula
    gate, and a chemist holds all three anyway.
    """
    try:
        result = accept_experiment_proposal(
            session,
            proposal_id=proposal_id,
            organization_id=principal.organization_id,
            actor_id=principal.user_id,
            version_id=payload.version_id,
            change_reason=payload.change_reason,
            technical_hypothesis=payload.technical_hypothesis,
            decision_note=payload.decision_note,
        )
    except ResearchError as exc:
        raise _refuse(exc) from exc
    except FormulationError as exc:
        # The revision refused — a missing driver, a released parent, a version
        # in another tenant. It is the caller's input that was wrong, so it is
        # a 422 rather than a 500, and the message is the service's own.
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from exc
    except CrossTenantReferenceError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc
    session.commit()
    return result


@router.post("/proposals/{proposal_id}/reject", summary="Decline a proposal, with a reason")
def post_reject_proposal(
    proposal_id: uuid.UUID,
    payload: ProposalReject,
    principal: Principal = Depends(require_permission("experiment.accept")),
    session: Session = Depends(get_db),
) -> dict[str, Any]:
    """The same permission as accepting: deciding is one authority, not two."""
    try:
        result = reject_experiment_proposal(
            session,
            proposal_id=proposal_id,
            organization_id=principal.organization_id,
            actor_id=principal.user_id,
            decision_note=payload.decision_note,
        )
    except ResearchError as exc:
        raise _refuse(exc) from exc
    session.commit()
    return result
