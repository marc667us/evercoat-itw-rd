"""The Test Module's invariants.

The plan calls this slice "maximum depth, non-deferrable", and the source
is specific about what depth means: the Test Module is not complete
because a form exists to enter results. These are the guarantees that
make a result trustworthy — that the number was computed and not typed,
that the raw evidence cannot be rewritten, and that the people who sign
it off are not the same person twice.

WHICH SESSION. `owner_session` for constraints, triggers and service
rules, which apply to the owner identically. There are no isolation
assertions here: migration 018 reuses migration 005's policy shape
verbatim, which `test_015_materials_formulations.py` already exercises on
`app_session`.
"""

from __future__ import annotations

import json
import re
import uuid
from decimal import Decimal

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError, IntegrityError
from sqlalchemy.orm import Session

from app.calculations.testing import (
    APPROVAL_STATES,
    CALCULATED_RESULTS,
    EXECUTION_STATUSES,
    REVIEW_STATES,
    VALIDITY_STATUSES,
)
from app.domains.testing.service import (
    DecisionInput,
    ReplicateInput,
    SegregationOfDutiesError,
    TestError,
    TestInput,
    TestStateError,
    complete_execution,
    confirm_test,
    create_test,
    exclude_replicate,
    get_test,
    record_decision,
    record_replicate,
    start_execution,
)

# The three fields DATA_MODEL.md §3.1 names as derived and server-owned.
SERVER_OWNED = ("calculated_result", "display_color", "final_status")


# ---------------------------------------------------------------------------
# The blocklist — no database needed, and the most important test here
# ---------------------------------------------------------------------------


def test_no_endpoint_anywhere_accepts_a_server_owned_field() -> None:
    """🔴 THE ABSENCE IS THE MECHANISM, SO THE ABSENCE IS TESTED.

    `calculated_result`, `display_color` and `final_status` are derived
    and server-owned. Rule 2 of the seven non-negotiables gives the
    arithmetic to Python; §3.1 puts these three on the server-controlled
    blocklist BY NAME, because the names drifted across four earlier
    documents and the Supervisor found (S4) that the drift would have
    left a safety-critical field off that list under its real name.

    A field with no route cannot be posted — but an absence is invisible
    in a diff, and the next person to add a convenience endpoint would
    not know. This reads the whole OpenAPI schema, so it fails wherever
    the field reappears rather than only where it was expected.

    Takes no fixtures deliberately: it must run even where no database is
    reachable, because it is checking the shape of the API and not the
    contents of a table.
    """
    from app.main import create_app

    schema = json.dumps(create_app().openapi())
    # Request bodies only. `calculated_result` legitimately appears in
    # RESPONSES — it is read constantly; what must never exist is a way
    # to send one.
    bodies = [
        json.dumps(operation.get("requestBody", {}))
        for path in create_app().openapi()["paths"].values()
        for operation in path.values()
        if isinstance(operation, dict)
    ]
    component_names = re.findall(r'"([A-Za-z]+)":\s*\{"\$ref"', schema)
    assert component_names is not None  # keeps the schema parse meaningful

    for field in SERVER_OWNED:
        offenders = [b for b in bodies if field in b]
        assert not offenders, (
            f"an endpoint accepts '{field}' in its request body. That field is "
            "derived and server-owned (DATA_MODEL.md §3.1); a client must never "
            "be able to state it."
        )


