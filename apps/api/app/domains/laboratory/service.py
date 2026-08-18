"""The guided batch flow.

The source's own sequence (ITWRD App.txt §15-16) is the shape of this
module, function for function:

    Create Laboratory Batch -> Calculate Batch Quantities
    -> Select Material Lots -> Lab Authorization -> Execute Batch
    -> Material Verification -> Mixing -> Process Data Capture
    -> Sample Creation -> Batch Completion -> Chemist Review

**The weigh-up sheet is produced by the ENGINE and then stored.** It is
not recomputed on read. A batch is the record of an instruction that was
issued at a moment in time; re-deriving it later would mean a correction
to a material's data silently changing what a technician was told to
weigh out last week, with the actual masses beside it becoming deviations
from a plan that never existed.

**The comparison is the engine's too.** `mass_deviation` computes the
delta and the percentage; nothing here subtracts a mass from another
mass. That rule has already caught a `fraction * 100` twice in this
repository, and a weighing reconciliation is exactly the kind of "easy
arithmetic" it exists to keep in one place.

**A batch can only be created from an APPROVED formula version**, checked
inside the INSERT rather than before it. `CLAUDE.md` §11 states the
workflow as "approve lab -> create batch", and a version that was
approved when the check ran and superseded when the insert landed would
otherwise produce a batch of a formula nobody approved.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.calculations.formulation import Component, mass_deviation, scale_to_batch
from app.core.audit import AuditEvent, write_audit
from app.core.tenancy import require_active_member

__all__ = [
    "BatchError",
    "BatchInput",
    "BatchNotFoundError",
    "BatchStateError",
    "DeviationInput",
    "LaboratoryError",
    "ProcessParameterInput",
    "SampleInput",
    "authorize_batch",
    "complete_batch",
    "create_batch",
    "create_sample",
    "get_batch",
    "list_batches",
    "raise_deviation",
    "record_process_parameter",
    "record_weighing",
    "review_batch",
    "start_batch",
]

# The statuses in which a technician may still record what happened.
_RECORDABLE = frozenset({"authorized", "in_progress"})


class LaboratoryError(RuntimeError):
    """Base for refusals that are business rules, not bugs."""


class BatchError(LaboratoryError):
    pass


class BatchNotFoundError(BatchError):
    """No such batch here -- or one in a restricted project this caller
    does not belong to. Indistinguishable on purpose."""


class BatchStateError(BatchError):
    """The batch is not at the step this action belongs to.

    Distinct from "not found" so the route answers 409 rather than 404,
    and carries the current status so the message can say where it is.
    """


@dataclass(frozen=True, slots=True)
class BatchInput:
    batch_number: str
    planned_quantity_kg: Decimal
    purpose: str | None = None
    mixing_procedure: str | None = None
    tolerance_percent: Decimal | None = None
    notes: str | None = None


@dataclass(frozen=True, slots=True)
class ProcessParameterInput:
    parameter_code: str
    value: Decimal
    unit: str
    stage: str | None = None
    notes: str | None = None


@dataclass(frozen=True, slots=True)
class DeviationInput:
    description: str
    severity: str = "minor"
    batch_component_id: uuid.UUID | None = None


@dataclass(frozen=True, slots=True)
class SampleInput:
    sample_number: str
    quantity_g: Decimal | None = None
    purpose: str | None = None
    storage_location: str | None = None
    notes: str | None = None


# ---------------------------------------------------------------------------
# Create -- and calculate the weigh-up sheet
# ---------------------------------------------------------------------------


def create_batch(
    session: Session,
    *,
    formula_version_id: uuid.UUID,
    organization_id: uuid.UUID,
    actor_id: uuid.UUID,
    spec: BatchInput,
) -> dict[str, Any]:
    """Create a batch and its weigh-up sheet from an approved formula.

    Three things happen in one transaction, in this order and for these
    reasons:

    1. The batch row is inserted with the formula version's own project,
       taken FROM the version rather than from the caller, and only if
       that version is `approved`. A caller cannot name a project, so a
       caller cannot get it wrong.
    2. The composition is read and handed to `scale_to_batch`, which
       returns masses summing EXACTLY to the batch quantity -- the
       invariant a technician reconciling the sheet depends on.
    3. Those masses are stored as the planned lines.

    The engine refuses an off-100% formula rather than renormalising it,
    so a formula that could not be submitted cannot produce a weigh-up
    sheet either. That refusal reaches the caller intact.
    """
    require_active_member(
        session, user_id=actor_id, organization_id=organization_id, role_description="author"
    )

    tolerance = spec.tolerance_percent

    try:
        batch = (
            session.execute(
                text(
                    """
                    INSERT INTO laboratory.batches
                        (organization_id, project_id, formula_version_id, batch_number,
                         planned_quantity_kg, tolerance_percent, purpose,
                         mixing_procedure, notes, created_by)
                    SELECT :org, v.project_id, v.id, :number,
                           :quantity,
                           COALESCE(CAST(:tolerance AS NUMERIC), 1.0), :purpose,
                           :procedure, :notes, :actor
                    FROM formulations.formula_versions v
                    WHERE v.id = :vid
                      AND v.organization_id = :org
                      AND v.status = 'approved'
                    RETURNING id, project_id, batch_number
                    """
                ),
                {
                    "org": organization_id,
                    "vid": formula_version_id,
                    "number": spec.batch_number,
                    "quantity": spec.planned_quantity_kg,
                    "tolerance": tolerance,
                    "purpose": spec.purpose,
                    "procedure": spec.mixing_procedure,
                    "notes": spec.notes,
                    "actor": actor_id,
                },
            )
            .mappings()
            .one_or_none()
        )
    except IntegrityError as exc:
        session.rollback()
        detail = str(exc.orig)
        if "batches_org_number_key" in detail:
            raise BatchError(
                f"batch number '{spec.batch_number}' is already used in this organization"
            ) from exc
        raise BatchError(detail) from exc

    if batch is None:
        # The INSERT ... SELECT matched no version. Say which of the two
        # reasons it was, without disclosing anything about a version the
        # caller cannot see.
        current = (
            session.execute(
                text(
                    """
                    SELECT status, version_code FROM formulations.formula_versions
                    WHERE id = :vid AND organization_id = :org
                    """
                ),
                {"vid": formula_version_id, "org": organization_id},
            )
            .mappings()
            .one_or_none()
        )
        if current is None:
            raise BatchNotFoundError("no such formula version in this organization")
        raise BatchStateError(
            f"version {current['version_code']} is {current['status']}; a batch can only "
            "be made from a version that has been approved for laboratory trial"
        )

    rows = _load_formula_components(
        session, version_id=formula_version_id, organization_id=organization_id
    )
    if not rows:
        raise BatchStateError("that formula version has no components to weigh out")

    try:
        masses = scale_to_batch(
            [
                Component(
                    material_code=r["material_code"],
                    percentage=r["percentage"],
                    role=r["effective_role"],
                )
                for r in rows
            ],
            spec.planned_quantity_kg,
        )
    except ValueError as exc:
        # An off-100% formula, a duplicated component, or a batch too small
        # to express at this precision. Each carries its own explanation,
        # so it is passed through rather than reworded.
        raise BatchStateError(str(exc)) from exc

    by_code = {r["material_code"]: r for r in rows}
    for order, (code, mass) in enumerate(masses.items()):
        session.execute(
            text(
                """
                INSERT INTO laboratory.batch_components
                    (organization_id, project_id, batch_id, material_id,
                     planned_mass_kg, display_order)
                VALUES (:org, :pid, :bid, :mid, :mass, :order)
                """
            ),
            {
                "org": organization_id,
                "pid": batch["project_id"],
                "bid": batch["id"],
                "mid": by_code[code]["material_id"],
                "mass": mass,
                "order": by_code[code]["display_order"] or order,
            },
        )

    write_audit(
        session,
        AuditEvent(
            action="batch.created",
            entity_type="batch",
            entity_id=str(batch["id"]),
            organization_id=organization_id,
            user_id=actor_id,
            new_state={
                "batch_number": spec.batch_number,
                "planned_quantity_kg": str(spec.planned_quantity_kg),
                "component_count": len(masses),
            },
            reason="laboratory batch created from an approved formula version",
        ),
    )
    return {
        "batch_id": batch["id"],
        "batch_number": batch["batch_number"],
        "component_count": len(masses),
    }


# ---------------------------------------------------------------------------
# The flow
# ---------------------------------------------------------------------------


# THE TRANSITION STATEMENTS ARE COMPLETE LITERALS, NOT A TEMPLATE.
#
# 🔴 THE FIRST VERSION OF THIS INTERPOLATED, AND DEFENDED IT IN A COMMENT.
#
# `_advance` built its SQL with an f-string carrying an `extra_set`
# fragment, and silenced ruff's S608 with a suppression comment arguing
# that the fragment was a literal from this module and never a caller's.
# Semgrep flagged it anyway (`avoid-sqlalchemy-text`) and was right to.
#
# (Ruff read the original wording of this paragraph as a live suppression
# directive, which is its own small lesson about writing rule names into
# prose.)
#
# That is the SAME defect this repository fixed hours earlier in
# `app/api/admin_reference_data.py`, where a table name was interpolated
# and defended with "it comes from a closed dictionary" -- and the same
# one it fixed before that in the RLS GUC setter, which argued in a
# docstring that a `uuid.UUID` cannot carry SQL. Three times now the
# safety has been an ARGUMENT that depends on a future edit not widening
# something, rather than a MECHANISM.
#
# So there is no template. Three transitions, three whole statements,
# nothing to build. The shared machinery below is the audit record and
# the error translation -- which is what was actually worth sharing.
_TRANSITIONS: dict[str, str] = {
    "authorize": """
        WITH prev AS (
            SELECT id, status, batch_number FROM laboratory.batches
            WHERE id = :bid AND organization_id = :org
            FOR UPDATE
        )
        UPDATE laboratory.batches b
        SET status = 'authorized',
            authorized_by = :actor,
            authorized_at = now(),
            updated_at = now()
        FROM prev
        WHERE b.id = prev.id AND prev.status = 'draft'
        RETURNING b.id, b.batch_number, b.status, prev.status AS previous_status
    """,
    "start": """
        WITH prev AS (
            SELECT id, status, batch_number FROM laboratory.batches
            WHERE id = :bid AND organization_id = :org
            FOR UPDATE
        )
        UPDATE laboratory.batches b
        SET status = 'in_progress',
            executed_by = :actor,
            started_at = now(),
            updated_at = now()
        FROM prev
        WHERE b.id = prev.id AND prev.status = 'authorized'
        RETURNING b.id, b.batch_number, b.status, prev.status AS previous_status
    """,
    "complete": """
        WITH prev AS (
            SELECT id, status, batch_number FROM laboratory.batches
            WHERE id = :bid AND organization_id = :org
            FOR UPDATE
        )
        UPDATE laboratory.batches b
        SET status = 'completed',
            completed_at = now(),
            updated_at = now()
        FROM prev
        WHERE b.id = prev.id AND prev.status = 'in_progress'
        RETURNING b.id, b.batch_number, b.status, prev.status AS previous_status
    """,
}

# Which statuses each transition may run from, for the refusal message
# only. The predicate itself lives in the SQL above -- stating it twice
# would be the two-lists-that-must-agree defect in miniature, so this is
# derived from nothing and used for nothing else.
_TRANSITION_SOURCES: dict[str, str] = {
    "authorize": "draft",
    "start": "authorized",
    "complete": "in_progress",
}


def _advance(
    session: Session,
    *,
    transition: str,
    batch_id: uuid.UUID,
    organization_id: uuid.UUID,
    actor_id: uuid.UUID,
    action: str,
    reason: str,
) -> dict[str, Any]:
    """Move a batch one step.

    Every transition goes through here so the guard cannot be written
    three different ways. The permitted source status is part of the
    UPDATE's own predicate: a batch that moved between a check and a
    write matches nothing and changes nothing, rather than being
    overwritten.
    """
    row = (
        session.execute(
            text(_TRANSITIONS[transition]),
            {"bid": batch_id, "org": organization_id, "actor": actor_id},
        )
        .mappings()
        .one_or_none()
    )

    if row is None:
        current = _batch_row(session, batch_id=batch_id, organization_id=organization_id)
        raise BatchStateError(
            f"batch {current['batch_number']} is {current['status']}; this step is only "
            f"available from {_TRANSITION_SOURCES[transition]}"
        )

    write_audit(
        session,
        AuditEvent(
            action=action,
            entity_type="batch",
            entity_id=str(batch_id),
            organization_id=organization_id,
            user_id=actor_id,
            previous_state={"status": row["previous_status"]},
            new_state={"status": row["status"]},
            reason=reason,
        ),
    )
    return dict(row)


def authorize_batch(
    session: Session, *, batch_id: uuid.UUID, organization_id: uuid.UUID, actor_id: uuid.UUID
) -> dict[str, Any]:
    """Issue the weigh-up sheet.

    From here the planned quantities are frozen by a trigger. The deeper
    authorisation -- that this formula may be made at all -- was the
    Lead's `formula.approve_lab`, without which the batch could not have
    been created.
    """
    return _advance(
        session,
        transition="authorize",
        batch_id=batch_id,
        organization_id=organization_id,
        actor_id=actor_id,
        action="batch.authorized",
        reason="weigh-up sheet issued",
    )


def start_batch(
    session: Session, *, batch_id: uuid.UUID, organization_id: uuid.UUID, actor_id: uuid.UUID
) -> dict[str, Any]:
    """Begin execution. Records who is at the bench and when."""
    return _advance(
        session,
        transition="start",
        batch_id=batch_id,
        organization_id=organization_id,
        actor_id=actor_id,
        action="batch.started",
        reason="batch execution started",
    )


def record_weighing(
    session: Session,
    *,
    batch_id: uuid.UUID,
    component_id: uuid.UUID,
    organization_id: uuid.UUID,
    actor_id: uuid.UUID,
    actual_mass_kg: Decimal,
    material_lot_id: uuid.UUID | None = None,
) -> dict[str, Any]:
    """Record what was actually weighed, and against which lot.

    **The lot is checked by the database, not here.** A three-column
    foreign key means a lot of the wrong material cannot be charged
    against this line at all -- the single most consequential mistake
    available on a weigh-up bench, and one an application-layer comparison
    could be forgotten.

    **A released lot only.** A quarantined or rejected lot is material
    nobody has cleared for use, and a batch made from one is a batch whose
    results mean nothing. Enforced in the predicate rather than checked
    first, so a lot released and then quarantined mid-weighing cannot slip
    through.
    """
    batch = _batch_row(session, batch_id=batch_id, organization_id=organization_id)
    if batch["status"] not in _RECORDABLE:
        raise BatchStateError(
            f"batch {batch['batch_number']} is {batch['status']}; weights can only be "
            "recorded while it is authorized or in progress"
        )

    if material_lot_id is not None:
        lot = (
            session.execute(
                text(
                    """
                    SELECT status, lot_number FROM materials.material_lots
                    WHERE id = :lid AND organization_id = :org
                    """
                ),
                {"lid": material_lot_id, "org": organization_id},
            )
            .mappings()
            .one_or_none()
        )
        if lot is None:
            raise BatchNotFoundError("no such material lot in this organization")
        if lot["status"] != "released":
            raise BatchStateError(
                f"lot {lot['lot_number']} is {lot['status']}; only a released lot may be "
                "charged into a batch"
            )

    try:
        row = (
            session.execute(
                text(
                    """
                    UPDATE laboratory.batch_components
                    SET actual_mass_kg = :actual,
                        material_lot_id = COALESCE(CAST(:lot AS UUID), material_lot_id),
                        weighed_by = :actor,
                        weighed_at = now()
                    WHERE id = :cid AND batch_id = :bid AND organization_id = :org
                    RETURNING id, material_id, planned_mass_kg, actual_mass_kg
                    """
                ),
                {
                    "cid": component_id,
                    "bid": batch_id,
                    "org": organization_id,
                    "actual": actual_mass_kg,
                    "lot": material_lot_id,
                    "actor": actor_id,
                },
            )
            .mappings()
            .one_or_none()
        )
    except IntegrityError as exc:
        session.rollback()
        if "batch_components_lot_fk" in str(exc.orig):
            raise BatchStateError(
                "that lot is not a lot of the material this line calls for"
            ) from exc
        raise BatchError(str(exc.orig)) from exc

    if row is None:
        raise BatchNotFoundError("no such component on this batch")

    deviation = mass_deviation(
        row["planned_mass_kg"],
        row["actual_mass_kg"],
        tolerance_percent=batch["tolerance_percent"],
    )

    write_audit(
        session,
        AuditEvent(
            action="batch.weighed",
            entity_type="batch",
            entity_id=str(batch_id),
            organization_id=organization_id,
            user_id=actor_id,
            new_state={
                "component_id": str(component_id),
                "planned_kg": str(deviation.planned_kg),
                "actual_kg": str(deviation.actual_kg),
                "within_tolerance": deviation.within_tolerance,
            },
            reason="material weighed into the batch",
        ),
    )
    return {
        "component_id": row["id"],
        "planned_mass_kg": deviation.planned_kg,
        "actual_mass_kg": deviation.actual_kg,
        "delta_kg": deviation.delta_kg,
        "delta_percent": deviation.delta_percent,
        "within_tolerance": deviation.within_tolerance,
    }


def complete_batch(
    session: Session, *, batch_id: uuid.UUID, organization_id: uuid.UUID, actor_id: uuid.UUID
) -> dict[str, Any]:
    """Close execution.

    **Refused while any line is unweighed.** A batch completed with a
    component nobody recorded is a batch whose composition is unknown, and
    every test result traced back to it would inherit that. The check is a
    count of NULLs rather than a flag somebody sets.
    """
    unweighed = session.execute(
        text(
            """
            SELECT count(*) FROM laboratory.batch_components
            WHERE batch_id = :bid AND organization_id = :org AND actual_mass_kg IS NULL
            """
        ),
        {"bid": batch_id, "org": organization_id},
    ).scalar_one()

    if unweighed:
        raise BatchStateError(
            f"{unweighed} component(s) have no recorded weight; a batch cannot be "
            "completed until every line has been weighed or a deviation raised"
        )

    return _advance(
        session,
        transition="complete",
        batch_id=batch_id,
        organization_id=organization_id,
        actor_id=actor_id,
        action="batch.completed",
        reason="batch execution completed",
    )


def review_batch(
    session: Session,
    *,
    batch_id: uuid.UUID,
    organization_id: uuid.UUID,
    actor_id: uuid.UUID,
    decision: str,
    note: str | None = None,
) -> dict[str, Any]:
    """Chemist Review: Accept for Testing, or Reject for Process Deviation.

    **The reviewer may not be the person who executed the batch.** The
    source makes review a distinct step performed by a distinct role, and
    a technician signing off their own weighing removes the only check on
    it. Enforced inside the UPDATE, so two racing requests cannot both
    pass.
    """
    if decision not in {"accept", "reject"}:
        raise LaboratoryError(f"'{decision}' is not a review decision")
    if decision == "reject" and not note:
        raise LaboratoryError(
            "a rejected batch must say what the process deviation was; the next "
            "person to make this formula needs to know"
        )

    status = "accepted" if decision == "accept" else "rejected"

    row = (
        session.execute(
            text(
                """
                WITH prev AS (
                    SELECT id, status, batch_number, executed_by
                    FROM laboratory.batches
                    WHERE id = :bid AND organization_id = :org
                    FOR UPDATE
                )
                UPDATE laboratory.batches b
                SET status = :status,
                    reviewed_by = :actor,
                    reviewed_at = now(),
                    review_note = :note,
                    updated_at = now()
                FROM prev
                WHERE b.id = prev.id
                  AND prev.status = 'completed'
                  AND prev.executed_by IS DISTINCT FROM :actor
                RETURNING b.id, b.batch_number, b.status, prev.status AS previous_status
                """
            ),
            {
                "bid": batch_id,
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
        current = _batch_row(session, batch_id=batch_id, organization_id=organization_id)
        if current["status"] != "completed":
            raise BatchStateError(
                f"batch {current['batch_number']} is {current['status']}, not awaiting review"
            )
        raise LaboratoryError(
            "the person who executed a batch may not review it; a technician signing "
            "off their own weighing removes the only check on it"
        )

    write_audit(
        session,
        AuditEvent(
            action=f"batch.{status}",
            entity_type="batch",
            entity_id=str(batch_id),
            organization_id=organization_id,
            user_id=actor_id,
            previous_state={"status": "completed"},
            new_state={"status": status},
            reason=note or "chemist review",
        ),
    )
    return dict(row)


# ---------------------------------------------------------------------------
# Process data, deviations, samples
# ---------------------------------------------------------------------------


def record_process_parameter(
    session: Session,
    *,
    batch_id: uuid.UUID,
    organization_id: uuid.UUID,
    actor_id: uuid.UUID,
    spec: ProcessParameterInput,
) -> uuid.UUID:
    """Capture one process measurement: mixing RPM, time, temperature, vacuum.

    Value AND unit, always. `CLAUDE.md` §5 requires measurements stored
    that way with canonical units, and a bare number labelled `temperature`
    is a figure nobody can safely compare against another batch.
    """
    batch = _batch_row(session, batch_id=batch_id, organization_id=organization_id)
    if batch["status"] not in _RECORDABLE:
        raise BatchStateError(
            f"batch {batch['batch_number']} is {batch['status']}; process data can only "
            "be captured while it is authorized or in progress"
        )

    parameter_id: uuid.UUID = session.execute(
        text(
            """
            INSERT INTO laboratory.batch_process_parameters
                (organization_id, project_id, batch_id, parameter_code, value, unit,
                 stage, notes, recorded_by)
            VALUES (:org, :pid, :bid, :code, :value, :unit, :stage, :notes, :actor)
            RETURNING id
            """
        ),
        {
            "org": organization_id,
            "pid": batch["project_id"],
            "bid": batch_id,
            "code": spec.parameter_code,
            "value": spec.value,
            "unit": spec.unit,
            "stage": spec.stage,
            "notes": spec.notes,
            "actor": actor_id,
        },
    ).scalar_one()

    write_audit(
        session,
        AuditEvent(
            action="batch.process_recorded",
            entity_type="batch",
            entity_id=str(batch_id),
            organization_id=organization_id,
            user_id=actor_id,
            new_state={"parameter": spec.parameter_code, "unit": spec.unit},
            reason="process data captured",
        ),
    )
    return parameter_id


def raise_deviation(
    session: Session,
    *,
    batch_id: uuid.UUID,
    organization_id: uuid.UUID,
    actor_id: uuid.UUID,
    spec: DeviationInput,
) -> uuid.UUID:
    """Record a deviation.

    Deliberately available at ANY status including after completion: a
    deviation noticed during review is exactly the evidence the review
    exists to act on, and a system that refused to record it then would
    push it into a paper note.
    """
    batch = _batch_row(session, batch_id=batch_id, organization_id=organization_id)

    deviation_id: uuid.UUID = session.execute(
        text(
            """
            INSERT INTO laboratory.batch_deviations
                (organization_id, project_id, batch_id, batch_component_id,
                 description, severity, raised_by)
            VALUES (:org, :pid, :bid, :cid, :description, :severity, :actor)
            RETURNING id
            """
        ),
        {
            "org": organization_id,
            "pid": batch["project_id"],
            "bid": batch_id,
            "cid": spec.batch_component_id,
            "description": spec.description,
            "severity": spec.severity,
            "actor": actor_id,
        },
    ).scalar_one()

    write_audit(
        session,
        AuditEvent(
            action="batch.deviation_raised",
            entity_type="batch",
            entity_id=str(batch_id),
            organization_id=organization_id,
            user_id=actor_id,
            new_state={"severity": spec.severity},
            reason=spec.description[:200],
        ),
    )
    return deviation_id


def create_sample(
    session: Session,
    *,
    batch_id: uuid.UUID,
    organization_id: uuid.UUID,
    actor_id: uuid.UUID,
    spec: SampleInput,
) -> uuid.UUID:
    """Take a sample from the batch.

    Sample Creation sits before Batch Completion in the source's flow, so
    a batch still in progress may be sampled -- and a completed one may
    be too, because samples are also drawn for retained reference after
    the fact. What is refused is sampling a batch that was never executed:
    a sample from a draft batch is a sample of nothing.
    """
    batch = _batch_row(session, batch_id=batch_id, organization_id=organization_id)
    if batch["status"] in {"draft", "authorized", "cancelled"}:
        raise BatchStateError(
            f"batch {batch['batch_number']} is {batch['status']}; there is no material "
            "to sample until it has been executed"
        )

    try:
        sample_id: uuid.UUID = session.execute(
            text(
                """
                INSERT INTO laboratory.samples
                    (organization_id, project_id, batch_id, sample_number, quantity_g,
                     purpose, storage_location, notes, taken_by)
                VALUES (:org, :pid, :bid, :number, :quantity, :purpose, :location,
                        :notes, :actor)
                RETURNING id
                """
            ),
            {
                "org": organization_id,
                "pid": batch["project_id"],
                "bid": batch_id,
                "number": spec.sample_number,
                "quantity": spec.quantity_g,
                "purpose": spec.purpose,
                "location": spec.storage_location,
                "notes": spec.notes,
                "actor": actor_id,
            },
        ).scalar_one()
    except IntegrityError as exc:
        session.rollback()
        if "samples_org_number_key" in str(exc.orig):
            raise BatchError(
                f"sample number '{spec.sample_number}' is already used in this organization"
            ) from exc
        raise BatchError(str(exc.orig)) from exc

    write_audit(
        session,
        AuditEvent(
            action="sample.created",
            entity_type="sample",
            entity_id=str(sample_id),
            organization_id=organization_id,
            user_id=actor_id,
            new_state={"sample_number": spec.sample_number, "batch_id": str(batch_id)},
            reason="sample taken from batch",
        ),
    )
    return sample_id


# ---------------------------------------------------------------------------
# Reading
# ---------------------------------------------------------------------------


def list_batches(
    session: Session,
    *,
    organization_id: uuid.UUID,
    project_id: uuid.UUID | None = None,
    status: str | None = None,
    limit: int = 200,
) -> list[dict[str, Any]]:
    rows = session.execute(
        text(
            """
            SELECT b.id, b.batch_number, b.status, b.planned_quantity_kg,
                   b.tolerance_percent, b.project_id, b.formula_version_id,
                   v.version_code, f.formula_code, f.name AS formula_name,
                   b.started_at, b.completed_at, b.updated_at,
                   (SELECT count(*) FROM laboratory.batch_components c
                     WHERE c.batch_id = b.id) AS component_count,
                   (SELECT count(*) FROM laboratory.batch_components c
                     WHERE c.batch_id = b.id AND c.actual_mass_kg IS NULL)
                     AS unweighed_count,
                   (SELECT count(*) FROM laboratory.batch_deviations d
                     WHERE d.batch_id = b.id) AS deviation_count,
                   (SELECT count(*) FROM laboratory.samples s
                     WHERE s.batch_id = b.id) AS sample_count
            FROM laboratory.batches b
            JOIN formulations.formula_versions v
              ON v.id = b.formula_version_id AND v.organization_id = b.organization_id
            JOIN formulations.formulas f
              ON f.id = v.formula_id AND f.organization_id = v.organization_id
            WHERE b.organization_id = :org
              AND (:pid IS NULL OR b.project_id = :pid)
              AND (:status IS NULL OR b.status = :status)
            ORDER BY b.created_at DESC
            LIMIT :limit
            """
        ),
        {"org": organization_id, "pid": project_id, "status": status, "limit": limit},
    ).mappings()
    return [dict(r) for r in rows]


def get_batch(
    session: Session, *, batch_id: uuid.UUID, organization_id: uuid.UUID
) -> dict[str, Any]:
    """One batch: the sheet, what was weighed against it, and the rest.

    Each line carries its deviation, computed by the engine at read time.
    That is derived data and is deliberately NOT stored: a stored delta
    would be a second source of truth that goes stale the moment a
    correction lands, which is the defect already found on this project
    where a status function called itself "derived" and read a stored
    string.
    """
    batch = _batch_row(session, batch_id=batch_id, organization_id=organization_id)

    components = session.execute(
        text(
            """
            SELECT c.id, c.material_id, c.planned_mass_kg, c.actual_mass_kg,
                   c.display_order, c.weighed_at, c.notes,
                   m.material_code, m.name AS material_name, m.role,
                   c.material_lot_id, l.lot_number, l.status AS lot_status
            FROM laboratory.batch_components c
            JOIN materials.materials m
              ON m.id = c.material_id AND m.organization_id = c.organization_id
            LEFT JOIN materials.material_lots l
              ON l.id = c.material_lot_id AND l.organization_id = c.organization_id
            WHERE c.batch_id = :bid AND c.organization_id = :org
            ORDER BY c.display_order, m.material_code
            """
        ),
        {"bid": batch_id, "org": organization_id},
    ).mappings()

    lines: list[dict[str, Any]] = []
    for row in components:
        line = dict(row)
        if row["actual_mass_kg"] is None:
            # NOT a zero deviation. An unweighed line is unweighed, and
            # reporting it as 0.00% within tolerance would make an
            # incomplete batch look finished.
            line["deviation"] = None
        else:
            d = mass_deviation(
                row["planned_mass_kg"],
                row["actual_mass_kg"],
                tolerance_percent=batch["tolerance_percent"],
            )
            line["deviation"] = {
                "delta_kg": d.delta_kg,
                "delta_percent": d.delta_percent,
                "within_tolerance": d.within_tolerance,
            }
        lines.append(line)

    batch["components"] = lines
    batch["process_parameters"] = [
        dict(r)
        for r in session.execute(
            text(
                """
                SELECT id, parameter_code, value, unit, stage, recorded_at, notes
                FROM laboratory.batch_process_parameters
                WHERE batch_id = :bid AND organization_id = :org
                ORDER BY recorded_at
                """
            ),
            {"bid": batch_id, "org": organization_id},
        ).mappings()
    ]
    batch["deviations"] = [
        dict(r)
        for r in session.execute(
            text(
                """
                SELECT id, description, severity, raised_at, resolution, resolved_at,
                       batch_component_id
                FROM laboratory.batch_deviations
                WHERE batch_id = :bid AND organization_id = :org
                ORDER BY raised_at
                """
            ),
            {"bid": batch_id, "org": organization_id},
        ).mappings()
    ]
    batch["samples"] = [
        dict(r)
        for r in session.execute(
            text(
                """
                SELECT id, sample_number, quantity_g, purpose, status, storage_location,
                       taken_at, expires_on
                FROM laboratory.samples
                WHERE batch_id = :bid AND organization_id = :org
                ORDER BY sample_number
                """
            ),
            {"bid": batch_id, "org": organization_id},
        ).mappings()
    ]
    return batch


def _batch_row(
    session: Session, *, batch_id: uuid.UUID, organization_id: uuid.UUID
) -> dict[str, Any]:
    row = (
        session.execute(
            text(
                """
                SELECT b.id, b.organization_id, b.project_id, b.formula_version_id,
                       b.batch_number, b.planned_quantity_kg, b.tolerance_percent,
                       b.status, b.mixing_procedure, b.purpose, b.notes,
                       b.created_by, b.authorized_by, b.authorized_at,
                       b.executed_by, b.started_at, b.completed_at,
                       b.reviewed_by, b.reviewed_at, b.review_note,
                       b.created_at, b.updated_at
                FROM laboratory.batches b
                WHERE b.id = :bid AND b.organization_id = :org
                """
            ),
            {"bid": batch_id, "org": organization_id},
        )
        .mappings()
        .one_or_none()
    )
    if row is None:
        raise BatchNotFoundError("no such batch in this organization")
    return dict(row)


def _load_formula_components(
    session: Session, *, version_id: uuid.UUID, organization_id: uuid.UUID
) -> list[dict[str, Any]]:
    return [
        dict(r)
        for r in session.execute(
            text(
                """
                SELECT c.material_id, c.percentage, c.display_order,
                       m.material_code, COALESCE(c.role_override, m.role) AS effective_role
                FROM formulations.formula_components c
                JOIN materials.materials m
                  ON m.id = c.material_id AND m.organization_id = c.organization_id
                WHERE c.formula_version_id = :vid AND c.organization_id = :org
                ORDER BY c.display_order, m.material_code
                """
            ),
            {"vid": version_id, "org": organization_id},
        ).mappings()
    ]
