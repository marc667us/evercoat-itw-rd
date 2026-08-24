"""Test Module routes.

🔴 THERE IS NO ENDPOINT THAT SETS `calculated_result`, `display_color` OR
`final_status`, AND THERE NEVER MAY BE.

Rule 2 of the seven non-negotiables: Python owns the arithmetic.
`DATA_MODEL.md` §3.1 names those three as derived and server-owned, and
§3.5 marks `calculated_result` as a SYS-only transition. The absence is
the mechanism — a field with no route cannot be posted — and it is
asserted by a test rather than left to inspection, because an absence is
invisible in a diff.

**Permissions, checked against migration 002 before these routes were
written:**

    test.view              everyone with laboratory sight
    test.plan              Engineer                  plan a test
    test.execute           Technician                start, measure, complete
    test.review            Chemist, Engineer         technical review
    test.approve_development  Chemist, Engineer      development approval
    test.approve_lead      Lead                      lead approval
    test.approve_qa        QA                        independent QA approval
    test.approve_director  Director                  release-critical
    test.confirm           Lead, QA, Director        final confirmation
                                                     (granted by migration 019)
    method.manage          Engineer                  methods and versions
    equipment.manage       Engineer                  equipment and calibration

The approval endpoint resolves ITS permission from the authority level in
the body, for the same reason the material status route does: a single
`require_permission` would either hand the Chemist a director-level
approval or block the Director from a development one.
"""

from __future__ import annotations

import datetime as dt
import uuid
from decimal import Decimal
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.security import (
    PermissionDenied,
    Principal,
    get_db,
    get_principal,
    require_permission,
)
from app.core.tenancy import CrossTenantReferenceError
from app.domains.failures.service import FailureError, FailureNotFoundError
from app.domains.testing.service import (
    DecisionInput,
    ReplicateInput,
    SegregationOfDutiesError,
    TestError,
    TestingError,
    TestInput,
    TestNotFoundError,
    TestStateError,
    complete_execution,
    confirm_test,
    create_test,
    exclude_replicate,
    get_test,
    list_methods,
    list_tests,
    record_decision,
    record_replicate,
    start_execution,
)

router = APIRouter()

# 🔴 A SECOND ROUTER, BECAUSE A METHOD IS NOT A SUB-RESOURCE OF A TEST.
#
# `router` is mounted at `/api/testing/tests`, so a `/methods` path declared on
# it would answer at `/api/testing/tests/methods` — which reads as "the methods
# of a test", is not what it is, and 404s the honest URL. Measured: the first
# attempt did exactly that.
#
# Test methods are reference data belonging to the module, not to any one test,
# so they get their own router mounted one level up at `/api/testing`. Widening
# the existing prefix instead would have moved every test route.
reference_router = APIRouter()

__all__ = ["reference_router", "router"]

# WHICH PERMISSION EACH APPROVAL AUTHORITY REQUIRES.
#
# The ladder from migration 002, as a table. `preliminary`, `development`
# and `controlled` are development-side; `validation` and above escalate.
# Read it against §9's five templates: SCREENING_SIMPLE stops at the
# Chemist/Engineer, RELEASE_CRITICAL runs to the Director.
# 🔴 REPLACED BY THE ROUTE'S OWN STEPS (I5). This used to map a
# CALLER-SUPPLIED authority level to the permission required, which is now
# actively WRONG: the approval route's STEP names the permission, and the two
# disagree constantly. A test at `qualification` authority opens
# QUALIFICATION_CONFIRMATION, whose FIRST rung requires
# `test.approve_development` -- so a caller naming `qualification` was checked
# against `test.approve_qa` and refused for a step that was never theirs.
#
# What remains is a coarse gate: hold SOME approval permission, or you have no
# business on this endpoint at all. Which step is yours is the engine's
# decision, made against the route rather than against a string in the request.
APPROVAL_PERMISSIONS: frozenset[str] = frozenset(
    {
        "test.approve_development",
        "test.approve_lead",
        "test.approve_qa",
        "test.approve_director",
    }
)