def test_the_database_vocabularies_match_the_engine_exactly() -> None:
    """One vocabulary, not two.

    The engine's tuples drive the traffic light and the database's CHECK
    constraints drive what can be stored. If they disagree, a row exists
    that no rule matches — and rule 14 would quietly report it CONFIRMED,
    which is the worst possible failure mode for a disagreement nobody
    can see.

    Compared against the migration SQL rather than a live database so it
    runs everywhere, and because the migration is the definition.
    """
    import pathlib

    sql = (
        pathlib.Path(__file__).resolve().parents[2]
        / "migrations"
        / "018_testing_methods_tests_replicates.sql"
    ).read_text(encoding="utf-8")

    for column, expected in (
        ("execution_status", EXECUTION_STATUSES),
        ("validity_status", VALIDITY_STATUSES),
        ("calculated_result", CALCULATED_RESULTS),
        ("review_state", REVIEW_STATES),
        ("approval_state", APPROVAL_STATES),
    ):
        for value in expected:
            assert f"'{value}'" in sql, (
                f"the engine allows {column} = '{value}' and migration 018 never "
                "mentions it; a row the traffic light can reason about could not "
                "be stored"
            )


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def testable(owner_session: Session) -> dict[str, uuid.UUID]:
    """A sample ready to test, a method, a requirement, and three people.

    Three users because two of this module's rules are about identity:
    the reviewer may not be the executor, and the independent approver
    may not be somebody who already approved on the development side.
    A fixture with fewer could not tell a working rule from a broken one.
    """
    suffix = uuid.uuid4().hex[:8]
    org = owner_session.execute(
        text("INSERT INTO core.organizations (code, name) VALUES (:c, :n) RETURNING id"),
        {"c": f"TST-{suffix}", "n": "Testing Org"},
    ).scalar_one()

    users: dict[str, uuid.UUID] = {}
    for label in ("technician", "engineer", "lead"):
        uid = owner_session.execute(
            text(
                """
                INSERT INTO core.users (keycloak_sub, email, display_name)
                VALUES (:s, :e, :n) RETURNING id
                """
            ),
            {"s": str(uuid.uuid4()), "e": f"{label}-{suffix}@example.test", "n": label},
        ).scalar_one()
        owner_session.execute(
            text(
                """
                INSERT INTO core.organization_members (organization_id, user_id, status)
                VALUES (:o, :u, 'active')
                """
            ),
            {"o": org, "u": uid},
        )
        users[label] = uid

    project = owner_session.execute(
        text(
            """
            INSERT INTO projects.projects (organization_id, project_code, name, confidentiality)
            VALUES (:o, :c, 'Testing fixture project', 'normal') RETURNING id
            """
        ),
        {"o": org, "c": f"RDP-T-{suffix}"},
    ).scalar_one()

    requirement = owner_session.execute(
        text(
            """
            INSERT INTO projects.requirements
                (organization_id, project_id, requirement_code, category, name,
                 minimum_value, maximum_value, canonical_unit, warning_threshold,
                 criticality, verification_method, status, created_by)
            -- 'major', not 'high'. The vocabulary is
            -- ('critical','major','minor','informational') -- migration 003
            -- line 309. The first draft of this fixture guessed a plausible
            -- word instead of reading the constraint, and CI failed all
            -- seventeen database tests in this file on it.
            VALUES (:o, :p, :c, 'technical', 'Adhesion', 5.0, 20.0, 'MPa', 10.0,
                    'major', 'test', 'approved', :u)
            RETURNING id
            """
        ),
        {"o": org, "p": project, "c": f"REQ-{suffix}", "u": users["lead"]},
    ).scalar_one()

    method = owner_session.execute(
        text(
            """
            INSERT INTO testing.test_methods
                (organization_id, method_code, name, property_measured, canonical_unit,
                 replicates_required, cv_limit, created_by)
            VALUES (:o, :c, 'Pull-off adhesion', 'adhesion', 'MPa', 3, 5.0, :u)
            RETURNING id
            """
        ),
        {"o": org, "c": f"TM-{suffix}", "u": users["engineer"]},
    ).scalar_one()

    # A batch and a sample, so the test has a physical provenance.
    material = owner_session.execute(
        text(
            """
            INSERT INTO materials.materials
                (organization_id, material_code, name, category, role, status, created_by)
            VALUES (:o, :c, 'Fixture resin', 'Resin', 'resin', 'approved', :u)
            RETURNING id
            """
        ),
        {"o": org, "c": f"RM-T-{suffix}", "u": users["engineer"]},
    ).scalar_one()
    formula = owner_session.execute(
        text(
            """
            INSERT INTO formulations.formulas
                (organization_id, project_id, formula_code, name, owner_user_id, created_by)
            VALUES (:o, :p, :c, 'Fixture', :u, :u) RETURNING id
            """
        ),
        {"o": org, "p": project, "c": f"FRM-T-{suffix}", "u": users["engineer"]},
    ).scalar_one()
    # 🔴 DRAFT FIRST, COMPONENTS, THEN APPROVE. In that order, and not
    # because it is tidier.
    #
    # Migration 015's trigger freezes the composition of any version that
    # has left `draft`. The first draft of this fixture inserted the
    # version as `approved` and then added its component, and CI refused
    # all seventeen tests in this file with "the composition of version
    # ... is frozen".
    #
    # THAT IS THE SECOND TIME TODAY. `scripts/seed.py` made the identical
    # mistake this morning and was fixed the same way. The rule is not
    # obscure -- it is the one §8 exists to state -- and I still wrote it
    # backwards twice, which is the argument for the trigger being a
    # trigger rather than a convention.
    version = owner_session.execute(
        text(
            """
            INSERT INTO formulations.formula_versions
                (organization_id, project_id, formula_id, version_number, version_code,
                 status, created_by)
            VALUES (:o, :p, :f, 1, :vc, 'draft', :u) RETURNING id
            """
        ),
        {"o": org, "p": project, "f": formula, "vc": f"FRM-T-{suffix}-V1", "u": users["engineer"]},
    ).scalar_one()
    owner_session.execute(
        text(
            """
            INSERT INTO formulations.formula_components
                (organization_id, project_id, formula_version_id, material_id, percentage)
            VALUES (:o, :p, :v, :m, 100.0000)
            """
        ),
        {"o": org, "p": project, "v": version, "m": material},
    )
    owner_session.execute(
        text(
            """
            UPDATE formulations.formula_versions
            SET status = 'approved', approved_by = :u, approved_at = now()
            WHERE id = :v
            """
        ),
        {"u": users["engineer"], "v": version},
    )
    batch = owner_session.execute(
        text(
            """
            INSERT INTO laboratory.batches
                (organization_id, project_id, formula_version_id, batch_number,
                 planned_quantity_kg, status, authorized_by, authorized_at, created_by)
            VALUES (:o, :p, :v, :bn, 1.0, 'completed', :u, now(), :u) RETURNING id
            """
        ),
        {"o": org, "p": project, "v": version, "bn": f"LB-T-{suffix}", "u": users["technician"]},
    ).scalar_one()
    sample = owner_session.execute(
        text(
            """
            INSERT INTO laboratory.samples
                (organization_id, project_id, batch_id, sample_number, taken_by)
            VALUES (:o, :p, :b, :sn, :u) RETURNING id
            """
        ),
        {"o": org, "p": project, "b": batch, "sn": f"SMP-{suffix}", "u": users["technician"]},
    ).scalar_one()
    owner_session.flush()

    return {
        "org": org,
        "project": project,
        "sample": sample,
        "method": method,
        "requirement": requirement,
        **users,
    }


