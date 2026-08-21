"""The formulation workspace: formulas, versions, components -- and the
first thing in this codebase that actually CALLS the calculation engine.

**Why that sentence matters.** `app/calculations/formulation.py` has been
pure, exact and property-tested since Slice 3's front half, and until this
module nothing invoked it at runtime. The figures on the deployed site are
produced by `scripts/build_demo_formulations.py` at BUILD time. That is an
honest demonstration and it is not a product: no chemist could change a
percentage and see a density move.

**The division of labour, restated because it is rule 2.** PostgreSQL owns
the verified facts. Python owns the arithmetic. This module owns neither:
it loads rows, hands them to the engine, and stores or returns what comes
back. There is no `+`, no `*` and no `/` over a quantity anywhere below.
A percentage delta computed here would be the fifth instance of a
calculation leaking out of the engine that review has caught in this
repository.

**Missing data is reported, never defaulted.** Each derived property is
returned as a value OR a stated reason it is unavailable. The engine
already refuses to compute a density it does not have; this module carries
that refusal through to the caller instead of turning it into a null that
a screen would render as a blank cell. `Number("")` is 0 and a blank
measurement once rendered a GREEN PASS on this project -- absence must
never present as a value.

**Immutability is the database's job.** Migration 015 puts triggers on
`formula_versions` and `formula_components`, so a version that has left
draft cannot be edited by this service, by a future endpoint, by a
backfill or by a psql session. The checks here exist to produce a
comprehensible refusal, not to be the mechanism: `CLAUDE.md` section 8
requires read-only *at the database level*, and a service-layer guard
alone is a claim.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.calculations.formulation import (
    Component,
    binder_to_filler_ratio,
    cost_per_kg,
    scale_to_batch,
    solids_content,
    theoretical_density,
    total_percentage,
    validate_for_submission,
    voc_content_g_per_l,
)
from app.core.audit import AuditEvent, write_audit
from app.core.tenancy import require_active_member
from app.domains.failures.service import DriverInput, record_driver
from app.domains.materials.service import BLOCKING_STATUSES

__all__ = [
    "ComponentInput",
    "FormulaError",
    "FormulaInput",
    "FormulaNotFoundError",
    "FormulationError",
    "RevisionInput",
    "SubmissionBlockedError",
    "VersionFrozenError",
    "VersionNotFoundError",
    "compare_versions",
    "create_formula",
    "decide_version",
    "evaluate_version",
    "get_version",
    "list_formulas",
    "record_observed_effect",
    "revise_version",
    "set_components",
    "submit_version",
    "weigh_up",
]

# The only status in which a version's composition may change. Everything
# else is a controlled record.
DRAFT = "draft"


class FormulationError(RuntimeError):
    """Base for refusals that are business rules, not bugs."""


class FormulaError(FormulationError):
    pass


class FormulaNotFoundError(FormulaError):
    pass


class VersionNotFoundError(FormulationError):
    pass


class VersionFrozenError(FormulationError):
    """The version has left draft and may not be edited in place.

    A distinct type because the answer is not "you may not" but "not like
    that": the caller should clone it. The route turns this into 409 with
    the version code in the message.
    """


class SubmissionBlockedError(FormulationError):
    """Hard submission blocks, all of them at once.

    Carries the full list rather than the first, because `CLAUDE.md`
    section 8 names four distinct blocks and a form that reveals one per
    attempt is how a chemist learns to distrust the software.
    """

    def __init__(self, blocks: list[dict[str, str]]) -> None:
        self.blocks = blocks
        super().__init__("; ".join(b["message"] for b in blocks))


@dataclass(frozen=True, slots=True)
class FormulaInput:
    formula_code: str
    name: str
    product_family: str | None = None
    description: str | None = None
    owner_user_id: uuid.UUID | None = None


@dataclass(frozen=True, slots=True)
class ComponentInput:
    """One line of a formula, as the caller states it.

    `percentage` is `Decimal`. The engine refuses a `float` at its
    boundary and this dataclass does not convert one on the way in -- a
    `float` reaching here is a caller bug that must surface as a type
    error, not as a plausible number.
    """

    material_id: uuid.UUID
    percentage: Decimal
    role_override: str | None = None
    display_order: int = 100
    notes: str | None = None


@dataclass(frozen=True, slots=True)
class RevisionInput:
    change_reason: str
    technical_hypothesis: str
    # 🔴 `driver_type` HAS NO DEFAULT, DELIBERATELY.
    #
    # §2: "A new formula revision must show exactly which failure or
    # improvement objective caused it." `change_reason` is free text — it
    # explains, it does not LINK — so a revision with only a change_reason
    # leaves §29's question ("why was F008 created?") answerable in prose and
    # unanswerable by query. That is the isolated data island §2 forbids.
    #
    # A default would silently pick a reason on the chemist's behalf, and
    # 'other' is the one answer that carries no information. The vocabulary
    # already covers every honest case — failure, requirement, optimization,
    # cost, regulatory, customer_request, other — so there is always a true
    # answer available and no reason to guess one.
    driver_type: str = ""
    # Required by migration 021's CHECK constraints when driver_type is
    # 'failure' or 'requirement' respectively. Validated here too so the
    # refusal explains itself instead of arriving as a constraint violation.
    driver_failure_id: uuid.UUID | None = None
    driver_requirement_id: uuid.UUID | None = None
    expected_effect: str | None = None
    version_code: str | None = None


# ---------------------------------------------------------------------------
# Formulas and versions
# ---------------------------------------------------------------------------


def create_formula(
    session: Session,
    *,
    project_id: uuid.UUID,
    organization_id: uuid.UUID,
    actor_id: uuid.UUID,
    spec: FormulaInput,
) -> dict[str, Any]:
    """Create a formula and its first draft version, in one transaction.

    A formula with no version is not a thing a chemist can use: every
    screen in the workspace is a view of a VERSION, and the empty state
    would be "this formula has no versions", which is a state the product
    should never be able to reach. So the two rows are created together.

    Version 1 has no parent, by constraint. The genealogy starts here.

    🔴 THE PROJECT IS AUTHORIZED IN THIS STATEMENT, NOT BY RLS.

    An earlier draft of this module claimed in its docstring that "project
    scope is enforced by RLS ... every write guarded by it refuses". That
    was TRUE of every other write here and FALSE of this one, which is the
    only write that names a project instead of loading one.

    Migration 005 deliberately made the project-scoped WITH CHECK
    organization-only, because requiring membership in order to WRITE
    makes the first row of a restricted project impossible to create. The
    consequence is that an INSERT naming a restricted project's id
    SUCCEEDS for a non-member -- the row simply becomes invisible to them
    afterwards. Invisible is not the same as refused: the write landed in
    another team's confidential project, and it would show up on the
    members' screens attributed to an outsider.

    Raised by Codex. It is exactly the defect class this repository names
    most often -- a comment asserting a guarantee the code does not
    provide -- committed inside the docstring that asserts it.

    The fix is an INSERT ... SELECT whose source row is the project, with
    the SAME predicate the RLS USING clause applies. No read-then-write:
    if the project is not visible-and-writable to this caller the SELECT
    yields nothing, the INSERT writes nothing, and there is no window
    between the check and the write for the project's confidentiality to
    change. `core.is_project_member` stays the single definition of
    membership, shared with every policy.
    """
    owner_id = spec.owner_user_id or actor_id
    require_active_member(
        session, user_id=owner_id, organization_id=organization_id, role_description="formula owner"
    )

    try:
        formula_id_or_none: uuid.UUID | None = session.execute(
            text(
                """
                INSERT INTO formulations.formulas
                    (organization_id, project_id, formula_code, name,
                     product_family, description, owner_user_id, created_by)
                SELECT :org, p.id, :code, :name, :family, :description, :owner, :actor
                FROM projects.projects p
                WHERE p.id = :pid
                  AND p.organization_id = :org
                  AND (p.confidentiality = 'normal' OR core.is_project_member(p.id))
                RETURNING id
                """
            ),
            {
                "org": organization_id,
                "pid": project_id,
                "code": spec.formula_code,
                "name": spec.name,
                "family": spec.product_family,
                "description": spec.description,
                "owner": owner_id,
                "actor": actor_id,
            },
        ).scalar_one_or_none()

        if formula_id_or_none is None:
            # One message for "no such project" and for "a restricted
            # project you do not belong to". The two must be
            # indistinguishable, or the error is a way to enumerate other
            # teams' project ids.
            raise FormulaNotFoundError("no such project in this organization")
        formula_id: uuid.UUID = formula_id_or_none

        version_id: uuid.UUID = session.execute(
            text(
                """
                INSERT INTO formulations.formula_versions
                    (organization_id, project_id, formula_id, version_number,
                     version_code, status, created_by)
                VALUES (:org, :pid, :fid, 1, :vcode, 'draft', :actor)
                RETURNING id
                """
            ),
            {
                "org": organization_id,
                "pid": project_id,
                "fid": formula_id,
                "vcode": f"{spec.formula_code}-V001",
                "actor": actor_id,
            },
        ).scalar_one()
    except IntegrityError as exc:
        session.rollback()
        detail = str(exc.orig)
        if "formulas_org_code_key" in detail:
            raise FormulaError(
                f"formula code '{spec.formula_code}' is already used in this organization"
            ) from exc
        if "formulas_project_fk" in detail:
            raise FormulaNotFoundError("no such project in this organization") from exc
        raise FormulaError(detail) from exc

    write_audit(
        session,
        AuditEvent(
            action="formula.created",
            entity_type="formula",
            entity_id=str(formula_id),
            organization_id=organization_id,
            user_id=actor_id,
            new_state={"formula_code": spec.formula_code, "name": spec.name, "version": 1},
            reason="formula created with its first draft version",
        ),
    )
    return {
        "formula_id": formula_id,
        "version_id": version_id,
        "formula_code": spec.formula_code,
        "version_code": f"{spec.formula_code}-V001",
    }


def list_formulas(
    session: Session,
    *,
    organization_id: uuid.UUID,
    project_id: uuid.UUID | None = None,
    limit: int = 200,
) -> list[dict[str, Any]]:
    """Formulas visible to this caller, with their latest version.

    RLS does the confidentiality filtering: a formula in a restricted
    project the caller does not belong to is simply absent. That is why
    this returns no count of what was hidden -- a "3 formulas you cannot
    see" line would itself disclose the existence of a restricted
    project's work.
    """
    rows = session.execute(
        text(
            """
            SELECT f.id, f.formula_code, f.name, f.product_family, f.status,
                   f.project_id, p.project_code, f.owner_user_id, f.updated_at,
                   latest.version_code AS latest_version_code,
                   latest.version_number AS latest_version_number,
                   latest.status AS latest_version_status,
                   (SELECT count(*) FROM formulations.formula_versions v
                     WHERE v.formula_id = f.id) AS version_count
            FROM formulations.formulas f
            JOIN projects.projects p
              ON p.id = f.project_id AND p.organization_id = f.organization_id
            LEFT JOIN LATERAL (
                SELECT v.version_code, v.version_number, v.status
                FROM formulations.formula_versions v
                WHERE v.formula_id = f.id AND v.organization_id = f.organization_id
                ORDER BY v.version_number DESC
                LIMIT 1
            ) latest ON TRUE
            WHERE f.organization_id = :org
              AND (:pid IS NULL OR f.project_id = :pid)
            ORDER BY f.formula_code
            LIMIT :limit
            """
        ),
        {"org": organization_id, "pid": project_id, "limit": limit},
    ).mappings()
    return [dict(r) for r in rows]


def get_version(
    session: Session,
    *,
    version_id: uuid.UUID,
    organization_id: uuid.UUID,
    include_cost: bool = False,
) -> dict[str, Any]:
    """One version with its components and every material property joined.

    The material properties come along because the engine needs them and
    because the workspace must show WHY a density is unavailable -- naming
    the material with no density is the difference between a blank field
    and an actionable one.

    🔴 `cost_per_kg` IS STRIPPED WITHOUT `formula.view_cost`.

    Raised by Codex. `_load_components` selects the per-material cost
    because the engine needs it, and this payload also carries every
    component's percentage -- so returning both to a caller holding only
    `formula.view` hands them everything needed to reconstruct the
    formula's cost. The permission would have been enforced on the
    `/evaluation` endpoint and bypassed one URL away.

    The key is REMOVED rather than nulled, for the reason stated on
    `evaluate_version`: a null says "this material has no cost on file",
    which is a different and false claim.
    """
    version = _load_version(session, version_id=version_id, organization_id=organization_id)
    components = _load_components(session, version_id=version_id, organization_id=organization_id)
    if not include_cost:
        for component in components:
            component.pop("cost_per_kg", None)
    version["components"] = components
    return version


def set_components(
    session: Session,
    *,
    version_id: uuid.UUID,
    organization_id: uuid.UUID,
    actor_id: uuid.UUID,
    components: list[ComponentInput],
) -> dict[str, Any]:
    """Replace a draft version's composition wholesale.

    **Replace, not merge.** A formula is a set of lines that must total
    100%; a partial update leaves the caller responsible for keeping the
    two halves consistent, and every intermediate state is invalid. Sending
    the whole composition makes the operation atomic and idempotent.

    The delete-then-insert runs inside the request's transaction, so a
    concurrent reader never observes an empty formula. The database refuses
    the whole operation if the version is not a draft -- the trigger fires
    on the DELETE as well as on the INSERT, which is what stops a
    "clearing" of an approved formula getting through.
    """
    version = _load_version(session, version_id=version_id, organization_id=organization_id)
    if version["status"] != DRAFT:
        raise VersionFrozenError(
            f"version {version['version_code']} is {version['status']}; "
            "clone it to a new draft before changing its composition"
        )
    if not components:
        raise FormulationError("a formula needs at least one component")

    seen: set[uuid.UUID] = set()
    for c in components:
        if c.material_id in seen:
            # Refused here as well as by the unique constraint, because the
            # constraint reports the second row and this reports the
            # intent: two lines for one material make the percentage
            # ambiguous and the engine refuses to scale such a formula.
            raise FormulationError(
                "the same material appears more than once; one line per material"
            )
        seen.add(c.material_id)

    session.execute(
        text(
            """
            DELETE FROM formulations.formula_components
            WHERE formula_version_id = :vid AND organization_id = :org
            """
        ),
        {"vid": version_id, "org": organization_id},
    )

    try:
        for c in components:
            session.execute(
                text(
                    """
                    INSERT INTO formulations.formula_components
                        (organization_id, project_id, formula_version_id, material_id,
                         percentage, role_override, display_order, notes)
                    VALUES (:org, :pid, :vid, :mid, :pct, :role, :order, :notes)
                    """
                ),
                {
                    "org": organization_id,
                    "pid": version["project_id"],
                    "vid": version_id,
                    "mid": c.material_id,
                    "pct": c.percentage,
                    "role": c.role_override,
                    "order": c.display_order,
                    "notes": c.notes,
                },
            )
    except IntegrityError as exc:
        session.rollback()
        detail = str(exc.orig)
        if "formula_components_material_fk" in detail:
            raise FormulationError(
                "one of the components names a material that does not exist in this organization"
            ) from exc
        raise FormulationError(detail) from exc

    write_audit(
        session,
        AuditEvent(
            action="formula_version.composition_set",
            entity_type="formula_version",
            entity_id=str(version_id),
            organization_id=organization_id,
            user_id=actor_id,
            # Component-level percentages are deliberately NOT written into
            # the audit payload. SECURITY.md section 11 forbids payload
            # logging and a formulation IS the secret this product exists
            # to protect -- an audit table that carried every draft
            # composition would be a second, less-guarded copy of it.
            new_state={"component_count": len(components)},
            reason="draft composition replaced",
        ),
    )
    return {"version_id": version_id, "component_count": len(components)}


# ---------------------------------------------------------------------------
# The engine call
# ---------------------------------------------------------------------------


def evaluate_version(
    session: Session,
    *,
    version_id: uuid.UUID,
    organization_id: uuid.UUID,
    include_cost: bool = False,
) -> dict[str, Any]:
    """Every derived property of a version, plus its submission blocks.

    THE SHAPE OF THE RESULT IS THE POINT. Each property is either a value
    or a stated reason it cannot be computed -- never a null, never a zero,
    never a silently omitted key. The engine raises "density unknown for:
    RM-FIL-07" and that sentence reaches the chemist, because a blank cell
    would leave them believing the property had been calculated and had
    come out empty.

    `include_cost` is a permission decision made by the route from
    `formula.view_cost`. When it is false the cost key is ABSENT rather
    than null: a null would read as "no cost data exists", which is a
    different and false statement about the formula.
    """
    version = _load_version(session, version_id=version_id, organization_id=organization_id)
    rows = _load_components(session, version_id=version_id, organization_id=organization_id)

    if not rows:
        return {
            "version": version,
            "component_count": 0,
            "properties": {},
            "submission_blocks": [
                {
                    "code": "NO_COMPONENTS",
                    "message": "this version has no components yet",
                }
            ],
            "submittable": False,
        }

    engine_components = _to_engine_components(rows)
    tolerance = version["total_tolerance_pct"]

    properties: dict[str, Any] = {
        "total_percentage": _try(lambda: total_percentage(engine_components)),
        "theoretical_density_g_cm3": _try(lambda: theoretical_density(engine_components)),
        "binder_to_filler_ratio": _try(lambda: binder_to_filler_ratio(engine_components)),
        "solids_content_pct": _try(lambda: solids_content(engine_components)),
        "voc_content_g_per_l": _try(lambda: voc_content_g_per_l(engine_components)),
    }
    if include_cost:
        properties["raw_material_cost_per_kg"] = _try(lambda: cost_per_kg(engine_components))

    blocks = validate_for_submission(
        engine_components,
        tolerance=tolerance,
        restricted_materials=frozenset(
            r["material_code"] for r in rows if r["material_status"] in BLOCKING_STATUSES
        ),
        # Density is required at submission. Every formulation decision in
        # this product turns on it -- the whole lightweighting story is a
        # density falling from 1.579 to 1.092 -- and a formula submitted
        # without one cannot be compared against the requirement it exists
        # to satisfy.
        require_density=True,
        failed_safety_checks=_safety_checks(rows),
    )

    return {
        "version": version,
        "component_count": len(rows),
        "properties": properties,
        "submission_blocks": [{"code": b.code, "message": b.message} for b in blocks],
        "submittable": not blocks,
    }


def weigh_up(
    session: Session,
    *,
    version_id: uuid.UUID,
    organization_id: uuid.UUID,
    batch_mass_kg: Decimal,
) -> dict[str, Any]:
    """Component masses for a batch, summing EXACTLY to the batch mass.

    This is the sheet a technician weighs against, which is why the engine
    refuses an off-100% formula rather than renormalising it silently: a
    stated percentage and a mass that contradict each other, printed in
    adjacent columns, is a discrepancy the software invented.
    """
    version = _load_version(session, version_id=version_id, organization_id=organization_id)
    rows = _load_components(session, version_id=version_id, organization_id=organization_id)
    if not rows:
        raise FormulationError("this version has no components to weigh up")

    try:
        masses = scale_to_batch(_to_engine_components(rows), batch_mass_kg)
    except ValueError as exc:
        # The engine's refusals are business facts, not bugs: an off-100%
        # formula, a duplicated component, a batch too small to express.
        # Each carries its own explanation, so it is passed through.
        raise FormulationError(str(exc)) from exc

    return {
        "version": version,
        "batch_mass_kg": batch_mass_kg,
        # ORDERED BY THE FORMULA, NOT BY THE ENGINE'S RETURN.
        # `scale_to_batch` returns a dict built largest-line-last, because
        # the largest line absorbs the rounding remainder. Iterating that
        # dict would print the weigh-up sheet in an order that matches
        # nothing on screen and moves whenever a percentage changes. The
        # technician's sheet follows `display_order`, which is the order
        # the composition is stored and rendered in.
        "lines": [
            {
                "material_code": r["material_code"],
                "material_name": r["material_name"],
                "percentage": r["percentage"],
                "mass_kg": masses[r["material_code"]],
            }
            for r in rows
        ],
    }


def compare_versions(
    session: Session,
    *,
    left_version_id: uuid.UUID,
    right_version_id: uuid.UUID,
    organization_id: uuid.UUID,
    include_cost: bool = False,
) -> dict[str, Any]:
    """The difference engine: old / new / delta / reason / expected / observed.

    The plan specifies exactly those columns. The percentage-point delta on
    a component is a SUBTRACTION OF TWO PERCENTAGES and is therefore
    arithmetic -- so it is not done here. It is expressed as the pair of
    values, and the one place that may subtract them is the engine.

    That is not pedantry. `fraction * 100` and a percentage delta were both
    caught in a React component in review on this project, and the rule
    that keeps catching them is that the arithmetic has exactly one home.
    """
    left = evaluate_version(
        session,
        version_id=left_version_id,
        organization_id=organization_id,
        include_cost=include_cost,
    )
    right = evaluate_version(
        session,
        version_id=right_version_id,
        organization_id=organization_id,
        include_cost=include_cost,
    )

    # `_load_version` does not attach components, so an earlier draft of
    # this function read a `_components` key that never existed and then
    # fell through to loading them anyway. Two code paths where one was
    # unreachable -- removed rather than left as a fast path that has
    # never once been taken.
    left_rows = {
        c["material_code"]: c
        for c in _load_components(
            session, version_id=left_version_id, organization_id=organization_id
        )
    }
    right_rows = {
        c["material_code"]: c
        for c in _load_components(
            session, version_id=right_version_id, organization_id=organization_id
        )
    }

    codes = sorted(set(left_rows) | set(right_rows))
    component_rows = [
        {
            "material_code": code,
            "material_name": (left_rows.get(code) or right_rows[code])["material_name"],
            "previous_percentage": left_rows[code]["percentage"] if code in left_rows else None,
            "new_percentage": right_rows[code]["percentage"] if code in right_rows else None,
            "change": (
                "added"
                if code not in left_rows
                else "removed"
                if code not in right_rows
                else "unchanged"
                if left_rows[code]["percentage"] == right_rows[code]["percentage"]
                else "changed"
            ),
        }
        for code in codes
    ]

    return {
        "previous": left["version"],
        "new": right["version"],
        "change_reason": right["version"]["change_reason"],
        "technical_hypothesis": right["version"]["technical_hypothesis"],
        "expected_effect": right["version"]["expected_effect"],
        "observed_effect": right["version"]["observed_effect"],
        "components": component_rows,
        "previous_properties": left["properties"],
        "new_properties": right["properties"],
    }


# ---------------------------------------------------------------------------
# Lifecycle
# ---------------------------------------------------------------------------


def submit_version(
    session: Session,
    *,
    version_id: uuid.UUID,
    organization_id: uuid.UUID,
    actor_id: uuid.UUID,
) -> dict[str, Any]:
    """Submit a draft for review, refusing every hard block at once.

    The validation runs against the rows in this transaction, not against
    a figure the client computed and sent -- a client-side "looks fine to
    me" is exactly the class of check that lets an out-of-tolerance
    formula reach a laboratory.
    """
    version = _load_version(session, version_id=version_id, organization_id=organization_id)
    if version["status"] != DRAFT:
        raise VersionFrozenError(
            f"version {version['version_code']} is already {version['status']}"
        )

    result = evaluate_version(
        session, version_id=version_id, organization_id=organization_id, include_cost=False
    )
    if result["submission_blocks"]:
        raise SubmissionBlockedError(result["submission_blocks"])

    row = (
        session.execute(
            text(
                """
                UPDATE formulations.formula_versions
                SET status = 'submitted',
                    submitted_by = :actor,
                    submitted_at = now(),
                    updated_at = now()
                WHERE id = :vid AND organization_id = :org AND status = 'draft'
                RETURNING id, version_code, status
                """
            ),
            {"vid": version_id, "org": organization_id, "actor": actor_id},
        )
        .mappings()
        .one_or_none()
    )
    if row is None:
        # The status moved between the load and the write. The guard is in
        # the WHERE clause precisely so that this is a refusal rather than
        # a silent overwrite of somebody else's decision.
        raise VersionFrozenError("this version was changed by someone else; reload it")

    write_audit(
        session,
        AuditEvent(
            action="formula_version.submitted",
            entity_type="formula_version",
            entity_id=str(version_id),
            organization_id=organization_id,
            user_id=actor_id,
            previous_state={"status": DRAFT},
            new_state={"status": "submitted"},
            reason="submitted for laboratory approval",
        ),
    )
    return dict(row)


def decide_version(
    session: Session,
    *,
    version_id: uuid.UUID,
    organization_id: uuid.UUID,
    actor_id: uuid.UUID,
    decision: str,
    note: str | None = None,
) -> dict[str, Any]:
    """Approve or reject a submitted version.

    **The approver may not be the submitter.** Segregation of duties is
    stated in `CLAUDE.md` section 9 for qualification and release
    authority, and a formula going to a laboratory is the first point at
    which one person's work becomes another's instruction. Enforced
    server-side, in the same statement, so it cannot be bypassed by a
    second request racing the first.

    Approving a revision supersedes its parent. That is a consequence of
    the decision rather than a separate action a user could forget: two
    versions both reading `approved` in a genealogy is how a laboratory
    picks the wrong one.
    """
    if decision not in {"approve", "reject"}:
        raise FormulationError(f"'{decision}' is not a decision")
    if decision == "reject" and not note:
        raise FormulationError("a rejection must say why")

    status = "approved" if decision == "approve" else "rejected"

    row = (
        session.execute(
            text(
                """
                WITH prev AS (
                    SELECT id, status, submitted_by, parent_version_id, version_code
                    FROM formulations.formula_versions
                    WHERE id = :vid AND organization_id = :org
                    FOR UPDATE
                )
                UPDATE formulations.formula_versions v
                SET status = :status,
                    -- 🔴 ONLY AN APPROVAL NAMES AN APPROVER.
                    -- This set both columns unconditionally, so a REJECTED
                    -- version committed with `approved_by` and
                    -- `approved_at` populated -- the CHECK is satisfied, so
                    -- nothing complained -- and every screen and report
                    -- rendering "Approved by" would have named the person
                    -- who rejected it. Raised by the Supervisor.
                    -- Who rejected it, and why, is in the audit event
                    -- written below; that is the permanent decision record
                    -- section 9 requires.
                    approved_by = CASE WHEN :status = 'approved' THEN CAST(:actor AS UUID) END,
                    approved_at = CASE WHEN :status = 'approved' THEN now() END,
                    approval_note = :note,
                    updated_at = now()
                FROM prev
                WHERE v.id = prev.id
                  AND prev.status = 'submitted'
                  AND prev.submitted_by IS DISTINCT FROM :actor
                RETURNING v.id, v.version_code, v.status,
                          prev.status AS previous_status,
                          prev.parent_version_id AS parent_version_id
                """
            ),
            {
                "vid": version_id,
                "org": organization_id,
                "status": status,
                "actor": actor_id,
                "note": note,
            },
        )
        .mappings()
        .one_or_none()
    )

    if row is None:
        # Two causes, and they must be distinguished for the user without
        # disclosing anything: look the version up and say which it was.
        current = _load_version(session, version_id=version_id, organization_id=organization_id)
        if current["status"] != "submitted":
            raise VersionFrozenError(
                f"version {current['version_code']} is {current['status']}, not awaiting a decision"
            )
        raise FormulationError(
            "the person who submitted a formula may not approve it "
            "(CLAUDE.md section 9, segregation of duties)"
        )

    superseded: str | None = None
    if decision == "approve" and row["parent_version_id"] is not None:
        parent = (
            session.execute(
                text(
                    """
                    UPDATE formulations.formula_versions
                    SET status = 'superseded', updated_at = now()
                    WHERE id = :pid AND organization_id = :org
                      AND status IN ('approved', 'submitted')
                    RETURNING version_code
                    """
                ),
                {"pid": row["parent_version_id"], "org": organization_id},
            )
            .mappings()
            .one_or_none()
        )
        superseded = parent["version_code"] if parent else None

    write_audit(
        session,
        AuditEvent(
            action=f"formula_version.{status}",
            entity_type="formula_version",
            entity_id=str(version_id),
            organization_id=organization_id,
            user_id=actor_id,
            previous_state={"status": row["previous_status"]},
            new_state={"status": status, "superseded": superseded},
            reason=note or "laboratory approval decision",
        ),
    )
    result = dict(row)
    result["superseded_version_code"] = superseded
    return result


def revise_version(
    session: Session,
    *,
    version_id: uuid.UUID,
    organization_id: uuid.UUID,
    actor_id: uuid.UUID,
    spec: RevisionInput,
) -> dict[str, Any]:
    """Clone a version into a new draft -- the ONLY way a formula changes.

    Section 8: never update an approved formula in place. The clone copies
    the composition so the chemist starts from the real thing rather than
    from an empty sheet, and records `parent_version_id`, `change_reason`
    and `technical_hypothesis`, which the database requires of every
    version after the first.

    **Two children of one parent is a BRANCH**, and it is permitted: this
    function does not check whether the parent already has a revision. The
    plan requires F004-A / F004-B, and refusing the second child would
    make a branch impossible to express.

    The new issue number is taken inside the INSERT, from the formula's
    current maximum, so two chemists revising the same version
    concurrently cannot both take the same number -- the unique constraint
    would refuse the second, which is a correct refusal reached by a race
    rather than by a check.
    """
    # Checked BEFORE anything is written. A revision that cannot record why it
    # exists must not exist: creating the version first and refusing the driver
    # afterwards would leave the exact orphan §2 forbids, and rely on the
    # caller's rollback to clean it up.
    if not spec.driver_type:
        raise FormulationError(
            "a revision must say what drove it — one of: failure, requirement, "
            "optimization, cost, regulatory, customer_request, other. §2 requires a "
            "revision to show which failure or objective caused it, and a change "
            "reason explains without linking."
        )
    if spec.driver_type == "failure" and spec.driver_failure_id is None:
        raise FormulationError(
            "a revision driven by a failure must name the failure it answers; "
            "otherwise the digital thread records a category and loses the link"
        )
    if spec.driver_type == "requirement" and spec.driver_requirement_id is None:
        raise FormulationError(
            "a revision driven by a requirement must name the requirement it chases"
        )

    parent = _load_version(session, version_id=version_id, organization_id=organization_id)

    try:
        new_row = (
            session.execute(
                text(
                    """
                    INSERT INTO formulations.formula_versions
                        (organization_id, project_id, formula_id, version_number,
                         version_code, parent_version_id, status, change_reason,
                         technical_hypothesis, expected_effect, total_tolerance_pct,
                         created_by)
                    SELECT :org, f.project_id, f.id,
                           (SELECT COALESCE(max(v.version_number), 0) + 1
                              FROM formulations.formula_versions v
                             WHERE v.formula_id = f.id AND v.organization_id = :org),
                           COALESCE(:vcode, f.formula_code || '-V' || lpad(
                               ((SELECT COALESCE(max(v.version_number), 0) + 1
                                   FROM formulations.formula_versions v
                                  WHERE v.formula_id = f.id
                                    AND v.organization_id = :org))::text, 3, '0')),
                           :parent, 'draft', :reason, :hypothesis, :expected,
                           :tolerance, :actor
                    FROM formulations.formulas f
                    WHERE f.id = :fid AND f.organization_id = :org
                    RETURNING id, version_code, version_number
                    """
                ),
                {
                    "org": organization_id,
                    "fid": parent["formula_id"],
                    "parent": version_id,
                    "vcode": spec.version_code,
                    "reason": spec.change_reason,
                    "hypothesis": spec.technical_hypothesis,
                    "expected": spec.expected_effect,
                    "tolerance": parent["total_tolerance_pct"],
                    "actor": actor_id,
                },
            )
            .mappings()
            .one_or_none()
        )
        if new_row is None:
            raise FormulaNotFoundError("the parent version's formula is not visible")

        # Copy the composition. INSERT ... SELECT rather than a read into
        # Python and a write back: the copy is then atomic with respect to
        # anything else touching the parent, and no percentage passes
        # through a Python float on the way.
        #
        # COUNTED IN THE DATABASE, in the same statement that writes.
        #
        # `.rowcount` is untyped on SQLAlchemy's `Result` (mypy said so) and
        # the DBAPI documents it as undefined for some statement shapes;
        # `len(...all())` drags every returned id across the wire for a
        # number, which Semgrep flagged (`len-all-count`). A CTE around the
        # INSERT gives the count without either problem.
        copied = session.execute(
            text(
                """
                WITH copied AS (
                    INSERT INTO formulations.formula_components
                        (organization_id, project_id, formula_version_id, material_id,
                         percentage, role_override, display_order, notes)
                    SELECT c.organization_id, c.project_id, :new_vid, c.material_id,
                           c.percentage, c.role_override, c.display_order, c.notes
                    FROM formulations.formula_components c
                    WHERE c.formula_version_id = :old_vid AND c.organization_id = :org
                    RETURNING id
                )
                SELECT count(*) FROM copied
                """
            ),
            {"new_vid": new_row["id"], "old_vid": version_id, "org": organization_id},
        ).scalar_one()
    except IntegrityError as exc:
        session.rollback()
        detail = str(exc.orig)
        if "formula_versions_code_key" in detail:
            raise FormulationError(
                "that version code is already used in this organization"
            ) from exc
        if "formula_versions_number_key" in detail:
            raise FormulationError(
                "another revision of this formula was created at the same moment; retry"
            ) from exc
        raise FormulationError(detail) from exc

    write_audit(
        session,
        AuditEvent(
            action="formula_version.revised",
            entity_type="formula_version",
            entity_id=str(new_row["id"]),
            organization_id=organization_id,
            user_id=actor_id,
            previous_state={"parent_version_code": parent["version_code"]},
            new_state={
                "version_code": new_row["version_code"],
                "component_count": copied,
            },
            reason=spec.change_reason,
        ),
    )

    # 🔴 I7 — THE OTHER END OF THE DIGITAL THREAD.
    # `record_driver` existed and had no caller from here, so
    # `formula_version_drivers` was never written by the only function that
    # creates a revision, and §29's "why was F008 created?" had no answer.
    # Reused rather than re-implemented (§12): it already enforces the
    # composite CHECKs and writes its own audit event.
    driver_id = record_driver(
        session,
        formula_version_id=new_row["id"],
        organization_id=organization_id,
        actor_id=actor_id,
        spec=DriverInput(
            driver_type=spec.driver_type,
            reason=spec.change_reason,
            failure_id=spec.driver_failure_id,
            requirement_id=spec.driver_requirement_id,
        ),
    )

    return {
        "version_id": new_row["id"],
        "version_code": new_row["version_code"],
        "version_number": new_row["version_number"],
        "parent_version_code": parent["version_code"],
        "component_count": copied,
        # Reported so the caller can show the link it just created, and so a
        # null here would be visible rather than silent.
        "driver_id": driver_id,
        "driver_type": spec.driver_type,
    }


def record_observed_effect(
    session: Session,
    *,
    version_id: uuid.UUID,
    organization_id: uuid.UUID,
    actor_id: uuid.UUID,
    observed_effect: str,
) -> dict[str, Any]:
    """Write what actually happened, after testing.

    Deliberately writable on a frozen version -- the immutability trigger
    allows exactly this column and the disposition columns to move. A
    version whose observed effect could never be recorded would make the
    digital thread one-way: the hypothesis would be preserved forever and
    the answer to it never captured.
    """
    row = (
        session.execute(
            text(
                """
                UPDATE formulations.formula_versions
                SET observed_effect = :observed, updated_at = now()
                WHERE id = :vid AND organization_id = :org
                RETURNING id, version_code, status
                """
            ),
            {"vid": version_id, "org": organization_id, "observed": observed_effect},
        )
        .mappings()
        .one_or_none()
    )
    if row is None:
        raise VersionNotFoundError("no such formula version in this organization")

    write_audit(
        session,
        AuditEvent(
            action="formula_version.observed_effect_recorded",
            entity_type="formula_version",
            entity_id=str(version_id),
            organization_id=organization_id,
            user_id=actor_id,
            new_state={"observed_effect": observed_effect[:200]},
            reason="observed effect recorded after testing",
        ),
    )
    return dict(row)


# ---------------------------------------------------------------------------
# Loading
# ---------------------------------------------------------------------------


def _load_version(
    session: Session, *, version_id: uuid.UUID, organization_id: uuid.UUID
) -> dict[str, Any]:
    row = (
        session.execute(
            text(
                """
                SELECT v.id, v.formula_id, v.project_id, v.organization_id,
                       v.version_number, v.version_code, v.parent_version_id,
                       v.status, v.change_reason, v.technical_hypothesis,
                       v.expected_effect, v.observed_effect, v.total_tolerance_pct,
                       v.submitted_by, v.submitted_at, v.approved_by, v.approved_at,
                       v.approval_note, v.created_at, v.updated_at,
                       f.formula_code, f.name AS formula_name, f.product_family,
                       parent.version_code AS parent_version_code
                FROM formulations.formula_versions v
                JOIN formulations.formulas f
                  ON f.id = v.formula_id AND f.organization_id = v.organization_id
                LEFT JOIN formulations.formula_versions parent
                  ON parent.id = v.parent_version_id
                 AND parent.organization_id = v.organization_id
                WHERE v.id = :vid AND v.organization_id = :org
                """
            ),
            {"vid": version_id, "org": organization_id},
        )
        .mappings()
        .one_or_none()
    )
    if row is None:
        raise VersionNotFoundError("no such formula version in this organization")
    return dict(row)


def _load_components(
    session: Session, *, version_id: uuid.UUID, organization_id: uuid.UUID
) -> list[dict[str, Any]]:
    """A version's lines, with every material property the engine needs.

    `COALESCE(role_override, m.role)` resolves the role HERE, in SQL,
    rather than in the engine or in a template. The vocabulary lives in
    one table and the precedence rule lives in one expression.
    """
    rows = session.execute(
        text(
            """
            SELECT c.id, c.material_id, c.percentage, c.role_override,
                   c.display_order, c.notes,
                   m.material_code, m.name AS material_name, m.category,
                   m.status AS material_status,
                   COALESCE(c.role_override, m.role) AS effective_role,
                   m.density_g_cm3, m.solids_fraction, m.voc_fraction,
                   m.cost_per_kg, m.requires_sds,
                   (SELECT count(*) FROM materials.material_documents d
                     WHERE d.material_id = m.id AND d.document_type = 'SDS') AS sds_count
            FROM formulations.formula_components c
            JOIN materials.materials m
              ON m.id = c.material_id AND m.organization_id = c.organization_id
            WHERE c.formula_version_id = :vid AND c.organization_id = :org
            ORDER BY c.display_order, m.material_code
            """
        ),
        {"vid": version_id, "org": organization_id},
    ).mappings()
    return [dict(r) for r in rows]


def _to_engine_components(rows: list[dict[str, Any]]) -> list[Component]:
    """Database rows to engine inputs, with no conversion of quantities.

    Every numeric column is NUMERIC in PostgreSQL and arrives as a
    `Decimal`, so nothing here casts, rounds or reformats. That is the
    whole reason the columns are NUMERIC: a float on this boundary would
    be refused by `Component.__post_init__`, which is the check working
    rather than an inconvenience.
    """
    return [
        Component(
            material_code=r["material_code"],
            percentage=r["percentage"],
            role=r["effective_role"],
            density_g_cm3=r["density_g_cm3"],
            solids_fraction=r["solids_fraction"],
            voc_fraction=r["voc_fraction"],
            cost_per_kg=r["cost_per_kg"],
        )
        for r in rows
    ]


def _safety_checks(rows: list[dict[str, Any]]) -> tuple[str, ...]:
    """Critical safety checks that have FAILED, as sentences.

    Passed INTO the engine rather than evaluated there: safety is a domain
    rule over hazard data, not arithmetic, and `validate_for_submission`
    says so in its own docstring.

    Today there is one check, and it is a real one rather than a
    placeholder: a material flagged `requires_sds` with no SDS document on
    file. A formulation containing a hazardous material whose safety data
    sheet nobody has filed is exactly the state that must not reach a
    laboratory bench, and section 8 says this block cannot be waived at
    submission.
    """
    return tuple(
        f"{r['material_code']} requires a safety data sheet and none is on file"
        for r in rows
        if r["requires_sds"] and r["sds_count"] == 0
    )


def _try(fn: Any) -> dict[str, Any]:
    """Run one engine calculation, reporting refusal as a stated reason.

    NOT a swallowed exception. The engine raises with a message naming the
    material and the missing property -- "density unknown for: RM-FIL-07"
    -- and that sentence is the most useful thing the screen can show. It
    is carried through as `unavailable_reason`, so the caller can never
    mistake a missing property for a computed zero.
    """
    try:
        return {"value": fn(), "unavailable_reason": None}
    except (ValueError, ZeroDivisionError) as exc:
        return {"value": None, "unavailable_reason": str(exc)}
