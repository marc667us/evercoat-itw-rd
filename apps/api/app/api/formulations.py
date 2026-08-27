"""Formulation workspace routes -- and the first HTTP surface in this
product that returns a number the calculation engine actually computed.

**Why there is no `project_id` in these paths.** A formula is addressed by
its own id, and project scope is enforced by RLS: a version belonging to a
restricted project the caller does not belong to is invisible to every
query in the service, so `_load_version` raises "no such formula version"
and every write guarded by it refuses. That is the same predicate
`core.is_project_member` that `require_project_member()` calls, applied by
the database to every row rather than once by the route -- so a future
endpoint that forgets the dependency is still safe.

**Cost is a separate permission and therefore a separate key.** When the
caller lacks `formula.view_cost` the cost figure is ABSENT from the
response, not null. A null would state that the formula has no cost data,
which is a different and false claim about the formula.
"""

from __future__ import annotations

import uuid
from decimal import Decimal
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

# 🔴 THE READS GO THROUGH THE ORCHESTRATOR (§0.2).
#
# This module called its domain service directly on every path, which meant the
# formulations department existed for HTTP callers and not at all for the agent
# tier -- and `include_cost=principal.has("formula.view_cost")` was written out
# four times, once per route. The conductor decides it once, from the verified
# principal, and there is no argument for it on the door: an agent cannot ask
# for cost it does not hold, because there is no flag to pass.
#
# ⚠️ THE WRITES DELIBERATELY DO NOT. §4: humans approve, and AI must not submit,
# approve, revise or classify a formula. The orchestrator exposes no write-side
# entry point at all, and every mutation below still calls the domain service
# directly. The asymmetry is the rule, not an omission.
#
# ⚠️ `export_version` STAYS ON THE DIRECT PATH TOO, AND IT IS A READ. It WRITES
# an export audit event naming the actor, so §4 keeps the audited act of taking
# proprietary composition out of the building where a human signed for it.
#
# ⚠️ `require_permission(...)` ON EACH ROUTE STAYS. The conductor asserts the
# same permission; that is defence in depth. The dependency refuses an
# unauthenticated caller before any handler runs, and the conductor refuses on
# the paths that have no route.
from app.agents.orchestrators.root_orchestrator import (
    AgentPrincipal,
    formulations_classifications,
    formulations_comparison,
    formulations_evaluation,
    formulations_formulas,
    formulations_version,
)
from app.core.security import Principal, get_db, require_permission
from app.core.tenancy import CrossTenantReferenceError
from app.domains.formulations.service import (
    ComponentInput,
    FormulaError,
    FormulaExportRefusedError,
    FormulaInput,
    FormulaNotFoundError,
    FormulationError,
    RevisionInput,
    SubmissionBlockedError,
    VersionFrozenError,
    VersionNotFoundError,
    create_formula,
    decide_version,
    export_version,
    record_observed_effect,
    revise_version,
    set_classification,
    set_components,
    submit_version,
    weigh_up,
)

router = APIRouter()

__all__ = ["router"]

_ROLES = "resin|binder|hardener|catalyst|filler|extender|pigment|additive|solvent|other"


class FormulaCreate(BaseModel):
    project_id: uuid.UUID
    formula_code: str = Field(min_length=2, max_length=50)
    name: str = Field(min_length=1, max_length=200)
    product_family: str | None = Field(default=None, max_length=100)
    description: str | None = None
    owner_user_id: uuid.UUID | None = None


class ComponentLine(BaseModel):
    """One line of a composition.

    `percentage` is `Decimal` with four decimal places of headroom,
    matching `NUMERIC(9,4)` in the schema and the quantum
    `normalize_to_100` rounds to. Declaring it as `float` here would undo
    the whole `Decimal` discipline at the one point where a number enters
    the system.
    """

    material_id: uuid.UUID
    percentage: Decimal = Field(ge=0, le=100)
    role_override: str | None = Field(default=None, pattern=f"^({_ROLES})$")
    display_order: int = Field(default=100, ge=0)
    notes: str | None = None