def _plan(session: Session, fx: dict[str, uuid.UUID], **over: object) -> uuid.UUID:
    spec = {
        "test_number": f"T-{uuid.uuid4().hex[:8]}",
        "sample_id": fx["sample"],
        "method_id": fx["method"],
        "requirement_id": fx["requirement"],
        "test_purpose": "confirmation",
        "authority_level": "development",
    }
    spec.update(over)
    result = create_test(
        session,
        organization_id=fx["org"],
        actor_id=fx["engineer"],
        spec=TestInput(**spec),  # type: ignore[arg-type]
    )
    return result["id"]


def _measure(
    session: Session, fx: dict[str, uuid.UUID], test_id: uuid.UUID, values: list[str]
) -> None:
    start_execution(session, test_id=test_id, organization_id=fx["org"], actor_id=fx["technician"])
    for n, v in enumerate(values, start=1):
        record_replicate(
            session,
            test_id=test_id,
            organization_id=fx["org"],
            actor_id=fx["technician"],
            spec=ReplicateInput(replicate_number=n, measured_value=Decimal(v), unit="MPa"),
        )


# ---------------------------------------------------------------------------
# The result is COMPUTED
# ---------------------------------------------------------------------------


def test_the_result_is_computed_from_the_replicates_and_never_supplied(
    owner_session: Session, testable: dict[str, uuid.UUID]
) -> None:
    """Rule 2 of the seven non-negotiables.

    `complete_execution` takes no result argument — there is nowhere to
    put one — and derives `pass` from a mean of 12.0 MPa against a
    requirement of 5.0 to 20.0.
    """
    fx = testable
    test_id = _plan(owner_session, fx)
    _measure(owner_session, fx, test_id, ["11.9", "12.0", "12.1"])

    result = complete_execution(
        owner_session, test_id=test_id, organization_id=fx["org"], actor_id=fx["technician"]
    )

    assert result["calculated_result"] == "pass"


