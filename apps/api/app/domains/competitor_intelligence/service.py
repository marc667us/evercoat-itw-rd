"""Competitor intelligence: products, samples, and the Composition Evidence Matrix.

🔴 THE ONE RULE THIS MODULE EXISTS TO KEEP

The specification, on competitor formulation analysis:

    "Safety Data Sheets often disclose only hazardous components or
     concentration ranges and normally do not reveal a complete proprietary
     formulation. The application shall therefore NEVER automatically present
     an inferred competitor recipe as a known or verified formula."

So there is no competitor formula anywhere in this module. There is a matrix of
CLAIMS, each carrying how it is known and how far it can be trusted. Reading the
matrix end to end gives a candidate composition — which is what the operator
asked for — and every line of it says what it rests on.

The purpose is stated in the same section and is worth keeping in view: this is
not for reconstructing somebody's proprietary information. It is for
understanding comparable chemistry, likely material functions, performance
characteristics and technology approaches, so that a technically superior
product can be developed. Lawful benchmarking, with evidence and inference kept
visibly apart.

🔴 THE THREE ENTRY MODES ARE PEERS

Label, product image, and manual entry. A person reading the back of a tin is
making an OBSERVATION, not an inference, and `manual_observation` says so —
an earlier design forced honest transcription into `inference`, which
misdescribed the person's work. What manual entry cannot do is reach
`verified`, because there is no document anybody else can re-check.

⚠️ DOCUMENTS BELONG TO THE ONE REGISTER. Uploading a label calls
`materials.store_document`, the same writer an SDS goes through, so a
competitor label gets the identical malware scan, checksum, expiry and
supersession rules. §14: do not build a second document repository.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from app.core.audit import AuditEvent, write_audit
from app.core.db import guarded_write

__all__ = [
    "CompetitorError",
    "CompetitorNotFoundError",
    "CompetitorStateError",
    "EvidenceInput",
    "composition_matrix",
    "list_benchmarks",
    "list_products",
    "list_samples",
    "record_benchmark",
    "record_evidence",
    "register_product",
    "register_sample",
    "verify_evidence",
]


class CompetitorError(RuntimeError):
    """A competitor record could not be written as asked."""


class CompetitorNotFoundError(CompetitorError):
    """It does not exist, or the caller cannot reach it."""


class CompetitorStateError(CompetitorError):
    """It exists but is not in a state that allows this."""


def _decimal_strings(row: Any) -> dict[str, Any]:
    """Every `Decimal` as a string; everything else untouched.

    🔴 WITHOUT THIS, `NUMERIC` LEAVES THE API AS A FLOAT. FastAPI's
    `jsonable_encoder` maps `Decimal` to float, so a disclosed range of
    10.0000-25.0000 arrives as 10.0-25.0: the manufacturer's stated precision
    destroyed, a float on a controlled record against CLAUDE.md §5, and the
    client's `z.string()` rejecting the response.

    This module is the FOURTH to need it — `formulations`, `laboratory`,
    `testing` and `material_safety` each carry a copy, because importing across
    domain services is the cross-domain dependency §0.3 forbids. Four copies is
    the point at which it should move to `core`; recorded here rather than done
    mid-slice, because moving it touches 36 existing call sites.
    """
    return {
        key: (str(value) if isinstance(value, Decimal) else value) for key, value in row.items()
    }


def _translate(exc: DBAPIError) -> CompetitorError:
    """A PostgreSQL refusal, as an answer a client can act on."""
    detail = str(getattr(exc, "orig", exc))

    if "products_org_name_key" in detail:
        return CompetitorStateError(
            "that manufacturer and product are already registered in this "
            "organization. Add evidence to the existing product rather than "
            "creating a second record of the same thing."
        )
    if "samples_org_reference_key" in detail:
        return CompetitorStateError("that sample reference is already used here")
    if "composition_evidence_document_fk" in detail:
        return CompetitorStateError(
            "that document does not belong to this competitor product. A label "
            "uploaded for one product cannot support a claim about another."
        )
    if "composition_evidence_verifiable_source" in detail:
        return CompetitorStateError(
            "only a document-backed or laboratory-backed claim can be verified. "
            "An observation, an inference or a model result can be supported, "
            "probable or possible -- never verified."
        )
    if "may only be marked verified by an active member holding" in detail:
        return CompetitorStateError(detail.strip().splitlines()[0])
    if "composition_evidence_observation_shape" in detail:
        return CompetitorError(
            "a manual observation must name who observed it and say what they saw"
        )
    if "composition_evidence_reasoned_shape" in detail:
        return CompetitorError("an inference must state what it was reasoned from")
    if "composition_evidence_document_shape" in detail:
        return CompetitorError("document-backed evidence must name the document")
    if "composition_evidence_balance_has_no_range" in detail:
        return CompetitorError("'the balance' is not also a concentration range")
    if "row-level security" in detail:
        return CompetitorStateError("this record names a project you cannot reach")
    return CompetitorError(detail)


# ---------------------------------------------------------------------------
# Products and samples
# ---------------------------------------------------------------------------


def register_product(
    session: Session,
    *,
    organization_id: uuid.UUID,
    actor_id: uuid.UUID,
    manufacturer: str,
    product_name: str,
    product_code: str | None = None,
    market_segment: str | None = None,
    project_id: uuid.UUID | None = None,
    notes: str | None = None,
) -> dict[str, Any]:
    """Register a competitor product.

    `project_id` is optional and that is the specification's own shape: a
    competitor product *may* be registered against a project. Most are public
    products the whole organization may see, and NULL says exactly that.
    """
    try:
        with guarded_write(session):
            product_id = session.execute(
                text(
                    """
                    INSERT INTO competitors.products
                        (organization_id, project_id, manufacturer, product_name,
                         product_code, market_segment, notes, registered_by)
                    VALUES (:org, :project, :manufacturer, :name, :code, :segment,
                            :notes, :actor)
                    RETURNING id
                    """
                ),
                {
                    "org": organization_id,
                    "project": project_id,
                    "manufacturer": manufacturer,
                    "name": product_name,
                    "code": product_code,
                    "segment": market_segment,
                    "notes": notes,
                    "actor": actor_id,
                },
            ).scalar_one()
    except DBAPIError as exc:
        raise _translate(exc) from exc

    write_audit(
        session,
        AuditEvent(
            action="COMPETITOR_CREATED",
            entity_type="competitor_product",
            entity_id=str(product_id),
            organization_id=organization_id,
            user_id=actor_id,
            new_state={"manufacturer": manufacturer, "product_name": product_name},
        ),
    )
    return {"id": product_id}


def list_products(
    session: Session, *, organization_id: uuid.UUID, limit: int = 200
) -> list[dict[str, Any]]:
    """Competitor products this caller can reach.

    RLS applies the project predicate, so a product registered against a
    restricted project is invisible to a non-member. Counts of documents and
    evidence come with it, because a product with neither is a stub somebody
    started and abandoned, and the screen should say so.
    """
    return [
        dict(r)
        for r in session.execute(
            text(
                """
                SELECT p.id, p.manufacturer, p.product_name, p.product_code,
                       p.market_segment, p.project_id, p.created_at,
                       (SELECT count(*) FROM materials.material_documents d
                         WHERE d.competitor_product_id = p.id
                           AND d.organization_id = p.organization_id) AS document_count,
                       (SELECT count(*) FROM competitors.composition_evidence e
                         WHERE e.competitor_product_id = p.id
                           AND e.organization_id = p.organization_id) AS evidence_count
                  FROM competitors.products p
                 WHERE p.organization_id = :org
                 ORDER BY p.manufacturer, p.product_name
                 LIMIT :limit
                """
            ),
            {"org": organization_id, "limit": limit},
        ).mappings()
    ]


def register_sample(
    session: Session,
    *,
    organization_id: uuid.UUID,
    actor_id: uuid.UUID,
    competitor_product_id: uuid.UUID,
    sample_reference: str,
    acquired_on: str | None = None,
    batch_marking: str | None = None,
    observations: str | None = None,
) -> dict[str, Any]:
    """Register a physical sample of a competitor product."""
    try:
        with guarded_write(session):
            sample_id = session.execute(
                text(
                    """
                    INSERT INTO competitors.samples
                        (organization_id, competitor_product_id, sample_reference,
                         acquired_on, batch_marking, observations, registered_by)
                    VALUES (:org, :product, :ref, CAST(:acquired AS DATE), :batch,
                            :observations, :actor)
                    RETURNING id
                    """
                ),
                {
                    "org": organization_id,
                    "product": competitor_product_id,
                    "ref": sample_reference,
                    "acquired": acquired_on,
                    "batch": batch_marking,
                    "observations": observations,
                    "actor": actor_id,
                },
            ).scalar_one()
    except DBAPIError as exc:
        raise _translate(exc) from exc

    write_audit(
        session,
        AuditEvent(
            action="COMPETITOR_SAMPLE_REGISTERED",
            entity_type="competitor_sample",
            entity_id=str(sample_id),
            organization_id=organization_id,
            user_id=actor_id,
            new_state={"sample_reference": sample_reference},
        ),
    )
    return {"id": sample_id}


def list_samples(
    session: Session, *, organization_id: uuid.UUID, competitor_product_id: uuid.UUID
) -> list[dict[str, Any]]:
    """Physical samples on file for one competitor product, newest first.

    🔴 WRITTEN BECAUSE `register_sample` HAD NO READER, AND A SAMPLE NOBODY
    CAN LIST IS A ROW THAT CANNOT BE CITED. `composition_evidence.sample_id`
    exists precisely so a `manual_observation` claim can name the tin it was
    read from -- and naming one requires being shown which ones exist. A
    writer without its reader is the same defect as a route without its
    control, one tier down.

    RLS supplies the organization and project predicate; the explicit
    `organization_id` here is the same belt-and-braces every reader in this
    module uses, not a substitute for it.
    """
    return [
        dict(r)
        for r in session.execute(
            text(
                """
                SELECT s.id, s.sample_reference, s.acquired_on, s.batch_marking,
                       s.observations, s.registered_by, s.created_at,
                       (SELECT count(*) FROM competitors.composition_evidence e
                         WHERE e.sample_id = s.id
                           AND e.organization_id = s.organization_id) AS evidence_count
                  FROM competitors.samples s
                 WHERE s.organization_id = :org
                   AND s.competitor_product_id = :product
                 ORDER BY s.acquired_on DESC NULLS LAST, s.created_at DESC
                """
            ),
            {"org": organization_id, "product": competitor_product_id},
        ).mappings()
    ]


# ---------------------------------------------------------------------------
# The Composition Evidence Matrix
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class EvidenceInput:
    component_name: str
    evidence_source: str
    evidence_grade: str
    cas_number: str | None = None
    component_function: str | None = None
    # Strings, not floats. NUMERIC(7,4) in PostgreSQL, and a float would round
    # the disclosed range before the database saw it.
    concentration_low: str | None = None
    concentration_high: str | None = None
    is_balance: bool = False
    source_document_id: uuid.UUID | None = None
    sample_id: uuid.UUID | None = None
    test_id: uuid.UUID | None = None
    source_locator: str | None = None
    rationale: str | None = None


def record_evidence(
    session: Session,
    *,
    organization_id: uuid.UUID,
    actor_id: uuid.UUID,
    competitor_product_id: uuid.UUID,
    spec: EvidenceInput,
) -> dict[str, Any]:
    """Record one claim about what a competitor product contains.

    🔴 IT IS RECORDED AT `possible`, NEVER AT `verified`.

    `confidence` is not an argument. A claim arrives as something somebody
    noticed; it becomes verified only through `verify_evidence`, which is a
    separate act by somebody holding `compliance.review_sds` — the same shape
    as a root cause, where §3 rule 4 says only a human moves a hypothesis to
    accepted. Letting the writer set `verified` would make the matrix's
    central distinction a matter of what the caller typed.

    `observed_by` is the actor for a manual observation: the person recording
    what they saw is the person who saw it, and the database requires a name.
    """
    try:
        with guarded_write(session):
            evidence_id = session.execute(
                text(
                    """
                    INSERT INTO competitors.composition_evidence
                        (organization_id, competitor_product_id, component_name,
                         cas_number, component_function, concentration_low,
                         concentration_high, is_balance, evidence_source,
                         evidence_grade, confidence, source_document_id, sample_id,
                         test_id, source_locator, rationale, observed_by, recorded_by)
                    VALUES (:org, :product, :name, :cas, :function,
                            CAST(:low AS NUMERIC), CAST(:high AS NUMERIC), :balance,
                            :source, :grade, 'possible', :doc, :sample, :test,
                            :locator, :rationale, :observed, :actor)
                    RETURNING id
                    """
                ),
                {
                    "org": organization_id,
                    "product": competitor_product_id,
                    "name": spec.component_name,
                    "cas": spec.cas_number,
                    "function": spec.component_function,
                    "low": spec.concentration_low,
                    "high": spec.concentration_high,
                    "balance": spec.is_balance,
                    "source": spec.evidence_source,
                    "grade": spec.evidence_grade,
                    "doc": spec.source_document_id,
                    "sample": spec.sample_id,
                    "test": spec.test_id,
                    "locator": spec.source_locator,
                    "rationale": spec.rationale,
                    "observed": actor_id if spec.evidence_source == "manual_observation" else None,
                    "actor": actor_id,
                },
            ).scalar_one()
    except DBAPIError as exc:
        raise _translate(exc) from exc

    write_audit(
        session,
        AuditEvent(
            action="COMPETITOR_EVIDENCE_RECORDED",
            entity_type="composition_evidence",
            entity_id=str(evidence_id),
            organization_id=organization_id,
            user_id=actor_id,
            # The component name is not a payload to withhold -- it is the
            # identity of the claim -- but the rationale and locator are, and
            # they are not copied here.
            new_state={
                "component_name": spec.component_name,
                "evidence_source": spec.evidence_source,
                "evidence_grade": spec.evidence_grade,
                "confidence": "possible",
            },
        ),
    )
    return {"id": evidence_id, "confidence": "possible"}


def verify_evidence(
    session: Session,
    *,
    organization_id: uuid.UUID,
    reviewer_id: uuid.UUID,
    evidence_id: uuid.UUID,
    confidence: str,
) -> dict[str, Any]:
    """Move a claim's confidence, including to `verified`.

    🔴 `verified` IS THE ONLY STATE THAT NEEDS A REVIEWER, AND THE DATABASE
    CHECKS THE REVIEWER HOLDS THE PERMISSION.

    A CHECK constraint can require a name and a time; it cannot establish that
    the named person was entitled. A trigger joins `member_roles` ->
    `role_permissions` -> `permissions` and refuses unless `verified_by` holds
    `compliance.review_sds` in this organization.

    ⚠️ A MISUSE BARRIER, NOT A BOUNDARY. Anything already running arbitrary SQL
    as `evercoat_app` is inside the trust boundary. This removes every
    accidental path and makes a deliberate one attributable — the same
    distinction I109/ADR-032 draws.
    """
    verified = confidence == "verified"
    row = (
        session.execute(
            text(
                """
                UPDATE competitors.composition_evidence
                   SET confidence  = :confidence,
                       verified_by = CASE WHEN :verified THEN :reviewer ELSE NULL END,
                       verified_at = CASE WHEN :verified THEN clock_timestamp() ELSE NULL END
                 WHERE id = :eid AND organization_id = :org
                RETURNING id, confidence, verified_at
                """
            ),
            {
                "eid": evidence_id,
                "org": organization_id,
                "confidence": confidence,
                "verified": verified,
                "reviewer": reviewer_id,
            },
        )
        .mappings()
        .one_or_none()
    )
    if row is None:
        raise CompetitorNotFoundError("no such evidence that you can reach")

    write_audit(
        session,
        AuditEvent(
            action="COMPETITOR_EVIDENCE_GRADED",
            entity_type="composition_evidence",
            entity_id=str(evidence_id),
            organization_id=organization_id,
            user_id=reviewer_id,
            new_state={"confidence": confidence},
        ),
    )
    return dict(row)


def composition_matrix(
    session: Session, *, organization_id: uuid.UUID, competitor_product_id: uuid.UUID
) -> dict[str, Any]:
    """🔴 A CANDIDATE COMPOSITION, AND EVERY LINE SAYS WHAT IT RESTS ON.

    This is the answer to *"what is in the competitor's product"* — and it is
    deliberately not shaped like a formula. It is the claims, strongest
    evidence first, each with its source, its grade, its confidence and the
    locator somebody else can use to re-check it.

    The summary counts exist so a reader can see at a glance how much of the
    picture is actually established: "3 verified, 2 supported, 6 inferred" is a
    different product understanding from "11 verified", and a bare list makes
    them look alike.
    """
    rows = [
        _decimal_strings(r)
        for r in session.execute(
            text(
                """
                SELECT e.id, e.component_name, e.cas_number, e.component_function,
                       e.concentration_low, e.concentration_high, e.is_balance,
                       e.evidence_source, e.evidence_grade, e.confidence,
                       e.source_locator, e.rationale, e.verified_at,
                       e.source_document_id, e.sample_id, e.test_id,
                       d.title AS source_document_title,
                       d.document_type AS source_document_type
                  FROM competitors.composition_evidence e
                  LEFT JOIN materials.material_documents d
                    ON d.id = e.source_document_id AND d.organization_id = e.organization_id
                 WHERE e.organization_id = :org AND e.competitor_product_id = :product
                 ORDER BY
                   -- Strongest first: a reader scanning the top of this list
                   -- should be reading the best-established claims.
                   CASE e.confidence WHEN 'verified'  THEN 0
                                     WHEN 'supported' THEN 1
                                     WHEN 'probable'  THEN 2
                                     WHEN 'possible'  THEN 3
                                     ELSE 4 END,
                   e.evidence_grade,
                   e.concentration_high DESC NULLS LAST,
                   e.component_name
                """
            ),
            {"org": organization_id, "product": competitor_product_id},
        ).mappings()
    ]

    by_confidence: dict[str, int] = {}
    for row in rows:
        key = str(row["confidence"])
        by_confidence[key] = by_confidence.get(key, 0) + 1

    return {
        "rows": rows,
        "summary": by_confidence,
        # 🔴 STATED IN THE PAYLOAD, NOT LEFT TO THE SCREEN TO REMEMBER.
        # Any client rendering this must say it, and a client that forgets
        # would be presenting an inferred recipe as a known one -- the single
        # thing the specification forbids outright.
        "disclaimer": (
            "This is a candidate composition assembled from evidence of "
            "differing strength. It is not a known or verified formula, and "
            "rows that are not marked verified have not been confirmed."
        ),
    }


def record_benchmark(
    session: Session,
    *,
    organization_id: uuid.UUID,
    actor_id: uuid.UUID,
    competitor_product_id: uuid.UUID,
    project_id: uuid.UUID,
    attribute: str,
    gap_summary: str,
    competitor_value: str | None = None,
    our_value: str | None = None,
    formula_version_id: uuid.UUID | None = None,
    test_id: uuid.UUID | None = None,
) -> dict[str, Any]:
    """Record a measured comparison against our own work.

    ⚠️ IT CITES A TEST; IT DOES NOT GRADE ONE. Testing owns GREEN/YELLOW/RED
    (CLAUDE.md §10) and this module must not produce a second disposition. The
    gap is stated in words for the same reason: the arithmetic belongs to the
    engine (§3 rule 2), and a delta computed here would be a second answer to a
    question Testing already answers.
    """
    try:
        with guarded_write(session):
            benchmark_id = session.execute(
                text(
                    """
                    INSERT INTO competitors.benchmarks
                        (organization_id, competitor_product_id, project_id,
                         formula_version_id, test_id, attribute, competitor_value,
                         our_value, gap_summary, recorded_by)
                    VALUES (:org, :product, :project, :version, :test, :attribute,
                            :theirs, :ours, :gap, :actor)
                    RETURNING id
                    """
                ),
                {
                    "org": organization_id,
                    "product": competitor_product_id,
                    "project": project_id,
                    "version": formula_version_id,
                    "test": test_id,
                    "attribute": attribute,
                    "theirs": competitor_value,
                    "ours": our_value,
                    "gap": gap_summary,
                    "actor": actor_id,
                },
            ).scalar_one()
    except DBAPIError as exc:
        raise _translate(exc) from exc

    write_audit(
        session,
        AuditEvent(
            action="COMPETITOR_BENCHMARK_RECORDED",
            entity_type="competitor_benchmark",
            entity_id=str(benchmark_id),
            organization_id=organization_id,
            user_id=actor_id,
            new_state={"attribute": attribute},
        ),
    )
    return {"id": benchmark_id}


def list_benchmarks(
    session: Session, *, organization_id: uuid.UUID, competitor_product_id: uuid.UUID
) -> list[dict[str, Any]]:
    """Measured comparisons recorded against one competitor product.

    🔴 WRITTEN BECAUSE `record_benchmark` HAD NO READER EITHER. The whole
    point of a benchmark is that somebody later reads it beside the gap it
    describes; a write-only benchmark table is an audit trail nobody can
    consult.

    ⚠️ IT REPORTS THE CITED TEST, IT DOES NOT REPORT A DISPOSITION. Testing
    owns GREEN/YELLOW/RED (`CLAUDE.md` §10) and this query deliberately does
    not join one in: a colour surfaced here would be a second answer to a
    question Testing already answers, and the two would drift.

    The project name is joined because `project_id` alone is a UUID a reader
    cannot act on -- the same reason `list_products` carries its counts.
    """
    return [
        dict(r)
        for r in session.execute(
            text(
                """
                SELECT b.id, b.attribute, b.competitor_value, b.our_value,
                       b.gap_summary, b.project_id, b.formula_version_id,
                       b.test_id, b.recorded_by, b.created_at,
                       p.name AS project_name, p.project_code
                  FROM competitors.benchmarks b
                  LEFT JOIN projects.projects p
                    ON p.id = b.project_id AND p.organization_id = b.organization_id
                 WHERE b.organization_id = :org
                   AND b.competitor_product_id = :product
                 ORDER BY b.created_at DESC
                """
            ),
            {"org": organization_id, "product": competitor_product_id},
        ).mappings()
    ]