class TestCreate(BaseModel):
    test_number: str = Field(min_length=3, max_length=50)
    sample_id: uuid.UUID
    method_id: uuid.UUID
    test_purpose: str = Field(
        default="oversight", pattern="^(screening|oversight|confirmation|improvement)$"
    )
    authority_level: str = Field(
        default="development",
        pattern="^(preliminary|development|controlled|validation|qualification|release)$",
    )
    requirement_id: uuid.UUID | None = None
    method_version_id: uuid.UUID | None = None
    equipment_id: uuid.UUID | None = None
    supersedes_test_id: uuid.UUID | None = None
    planned_for: dt.date | None = None
    notes: str | None = None


class ReplicateCreate(BaseModel):
    """One raw measurement.

    `Decimal`, never `float`. A measured value is a controlled quantity
    and the engine refuses a float at its boundary; declaring it as a
    float here would undo that at the one point a number enters the
    system.
    """

    replicate_number: int = Field(ge=1)
    measured_value: Decimal
    # Required, and checked against the method's canonical unit by the
    # service. A value in the wrong unit compares against the requirement
    # as nonsense while looking entirely plausible.
    unit: str = Field(min_length=1, max_length=20)
    notes: str | None = None


class ExclusionCreate(BaseModel):
    reason: str = Field(min_length=3, max_length=1000)


class DecisionCreate(BaseModel):
    """A review or approval decision.

    Seven decision types, not two. §9: "Decisions are richer than
    approve/reject" — returning for correction and rejecting have
    different consequences, and collapsing them loses the difference.
    """

    decision: str = Field(
        pattern="^(approve|approve_with_condition|return_for_correction|"
        "request_retest|reject|escalate|request_additional_test)$"
    )
    stage: str = Field(default="review", pattern="^(review|approval)$")
    authority_level: str | None = Field(
        default=None,
        pattern="^(preliminary|development|controlled|validation|qualification|release)$",
    )
    condition_text: str | None = Field(default=None, max_length=2000)
    rationale: str | None = Field(default=None, max_length=2000)


def _missing(exc: Exception) -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


def _conflict(exc: Exception) -> HTTPException:
    return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))


def _invalid(exc: Exception) -> HTTPException:
    return HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))


@router.get("", tags=["testing"])
def get_tests(
    project_id: uuid.UUID | None = Query(default=None),
    review_state: str | None = Query(default=None),
    principal: Principal = Depends(require_permission("test.view")),
    session: Session = Depends(get_db),
) -> list[dict[str, Any]]:
    """The test queue.

    `review_state` is filterable because the review queue — "what is
    waiting for me" — is the screen this module is used from most.
    """
    return list_tests(
        session,
        organization_id=principal.organization_id,
        project_id=project_id,
        review_state=review_state,
    )


@reference_router.get("/methods", tags=["testing"])
def get_methods(
    principal: Principal = Depends(require_permission("test.view")),
    session: Session = Depends(get_db),
) -> list[dict[str, Any]]:
    """The methods a test can be planned against.

    On `reference_router`, so this answers at `/api/testing/methods` rather
    than `/api/testing/tests/methods` -- see the routers above.

    Gated on `test.view` rather than `method.manage`: choosing a method is
    part of planning and reading, and requiring the administration permission
    merely to SEE the list would put the planning form out of reach of the
    Engineer who uses it.
    """
    return list_methods(session, organization_id=principal.organization_id)


@router.post("", status_code=status.HTTP_201_CREATED, tags=["testing"])
def post_test(
    payload: TestCreate,
    principal: Principal = Depends(require_permission("test.plan")),
    session: Session = Depends(get_db),
) -> dict[str, Any]:
    """Plan a test against a physical sample."""
    try:
        return create_test(
            session,
            organization_id=principal.organization_id,
            actor_id=principal.user_id,
            spec=TestInput(**payload.model_dump()),
        )
    except TestNotFoundError as exc:
        raise _missing(exc) from exc
    except TestStateError as exc:
        raise _conflict(exc) from exc
    except (TestError, CrossTenantReferenceError) as exc:
        raise _invalid(exc) from exc