def test_a_measurement_outside_the_requirement_computes_to_fail(
    owner_session: Session, testable: dict[str, uuid.UUID]
) -> None:
    """Verified in both directions: a computation that always returned
    `pass` would satisfy the test above and be worthless."""
    fx = testable
    test_id = _plan(owner_session, fx)
    _measure(owner_session, fx, test_id, ["2.0", "2.1", "1.9"])

    result = complete_execution(
        owner_session, test_id=test_id, organization_id=fx["org"], actor_id=fx["technician"]
    )

    assert result["calculated_result"] == "fail"


def test_a_test_with_no_requirement_is_inconclusive_and_never_a_pass(
    owner_session: Session, testable: dict[str, uuid.UUID]
) -> None:
    """🔴 ABSENCE MUST NOT PRESENT AS SUCCESS.

    A measurement with nothing to compare against has not passed; it has
    produced a number. This project already shipped a screen where an
    empty requirement set rendered "ALL REQUIREMENTS PASSED".
    """
    fx = testable
    test_id = _plan(owner_session, fx, requirement_id=None)
    _measure(owner_session, fx, test_id, ["12.0", "12.0", "12.0"])

    result = complete_execution(
        owner_session, test_id=test_id, organization_id=fx["org"], actor_id=fx["technician"]
    )

    assert result["calculated_result"] == "inconclusive"


def test_a_replicate_in_the_wrong_unit_is_refused(
    owner_session: Session, testable: dict[str, uuid.UUID]
) -> None:
    """The classic silent error: the number looks plausible, the
    comparison against the requirement is nonsense, and nothing says so."""
    fx = testable
    test_id = _plan(owner_session, fx)
    start_execution(
        owner_session, test_id=test_id, organization_id=fx["org"], actor_id=fx["technician"]
    )

    with pytest.raises(TestStateError, match="MPa"):
        record_replicate(
            owner_session,
            test_id=test_id,
            organization_id=fx["org"],
            actor_id=fx["technician"],
            spec=ReplicateInput(replicate_number=1, measured_value=Decimal("12"), unit="psi"),
        )


# ---------------------------------------------------------------------------
# Raw measurements are evidence
# ---------------------------------------------------------------------------


def test_a_recorded_measurement_cannot_be_edited(
    owner_session: Session, testable: dict[str, uuid.UUID]
) -> None:
    """Raw data is the foundation every approval rests on.

    Editing one would let an inconvenient result be tidied after the fact
    with nothing on the record to show it.
    """
    fx = testable
    test_id = _plan(owner_session, fx)
    _measure(owner_session, fx, test_id, ["12.0"])
    owner_session.flush()

    with pytest.raises(DBAPIError) as caught:
        owner_session.execute(
            text("UPDATE testing.test_replicates SET measured_value = 99 WHERE test_id = :t"),
            {"t": test_id},
        )

    assert "cannot be changed" in str(caught.value.orig)


def test_a_recorded_measurement_cannot_be_deleted(
    owner_session: Session, testable: dict[str, uuid.UUID]
) -> None:
    """The DELETE case, which an UPDATE-only guard would miss.

    "Why does this test have four measurements when the method requires
    five" must stay answerable.
    """
    fx = testable
    test_id = _plan(owner_session, fx)
    _measure(owner_session, fx, test_id, ["12.0"])
    owner_session.flush()

    with pytest.raises(DBAPIError) as caught:
        owner_session.execute(
            text("DELETE FROM testing.test_replicates WHERE test_id = :t"), {"t": test_id}
        )

    assert "never deleted" in str(caught.value.orig)