class CompositionUpdate(BaseModel):
    """The WHOLE composition. See `set_components` for why it is not a patch."""

    components: list[ComponentLine] = Field(min_length=1)


class VersionDecision(BaseModel):
    decision: str = Field(pattern="^(approve|reject)$")
    note: str | None = Field(default=None, max_length=2000)


class RevisionCreate(BaseModel):
    # Both required by the database for any version after the first. Stated
    # here too so the API contract shows them, rather than surfacing as a
    # constraint violation from the domain.
    change_reason: str = Field(min_length=3, max_length=2000)
    technical_hypothesis: str = Field(min_length=3, max_length=2000)
    # 🔴 REQUIRED, and a BREAKING CHANGE to this endpoint's contract — stated
    # rather than slipped in. §2: "A new formula revision must show exactly
    # which failure or improvement objective caused it." `change_reason` is
    # prose; this is the link. Without it `formula_version_drivers` is never
    # written and §29's "why was F008 created?" is unanswerable by query.
    # A default would answer the question on the chemist's behalf.
    driver_type: Literal[
        "failure",
        "requirement",
        "optimization",
        "cost",
        "regulatory",
        "customer_request",
        "other",
    ]
    driver_failure_id: uuid.UUID | None = None
    driver_requirement_id: uuid.UUID | None = None
    expected_effect: str | None = Field(default=None, max_length=2000)
    version_code: str | None = Field(default=None, max_length=50)


class ObservedEffect(BaseModel):
    observed_effect: str = Field(min_length=3, max_length=2000)


class WeighUp(BaseModel):
    batch_mass_kg: Decimal = Field(gt=0)


def _missing(exc: Exception) -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


def _frozen(exc: VersionFrozenError) -> HTTPException:
    return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))


def _invalid(exc: Exception) -> HTTPException:
    return HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))


@router.get("", tags=["formulations"])
def get_formulas(
    project_id: uuid.UUID | None = Query(default=None),
    principal: Principal = Depends(require_permission("formula.view")),
    session: Session = Depends(get_db),
) -> list[dict[str, Any]]:
    return formulations_formulas(
        session, caller=AgentPrincipal.of(principal), project_id=project_id
    )


@router.get("/classifications", tags=["formulations"])
def get_classifications(
    principal: Principal = Depends(require_permission("formula.view")),
    session: Session = Depends(get_db),
) -> list[dict[str, Any]]:
    """The classification ladder, in rank order.

    🔴 DECLARED BEFORE `/{formula_id}/classification` for the same reason the
    testing route is: a literal segment registered after a path parameter is
    shadowed by it.

    Authenticated but not privileged: knowing that a level named
    `FORMULA_RESTRICTED` exists is not a disclosure, and the reclassification
    route itself is gated on `formula.classify`. Hiding the vocabulary would
    only stop the person who is allowed to change it from seeing the options.
    """
    return formulations_classifications(session, caller=AgentPrincipal.of(principal))


@router.post("", status_code=status.HTTP_201_CREATED, tags=["formulations"])
def post_formula(
    payload: FormulaCreate,
    principal: Principal = Depends(require_permission("formula.create")),
    session: Session = Depends(get_db),
) -> dict[str, Any]:
    """Create a formula and its first draft version together.

    A 404 for an unknown project is deliberate and is not a lie about
    permissions: `formulas_project_fk` refuses a project that does not
    exist in this organization, and RLS makes a restricted project the
    caller cannot see indistinguishable from one that is not there. Those
    two must be indistinguishable, or the error becomes a way to
    enumerate other teams' project ids.
    """
    try:
        return create_formula(
            session,
            project_id=payload.project_id,
            organization_id=principal.organization_id,
            actor_id=principal.user_id,
            spec=FormulaInput(
                formula_code=payload.formula_code,
                name=payload.name,
                product_family=payload.product_family,
                description=payload.description,
                owner_user_id=payload.owner_user_id,
            ),
        )
    except FormulaNotFoundError as exc:
        raise _missing(exc) from exc
    except CrossTenantReferenceError as exc:
        raise _invalid(exc) from exc
    except FormulaError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc


