"""Material Safety Data — reading a safety data sheet into structured facts,
and working out what a revision hit.

🔴 THE THREE RULES THIS MODULE OBEYS, AND WHERE THEY CAME FROM

**1. The document is not ours.** `materials.material_documents` owns the SDS
file, its bytes, its checksum, its scanner verdict, its revision chain and its
classification. `materials.usable_documents` (037) is the ONE definition of a
document that may be relied on, and the formula-submission gate reads it. This
module stores what a sheet SAYS and never re-decides whether it may be relied
on. 037's own header records that four queries in two modules had already
disagreed about that once.

**2. Currency is derived, never stored.** There is no `status` column on
`safety.sds_versions`. Every query that answers *"what is the safety position
now"* joins `materials.usable_documents`. `review_state` describes the human
review workflow and is named so it cannot be mistaken for the other question.

**3. This module reports record state. It does not assess hazard.**
`app/agents/tools/safety.py` established the rule and it binds here too:

    "RM-104 is `restricted`, the reason on file is X, its SDS is missing" are
    facts read out of columns. "RM-104 is safe to use at 4%" is a compliance
    determination, and nothing here produces one.

So `compare_revisions` reports that H317 was added. It does not report that
anything became dangerous. That judgement belongs to the `compliance.review_sds`
holder, through the approval route this module opens for them.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from app.core.audit import AuditEvent, write_audit
from app.core.db import guarded_write
from app.core.notifications import notify
from app.domains.approvals.service import (
    ApprovalError,
    ApprovalNotFoundError,
    open_route,
    route_for_entity,
)
from app.domains.events.service import SAFETY_REVIEW_REQUIRED
from app.domains.events.service import emit as emit_domain_event
from app.domains.formulations.service import safety_blocks
from app.domains.materials.service import material_usage

__all__ = [
    "ComponentInput",
    "HazardInput",
    "MaterialSafetyError",
    "MaterialSafetyNotFoundError",
    "MaterialSafetyStateError",
    "SdsInterpretation",
    "SectionInput",
    "acknowledge_alert",
    "compare_revisions",
    "confirm_interpretation",
    "current_safety_position",
    "impact_of_revision",
    "interpret_sds",
    "list_alerts",
    "list_comparable_revisions",
    "list_interpretable_documents",
    "list_interpretations_for_material",
    "list_pending_interpretations",
    "on_formula_version_created",
    "open_safety_review",
    "raise_alerts_for_revision",
    "safety_review_status",
]


class MaterialSafetyError(RuntimeError):
    """A safety record could not be written as asked."""


class MaterialSafetyNotFoundError(MaterialSafetyError):
    """The record does not exist, or the caller cannot reach it."""


class MaterialSafetyStateError(MaterialSafetyError):
    """The record exists but is not in a state that allows this."""


# 🔴 THE TWO FORMULA-VERSION STATES A SAFETY ALERT MUST NOT FIRE ON.
#
# Measured from `formula_versions`'s own CHECK, not assumed: the vocabulary is
# draft / submitted / approved / rejected / superseded / released. A `rejected`
# or `superseded` version is abandoned work, and alerting on it sends a lead to
# look at something nobody is going to make. Everything else is kept -- a DRAFT
# containing a newly hazardous material is exactly what a chemist needs told.
_INACTIVE_VERSION_STATES = frozenset({"rejected", "superseded"})


def _translate(exc: DBAPIError) -> MaterialSafetyError:
    """Turn a PostgreSQL refusal into an answer a client can act on.

    🔴 `DBAPIError`, NOT `IntegrityError`. The S1a trigger refuses with
    `RAISE EXCEPTION`, which psycopg surfaces as `RaiseException` -- a
    `DBAPIError` that is **not** an `IntegrityError`. An earlier version caught
    only `IntegrityError`, so the single most important refusal in this module
    -- "that document is not usable" -- escaped as an unhandled 500 while the
    docstring claimed it was translated into a friendly message.

    The distinction between the three outcomes is kept because a client acts on
    each differently: 409 means "it is there and this is not a thing you may do
    to it now", 422 means "send different input", 404 means "it is not there".
    """
    detail = str(getattr(exc, "orig", exc))

    if "sds_versions_document_key" in detail:
        return MaterialSafetyStateError(
            "this document has already been interpreted. A second reading of "
            "the same sheet is a correction, not a new fact -- two rows would "
            "leave 'what does this SDS say' with two answers."
        )
    if "safety_reviews_one_per_project" in detail:
        return MaterialSafetyStateError(
            "a safety review for this revision already exists on this project. "
            "A second would let two people decide the same change with no "
            "answer to which governed."
        )
    if "not a usable document" in detail or "not an SDS" in detail:
        return MaterialSafetyStateError(detail.strip().splitlines()[0])
    if "belongs to material" in detail:
        return MaterialSafetyStateError(detail.strip().splitlines()[0])
    if "sds_sections_one_per_number" in detail:
        return MaterialSafetyError(
            "the same SDS section number was supplied twice. The sixteen "
            "sections are a standard, and one sheet has one of each."
        )
    if "chemical_components_range_ordered" in detail:
        return MaterialSafetyError(
            "a component's concentration range is inverted: the upper bound is "
            "below the lower bound."
        )
    if "row-level security" in detail:
        # Not a 404: the caller may not be told whether the project exists.
        return MaterialSafetyStateError("this record names a project you do not have access to.")
    return MaterialSafetyError(detail)


def _decimal_strings(row: Any) -> dict[str, Any]:
    """Every `Decimal` in the row as a string; everything else untouched.

    🔴 WITHOUT THIS, `NUMERIC` LEAVES THE API AS A FLOAT.

    FastAPI's `jsonable_encoder` maps `Decimal` to **float**, so a
    `NUMERIC(7,4)` concentration of 10.0000 arrives as `10.0` -- CLAUDE.md §5
    forbids float on a controlled record, the stored scale is lost, and the
    client's `z.string()` throws `Expected string, received number`, taking the
    whole screen down for any material that has a disclosed concentration.

    That is I84, and this module reintroduced it: `formulations`, `laboratory`
    and `testing` each carry this helper and apply it at 36 call sites between
    them, and this one applied it at none. The live suite passed anyway because
    the demonstration database holds no interpreted sheets yet, so the field
    was never populated -- a path no test had exercised.

    Duplicated here rather than imported for the same reason the other three
    duplicate it: importing across domain services is the cross-domain
    dependency §0.3 forbids. If a fourth copy appears, promote it to `core`.
    """
    return {
        key: (str(value) if isinstance(value, Decimal) else value) for key, value in row.items()
    }


# ---------------------------------------------------------------------------
# Inputs
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class SectionInput:
    section_number: int
    heading: str
    body: str | None = None


@dataclass(frozen=True, slots=True)
class HazardInput:
    hazard_class: str
    hazard_category: str | None = None
    hazard_code: str | None = None
    signal_word: str | None = None
    statement: str | None = None


@dataclass(frozen=True, slots=True)
class ComponentInput:
    component_name: str
    cas_number: str | None = None
    ec_number: str | None = None
    # NUMERIC in the database, and a RANGE rather than a value. An SDS
    # discloses "10-25%"; storing a midpoint would invent a precision the
    # manufacturer deliberately withheld.
    concentration_low: str | None = None
    concentration_high: str | None = None


@dataclass(frozen=True, slots=True)
class SdsInterpretation:
    supplier_revision: str | None = None
    manufacturer: str | None = None
    effective_date: str | None = None
    sections: tuple[SectionInput, ...] = field(default_factory=tuple)
    hazards: tuple[HazardInput, ...] = field(default_factory=tuple)
    components: tuple[ComponentInput, ...] = field(default_factory=tuple)


# ---------------------------------------------------------------------------
# Writing an interpretation
# ---------------------------------------------------------------------------


def interpret_sds(
    session: Session,
    *,
    organization_id: uuid.UUID,
    actor_id: uuid.UUID,
    document_id: uuid.UUID,
    material_id: uuid.UUID,
    spec: SdsInterpretation,
) -> dict[str, Any]:
    """Record what one SDS revision says.

    🔴 THE USABILITY RULE IS NOT ENFORCED HERE, AND THAT IS DELIBERATE.

    A `BEFORE INSERT` trigger on `safety.sds_versions` refuses a document that
    `materials.usable_documents` does not return, refuses a document that is not
    an SDS, and refuses a document/material mismatch. It lives in the database
    because a check in this function is not a rule the database has: the db
    suite, and anything else holding the `evercoat_app` connection, issues
    INSERTs this function never sees.

    What happens here is the translation of the trigger's message into a
    domain error, so a route can answer 422 instead of leaking a PL/pgSQL
    exception to a browser.

    🔴 THE PARENT AND ITS CHILDREN ARE IN **ONE** SAVEPOINT.

    They were in two. Savepoint A had already released by the time B rolled
    back, so a caller that caught the refusal and committed its own work left
    an `sds_versions` row with no sections, hazards or components -- holding
    `sds_versions_document_key`, which made that sheet permanently
    un-interpretable ("this document has already been interpreted"). Over HTTP
    the request rollback hid it; `guarded_write` exists precisely so a §12
    composing caller CAN continue after catching a refusal, which is when it
    would have bitten. Found by the Supervisor review.

    One sheet is one reading: a partial interpretation is not a state this
    schema should be able to hold.

    ⚠️ THE INTERPRETATION LANDS AS `pending_review`. The specification is
    explicit: *"Where a document cannot be reliably interpreted automatically,
    the information shall remain pending technical review rather than being
    treated as confirmed safety data."* Nothing in this module promotes it;
    `confirm_interpretation` is a separate, permissioned act.
    """
    # 🔴 A SAVEPOINT, NOT A BARE `try`. `Session.rollback()` rolls back the
    # TOPMOST transaction, so a duplicate-document refusal caught here would
    # otherwise destroy whatever the caller had already done -- and this
    # function is exactly the kind §12 pushes other modules to compose with.
    # `test_no_transaction_destroyers` found both call sites in this file.
    try:
        with guarded_write(session):
            version_id = session.execute(
                text(
                    """
                    INSERT INTO safety.sds_versions
                        (organization_id, document_id, material_id, supplier_revision,
                         manufacturer, effective_date, interpreted_by)
                    VALUES (:org, :doc, :mat, :rev, :manufacturer,
                            CAST(:effective AS DATE), :actor)
                    RETURNING id
                    """
                ),
                {
                    "org": organization_id,
                    "doc": document_id,
                    "mat": material_id,
                    "rev": spec.supplier_revision,
                    "manufacturer": spec.manufacturer,
                    "effective": spec.effective_date,
                    "actor": actor_id,
                },
            ).scalar_one()

            for section in spec.sections:
                session.execute(
                    text(
                        """
                        INSERT INTO safety.sds_sections
                            (organization_id, sds_version_id, section_number, heading, body)
                        VALUES (:org, :vid, :number, :heading, :body)
                        """
                    ),
                    {
                        "org": organization_id,
                        "vid": version_id,
                        "number": section.section_number,
                        "heading": section.heading,
                        "body": section.body,
                    },
                )

            for hazard in spec.hazards:
                session.execute(
                    text(
                        """
                        INSERT INTO safety.hazard_classifications
                            (organization_id, sds_version_id, hazard_class, hazard_category,
                             hazard_code, signal_word, statement)
                        VALUES (:org, :vid, :cls, :cat, :code, :signal, :statement)
                        """
                    ),
                    {
                        "org": organization_id,
                        "vid": version_id,
                        "cls": hazard.hazard_class,
                        "cat": hazard.hazard_category,
                        "code": hazard.hazard_code,
                        "signal": hazard.signal_word,
                        "statement": hazard.statement,
                    },
                )

            for component in spec.components:
                session.execute(
                    text(
                        """
                        INSERT INTO safety.chemical_components
                            (organization_id, sds_version_id, component_name, cas_number,
                             ec_number, concentration_low, concentration_high)
                        VALUES (:org, :vid, :name, :cas, :ec,
                                CAST(:low AS NUMERIC), CAST(:high AS NUMERIC))
                        """
                    ),
                    {
                        "org": organization_id,
                        "vid": version_id,
                        "name": component.component_name,
                        "cas": component.cas_number,
                        "ec": component.ec_number,
                        "low": component.concentration_low,
                        "high": component.concentration_high,
                    },
                )
    except DBAPIError as exc:
        raise _translate(exc) from exc

    write_audit(
        session,
        AuditEvent(
            action="SDS_INTERPRETED",
            entity_type="sds_version",
            entity_id=str(version_id),
            organization_id=organization_id,
            user_id=actor_id,
            # Counts, not contents. SECURITY.md §11 forbids payload logging,
            # and a hazard statement copied into the audit log is exactly the
            # kind of payload it means.
            new_state={
                "document_id": str(document_id),
                "sections": len(spec.sections),
                "hazards": len(spec.hazards),
                "components": len(spec.components),
                "review_state": "pending_review",
            },
        ),
    )

    return {"id": version_id, "review_state": "pending_review"}


def confirm_interpretation(
    session: Session,
    *,
    organization_id: uuid.UUID,
    reviewer_id: uuid.UUID,
    sds_version_id: uuid.UUID,
    accept: bool,
) -> dict[str, Any]:
    """Move an interpretation out of `pending_review`.

    The permission (`compliance.review_sds`) is enforced at the route. This
    function enforces the STATE rule: an interpretation may be reviewed once.
    Re-confirming would overwrite who reviewed it and when, and a safety record
    whose reviewer can be silently replaced is not a controlled record.
    """
    row = (
        session.execute(
            text(
                """
                UPDATE safety.sds_versions
                   SET review_state = CASE WHEN :accept THEN 'confirmed' ELSE 'rejected' END,
                       reviewed_by  = :reviewer,
                       reviewed_at  = clock_timestamp()
                 WHERE id = :vid AND organization_id = :org
                   AND review_state = 'pending_review'
                RETURNING id, review_state, reviewed_at
                """
            ),
            {
                "vid": sds_version_id,
                "org": organization_id,
                "reviewer": reviewer_id,
                "accept": accept,
            },
        )
        .mappings()
        .one_or_none()
    )
    if row is None:
        raise MaterialSafetyNotFoundError(
            "no interpretation awaiting review with that id. It may not exist, "
            "may belong to another organization, or may already have been reviewed."
        )

    write_audit(
        session,
        AuditEvent(
            action="SAFETY_REVIEWED",
            entity_type="sds_version",
            entity_id=str(sds_version_id),
            organization_id=organization_id,
            user_id=reviewer_id,
            new_state={"review_state": row["review_state"]},
        ),
    )
    return dict(row)


# ---------------------------------------------------------------------------
# Reading — currency is ALWAYS a join to materials.usable_documents
# ---------------------------------------------------------------------------


def current_safety_position(
    session: Session, *, organization_id: uuid.UUID, material_id: uuid.UUID
) -> dict[str, Any]:
    """What is on file for this material RIGHT NOW.

    🔴 THE JOIN TO `materials.usable_documents` IS THE WHOLE ANSWER (S1c).

    An interpretation whose document has been superseded, has expired, or whose
    scan verdict is not clean is HISTORY -- readable by `compare_revisions`,
    never shown as the current position. That distinction is not stored
    anywhere in `safety.*`, on purpose: a stored flag would be a second opinion
    about document currency, and 037 exists because two modules had already
    disagreed about that.

    Returns the current interpretation or `None` for it, plus the material-level
    rules, which are NOT revision-scoped -- "store below 25 °C" is a fact about
    the substance in the drum and must not expire when a new sheet arrives.
    """
    current = (
        session.execute(
            text(
                """
                SELECT v.id, v.document_id, v.supplier_revision, v.manufacturer,
                       v.effective_date, v.review_state, v.reviewed_at, v.created_at,
                       d.title AS document_title, d.issued_on, d.expires_on
                  FROM safety.sds_versions v
                  -- 🔴 NOT material_documents. The VIEW is the definition.
                  JOIN materials.usable_documents d
                    ON d.id = v.document_id AND d.organization_id = v.organization_id
                 WHERE v.organization_id = :org AND v.material_id = :mat
                 ORDER BY v.created_at DESC
                 LIMIT 1
                """
            ),
            {"org": organization_id, "mat": material_id},
        )
        .mappings()
        .one_or_none()
    )

    hazards: list[dict[str, Any]] = []
    components: list[dict[str, Any]] = []
    if current is not None:
        hazards = [
            dict(r)
            for r in session.execute(
                text(
                    """
                    SELECT hazard_class, hazard_category, hazard_code,
                           signal_word, statement
                      FROM safety.hazard_classifications
                     WHERE sds_version_id = :vid AND organization_id = :org
                     ORDER BY hazard_code NULLS LAST, hazard_class
                    """
                ),
                {"vid": current["id"], "org": organization_id},
            ).mappings()
        ]
        components = [
            _decimal_strings(r)
            for r in session.execute(
                text(
                    """
                    SELECT component_name, cas_number, ec_number,
                           concentration_low, concentration_high
                      FROM safety.chemical_components
                     WHERE sds_version_id = :vid AND organization_id = :org
                     ORDER BY concentration_high DESC NULLS LAST, component_name
                    """
                ),
                {"vid": current["id"], "org": organization_id},
            ).mappings()
        ]

    storage = [
        _decimal_strings(r)
        for r in session.execute(
            text(
                """
                SELECT id, min_temperature_c, max_temperature_c, segregation_class,
                       shelf_life_months, requirement
                  FROM safety.storage_rules
                 WHERE organization_id = :org AND material_id = :mat
                 ORDER BY created_at
                """
            ),
            {"org": organization_id, "mat": material_id},
        ).mappings()
    ]

    incompatibilities = [
        dict(r)
        for r in session.execute(
            text(
                """
                SELECT i.id, i.severity, i.consequence, i.incompatible_hazard_class,
                       m.material_code AS incompatible_material_code,
                       m.name          AS incompatible_material_name
                  FROM safety.incompatibility_rules i
                  LEFT JOIN materials.materials m
                    ON m.id = i.incompatible_with_material_id
                   AND m.organization_id = i.organization_id
                 WHERE i.organization_id = :org AND i.material_id = :mat
                 ORDER BY CASE i.severity WHEN 'prohibited' THEN 0
                                          WHEN 'segregate'  THEN 1
                                          ELSE 2 END
                """
            ),
            {"org": organization_id, "mat": material_id},
        ).mappings()
    ]

    return {
        # `None` is a real, meaningful answer and the screen must say so
        # plainly: "no usable SDS is on file" is the ACTIONABLE fact, and it is
        # exactly what `agents/tools/safety.py` reports rather than hiding.
        "current": dict(current) if current is not None else None,
        "hazards": hazards,
        "components": components,
        "storage_rules": storage,
        "incompatibilities": incompatibilities,
    }


def list_comparable_revisions(
    session: Session, *, organization_id: uuid.UUID, limit: int = 100
) -> list[dict[str, Any]]:
    """Materials with at least two readings: the newest, and the one before it.

    🔴 THIS IS WHAT MAKES `POST .../alerts` PRESSABLE.

    Raising alerts needs TWO interpretation ids of the same material -- the
    revision and its predecessor. Nothing in the browser could supply that pair
    without asking a person to paste two UUIDs, so the route had a hook and no
    button, which is the same defect as having no hook at all.

    Ordered newest-first per material with a window function rather than one
    query per material: the alternative is N+1 requests on a page that may list
    every material in the organization, which is the reason `list_tests` gives
    for withholding statistics.
    """
    return [
        dict(r)
        for r in session.execute(
            text(
                """
                WITH ranked AS (
                    SELECT v.id, v.material_id, v.supplier_revision, v.created_at,
                           v.review_state,
                           row_number() OVER (PARTITION BY v.material_id
                                              ORDER BY v.created_at DESC) AS rn
                      FROM safety.sds_versions v
                     WHERE v.organization_id = :org
                )
                SELECT cur.id            AS current_id,
                       cur.supplier_revision AS current_revision,
                       cur.review_state  AS current_review_state,
                       prev.id           AS previous_id,
                       prev.supplier_revision AS previous_revision,
                       m.id              AS material_id,
                       m.material_code, m.name AS material_name
                  FROM ranked cur
                  JOIN ranked prev
                    ON prev.material_id = cur.material_id AND prev.rn = 2
                  JOIN materials.materials m
                    ON m.id = cur.material_id AND m.organization_id = :org
                 WHERE cur.rn = 1
                 ORDER BY m.material_code
                 LIMIT :limit
                """
            ),
            {"org": organization_id, "limit": limit},
        ).mappings()
    ]


def list_interpretable_documents(
    session: Session, *, organization_id: uuid.UUID, limit: int = 200
) -> list[dict[str, Any]]:
    """Usable SDS documents that have not been interpreted yet.

    🔴 THIS EXISTS SO THE WRITE IS PRESSABLE WITHOUT TYPING A UUID.

    `POST /interpretations` needs a `document_id` and a `material_id`. Without
    this, the only way to use it from a browser would be to paste two UUIDs --
    which this project has already recorded as a defect once, on the screen that
    adds a project member. A control a person cannot realistically operate is
    not a caller.

    Reads `materials.usable_documents`, so it offers only documents that could
    actually be interpreted: the S1a trigger would refuse anything else, and
    offering a choice the database will reject is a form that lies.
    """
    return [
        dict(r)
        for r in session.execute(
            text(
                """
                SELECT d.id AS document_id, d.material_id, d.title, d.issued_on,
                       d.expires_on, m.material_code, m.name AS material_name
                  FROM materials.usable_documents d
                  JOIN materials.materials m
                    ON m.id = d.material_id AND m.organization_id = d.organization_id
                 WHERE d.organization_id = :org
                   AND d.document_type = 'SDS'
                   AND NOT EXISTS (
                       SELECT 1 FROM safety.sds_versions v
                        WHERE v.document_id = d.id AND v.organization_id = d.organization_id)
                 ORDER BY m.material_code, d.issued_on DESC NULLS LAST
                 LIMIT :limit
                """
            ),
            {"org": organization_id, "limit": limit},
        ).mappings()
    ]


def list_interpretations_for_material(
    session: Session, *, organization_id: uuid.UUID, material_id: uuid.UUID
) -> list[dict[str, Any]]:
    """Every interpretation for a material, newest first — history included.

    Deliberately NOT joined to `usable_documents`: this is the list a reviewer
    picks two entries from in order to COMPARE them, and the previous revision
    has by definition left that view. `current_safety_position` is the query
    that answers "what is on file now"; this one answers "what has been read".
    """
    return [
        dict(r)
        for r in session.execute(
            text(
                """
                SELECT v.id, v.supplier_revision, v.manufacturer, v.effective_date,
                       v.review_state, v.created_at,
                       (u.id IS NOT NULL) AS is_current
                  FROM safety.sds_versions v
                  LEFT JOIN materials.usable_documents u
                    ON u.id = v.document_id AND u.organization_id = v.organization_id
                 WHERE v.organization_id = :org AND v.material_id = :mat
                 ORDER BY v.created_at DESC
                """
            ),
            {"org": organization_id, "mat": material_id},
        ).mappings()
    ]


def list_pending_interpretations(
    session: Session, *, organization_id: uuid.UUID, limit: int = 100
) -> list[dict[str, Any]]:
    """Interpretations awaiting technical review."""
    return [
        dict(r)
        for r in session.execute(
            text(
                """
                SELECT v.id, v.material_id, v.supplier_revision, v.manufacturer,
                       v.effective_date, v.created_at,
                       m.material_code, m.name AS material_name
                  FROM safety.sds_versions v
                  JOIN materials.materials m
                    ON m.id = v.material_id AND m.organization_id = v.organization_id
                 WHERE v.organization_id = :org AND v.review_state = 'pending_review'
                 ORDER BY v.created_at
                 LIMIT :limit
                """
            ),
            {"org": organization_id, "limit": limit},
        ).mappings()
    ]


# ---------------------------------------------------------------------------
# Revision comparison — the reason interpretations outlive their documents
# ---------------------------------------------------------------------------


def compare_revisions(
    session: Session,
    *,
    organization_id: uuid.UUID,
    previous_version_id: uuid.UUID,
    current_version_id: uuid.UUID,
) -> dict[str, Any]:
    """What changed between two interpretations of the same material's sheets.

    🔴 THIS IS WHY INTERPRETATIONS SURVIVE SUPERSESSION (S1b).

    `materials.usable_documents` EXCLUDES a document that a newer approved
    revision supersedes (037:79-84). So the previous revision leaves that view
    the instant the new one is approved -- and comparing them is the entire
    point of the feature. If this module had deleted or invalidated the old
    interpretation, revision comparison would have become impossible at exactly
    the moment it became possible.

    ⚠️ IT REPORTS CHANGES, NOT CONSEQUENCES. "H317 was added" is a fact.
    "This is now unsafe" is a compliance determination and belongs to the
    `compliance.review_sds` holder -- the rule `agents/tools/safety.py` set and
    this module inherits.
    """
    materials = session.execute(
        text(
            """
            SELECT id, material_id FROM safety.sds_versions
             WHERE organization_id = :org AND id IN (:previous, :current)
            """
        ),
        {"org": organization_id, "previous": previous_version_id, "current": current_version_id},
    ).mappings()
    seen = {row["id"]: row["material_id"] for row in materials}

    for name, wanted in (("previous", previous_version_id), ("current", current_version_id)):
        if wanted not in seen:
            raise MaterialSafetyNotFoundError(f"no {name} interpretation with id {wanted}")

    # Comparing two different materials' sheets would produce a plausible,
    # meaningless diff -- every component "added", every hazard "removed".
    if seen[previous_version_id] != seen[current_version_id]:
        raise MaterialSafetyStateError(
            "those interpretations belong to different materials; comparing "
            "them would report every component as added and every hazard as "
            "removed, which describes nothing"
        )

    def _components(version_id: uuid.UUID) -> dict[str, dict[str, Any]]:
        rows = session.execute(
            text(
                """
                SELECT component_name, cas_number, concentration_low, concentration_high
                  FROM safety.chemical_components
                 WHERE sds_version_id = :vid AND organization_id = :org
                """
            ),
            {"vid": version_id, "org": organization_id},
        ).mappings()
        # Keyed on CAS where there is one -- a manufacturer may rename a
        # component between revisions without changing the substance, and a
        # name-keyed diff would report that as one removal and one addition.
        return {(r["cas_number"] or r["component_name"]): _decimal_strings(r) for r in rows}

    def _hazards(version_id: uuid.UUID) -> dict[str, dict[str, Any]]:
        rows = session.execute(
            text(
                """
                SELECT hazard_class, hazard_category, hazard_code, signal_word, statement
                  FROM safety.hazard_classifications
                 WHERE sds_version_id = :vid AND organization_id = :org
                """
            ),
            {"vid": version_id, "org": organization_id},
        ).mappings()
        return {(r["hazard_code"] or r["hazard_class"]): dict(r) for r in rows}

    before_components, after_components = (
        _components(previous_version_id),
        _components(current_version_id),
    )
    before_hazards, after_hazards = _hazards(previous_version_id), _hazards(current_version_id)

    changed_concentrations = [
        {
            "key": key,
            "component_name": after_components[key]["component_name"],
            "previous_low": before_components[key]["concentration_low"],
            "previous_high": before_components[key]["concentration_high"],
            "current_low": after_components[key]["concentration_low"],
            "current_high": after_components[key]["concentration_high"],
        }
        for key in before_components.keys() & after_components.keys()
        if (
            before_components[key]["concentration_low"]
            != after_components[key]["concentration_low"]
            or before_components[key]["concentration_high"]
            != after_components[key]["concentration_high"]
        )
    ]

    # 🔴 A HAZARD THAT STAYS BUT GETS WORSE IS A CHANGE, AND IT WAS BEING
    # REPORTED AS "no substantive change".
    #
    # The diff below compares key SETS only, and the key is `hazard_code or
    # hazard_class`. So a revision that keeps H317 while moving it from
    # Category 2 / Warning to **Category 1A / Danger** produced five empty
    # lists, `_summarise` said "no substantive change", no alert was raised,
    # and the screen told the reviewer nothing had happened -- about a hazard
    # SEVERITY INCREASE, which is the single most important thing this module
    # exists to surface. Components already had an attribute diff; hazards had
    # none. Found by the Supervisor review.
    escalations = [
        {
            "key": key,
            "hazard_class": after_hazards[key]["hazard_class"],
            "hazard_code": after_hazards[key]["hazard_code"],
            "previous_category": before_hazards[key]["hazard_category"],
            "current_category": after_hazards[key]["hazard_category"],
            "previous_signal_word": before_hazards[key]["signal_word"],
            "current_signal_word": after_hazards[key]["signal_word"],
        }
        for key in before_hazards.keys() & after_hazards.keys()
        if (
            before_hazards[key]["hazard_category"] != after_hazards[key]["hazard_category"]
            or before_hazards[key]["signal_word"] != after_hazards[key]["signal_word"]
            or before_hazards[key]["statement"] != after_hazards[key]["statement"]
        )
    ]

    return {
        "material_id": seen[current_version_id],
        "components_added": [
            after_components[k] for k in after_components.keys() - before_components.keys()
        ],
        "components_removed": [
            before_components[k] for k in before_components.keys() - after_components.keys()
        ],
        "concentrations_changed": changed_concentrations,
        "hazards_added": [after_hazards[k] for k in after_hazards.keys() - before_hazards.keys()],
        "hazards_removed": [
            before_hazards[k] for k in before_hazards.keys() - after_hazards.keys()
        ],
        "hazards_changed": escalations,
    }


def _summarise(change: dict[str, Any]) -> str:
    """One line describing a revision's changes, for an alert.

    Deliberately mechanical. A generated sentence that characterised the change
    ("this revision makes the resin more hazardous") would be the hazard
    assessment this module is forbidden to perform.
    """
    parts: list[str] = []
    for label, key in (
        ("component(s) added", "components_added"),
        ("component(s) removed", "components_removed"),
        ("concentration range(s) changed", "concentrations_changed"),
        ("hazard classification(s) added", "hazards_added"),
        ("hazard classification(s) removed", "hazards_removed"),
        # Separate from added/removed because "H317 became Danger" is not
        # "H317 appeared", and a reviewer needs to know which.
        ("hazard classification(s) changed in severity", "hazards_changed"),
    ):
        count = len(change[key])
        if count:
            parts.append(f"{count} {label}")
    return "; ".join(parts) if parts else "no substantive change"


# ---------------------------------------------------------------------------
# Impact — §23's chain
# ---------------------------------------------------------------------------


def impact_of_revision(
    session: Session, *, organization_id: uuid.UUID, sds_version_id: uuid.UUID
) -> dict[str, Any]:
    """Which formulas, projects and open batches a revised sheet reaches.

    🔴 HOPS 1 AND 2 ARE `materials.material_usage()`, NOT A NEW QUERY.

    That function (domains/materials/service.py:771) already answers *"which
    formula versions use this material, and in which projects"*, is already
    RLS-scoped, and is already served by `formula_components_material_idx`. It
    is also the query an approver relies on before restricting a material.
    Writing a second component join here would be the duplication CLAUDE.md §12
    forbids, and the two would drift.

    ⚠️ NOT `agents/tools/safety.py:formulas_containing`, which does the same
    join on a FUZZY STRING for the assistant. An impact analysis that matched
    materials by ILIKE would silently miss "RM-104" when asked about "RM-1040",
    or over-report the reverse. This is keyed on the id.

    ⚠️ RLS MEANS THIS ANSWER IS THE CALLER'S ANSWER. A restricted project the
    caller is not a member of is invisible here, exactly as `material_usage`
    documents. That is intended: the alert is raised per project, and a project
    the caller cannot see is not theirs to be alerted about. The reviewer who
    CAN see it gets the alert through their own session.
    """
    material_id = session.execute(
        text(
            "SELECT material_id FROM safety.sds_versions WHERE id = :vid AND organization_id = :org"
        ),
        {"vid": sds_version_id, "org": organization_id},
    ).scalar_one_or_none()
    if material_id is None:
        raise MaterialSafetyNotFoundError(f"no interpretation with id {sds_version_id}")

    all_usage = material_usage(session, material_id=material_id, organization_id=organization_id)

    # 🔴 `material_usage` RETURNS EVERY VERSION, NOT THE ACTIVE ONES, AND AN
    # EARLIER COMMENT HERE CLAIMED OTHERWISE.
    #
    # Codex measured it: `materials/service.py:771` filters on `material_id`
    # alone and returns `version_status` for the caller to interpret. It is
    # right not to filter -- it exists to answer "what would restricting this
    # material invalidate", which needs the drafts too.
    #
    # But §23's chain says *"find every ACTIVE formula using RM-0042"*, and
    # raising a project alert off a `superseded` or `rejected` version would
    # send somebody to look at work that was abandoned. The vocabulary is
    # draft/submitted/approved/rejected/superseded/released, measured from
    # `formula_versions`'s own CHECK; the two terminal-and-irrelevant states
    # are excluded and the rest kept, because a DRAFT containing a newly
    # hazardous material is exactly what a chemist needs told.
    usage = [row for row in all_usage if row["version_status"] not in _INACTIVE_VERSION_STATES]

    # 🔴 BATCHES ARE LOOKED UP ACROSS **EVERY** VERSION, NOT ONLY ACTIVE ONES.
    #
    # Codex argued the opposite case and won it: a `superseded` formula version
    # can still have an `authorized` or `in_progress` laboratory batch. Somebody
    # is physically making that material right now. Filtering the version before
    # asking about batches would hide exactly the live exposure a safety alert
    # exists to surface -- lifecycle retirement of a RECIPE is not proof that
    # PHYSICAL WORK stopped.
    #
    # So `usage` (active only) drives the "which formulas" answer, and
    # `all_usage` drives the "which batches are open" one. They are different
    # questions and they get different inputs.
    version_ids = [row["formula_version_id"] for row in all_usage]
    batches: list[dict[str, Any]] = []
    if version_ids:
        batches = [
            dict(r)
            for r in session.execute(
                text(
                    """
                    SELECT b.id, b.batch_number, b.status, b.formula_version_id,
                           f.project_id
                      FROM laboratory.batches b
                      JOIN formulations.formula_versions v
                        ON v.id = b.formula_version_id AND v.organization_id = b.organization_id
                      JOIN formulations.formulas f
                        ON f.id = v.formula_id AND f.organization_id = v.organization_id
                     WHERE b.organization_id = :org
                       AND b.formula_version_id = ANY(:versions)
                       -- OPEN batches only: a finished batch cannot be
                       -- stopped, and alerting about it buries the ones
                       -- somebody can still act on.
                       --
                       -- 🔴 EXPRESSED AS AN EXCLUSION, NOT AN INCLUSION, AND
                       -- THAT IS THE SAFE DIRECTION HERE. The vocabulary is
                       -- draft / authorized / in_progress / completed /
                       -- accepted / rejected / cancelled (measured from the
                       -- CHECK, not assumed -- an earlier draft of this query
                       -- omitted `accepted` because it guessed the list). If a
                       -- status is added later, an exclusion counts it as open
                       -- and somebody sees an alert they may not need; an
                       -- inclusion would silently drop it and somebody would
                       -- not see an alert they did need. For a safety alert
                       -- the first failure is the one to prefer.
                       AND b.status NOT IN ('completed', 'accepted', 'rejected', 'cancelled')
                    """
                ),
                {"org": organization_id, "versions": version_ids},
            ).mappings()
        ]

    # A project qualifies if it has an ACTIVE version, or an OPEN BATCH on any
    # version. The second half is what keeps a retired recipe's live batch from
    # disappearing from the alert.
    projects = sorted(
        {row["project_id"] for row in usage if row["project_id"] is not None}
        | {b["project_id"] for b in batches if b["project_id"] is not None}
    )

    return {
        "material_id": material_id,
        "formula_versions": usage,
        # Stated so a caller can tell "nothing uses this" from "everything that
        # uses it is retired" -- two very different answers to give a reviewer.
        "inactive_versions_excluded": len(all_usage) - len(usage),
        "projects": projects,
        "open_batches": batches,
    }


def raise_alerts_for_revision(
    session: Session,
    *,
    organization_id: uuid.UUID,
    actor_id: uuid.UUID,
    sds_version_id: uuid.UUID,
    previous_version_id: uuid.UUID,
) -> list[dict[str, Any]]:
    """Compare, find what is affected, and raise one alert per project.

    Per PROJECT rather than per formula version, because a project lead who
    reads "eleven alerts" acts on none of them. The affected versions are
    carried on the alert.

    🔴 THE NOTIFICATION GOES TO THE PROJECT LEAD, AND ONLY FOR PROJECTS THIS
    QUERY RETURNED. §7: a notification must not disclose what its recipient
    cannot see. `material_usage` is RLS-scoped, so a restricted project the
    caller cannot reach never appears here and never generates a notification
    naming it -- which is the leak `messaging/service.py` documents at length.
    """
    change = compare_revisions(
        session,
        organization_id=organization_id,
        previous_version_id=previous_version_id,
        current_version_id=sds_version_id,
    )
    summary = _summarise(change)

    # A revision with no substantive change raises nothing. An alert that says
    # "nothing changed" trains people to close alerts without reading them.
    if summary == "no substantive change":
        return []

    # 🔴 AN ESCALATION IS AS CRITICAL AS AN ADDITION. A sheet moving an
    # existing hazard to a higher category is exactly as urgent as one
    # naming a new hazard; grading it merely "high" would bury it.
    hazards_added = len(change["hazards_added"]) + len(change["hazards_changed"])
    severity = (
        "critical"
        if hazards_added
        else (
            "high"
            if (change["components_added"] or change["concentrations_changed"])
            else "informational"
        )
    )

    impact = impact_of_revision(
        session, organization_id=organization_id, sds_version_id=sds_version_id
    )
    batches_by_project: dict[uuid.UUID, list[dict[str, Any]]] = {}
    for batch in impact["open_batches"]:
        batches_by_project.setdefault(batch["project_id"], []).append(batch)

    raised: list[dict[str, Any]] = []
    for project_id in impact["projects"]:
        first_batch = batches_by_project.get(project_id, [{}])[0].get("id")
        alert_id = session.execute(
            text(
                """
                INSERT INTO safety.safety_alerts
                    (organization_id, sds_version_id, project_id, material_id,
                     batch_id, severity, change_summary)
                VALUES (:org, :vid, :project, :material, :batch, :severity, :summary)
                RETURNING id
                """
            ),
            {
                "org": organization_id,
                "vid": sds_version_id,
                "project": project_id,
                "material": impact["material_id"],
                "batch": first_batch,
                "severity": severity,
                "summary": summary,
            },
        ).scalar_one()

        lead_id = session.execute(
            text(
                "SELECT lead_user_id FROM projects.projects "
                "WHERE id = :pid AND organization_id = :org"
            ),
            {"pid": project_id, "org": organization_id},
        ).scalar_one_or_none()

        if lead_id is not None:
            notify(
                session,
                organization_id=organization_id,
                recipient_id=lead_id,
                notification_type="safety.alert",
                title="A safety data sheet changed for a material in your project",
                body=summary,
                entity_type="safety_alert",
                entity_id=alert_id,
                # ACTIONABLE: somebody must look. §11 requires the badge to
                # count items needing action, and this is one.
                is_actionable=True,
            )

        raised.append({"id": alert_id, "project_id": project_id, "severity": severity})

    write_audit(
        session,
        AuditEvent(
            action="SAFETY_ALERTS_RAISED",
            entity_type="sds_version",
            entity_id=str(sds_version_id),
            organization_id=organization_id,
            user_id=actor_id,
            new_state={"alerts": len(raised), "severity": severity, "summary": summary},
        ),
    )
    return raised


def list_alerts(
    session: Session,
    *,
    organization_id: uuid.UUID,
    unacknowledged_only: bool = False,
    limit: int = 100,
) -> list[dict[str, Any]]:
    """Safety alerts this caller can reach.

    RLS applies the project predicate, so a restricted project's alerts are
    invisible to a non-member -- permission and resource scope are separate
    gates (SECURITY.md §3) and holding `compliance.review_sds` is not membership.
    """
    return [
        dict(r)
        for r in session.execute(
            text(
                """
                SELECT a.id, a.severity, a.change_summary, a.created_at,
                       a.acknowledged_at, a.project_id, a.material_id,
                       -- 🔴 THE REVISION THIS ALERT IS ABOUT. Without it the
                       -- "open a safety review" control had nothing correct to
                       -- send: it passed the ALERT's id where an
                       -- `sds_version_id` was required, so every press would
                       -- have failed the foreign key. Codex found it.
                       a.sds_version_id,
                       a.formula_version_id, a.batch_id,
                       p.project_code, p.name AS project_name,
                       m.material_code, m.name AS material_name
                  FROM safety.safety_alerts a
                  JOIN projects.projects p
                    ON p.id = a.project_id AND p.organization_id = a.organization_id
                  LEFT JOIN materials.materials m
                    ON m.id = a.material_id AND m.organization_id = a.organization_id
                 WHERE a.organization_id = :org
                   AND (:unack = FALSE OR a.acknowledged_at IS NULL)
                 ORDER BY CASE a.severity WHEN 'critical' THEN 0
                                          WHEN 'high'     THEN 1
                                          ELSE 2 END,
                          a.created_at DESC
                 LIMIT :limit
                """
            ),
            {"org": organization_id, "unack": unacknowledged_only, "limit": limit},
        ).mappings()
    ]


def acknowledge_alert(
    session: Session, *, organization_id: uuid.UUID, actor_id: uuid.UUID, alert_id: uuid.UUID
) -> dict[str, Any]:
    """Mark an alert as seen.

    Acknowledging is not clearing: the alert stays, with a name and a time on
    it. A safety alert that could be deleted would let the record of a change
    nobody acted on disappear.
    """
    row = (
        session.execute(
            text(
                """
                UPDATE safety.safety_alerts
                   SET acknowledged_by = :actor, acknowledged_at = clock_timestamp()
                 WHERE id = :aid AND organization_id = :org AND acknowledged_at IS NULL
                RETURNING id, acknowledged_at
                """
            ),
            {"aid": alert_id, "org": organization_id, "actor": actor_id},
        )
        .mappings()
        .one_or_none()
    )
    if row is None:
        raise MaterialSafetyNotFoundError("no unacknowledged alert with that id that you can reach")
    return dict(row)


# ---------------------------------------------------------------------------
# The controlled review, through the ONE approval engine
# ---------------------------------------------------------------------------


def safety_review_status(
    session: Session, *, organization_id: uuid.UUID, review_id: uuid.UUID
) -> dict[str, Any] | None:
    """Where a safety review has got to — READ FROM THE APPROVAL ROUTE.

    🔴 THERE IS NO STATUS COLUMN ON `safety_reviews`, AND THAT IS THE POINT.

    The first version of this schema gave the table
    `review_state ∈ (open, cleared, action_required, cancelled)` plus
    `closed_by`/`closed_at`, and **nothing ever updated them**. The approval
    route could be approved through `/approvals` while the safety review sat at
    `open` for ever, and this module's own header claimed there was "no second
    notion of signed off". Codex measured it and the claim was false.

    A safety review IS its approval route. `route_for_entity` is how every
    other entity in the engine reads its status, and it is how this one does
    too. `None` means no route is open — which after a decision is the ordinary
    state, not a fault.
    """
    # `include_closed=True`: a DECIDED review must not read as one that was
    # never opened. `route_for_entity` answered None for both until the
    # approvals module was given this parameter -- Codex found it, and the fix
    # belongs in the module that OWNS routes rather than in a query here.
    return route_for_entity(
        session,
        organization_id=organization_id,
        entity_type="safety_review",
        entity_id=review_id,
        include_closed=True,
    )


def open_safety_review(
    session: Session,
    *,
    organization_id: uuid.UUID,
    actor_id: uuid.UUID,
    sds_version_id: uuid.UUID,
    project_id: uuid.UUID,
    reason: str,
) -> dict[str, Any]:
    """Open a safety review and its approval route.

    🔴 IT CALLS `approvals.open_route`. There is no second approval engine, no
    second queue and no second notion of "signed off" -- CLAUDE.md §12 and the
    specification's §12 both forbid one, and `/approvals` already renders the
    queue this route joins.

    ⚠️ `project_id` IS REQUIRED BY `open_route` (approvals/service.py:103), which
    is why `safety_reviews.project_id` is NOT NULL. A review with no project
    could never open a route: a control pointing at inert workflow.

    An SDS revision affecting four projects therefore produces four reviews.
    That is also right on its own terms -- each project's lead approves for
    their own work, and one organization-wide sign-off would let somebody clear
    a change for a restricted project they cannot see.
    """
    # A SAVEPOINT for the same reason as `interpret_sds`: the duplicate-open
    # refusal below must not discard the caller's earlier work.
    try:
        with guarded_write(session):
            review_id = session.execute(
                text(
                    """
                    INSERT INTO safety.safety_reviews
                        (organization_id, sds_version_id, project_id, reason, opened_by)
                    VALUES (:org, :vid, :project, :reason, :actor)
                    RETURNING id
                    """
                ),
                {
                    "org": organization_id,
                    "vid": sds_version_id,
                    "project": project_id,
                    "reason": reason,
                    "actor": actor_id,
                },
            ).scalar_one()
    except DBAPIError as exc:
        # 🔴 `DBAPIError`, NOT `IntegrityError`. A row-level security refusal on
        # a restricted project is an `InsufficientPrivilege`, not an integrity
        # violation, so the narrower class turned "you are not a member of that
        # project" into a 500. Codex found it.
        raise _translate(exc) from exc

    # 🔴 THE APPROVAL DOMAIN'S ERRORS ARE TRANSLATED, NOT LET THROUGH.
    #
    # `ApprovalError` and its subclasses are outside this module's hierarchy,
    # so the route handler's `except MaterialSafetyError` would not have caught
    # them: a missing SAFETY_REVIEW template, or a route already open, would
    # have become a 500 instead of a 409. Codex found it.
    try:
        route = open_route(
            session,
            organization_id=organization_id,
            project_id=project_id,
            entity_type="safety_review",
            entity_id=review_id,
            authority_level="safety",
            actor_id=actor_id,
        )
    except ApprovalNotFoundError as exc:
        raise MaterialSafetyNotFoundError(str(exc)) from exc
    except ApprovalError as exc:
        raise MaterialSafetyStateError(str(exc)) from exc

    write_audit(
        session,
        AuditEvent(
            action="SAFETY_REVIEW_OPENED",
            entity_type="safety_review",
            entity_id=str(review_id),
            organization_id=organization_id,
            user_id=actor_id,
            # 🔴 `route_id`, NOT `id`. `open_route` returns
            # {"route_id", "template_code", "steps"} (approvals/service.py:216).
            # An earlier draft read `route.get("id", "")` and would have written
            # an EMPTY STRING into the audit record of a controlled safety
            # review -- silently, forever, with nothing failing.
            new_state={"project_id": str(project_id), "route_id": str(route["route_id"])},
            reason=reason,
        ),
    )

    return {"id": review_id, "route": route}


# ---------------------------------------------------------------------------
# §22, first chain — the reaction to `FormulaVersionCreated`
# ---------------------------------------------------------------------------


def on_formula_version_created(
    session: Session,
    *,
    organization_id: uuid.UUID,
    subject_id: uuid.UUID,
    project_id: uuid.UUID | None = None,
    payload: dict[str, Any] | None = None,
    actor_id: uuid.UUID | None = None,
    triggered_by_event: int | None = None,
) -> dict[str, Any]:
    """`FormulaVersionCreated` → this evaluates → `SafetyReviewRequired`.

    §22's first chain, and until migration 066 only its first hop existed:
    `revise_version` announced the fact and **nothing consumed it**.

    🔴 IT ASKS THE FORMULATIONS MODULE, IT DOES NOT RE-DERIVE THE ANSWER.
    `formulations.safety_blocks` wraps the same `_safety_checks` the submission
    gate uses, over components loaded through `materials.usable_documents`. A
    join written here would be a second opinion about whether a formula is
    safe, and the version this repository would notice last is the one where
    the safety module says clean and submission refuses.

    ⚠️ IT RAISES NO ALERT AND WRITES NO CONTROLLED RECORD. `safety_alerts` is
    the SDS-revision chain's table (§23) and is raised per PROJECT by a
    permissioned act; announcing here as well would put two writers on one
    table for two different reasons. What this produces is the ANNOUNCEMENT
    that a review is required — which is what §22 asks for, and what a screen
    or a later consumer can react to.

    ⚠️ AND IT IS SILENT WHEN THERE IS NOTHING TO SAY. A version whose materials
    all have their sheets announces nothing. An event stream that fires on
    every revision regardless trains its readers to ignore it, which is the
    same reason `raise_alerts_for_revision` refuses to raise on "no substantive
    change".
    """
    blocks = safety_blocks(session, version_id=subject_id, organization_id=organization_id)
    if not blocks:
        return {"event_id": None, "blocks": []}

    payload = payload or {}
    event_id = emit_domain_event(
        session,
        organization_id=organization_id,
        event_type=SAFETY_REVIEW_REQUIRED,
        subject_id=subject_id,
        project_id=project_id,
        payload={
            "version_code": payload.get("version_code"),
            # The sentences, not a count. "2 problems" sends the reader looking;
            # "RM-0042 requires a safety data sheet and none is on file" is the
            # answer.
            "reasons": list(blocks),
            "triggered_by_event": triggered_by_event,
        },
        # No actor: a reaction has no person behind it. Somebody revised a
        # formula; nobody decided this version needed a safety review.
        actor_id=None,
    )
    return {"event_id": event_id, "blocks": list(blocks)}