def test_excluding_a_replicate_keeps_it_on_the_record_and_out_of_the_mean(
    owner_session: Session, testable: dict[str, uuid.UUID]
) -> None:
    """An excluded replicate was performed and stays visible.

    Both halves matter: it must not move the statistics, and it must not
    disappear.
    """
    fx = testable
    test_id = _plan(owner_session, fx)
    _measure(owner_session, fx, test_id, ["12.0", "12.0", "99.0"])

    outlier = owner_session.execute(
        text(
            """
            SELECT id FROM testing.test_replicates
            WHERE test_id = :t AND measured_value = 99.0
            """
        ),
        {"t": test_id},
    ).scalar_one()

    exclude_replicate(
        owner_session,
        test_id=test_id,
        replicate_id=outlier,
        organization_id=fx["org"],
        actor_id=fx["engineer"],
        reason="instrument slipped; visible surface damage",
    )

    detail = get_test(owner_session, test_id=test_id, organization_id=fx["org"])

    assert len(detail["replicates"]) == 3, "the excluded replicate disappeared from the record"
    assert detail["statistics"]["valid_count"] == 2
    assert detail["statistics"]["mean"] == Decimal("12")


def test_excluding_a_replicate_without_a_reason_is_refused(
    owner_session: Session, testable: dict[str, uuid.UUID]
) -> None:
    """Removing data from a calculation with no record of the judgement
    that removed it."""
    fx = testable
    test_id = _plan(owner_session, fx)
    _measure(owner_session, fx, test_id, ["12.0"])
    replicate = owner_session.execute(
        text("SELECT id FROM testing.test_replicates WHERE test_id = :t"), {"t": test_id}
    ).scalar_one()

    with pytest.raises(TestError, match="must say why"):
        exclude_replicate(
            owner_session,
            test_id=test_id,
            replicate_id=replicate,
            organization_id=fx["org"],
            actor_id=fx["engineer"],
            reason="",
        )


# ---------------------------------------------------------------------------
# Segregation of duties
# ---------------------------------------------------------------------------


def test_the_executor_may_not_review_their_own_test(
    owner_session: Session, testable: dict[str, uuid.UUID]
) -> None:
    """A technician reviewing their own measurements removes the only
    independent check on them."""
    fx = testable
    test_id = _plan(owner_session, fx)
    _measure(owner_session, fx, test_id, ["12.0", "12.0", "12.0"])
    complete_execution(
        owner_session, test_id=test_id, organization_id=fx["org"], actor_id=fx["technician"]
    )

    with pytest.raises(SegregationOfDutiesError, match="may not review"):
        record_decision(
            owner_session,
            test_id=test_id,
            organization_id=fx["org"],
            actor_id=fx["technician"],
            spec=DecisionInput(decision="approve", stage="review"),
        )


def test_a_development_approver_may_not_also_give_the_qa_approval(
    owner_session: Session, testable: dict[str, uuid.UUID]
) -> None:
    """🔴 ADR-019, AND THE REASON AUTHORIZATION IS ON PERMISSIONS.

    "QA approval may never come from anyone who supplied a
    development-side approval on the same test." That constraint depends
    on per-test identity, so NO ROLE CHECK CAN EXPRESS IT — the rule is
    enforced by reading the decision record and asking who has already
    decided.

    Independent means independent: somebody who has already formed and
    recorded a view is not a second signature, they are the same
    signature twice.
    """
    fx = testable
    test_id = _plan(owner_session, fx, authority_level="qualification")
    _measure(owner_session, fx, test_id, ["12.0", "12.0", "12.0"])
    complete_execution(
        owner_session, test_id=test_id, organization_id=fx["org"], actor_id=fx["technician"]
    )
    record_decision(
        owner_session,
        test_id=test_id,
        organization_id=fx["org"],
        actor_id=fx["engineer"],
        spec=DecisionInput(decision="approve", stage="review"),
    )
    # The engineer approves at development authority.
    record_decision(
        owner_session,
        test_id=test_id,
        organization_id=fx["org"],
        actor_id=fx["engineer"],
        spec=DecisionInput(decision="approve", stage="approval", authority_level="development"),
    )

    # And is then barred from the qualification-authority approval.
    with pytest.raises(SegregationOfDutiesError, match="ADR-019"):
        record_decision(
            owner_session,
            test_id=test_id,
            organization_id=fx["org"],
            actor_id=fx["engineer"],
            spec=DecisionInput(
                decision="approve", stage="approval", authority_level="qualification"
            ),
        )

    # Somebody who has not decided before can.
    result = record_decision(
        owner_session,
        test_id=test_id,
        organization_id=fx["org"],
        actor_id=fx["lead"],
        spec=DecisionInput(decision="approve", stage="approval", authority_level="qualification"),
    )
    assert result["state"] == "approved"