@router.get("/versions/{version_id}", tags=["formulations"])
def get_one_version(
    version_id: uuid.UUID,
    principal: Principal = Depends(require_permission("formula.view")),
    session: Session = Depends(get_db),
) -> dict[str, Any]:
    try:
        # Per-material cost plus per-component percentage is the whole cost of
        # the formula. Codex found this payload handing both to a caller holding
        # only `formula.view`; the conductor now decides it from the verified
        # principal, so the decision cannot differ between the four routes that
        # used to make it separately.
        return formulations_version(
            session, version_id=version_id, caller=AgentPrincipal.of(principal)
        )
    except VersionNotFoundError as exc:
        raise _missing(exc) from exc


@router.put("/versions/{version_id}/components", tags=["formulations"])
def put_components(
    version_id: uuid.UUID,
    payload: CompositionUpdate,
    principal: Principal = Depends(require_permission("formula.modify_draft")),
    session: Session = Depends(get_db),
) -> dict[str, Any]:
    """Replace a draft version's composition.

    `formula.modify_draft` is deliberately NOT held by the Engineer role
    (migration 002 says so in a comment and enforces it by omission): an
    Engineer must trigger a revision through the Chemist rather than
    overwrite a composition.
    """
    try:
        return set_components(
            session,
            version_id=version_id,
            organization_id=principal.organization_id,
            actor_id=principal.user_id,
            components=[
                ComponentInput(
                    material_id=c.material_id,
                    percentage=c.percentage,
                    role_override=c.role_override,
                    display_order=c.display_order,
                    notes=c.notes,
                )
                for c in payload.components
            ],
        )
    except VersionNotFoundError as exc:
        raise _missing(exc) from exc
    except VersionFrozenError as exc:
        raise _frozen(exc) from exc
    except FormulationError as exc:
        raise _invalid(exc) from exc


@router.get("/versions/{version_id}/evaluation", tags=["formulations"])
def get_evaluation(
    version_id: uuid.UUID,
    principal: Principal = Depends(require_permission("formula.view")),
    session: Session = Depends(get_db),
) -> dict[str, Any]:
    """Every derived property, plus the submission blocks, computed now.

    Nothing is stored. These figures are DERIVED, and a stored copy would
    be a second source of truth that goes stale the moment a material's
    density is corrected -- the defect already found on this project where
    a status function called itself "derived" and read a stored string.
    """
    try:
        return formulations_evaluation(
            session, version_id=version_id, caller=AgentPrincipal.of(principal)
        )
    except VersionNotFoundError as exc:
        raise _missing(exc) from exc


class ClassificationChange(BaseModel):
    classification: str = Field(..., description="A level from core.classifications")
    reason: str = Field(..., min_length=3, description="Why. Required, and audited.")


@router.post("/{formula_id}/classification", tags=["formulations"])
def post_classification(
    formula_id: uuid.UUID,
    payload: ClassificationChange,
    principal: Principal = Depends(require_permission("formula.classify")),
    session: Session = Depends(get_db),
) -> dict[str, str]:
    """Set a formula's data classification. I48's missing writer.

    🔴 WITHOUT THIS THE LATTICE WAS DECORATIVE. Migration 039 added the column
    and its ceiling default and nothing that decides, so every new formula was
    `DIRECTOR_CONTROLLED` and `export_version` refuses above `R&D_RESTRICTED` --
    permanently un-exportable, by anybody, with no path to change it.

    `formula.classify` is granted to EXACTLY the roles holding
    `formula.export`, and migration 040 refuses to complete if the two sets
    diverge: lowering a classification is the precondition for exporting one,
    so a wider grant would hand a broader group the export ceiling in two
    requests.
    """
    try:
        applied = set_classification(
            session,
            formula_id=formula_id,
            organization_id=principal.organization_id,
            actor_id=principal.user_id,
            classification=payload.classification,
            reason=payload.reason,
        )
    except FormulaNotFoundError as exc:
        raise _missing(exc) from exc
    except FormulaError as exc:
        raise _invalid(exc) from exc
    return {"classification": applied}


