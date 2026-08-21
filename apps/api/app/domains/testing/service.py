"""The Test Module.

**`calculated_result` is computed here and accepted from nobody.** Rule 2
of the seven non-negotiables gives deterministic scientific calculation to
Python, and `DATA_MODEL.md` §3.5 marks that axis **SYS only**. No route
exposes it; `complete_execution` derives it from the raw replicates and
the requirement, and that is the only writer.

**The traffic light is derived on read, never stored.** There is no
`display_color` column. A stored one would be a second implementation of
a fourteen-rule ordered algorithm that nothing could check against the
first — the two-literals-in-two-files defect this repository keeps
rediscovering, applied to the one field a chemist most needs to trust.

**Segregation of duties is enforced against the decision record**, not
against role names. ADR-019: QA approval may never come from anyone who
supplied a development-side approval on the same test. No role check can
express that — it depends on per-test identity — which is why
authorization here reads `testing.test_decisions` and asks who has
already decided.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from sqlalchemy import text
from sqlalchemy.engine import RowMapping
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.calculations.testing import (
    DispositionInputs,
    derive_disposition,
    evaluate_against_requirement,
    replicate_statistics,
)
from app.core.audit import AuditEvent, write_audit
from app.core.tenancy import require_active_member

# `open_failure_for_failed_test` is imported cross-domain, in the same direction
# as the existing `formulations -> materials` dependency. Quality does not import
# testing, so this cannot become a cycle. §10 makes opening the investigation
# part of what a RED confirmation result MEANS, not a follow-up somebody may
# forget, so the dependency belongs in the service and not in the route.
from app.domains.failures.service import open_failure_for_failed_test

__all__ = [
    "DecisionInput",
    "ReplicateInput",
    "SegregationOfDutiesError",
    "TestError",
    "TestInput",
    "TestNotFoundError",
    "TestStateError",
    "TestingError",
    "complete_execution",
    "confirm_test",
    "create_test",
    "exclude_replicate",
    "get_test",
    "list_tests",
    "record_decision",
    "record_replicate",
    "start_execution",
]

# Which decisions belong to which stage, and what each does to the axes.
# A table rather than a chain of ifs: this IS the review/approval state
# machine, and it has to be readable against DATA_MODEL.md §3.5 without
# following control flow.
_REVIEW_OUTCOMES: dict[str, str] = {
    "return_for_correction": "returned_for_correction",
    "request_retest": "retest_requested",
    "escalate": "escalated",
    "request_additional_test": "under_review",
    "approve": "reviewed",
    "approve_with_condition": "reviewed",
}

_APPROVAL_OUTCOMES: dict[str, str] = {
    "approve": "approved",
    "approve_with_condition": "conditionally_approved",
    "reject": "rejected",
}

# The development-side approval permission. Anyone who has decided at this
# stage is barred from supplying the independent QA approval (ADR-019).
_DEVELOPMENT_APPROVAL = "development"


# ---------------------------------------------------------------------------
# Decimal on the wire
# ---------------------------------------------------------------------------
#: 🔴 A `NUMERIC` COLUMN REACHES JSON AS A **FLOAT** UNLESS IT IS STRINGIFIED.
#:
#: FastAPI's `jsonable_encoder` maps `Decimal` to `float`. Measured:
#: `jsonable_encoder(Decimal("12.5000")) -> 12.5`, and
#: `Decimal("2.00") -> 2.0`. So a batch mass recorded to four decimal
#: places went out carrying one, which is exactly the round trip
#: `CLAUDE.md` §5 forbids -- *"NUMERIC, never float, for percentages,
#: masses, densities and measured values"*.
#:
#: This is the same defect Codex found in `materials` on 2026-08-19, which
#: "would have rejected every live material row". It was fixed there and
#: nowhere else; this module had it too, undetected, because no screen was
#: wired to these routes yet.
#:
#: 🔴 GENERIC, NOT A KEY LIST. `materials` enumerates its quantity columns
#: by name. That works until somebody adds a NUMERIC column and does not
#: think to extend the tuple -- which is precisely how this class of bug
#: survives. Converting every `Decimal` in the row cannot be forgotten,
#: because there is nothing to remember.
def _decimal_strings(row: RowMapping | dict[str, Any]) -> dict[str, Any]:
    """Every `Decimal` in the row as a string; everything else untouched.

    Strings preserve the stored scale across the wire. The web client
    parses them with `zod` and never does arithmetic on them -- §4 keeps
    derivation on the server.
    """
    return {
        key: (str(value) if isinstance(value, Decimal) else value) for key, value in row.items()
    }


class TestingError(RuntimeError):
    """Base for refusals that are business rules, not bugs."""


class TestError(TestingError):
    pass


class TestNotFoundError(TestError):
    """No such test here -- or one in a restricted project this caller is
    not a member of. Indistinguishable on purpose."""


class TestStateError(TestError):
    """The test is not at the step this action belongs to."""


class SegregationOfDutiesError(TestingError):
    """The caller may not make this decision on THIS test.

    A distinct type because it is not "you may never do this" but "not
    here": the same person holds the permission and is barred by their
    own earlier involvement. The route answers 403 and says which.
    """


@dataclass(frozen=True, slots=True)
class TestInput:
    test_number: str
    sample_id: uuid.UUID
    method_id: uuid.UUID
    test_purpose: str = "oversight"
    authority_level: str = "development"
    requirement_id: uuid.UUID | None = None
    method_version_id: uuid.UUID | None = None
    equipment_id: uuid.UUID | None = None
    supersedes_test_id: uuid.UUID | None = None
    planned_for: Any = None
    notes: str | None = None


@dataclass(frozen=True, slots=True)
class ReplicateInput:
    replicate_number: int
    measured_value: Decimal
    unit: str
    notes: str | None = None


@dataclass(frozen=True, slots=True)
class DecisionInput:
    decision: str
    stage: str = "review"
    condition_text: str | None = None
    rationale: str | None = None
    authority_level: str | None = None


# ---------------------------------------------------------------------------
# Create and execute
# ---------------------------------------------------------------------------


def create_test(
    session: Session,
    *,
    organization_id: uuid.UUID,
    actor_id: uuid.UUID,
    spec: TestInput,
) -> dict[str, Any]:
    """Plan a test against a physical sample.

    The project comes FROM THE SAMPLE, never from the caller. A sample
    belongs to a batch which belongs to a project, and taking the project
    from anywhere else would let a test be filed against work it did not
    come from — which is the whole traceability chain broken at its last
    link.
    """
    require_active_member(
        session, user_id=actor_id, organization_id=organization_id, role_description="author"
    )

    try:
        row = (
            session.execute(
                text(
                    """
                    INSERT INTO testing.tests
                        (organization_id, project_id, test_number, sample_id, method_id,
                         method_version_id, equipment_id, requirement_id, test_purpose,
                         authority_level, supersedes_test_id, planned_for, notes,
                         created_by)
                    SELECT :org, s.project_id, :number, s.id, :method,
                           :method_version, :equipment, :requirement, :purpose,
                           :authority, :supersedes, CAST(:planned AS DATE), :notes,
                           :actor
                    FROM laboratory.samples s
                    WHERE s.id = :sample AND s.organization_id = :org
                      -- A consumed or discarded sample has no material left
                      -- to test. DATA_MODEL.md §3.5 makes this the guard on
                      -- starting execution; it is applied at planning too,
                      -- because planning a test nobody can perform just
                      -- moves the disappointment later.
                      AND s.status IN ('available', 'in_test')
                    RETURNING id, test_number, project_id
                    """
                ),
                {
                    "org": organization_id,
                    "number": spec.test_number,
                    "sample": spec.sample_id,
                    "method": spec.method_id,
                    "method_version": spec.method_version_id,
                    "equipment": spec.equipment_id,
                    "requirement": spec.requirement_id,
                    "purpose": spec.test_purpose,
                    "authority": spec.authority_level,
                    "supersedes": spec.supersedes_test_id,
                    "planned": spec.planned_for,
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
        if "tests_org_number_key" in detail:
            raise TestError(
                f"test number '{spec.test_number}' is already used in this organization"
            ) from exc
        if "tests_method_fk" in detail:
            raise TestNotFoundError("no such test method in this organization") from exc
        if "tests_requirement_fk" in detail:
            raise TestNotFoundError("no such requirement in this organization") from exc
        raise TestError(detail) from exc

    if row is None:
        sample = (
            session.execute(
                text(
                    """
                    SELECT status, sample_number FROM laboratory.samples
                    WHERE id = :sid AND organization_id = :org
                    """
                ),
                {"sid": spec.sample_id, "org": organization_id},
            )
            .mappings()
            .one_or_none()
        )
        if sample is None:
            raise TestNotFoundError("no such sample in this organization")
        raise TestStateError(
            f"sample {sample['sample_number']} is {sample['status']}; there is no "
            "material left to test"
        )

    write_audit(
        session,
        AuditEvent(
            action="test.created",
            entity_type="test",
            entity_id=str(row["id"]),
            organization_id=organization_id,
            user_id=actor_id,
            new_state={
                "test_number": spec.test_number,
                "purpose": spec.test_purpose,
                "authority_level": spec.authority_level,
            },
            reason="test planned against a physical sample",
        ),
    )
    return _decimal_strings(row)


def start_execution(
    session: Session, *, test_id: uuid.UUID, organization_id: uuid.UUID, actor_id: uuid.UUID
) -> dict[str, Any]:
    """Begin the physical work."""
    row = (
        session.execute(
            text(
                """
                WITH prev AS (
                    SELECT id, execution_status, test_number FROM testing.tests
                    WHERE id = :tid AND organization_id = :org
                    FOR UPDATE
                )
                UPDATE testing.tests t
                SET execution_status = 'in_progress',
                    executed_by = :actor,
                    executed_at = now(),
                    updated_at = now()
                FROM prev
                WHERE t.id = prev.id AND prev.execution_status = 'not_started'
                RETURNING t.id, t.test_number, t.execution_status
                """
            ),
            {"tid": test_id, "org": organization_id, "actor": actor_id},
        )
        .mappings()
        .one_or_none()
    )
    if row is None:
        current = _test_row(session, test_id=test_id, organization_id=organization_id)
        raise TestStateError(
            f"test {current['test_number']} is {current['execution_status']}; execution "
            "can only be started from not_started"
        )

    write_audit(
        session,
        AuditEvent(
            action="test.started",
            entity_type="test",
            entity_id=str(test_id),
            organization_id=organization_id,
            user_id=actor_id,
            new_state={"execution_status": "in_progress"},
            reason="test execution started",
        ),
    )
    return _decimal_strings(row)


def record_replicate(
    session: Session,
    *,
    test_id: uuid.UUID,
    organization_id: uuid.UUID,
    actor_id: uuid.UUID,
    spec: ReplicateInput,
) -> uuid.UUID:
    """Record ONE raw measurement.

    Raw, per replicate, always. Rules 5 and 6 of the traffic light compare
    the valid replicate count and the coefficient of variation against the
    method's limits, and NEITHER can be recomputed from a stored mean. A
    system that kept only the average would leave two of fourteen rules
    permanently unevaluable — and they would fail silently, as a light
    that never turns yellow.

    The unit is checked against the method's canonical unit. A result
    recorded in the wrong unit is the classic silent error: the number
    looks plausible, the comparison against the requirement is nonsense,
    and nothing anywhere says so.
    """
    test = _test_row(session, test_id=test_id, organization_id=organization_id)
    if test["execution_status"] != "in_progress":
        raise TestStateError(
            f"test {test['test_number']} is {test['execution_status']}; measurements "
            "can only be recorded while it is in progress"
        )

    canonical = session.execute(
        text("SELECT canonical_unit FROM testing.test_methods WHERE id = :m"),
        {"m": test["method_id"]},
    ).scalar_one()
    if spec.unit != canonical:
        raise TestStateError(
            f"this method records {canonical}, not {spec.unit}; a value in the wrong "
            "unit compares against the requirement as nonsense"
        )

    try:
        replicate_id: uuid.UUID = session.execute(
            text(
                """
                INSERT INTO testing.test_replicates
                    (organization_id, project_id, test_id, replicate_number,
                     measured_value, unit, notes, recorded_by)
                VALUES (:org, :pid, :tid, :number, :value, :unit, :notes, :actor)
                RETURNING id
                """
            ),
            {
                "org": organization_id,
                "pid": test["project_id"],
                "tid": test_id,
                "number": spec.replicate_number,
                "value": spec.measured_value,
                "unit": spec.unit,
                "notes": spec.notes,
                "actor": actor_id,
            },
        ).scalar_one()
    except IntegrityError as exc:
        session.rollback()
        if "test_replicates_number_key" in str(exc.orig):
            raise TestError(
                f"replicate {spec.replicate_number} has already been recorded for this "
                "test; exclude it and record a new number rather than overwriting it"
            ) from exc
        raise TestError(str(exc.orig)) from exc

    write_audit(
        session,
        AuditEvent(
            action="test.replicate_recorded",
            entity_type="test",
            entity_id=str(test_id),
            organization_id=organization_id,
            user_id=actor_id,
            new_state={"replicate": spec.replicate_number, "unit": spec.unit},
            reason="raw measurement recorded",
        ),
    )
    return replicate_id


def exclude_replicate(
    session: Session,
    *,
    test_id: uuid.UUID,
    replicate_id: uuid.UUID,
    organization_id: uuid.UUID,
    actor_id: uuid.UUID,
    reason: str,
) -> dict[str, Any]:
    """Set a replicate aside, with a stated reason.

    NOT a delete — the database refuses that. An excluded replicate was
    performed, stays on the record, and is visibly excluded. Deleting it
    would rewrite the raw data, and "why does this test have four
    measurements when the method requires five" would become
    unanswerable.
    """
    if not reason:
        raise TestError("excluding a replicate removes data from the calculation; it must say why")

    row = (
        session.execute(
            text(
                """
                UPDATE testing.test_replicates
                SET is_excluded = TRUE, exclusion_reason = :reason
                WHERE id = :rid AND test_id = :tid AND organization_id = :org
                RETURNING id, replicate_number
                """
            ),
            {"rid": replicate_id, "tid": test_id, "org": organization_id, "reason": reason},
        )
        .mappings()
        .one_or_none()
    )
    if row is None:
        raise TestNotFoundError("no such replicate on this test")

    write_audit(
        session,
        AuditEvent(
            action="test.replicate_excluded",
            entity_type="test",
            entity_id=str(test_id),
            organization_id=organization_id,
            user_id=actor_id,
            new_state={"replicate": row["replicate_number"]},
            reason=reason,
        ),
    )
    return _decimal_strings(row)


def complete_execution(
    session: Session, *, test_id: uuid.UUID, organization_id: uuid.UUID, actor_id: uuid.UUID
) -> dict[str, Any]:
    """Close execution and COMPUTE the result.

    🔴 THE ONLY WRITER OF `calculated_result` IN THIS APPLICATION.

    Rule 2 of the seven non-negotiables, and `DATA_MODEL.md` §3.5 marks
    that axis SYS-only. No route accepts it. It is derived here from the
    valid raw replicates and the requirement, both read inside this
    transaction.

    A test with no requirement yields `inconclusive`, never `pass`: a
    measurement with nothing to compare against has not passed, it has
    produced a number.
    """
    test = _test_row(session, test_id=test_id, organization_id=organization_id)
    if test["execution_status"] != "in_progress":
        raise TestStateError(
            f"test {test['test_number']} is {test['execution_status']}; only a test in "
            "progress can be completed"
        )

    context = _evaluation_context(session, test=test, organization_id=organization_id)

    if context["statistics"].mean is None:
        raise TestStateError(
            "this test has no valid measurements; record the replicates or abandon it"
        )

    result = context["evaluation"].result

    row = (
        session.execute(
            text(
                """
                UPDATE testing.tests
                SET execution_status = 'complete',
                    calculated_result = :result,
                    review_state = 'awaiting_review',
                    updated_at = now()
                WHERE id = :tid AND organization_id = :org
                  AND execution_status = 'in_progress'
                RETURNING id, test_number, execution_status, calculated_result
                """
            ),
            {"tid": test_id, "org": organization_id, "result": result},
        )
        .mappings()
        .one_or_none()
    )
    if row is None:
        raise TestStateError("this test was changed by someone else; reload it")

    write_audit(
        session,
        AuditEvent(
            action="test.completed",
            entity_type="test",
            entity_id=str(test_id),
            organization_id=organization_id,
            user_id=actor_id,
            new_state={
                "execution_status": "complete",
                "calculated_result": result,
                "replicates_valid": context["statistics"].valid_count,
            },
            reason="execution complete; result computed from the raw replicates",
        ),
    )
    # §10: "A RED confirmation result automatically opens or links a Failure
    # Investigation." This is the moment such a result comes into existence —
    # `complete_execution` is the only writer of `calculated_result` — so it is
    # the only place the rule can be enforced without relying on a caller.
    #
    # DELIBERATELY IN THE SAME TRANSACTION, AND DELIBERATELY NOT SWALLOWED.
    # A completed RED confirmation with no investigation is precisely the state
    # §10 forbids, so it must not be reachable by committing half of this. If
    # the open fails, the completion fails with it and says why.
    #
    # 🔴 Do NOT "harden" this with a savepoint and a bare except. SQLAlchemy's
    # `Session.rollback()` always rolls back the TOPMOST transaction and
    # discards nested ones, and `open_failure` calls it on IntegrityError — so
    # a savepoint would not protect this completion, it would only hide that it
    # had already been destroyed.
    #
    # Idempotent by construction: the helper returns the existing investigation
    # when one already points at this test, and returns None for a screening
    # test or a non-failing result.
    investigation = open_failure_for_failed_test(
        session,
        test_id=test_id,
        organization_id=organization_id,
        actor_id=actor_id,
    )

    out = _decimal_strings(row)
    out["evaluation_detail"] = context["evaluation"].detail
    # Reported rather than left for the caller to discover: a technician who
    # completes a test needs to see that it opened an investigation, and a
    # null here means "no investigation was warranted", not "not checked".
    out["failure_investigation"] = dict(investigation) if investigation else None
    return out


# ---------------------------------------------------------------------------
# Review, approval, confirmation
# ---------------------------------------------------------------------------


def record_decision(
    session: Session,
    *,
    test_id: uuid.UUID,
    organization_id: uuid.UUID,
    actor_id: uuid.UUID,
    spec: DecisionInput,
) -> dict[str, Any]:
    """Record one review or approval decision, and move the axes.

    **The decision record is written first and is append-only.** §9
    requires every approval to write an electronic decision record into
    permanent audit history, and a record written only when the state
    change succeeds would lose exactly the decisions that were refused.

    **Segregation of duties, checked against that record.** ADR-019: QA
    approval may never come from anyone who supplied a development-side
    approval on the same test. That constraint depends on per-test
    identity, so no role check can express it — which is why authorization
    in this product is on permissions and the check is here.
    """
    test = _test_row(session, test_id=test_id, organization_id=organization_id)

    if spec.stage == "review":
        if test["execution_status"] != "complete":
            raise TestStateError(
                f"test {test['test_number']} is {test['execution_status']}; there is "
                "nothing to review until execution is complete"
            )
        # The reviewer may not be the executor. DATA_MODEL.md §3.5 states
        # it as the guard on `awaiting_review -> under_review`, and a
        # technician reviewing their own measurements removes the only
        # independent check on them.
        if test["executed_by"] is not None and test["executed_by"] == actor_id:
            raise SegregationOfDutiesError("the person who performed a test may not review it")
        new_state = _REVIEW_OUTCOMES.get(spec.decision)
        if new_state is None:
            raise TestError(f"'{spec.decision}' is not a review decision")
    elif spec.stage == "approval":
        if test["review_state"] != "reviewed":
            raise TestStateError(
                f"test {test['test_number']} has not completed technical review; "
                "approval follows review"
            )
        new_state = _APPROVAL_OUTCOMES.get(spec.decision)
        if new_state is None:
            raise TestError(f"'{spec.decision}' is not an approval decision")
        _refuse_conflicted_approver(
            session,
            test_id=test_id,
            organization_id=organization_id,
            actor_id=actor_id,
            authority_level=spec.authority_level,
        )
    else:
        raise TestError(f"'{spec.stage}' is not a decision stage")

    if spec.decision == "approve_with_condition" and not spec.condition_text:
        raise TestError(
            "a conditional approval must state its limitation; §9 requires the "
            "condition to be preserved and displayed with the result"
        )

    session.execute(
        text(
            """
            INSERT INTO testing.test_decisions
                (organization_id, project_id, test_id, decision, decision_stage,
                 authority_level, condition_text, rationale, decided_by)
            VALUES (:org, :pid, :tid, :decision, :stage, :authority, :condition,
                    :rationale, :actor)
            """
        ),
        {
            "org": organization_id,
            "pid": test["project_id"],
            "tid": test_id,
            "decision": spec.decision,
            "stage": spec.stage,
            "authority": spec.authority_level,
            "condition": spec.condition_text,
            "rationale": spec.rationale,
            "actor": actor_id,
        },
    )

    if spec.stage == "review":
        # Reaching `reviewed` opens the approval chain. DATA_MODEL.md
        # §3.5: `not_required -> pending` is a SYS transition made when
        # review completes.
        approval_state = "pending" if new_state == "reviewed" else test["approval_state"]
        session.execute(
            text(
                """
                UPDATE testing.tests
                SET review_state = :review, approval_state = :approval, updated_at = now()
                WHERE id = :tid AND organization_id = :org
                """
            ),
            {
                "review": new_state,
                "approval": approval_state,
                "tid": test_id,
                "org": organization_id,
            },
        )
    else:
        session.execute(
            text(
                """
                UPDATE testing.tests
                SET approval_state = :approval,
                    approval_condition = :condition,
                    updated_at = now()
                WHERE id = :tid AND organization_id = :org
                """
            ),
            {
                "approval": new_state,
                "condition": spec.condition_text,
                "tid": test_id,
                "org": organization_id,
            },
        )

    write_audit(
        session,
        AuditEvent(
            action=f"test.{spec.stage}_{spec.decision}",
            entity_type="test",
            entity_id=str(test_id),
            organization_id=organization_id,
            user_id=actor_id,
            new_state={"stage": spec.stage, "decision": spec.decision, "state": new_state},
            reason=spec.rationale or spec.condition_text or f"{spec.stage} decision",
        ),
    )
    return {"test_id": test_id, "stage": spec.stage, "decision": spec.decision, "state": new_state}


def _refuse_conflicted_approver(
    session: Session,
    *,
    test_id: uuid.UUID,
    organization_id: uuid.UUID,
    actor_id: uuid.UUID,
    authority_level: str | None,
) -> None:
    """ADR-019, enforced against the decision record.

    Independent QA approval must be INDEPENDENT. Somebody who already
    supplied a development-side approval on this test has formed a view;
    letting them also supply the QA approval turns a two-signature control
    into one person signing twice.

    Read from `test_decisions` rather than from role names, because the
    constraint is about who decided on THIS test, which no role can say.
    """
    if authority_level not in {"qualification", "release"}:
        return

    already = session.execute(
        text(
            """
            SELECT count(*) FROM testing.test_decisions
            WHERE test_id = :tid
              AND organization_id = :org
              AND decided_by = :actor
              AND decision_stage = 'approval'
              AND authority_level = :development
            """
        ),
        {
            "tid": test_id,
            "org": organization_id,
            "actor": actor_id,
            "development": _DEVELOPMENT_APPROVAL,
        },
    ).scalar_one()

    if already:
        raise SegregationOfDutiesError(
            "you supplied a development-side approval on this test, so you may not "
            "also supply the independent approval at this authority (ADR-019)"
        )


def confirm_test(
    session: Session, *, test_id: uuid.UUID, organization_id: uuid.UUID, actor_id: uuid.UUID
) -> dict[str, Any]:
    """Mark a result `final_confirmed`.

    **Only from `approved`, never from `conditionally_approved`.** A
    conditional approval carries a limitation that must travel with the
    result; confirming one would silently discard it. Guarded in the
    predicate AND by a CHECK constraint, so neither this function nor a
    future one can reach the state.
    """
    row = (
        session.execute(
            text(
                """
                WITH prev AS (
                    SELECT id, approval_state, test_number, final_confirmed
                    FROM testing.tests
                    WHERE id = :tid AND organization_id = :org
                    FOR UPDATE
                )
                UPDATE testing.tests t
                SET final_confirmed = TRUE,
                    confirmed_by = :actor,
                    confirmed_at = now(),
                    updated_at = now()
                FROM prev
                WHERE t.id = prev.id
                  AND prev.approval_state = 'approved'
                  AND prev.final_confirmed = FALSE
                RETURNING t.id, t.test_number, t.final_confirmed
                """
            ),
            {"tid": test_id, "org": organization_id, "actor": actor_id},
        )
        .mappings()
        .one_or_none()
    )

    if row is None:
        current = _test_row(session, test_id=test_id, organization_id=organization_id)
        if current["final_confirmed"]:
            raise TestStateError(f"test {current['test_number']} is already confirmed")
        raise TestStateError(
            f"test {current['test_number']} is {current['approval_state']}; only a fully "
            "approved result may be confirmed — a conditional approval carries a "
            "limitation that confirmation would discard"
        )

    write_audit(
        session,
        AuditEvent(
            action="test.confirmed",
            entity_type="test",
            entity_id=str(test_id),
            organization_id=organization_id,
            user_id=actor_id,
            new_state={"final_confirmed": True},
            reason="result confirmed as final",
        ),
    )
    return _decimal_strings(row)


# ---------------------------------------------------------------------------
# Reading — where the traffic light is derived
# ---------------------------------------------------------------------------


def get_test(session: Session, *, test_id: uuid.UUID, organization_id: uuid.UUID) -> dict[str, Any]:
    """One test, its raw replicates, its decisions — and its disposition.

    The disposition is COMPUTED HERE, on every read, from the five stored
    axes plus the method's limits and the requirement's threshold. There
    is no `display_color` column to go stale.

    Both fields are returned, always: `automatic_evaluation` beside
    `final_disposition`. §3.3 requires them displayed separately — a
    low-margin pass awaiting approval is both a pass and not final, and
    one field cannot say that.
    """
    test = _test_row(session, test_id=test_id, organization_id=organization_id)
    context = _evaluation_context(session, test=test, organization_id=organization_id)
    disposition = context["disposition"]

    test["replicates"] = context["replicates"]
    test["statistics"] = {
        "count": context["statistics"].count,
        "valid_count": context["statistics"].valid_count,
        "mean": context["statistics"].mean,
        "standard_deviation": context["statistics"].standard_deviation,
        "cv_percent": context["statistics"].cv_percent,
    }
    # TWO SEPARATE FIELDS, ALWAYS.
    test["automatic_evaluation"] = {
        "calculated_result": test["calculated_result"],
        "detail": context["evaluation"].detail,
        "margin_percent": context["evaluation"].margin_percent,
    }
    test["final_disposition"] = {
        "colour": disposition.colour,
        "label": disposition.label,
        "reason": disposition.reason,
        "next_action": disposition.next_action,
        "rule": disposition.rule,
    }
    test["decisions"] = [
        _decimal_strings(r)
        for r in session.execute(
            text(
                """
                SELECT id, decision, decision_stage, authority_level, condition_text,
                       rationale, decided_by, decided_at
                FROM testing.test_decisions
                WHERE test_id = :tid AND organization_id = :org
                ORDER BY decided_at
                """
            ),
            {"tid": test_id, "org": organization_id},
        ).mappings()
    ]
    return test


def list_tests(
    session: Session,
    *,
    organization_id: uuid.UUID,
    project_id: uuid.UUID | None = None,
    review_state: str | None = None,
    limit: int = 200,
) -> list[dict[str, Any]]:
    """The test queue.

    Deliberately does NOT derive a disposition per row. Doing so would
    mean a statistics query per test, and a list view that silently costs
    N round trips is how a queue becomes unusable at fifty rows. The
    stored axes are returned so a list can show what is waiting; the
    traffic light belongs to the detail view, where it can be computed
    from real replicates rather than guessed from a subset.
    """
    rows = session.execute(
        text(
            """
            SELECT t.id, t.test_number, t.project_id, t.execution_status,
                   t.validity_status, t.calculated_result, t.review_state,
                   t.approval_state, t.test_purpose, t.authority_level,
                   t.final_confirmed, t.planned_for, t.executed_at, t.updated_at,
                   m.method_code, m.name AS method_name, m.canonical_unit,
                   m.replicates_required,
                   s.sample_number,
                   (SELECT count(*) FROM testing.test_replicates r
                     WHERE r.test_id = t.id AND r.is_excluded = FALSE) AS replicates_valid
            FROM testing.tests t
            JOIN testing.test_methods m
              ON m.id = t.method_id AND m.organization_id = t.organization_id
            JOIN laboratory.samples s
              ON s.id = t.sample_id AND s.organization_id = t.organization_id
            WHERE t.organization_id = :org
              AND (:pid IS NULL OR t.project_id = :pid)
              AND (:review IS NULL OR t.review_state = :review)
            ORDER BY t.created_at DESC
            LIMIT :limit
            """
        ),
        {"org": organization_id, "pid": project_id, "review": review_state, "limit": limit},
    ).mappings()
    return [_decimal_strings(r) for r in rows]


# ---------------------------------------------------------------------------
# Internals
# ---------------------------------------------------------------------------


def _evaluation_context(
    session: Session, *, test: dict[str, Any], organization_id: uuid.UUID
) -> dict[str, Any]:
    """Everything the traffic light needs, gathered once.

    One place assembles the inputs, so `complete_execution` and
    `get_test` cannot disagree about what the numbers say — which is the
    exact shape of drift that a stored `display_color` would have made
    permanent.
    """
    method = (
        session.execute(
            text(
                """
                SELECT replicates_required, cv_limit, canonical_unit,
                       calibration_breach_policy
                FROM testing.test_methods
                WHERE id = :m AND organization_id = :org
                """
            ),
            {"m": test["method_id"], "org": organization_id},
        )
        .mappings()
        .one()
    )

    replicates = [
        _decimal_strings(r)
        for r in session.execute(
            text(
                """
                SELECT id, replicate_number, measured_value, unit, is_excluded,
                       exclusion_reason, observed_at, notes
                FROM testing.test_replicates
                WHERE test_id = :tid AND organization_id = :org
                ORDER BY replicate_number
                """
            ),
            {"tid": test["id"], "org": organization_id},
        ).mappings()
    ]

    # EXCLUDED REPLICATES ARE NOT IN THE STATISTICS AND ARE STILL RETURNED.
    # They were performed and they stay visible; what they do not do is
    # move the mean.
    statistics = replicate_statistics(
        [r["measured_value"] for r in replicates if not r["is_excluded"]]
    )

    requirement = None
    if test["requirement_id"] is not None:
        requirement = (
            session.execute(
                text(
                    """
                    SELECT target_value, minimum_value, maximum_value,
                           warning_threshold, canonical_unit
                    FROM projects.requirements
                    WHERE id = :r AND organization_id = :org
                    """
                ),
                {"r": test["requirement_id"], "org": organization_id},
            )
            .mappings()
            .one_or_none()
        )

    if statistics.mean is None:
        from app.calculations.testing import MeasurementEvaluation

        evaluation = MeasurementEvaluation(
            result="inconclusive",
            margin_percent=None,
            detail="no valid measurements have been recorded",
        )
    elif requirement is None:
        from app.calculations.testing import MeasurementEvaluation

        evaluation = MeasurementEvaluation(
            result="inconclusive",
            margin_percent=None,
            detail="this test is not linked to a requirement, so it cannot be graded",
        )
    else:
        evaluation = evaluate_against_requirement(
            statistics.mean,
            target=requirement["target_value"],
            minimum=requirement["minimum_value"],
            maximum=requirement["maximum_value"],
        )

    disposition = derive_disposition(
        DispositionInputs(
            execution_status=test["execution_status"],
            validity_status=test["validity_status"],
            calculated_result=test["calculated_result"],
            review_state=test["review_state"],
            approval_state=test["approval_state"],
            test_purpose=test["test_purpose"],
            authority_level=test["authority_level"],
            final_confirmed=test["final_confirmed"],
            replicates_required=method["replicates_required"],
            replicates_valid=statistics.valid_count,
            cv_percent=statistics.cv_percent,
            cv_limit=method["cv_limit"],
            margin_percent=evaluation.margin_percent,
            warning_threshold=(
                requirement["warning_threshold"] if requirement is not None else None
            ),
            trend_alert=test["trend_alert"],
            approval_condition=test["approval_condition"],
            next_approver=test["next_approver_role"],
        )
    )

    return {
        "method": dict(method),
        "replicates": replicates,
        "statistics": statistics,
        "evaluation": evaluation,
        "disposition": disposition,
    }


def _test_row(
    session: Session, *, test_id: uuid.UUID, organization_id: uuid.UUID
) -> dict[str, Any]:
    row = (
        session.execute(
            text(
                """
                SELECT id, organization_id, project_id, test_number, sample_id, method_id,
                       method_version_id, equipment_id, requirement_id,
                       execution_status, validity_status, calculated_result,
                       review_state, approval_state, test_purpose, authority_level,
                       final_confirmed, confirmed_by, confirmed_at,
                       approval_condition, next_approver_role, trend_alert,
                       planned_for, executed_by, executed_at, supersedes_test_id,
                       notes, created_by, created_at, updated_at
                FROM testing.tests
                WHERE id = :tid AND organization_id = :org
                """
            ),
            {"tid": test_id, "org": organization_id},
        )
        .mappings()
        .one_or_none()
    )
    if row is None:
        raise TestNotFoundError("no such test in this organization")
    return _decimal_strings(row)