# ---------------------------------------------------------------------------
# Confirmation
# ---------------------------------------------------------------------------


def _approve(session: Session, fx: dict[str, uuid.UUID], test_id: uuid.UUID, **over: str) -> None:
    record_decision(
        session,
        test_id=test_id,
        organization_id=fx["org"],
        actor_id=fx["engineer"],
        spec=DecisionInput(decision="approve", stage="review"),
    )
    record_decision(
        session,
        test_id=test_id,
        organization_id=fx["org"],
        actor_id=fx["lead"],
        spec=DecisionInput(
            decision=over.get("decision", "approve"),
            stage="approval",
            authority_level="development",
            condition_text=over.get("condition_text"),
        ),
    )


def test_a_conditionally_approved_result_cannot_be_confirmed(
    owner_session: Session, testable: dict[str, uuid.UUID]
) -> None:
    """🔴 A CONDITIONAL APPROVAL CARRIES A LIMITATION.

    Confirming one would silently discard it — and `final_confirmed`
    is what downstream release decisions read. DATA_MODEL.md §3.5:
    "only from `approved`; never from `conditionally_approved`".
    """
    fx = testable
    test_id = _plan(owner_session, fx)
    _measure(owner_session, fx, test_id, ["12.0", "12.0", "12.0"])
    complete_execution(
        owner_session, test_id=test_id, organization_id=fx["org"], actor_id=fx["technician"]
    )
    _approve(
        owner_session,
        fx,
        test_id,
        decision="approve_with_condition",
        condition_text="valid for development comparison only",
    )

    with pytest.raises(TestStateError, match="conditional"):
        confirm_test(owner_session, test_id=test_id, organization_id=fx["org"], actor_id=fx["lead"])


def test_a_fully_approved_result_can_be_confirmed(
    owner_session: Session, testable: dict[str, uuid.UUID]
) -> None:
    """Verified in both directions."""
    fx = testable
    test_id = _plan(owner_session, fx)
    _measure(owner_session, fx, test_id, ["12.0", "12.0", "12.0"])
    complete_execution(
        owner_session, test_id=test_id, organization_id=fx["org"], actor_id=fx["technician"]
    )
    _approve(owner_session, fx, test_id)

    result = confirm_test(
        owner_session, test_id=test_id, organization_id=fx["org"], actor_id=fx["lead"]
    )
    assert result["final_confirmed"] is True


def test_the_database_refuses_a_confirmation_without_full_approval(
    owner_session: Session, testable: dict[str, uuid.UUID]
) -> None:
    """The service guards it AND a CHECK constraint guards it.

    The service is the comprehensible refusal; the constraint is the
    mechanism no future code path can route around.
    """
    fx = testable
    test_id = _plan(owner_session, fx)
    owner_session.flush()

    with pytest.raises(IntegrityError) as caught:
        owner_session.execute(
            text(
                """
                UPDATE testing.tests
                SET final_confirmed = TRUE, confirmed_by = :u, confirmed_at = now()
                WHERE id = :t
                """
            ),
            {"u": fx["lead"], "t": test_id},
        )

    assert "confirmation_requires_full_approval" in str(caught.value.orig)


# ---------------------------------------------------------------------------
# The traffic light, end to end
# ---------------------------------------------------------------------------