@router.get("/versions/{version_id}/export", tags=["formulations"])
def get_export(
    version_id: uuid.UUID,
    principal: Principal = Depends(require_permission("formula.export")),
    session: Session = Depends(get_db),
) -> dict[str, Any]:
    """Export a full formula composition. I43.

    🔴 SCOPE: THIS AUTHORIZES AND AUDITS **THIS ENDPOINT**. IT DOES NOT
    PREVENT EXFILTRATION BY ANYONE WHO CAN ALREADY VIEW THE FORMULA.

    `GET /versions/{id}` requires only `formula.view` and returns the complete
    component list with percentages; `/evaluation`, `/weigh-up` and
    `/comparison` reconstruct it from other angles. Codex refused an earlier
    version of this docstring that implied otherwise, and was right.

    What this delivers is that §31's five-permission rule is implementable at
    all -- `formula.export` did not exist, so view/edit/approve/release/export
    could not be distinguished -- that the deliberate act is entitled to a
    narrower group than reading, and that every use is audited. Prevention
    needs classification enforced on every output channel (I68).

    `formula.export` is held by the Lead, QA and the Administrator -- and
    deliberately NOT by the Director (§31: seniority is not a reason) nor by
    the Chemist, who may read and edit the formula and may not take it out.
    The separation only means something because it is asymmetric.

    Cost is included only if the caller ALSO holds `formula.view_cost`, for
    the reason `get_version` records: percentages plus per-material cost
    reconstruct the formula's cost, so the two permissions compose rather than
    one implying the other.

    403 no `formula.export`
    404 no such version in this organization
    409 classified above the level one person may export alone
    """
    try:
        return export_version(
            session,
            version_id=version_id,
            organization_id=principal.organization_id,
            actor_id=principal.user_id,
            include_cost=principal.has("formula.view_cost"),
        )
    except VersionNotFoundError as exc:
        raise _missing(exc) from exc
    except FormulaExportRefusedError as exc:
        # 409 rather than 403: the caller HOLDS the permission. What is
        # missing is a second person, which is a state of the request rather
        # than of the caller -- and a 403 would send them to an administrator
        # to be granted something they already have.
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc


@router.post("/versions/{version_id}/weigh-up", tags=["formulations"])
def post_weigh_up(
    version_id: uuid.UUID,
    payload: WeighUp,
    principal: Principal = Depends(require_permission("formula.view")),
    session: Session = Depends(get_db),
) -> dict[str, Any]:
    """Component masses for a batch, summing exactly to the batch mass."""
    try:
        return weigh_up(
            session,
            version_id=version_id,
            organization_id=principal.organization_id,
            batch_mass_kg=payload.batch_mass_kg,
        )
    except VersionNotFoundError as exc:
        raise _missing(exc) from exc
    except FormulationError as exc:
        raise _invalid(exc) from exc


@router.post("/versions/{version_id}/submission", tags=["formulations"])
def post_submission(
    version_id: uuid.UUID,
    principal: Principal = Depends(require_permission("formula.submit")),
    session: Session = Depends(get_db),
) -> dict[str, Any]:
    """Submit a draft for laboratory approval.

    A blocked submission answers 422 with EVERY block listed. Returning
    the first one would make the chemist discover them one request at a
    time, which is how a form teaches people to distrust it.
    """
    try:
        return submit_version(
            session,
            version_id=version_id,
            organization_id=principal.organization_id,
            actor_id=principal.user_id,
        )
    except VersionNotFoundError as exc:
        raise _missing(exc) from exc
    except SubmissionBlockedError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"message": "this formula cannot be submitted", "blocks": exc.blocks},
        ) from exc
    except VersionFrozenError as exc:
        raise _frozen(exc) from exc