@router.get("/{test_id}", tags=["testing"])
def get_one_test(
    test_id: uuid.UUID,
    principal: Principal = Depends(require_permission("test.view")),
    session: Session = Depends(get_db),
) -> dict[str, Any]:
    """One test, with its raw replicates, decisions and disposition.

    Returns `automatic_evaluation` AND `final_disposition`, always and
    separately. §3.3: a low-margin pass awaiting approval is both a pass
    and not final, and one field cannot say that. A client that renders
    only one of them is rendering half the truth.
    """
    try:
        return get_test(session, test_id=test_id, organization_id=principal.organization_id)
    except TestNotFoundError as exc:
        raise _missing(exc) from exc


@router.post("/{test_id}/start", tags=["testing"])
def post_start(
    test_id: uuid.UUID,
    principal: Principal = Depends(require_permission("test.execute")),
    session: Session = Depends(get_db),
) -> dict[str, Any]:
    try:
        return start_execution(
            session,
            test_id=test_id,
            organization_id=principal.organization_id,
            actor_id=principal.user_id,
        )
    except TestNotFoundError as exc:
        raise _missing(exc) from exc
    except TestStateError as exc:
        raise _conflict(exc) from exc


@router.post("/{test_id}/replicates", status_code=status.HTTP_201_CREATED, tags=["testing"])
def post_replicate(
    test_id: uuid.UUID,
    payload: ReplicateCreate,
    principal: Principal = Depends(require_permission("test.execute")),
    session: Session = Depends(get_db),
) -> dict[str, str]:
    """Record one raw measurement.

    Per replicate, always — never an aggregate. Rules 5 and 6 of the
    traffic light cannot be recomputed from a mean, so a system that
    accepted only an average would leave two of fourteen rules
    permanently unevaluable and silent about it.
    """
    try:
        replicate_id = record_replicate(
            session,
            test_id=test_id,
            organization_id=principal.organization_id,
            actor_id=principal.user_id,
            spec=ReplicateInput(**payload.model_dump()),
        )
    except TestNotFoundError as exc:
        raise _missing(exc) from exc
    except TestStateError as exc:
        raise _conflict(exc) from exc
    except TestError as exc:
        raise _invalid(exc) from exc
    return {"id": str(replicate_id)}


@router.post("/{test_id}/replicates/{replicate_id}/exclusion", tags=["testing"])
def post_exclusion(
    test_id: uuid.UUID,
    replicate_id: uuid.UUID,
    payload: ExclusionCreate,
    principal: Principal = Depends(require_permission("test.execute", "test.review")),
    session: Session = Depends(get_db),
) -> dict[str, Any]:
    """Set a replicate aside, with a reason.

    There is deliberately no DELETE endpoint for a replicate, and the
    database refuses one anyway. Raw measurements are evidence: an
    excluded replicate stays on the record, visibly excluded, so that
    "why does this test have four measurements when the method requires
    five" remains answerable.
    """
    try:
        return exclude_replicate(
            session,
            test_id=test_id,
            replicate_id=replicate_id,
            organization_id=principal.organization_id,
            actor_id=principal.user_id,
            reason=payload.reason,
        )
    except TestNotFoundError as exc:
        raise _missing(exc) from exc
    except TestError as exc:
        raise _invalid(exc) from exc