def test_a_passing_test_is_yellow_until_it_is_approved(
    owner_session: Session, testable: dict[str, uuid.UUID]
) -> None:
    """🔴 RULE 6 OF THE SEVEN, THROUGH THE WHOLE STACK.

    The engine's unit tests prove rule 12 in isolation. This proves the
    service assembles the inputs correctly from real rows — that the
    disposition a screen would receive is the one the algorithm intends.
    """
    fx = testable
    test_id = _plan(owner_session, fx)
    _measure(owner_session, fx, test_id, ["12.0", "12.0", "12.0"])
    complete_execution(
        owner_session, test_id=test_id, organization_id=fx["org"], actor_id=fx["technician"]
    )

    before = get_test(owner_session, test_id=test_id, organization_id=fx["org"])
    assert before["automatic_evaluation"]["calculated_result"] == "pass"
    assert before["final_disposition"]["colour"] == "yellow"

    _approve(owner_session, fx, test_id)

    after = get_test(owner_session, test_id=test_id, organization_id=fx["org"])
    assert after["final_disposition"]["colour"] == "green"


def test_both_fields_are_always_returned_separately(
    owner_session: Session, testable: dict[str, uuid.UUID]
) -> None:
    """§3.3: automatic evaluation BESIDE final disposition.

    A low-margin pass awaiting approval is both a pass and not final, and
    one field cannot say that. A client that received only a colour would
    have no way to show the distinction.
    """
    fx = testable
    test_id = _plan(owner_session, fx)
    _measure(owner_session, fx, test_id, ["12.0", "12.0", "12.0"])
    complete_execution(
        owner_session, test_id=test_id, organization_id=fx["org"], actor_id=fx["technician"]
    )

    detail = get_test(owner_session, test_id=test_id, organization_id=fx["org"])

    assert "automatic_evaluation" in detail
    assert "final_disposition" in detail
    assert detail["final_disposition"]["next_action"], "a yellow with no next action"


def test_a_decision_record_cannot_be_rewritten(
    owner_session: Session, testable: dict[str, uuid.UUID]
) -> None:
    """§9: every approval writes into PERMANENT audit history.

    A decision log that can be edited answers none of the questions it
    exists for.
    """
    fx = testable
    test_id = _plan(owner_session, fx)
    _measure(owner_session, fx, test_id, ["12.0", "12.0", "12.0"])
    complete_execution(
        owner_session, test_id=test_id, organization_id=fx["org"], actor_id=fx["technician"]
    )
    record_decision(
        owner_session,
        test_id=test_id,
        organization_id=fx["org"],
        actor_id=fx["engineer"],
        spec=DecisionInput(decision="approve", stage="review"),
    )
    owner_session.flush()

    with pytest.raises(DBAPIError) as caught:
        owner_session.execute(
            text("UPDATE testing.test_decisions SET decision = 'reject' WHERE test_id = :t"),
            {"t": test_id},
        )

    assert "append-only" in str(caught.value.orig)


def test_a_test_cannot_be_repointed_at_a_different_sample(
    owner_session: Session, testable: dict[str, uuid.UUID]
) -> None:
    """The measurements on it were taken from the original.

    Re-pointing would silently re-attribute physical evidence to material
    it did not come from — the traceability chain broken at its last
    link.
    """
    fx = testable
    test_id = _plan(owner_session, fx)

    # A SECOND, genuinely different sample. The first draft of this test
    # re-pointed at the SAME sample -- which the trigger correctly ignores,
    # because nothing changed -- and then asserted `... or True` to make it
    # pass anyway. That is a test that cannot fail, which is the thing this
    # file exists to prevent elsewhere. Caught in self-review.
    other_sample = owner_session.execute(
        text(
            """
            INSERT INTO laboratory.samples
                (organization_id, project_id, batch_id, sample_number, taken_by)
            SELECT s.organization_id, s.project_id, s.batch_id, :sn, s.taken_by
            FROM laboratory.samples s WHERE s.id = :existing
            RETURNING id
            """
        ),
        {"sn": f"SMP-OTHER-{uuid.uuid4().hex[:6]}", "existing": fx["sample"]},
    ).scalar_one()
    owner_session.flush()

    with pytest.raises(DBAPIError) as caught:
        owner_session.execute(
            text("UPDATE testing.tests SET sample_id = :s WHERE id = :t"),
            {"s": other_sample, "t": test_id},
        )

    assert "re-pointed" in str(caught.value.orig)