@router.post("/versions/{version_id}/decision", tags=["formulations"])
def post_decision(
    version_id: uuid.UUID,
    payload: VersionDecision,
    principal: Principal = Depends(require_permission("formula.approve_lab")),
    session: Session = Depends(get_db),
) -> dict[str, Any]:
    """Approve or reject a submitted version.

    The submitter may not be the approver. That is enforced inside the
    UPDATE's own WHERE clause, so two racing requests cannot both pass a
    check and then both commit.
    """
    try:
        return decide_version(
            session,
            version_id=version_id,
            organization_id=principal.organization_id,
            actor_id=principal.user_id,
            decision=payload.decision,
            note=payload.note,
        )
    except VersionNotFoundError as exc:
        raise _missing(exc) from exc
    except VersionFrozenError as exc:
        raise _frozen(exc) from exc
    except FormulationError as exc:
        raise _invalid(exc) from exc


@router.post(
    "/versions/{version_id}/revision", status_code=status.HTTP_201_CREATED, tags=["formulations"]
)
def post_revision(
    version_id: uuid.UUID,
    payload: RevisionCreate,
    principal: Principal = Depends(require_permission("formula.clone")),
    session: Session = Depends(get_db),
) -> dict[str, Any]:
    """Clone a version into a new draft -- the only way a formula changes.

    Two revisions of the same parent is a BRANCH and is permitted. The
    plan requires F004-A / F004-B, so refusing the second child would make
    a branch inexpressible.
    """
    try:
        return revise_version(
            session,
            version_id=version_id,
            organization_id=principal.organization_id,
            actor_id=principal.user_id,
            spec=RevisionInput(
                change_reason=payload.change_reason,
                technical_hypothesis=payload.technical_hypothesis,
                driver_type=payload.driver_type,
                driver_failure_id=payload.driver_failure_id,
                driver_requirement_id=payload.driver_requirement_id,
                expected_effect=payload.expected_effect,
                version_code=payload.version_code,
            ),
        )
    except (VersionNotFoundError, FormulaNotFoundError) as exc:
        raise _missing(exc) from exc
    except FormulationError as exc:
        raise _invalid(exc) from exc


@router.post("/versions/{version_id}/observed-effect", tags=["formulations"])
def post_observed_effect(
    version_id: uuid.UUID,
    payload: ObservedEffect,
    principal: Principal = Depends(require_permission("formula.clone", "formula.modify_draft")),
    session: Session = Depends(get_db),
) -> dict[str, Any]:
    """Record what actually happened, after testing.

    Guarded by either permission, because both the Chemist who wrote the
    hypothesis and whoever holds the revision right are legitimate authors
    of the answer to it -- and a frozen version's observed effect is the
    one field section 8 requires to stay writable.
    """
    try:
        return record_observed_effect(
            session,
            version_id=version_id,
            organization_id=principal.organization_id,
            actor_id=principal.user_id,
            observed_effect=payload.observed_effect,
        )
    except VersionNotFoundError as exc:
        raise _missing(exc) from exc


@router.get("/versions/{version_id}/comparison", tags=["formulations"])
def get_comparison(
    version_id: uuid.UUID,
    against: uuid.UUID = Query(description="the version to compare against"),
    principal: Principal = Depends(require_permission("formula.view")),
    session: Session = Depends(get_db),
) -> dict[str, Any]:
    """The difference engine: previous / new / reason / expected / observed.

    `version_id` is the NEW version and `against` is the previous one, so
    the URL reads the way the screen does -- "what changed to get here".
    """
    try:
        return formulations_comparison(
            session,
            left_version_id=against,
            right_version_id=version_id,
            caller=AgentPrincipal.of(principal),
        )
    except VersionNotFoundError as exc:
        raise _missing(exc) from exc