@router.post("/{test_id}/completion", tags=["testing"])
def post_completion(
    test_id: uuid.UUID,
    principal: Principal = Depends(require_permission("test.execute")),
    session: Session = Depends(get_db),
) -> dict[str, Any]:
    """Close execution. The result is COMPUTED, not supplied.

    This endpoint takes no body on purpose. There is nowhere to put a
    result, because the caller does not get to state one.
    """
    try:
        return complete_execution(
            session,
            test_id=test_id,
            organization_id=principal.organization_id,
            actor_id=principal.user_id,
        )
    except TestNotFoundError as exc:
        raise _missing(exc) from exc
    except TestStateError as exc:
        raise _conflict(exc) from exc
    # §10's automatic Failure Investigation can refuse. Mapped to the SAME
    # statuses `app/api/failures.py` gives the identical conditions, so the
    # caller gets one answer for one situation regardless of which route
    # surfaced it. Previously these escaped as an unhandled 500 with no
    # actionable message.
    except FailureNotFoundError as exc:
        raise _missing(exc) from exc
    except FailureError as exc:
        raise _conflict(exc) from exc


@router.post("/{test_id}/decisions", status_code=status.HTTP_201_CREATED, tags=["testing"])
def post_decision(
    test_id: uuid.UUID,
    payload: DecisionCreate,
    principal: Principal = Depends(get_principal),
    session: Session = Depends(get_db),
) -> dict[str, Any]:
    """Record a review or approval decision.

    Depends on `get_principal` because the required permission depends on
    the STAGE and the AUTHORITY LEVEL in the body. A single permission on
    the endpoint would either let a Chemist supply a director-level
    approval, or stop the Director supplying a development one.

    A 403 here can mean two different things and says which: the caller
    lacks the permission, or the caller holds it and is barred on THIS
    test by their own earlier involvement (ADR-019).
    """
    if payload.stage == "review":
        if not principal.has("test.review"):
            raise PermissionDenied()
    else:
        # 🔴 REFUSED, NOT IGNORED. `authority_level` no longer selects
        # anything: the route was opened at the TEST's authority when review
        # completed, and each rung names its own permission. Accepting the
        # field and quietly disregarding it would let a caller believe they had
        # chosen the authority their signature carries -- a field that claims
        # more than the code does, which is this codebase's most repeated
        # defect. So say so.
        if payload.authority_level is not None:
            raise _invalid(
                TestError(
                    "an approval decision no longer names its authority level: the "
                    "route was opened at the test's authority when review completed, "
                    "and each step carries the permission it requires (§9)"
                )
            )
        if not (principal.permissions & APPROVAL_PERMISSIONS):
            raise PermissionDenied()

    try:
        return record_decision(
            session,
            test_id=test_id,
            organization_id=principal.organization_id,
            actor_id=principal.user_id,
            # 🔴 THE CALLER'S PERMISSIONS, PASSED THROUGH (I5). An approval
            # step names the permission it requires, and the engine checks the
            # STEP's permission rather than one this route chose. Without this
            # the service could not tell which step is the caller's, and the
            # ladder would be unenforceable.
            held_permissions=principal.permissions,
            spec=DecisionInput(
                decision=payload.decision,
                stage=payload.stage,
                authority_level=payload.authority_level,
                condition_text=payload.condition_text,
                rationale=payload.rationale,
            ),
        )
    except TestNotFoundError as exc:
        raise _missing(exc) from exc
    except SegregationOfDutiesError as exc:
        raise PermissionDenied(str(exc)) from exc
    except TestStateError as exc:
        raise _conflict(exc) from exc
    except TestingError as exc:
        raise _invalid(exc) from exc


@router.post("/{test_id}/confirmation", tags=["testing"])
def post_confirmation(
    test_id: uuid.UUID,
    principal: Principal = Depends(require_permission("test.confirm")),
    session: Session = Depends(get_db),
) -> dict[str, Any]:
    """Mark a result final.

    `test.confirm` is held by the Lead, QA and the Director — granted by
    migration 019, which closed it as an orphaned permission. The
    administrator is deliberately excluded and a test asserts that:
    administering the system is not the authority to make a technical
    decision.

    Only from `approved`. A conditional approval carries a limitation,
    and confirming one would silently discard it.
    """
    try:
        return confirm_test(
            session,
            test_id=test_id,
            organization_id=principal.organization_id,
            actor_id=principal.user_id,
        )
    except TestNotFoundError as exc:
        raise _missing(exc) from exc
    except TestStateError as exc:
        raise _conflict(exc) from exc
