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
from app.domains.failures.service import (
    FailureError,
    FailureInput,
    open_failure,
    open_failure_for_failed_test,
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

    FIVE users, because the rules here are about identity and the approval
    LADDER now has real steps (I5). The reviewer may not be the executor; the
    independent QA approver may not be anyone who approved on the development
    side; and QUALIFICATION_CONFIRMATION has two parallel development steps
    before the lead and QA rungs, so a fixture with fewer people simply cannot
    walk it. A fixture too small to reach a rule cannot tell a working rule
    from a broken one.
    """
    suffix = uuid.uuid4().hex[:8]
    org = owner_session.execute(
        text("INSERT INTO core.organizations (code, name) VALUES (:c, :n) RETURNING id"),
        {"c": f"TST-{suffix}", "n": "Testing Org"},
    ).scalar_one()

    # 🔴 THE TENANT GUC, BECAUSE `confirm_test` NOW TOUCHES A FORCE-RLS TABLE.
    #
    # `app/core/db.py:514` sets `app.current_org` on every real request, so
    # production has always had it. This fixture never did, and got away with
    # it because `testing.tests` is RLS-enabled but NOT forced -- the owner
    # bypasses it. `workflow.domain_events` (migration 063) is born FORCE, as
    # every table since 058 is, so the owner IS subject to the policy and an
    # unset GUC denies the insert.
    #
    # Setting it here makes the fixture faithful to production rather than
    # loosening the new table to match a fixture. `false` rather than `true`
    # because this fixture spans more than one transaction.
    owner_session.execute(text("SELECT set_config('app.current_org', :o, false)"), {"o": str(org)})

    users: dict[str, uuid.UUID] = {}
    for label in ("technician", "engineer", "lead", "chemist", "qa"):
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
                "INSERT INTO core.organization_members (organization_id, user_id, status,"
                " email, display_name) SELECT :o, :u, 'active', u.email, u.display_name FROM"
                " core.users u WHERE u.id = :u"
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

    # 🔴 A STRING, AND THE ASSERTION CHECKS BOTH HALVES (I84).
    #
    # `get_test` now returns every statistic as a string, because FastAPI's
    # `jsonable_encoder` maps `Decimal` to float and this endpoint was
    # shipping a mean with its scale destroyed. `isinstance` pins the
    # contract; comparing the PARSED value pins the arithmetic without
    # pinning an incidental scale -- `Decimal("12.000000") == Decimal("12")`
    # is true, and a test that demanded the literal "12.000000" would break
    # the next time the engine's quantum changed for an unrelated reason.
    assert isinstance(detail["statistics"]["mean"], str), (
        "a measured mean must leave the service as a string, or the encoder "
        "turns it into a float and the recorded scale is lost"
    )
    assert Decimal(detail["statistics"]["mean"]) == Decimal("12")


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
    """🔴 ADR-019, NOW ENFORCED BY THE ROUTE RATHER THAN BY THIS MODULE.

    Independent QA approval must be INDEPENDENT: somebody who has already
    formed and recorded a view is not a second signature, they are the same
    signature twice.

    The rule used to be a query in `testing/service.py` against
    `test_decisions`. It is now carried as DATA on the template step —
    `must_differ_from_group = 1` on QUALIFICATION_CONFIRMATION's QA rung — and
    enforced by the engine against the route's own snapshot. That matters
    beyond tidiness: the same rule now applies to every module that routes an
    approval, instead of to whichever one remembered to re-implement it.

    🔴 AND THIS TEST WALKS THE REAL LADDER. Before I5 a single call approved a
    qualification-authority test outright. QUALIFICATION_CONFIRMATION has FOUR
    mandatory rungs — engineer and chemist in parallel (group 1), then the lead
    (group 2), then independent QA (group 3) — and the test asserts the route
    is still `pending` until the last of them, which is the bypass it exists to
    prevent.
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

    # Group 1, both rungs: two DIFFERENT people at development authority.
    first = record_decision(
        owner_session,
        test_id=test_id,
        organization_id=fx["org"],
        actor_id=fx["engineer"],
        held_permissions=DEV,
        spec=DecisionInput(decision="approve", stage="approval"),
    )
    assert first["state"] == "pending", (
        "one development approval completed a four-rung qualification ladder — "
        "this is exactly the bypass I5 closed"
    )

    record_decision(
        owner_session,
        test_id=test_id,
        organization_id=fx["org"],
        actor_id=fx["chemist"],
        held_permissions=DEV,
        spec=DecisionInput(decision="approve", stage="approval"),
    )
    # Group 2: the lead.
    record_decision(
        owner_session,
        test_id=test_id,
        organization_id=fx["org"],
        actor_id=fx["lead"],
        held_permissions=LEAD,
        spec=DecisionInput(decision="approve", stage="approval"),
    )

    # Group 3: the ENGINEER holds QA permission too, and is barred — they
    # decided in group 1, which is the group the QA rung must differ from.
    with pytest.raises(SegregationOfDutiesError, match="ADR-019"):
        record_decision(
            owner_session,
            test_id=test_id,
            organization_id=fx["org"],
            actor_id=fx["engineer"],
            held_permissions=QA,
            spec=DecisionInput(decision="approve", stage="approval"),
        )

    # Somebody who has not decided before can, and THAT completes the route.
    result = record_decision(
        owner_session,
        test_id=test_id,
        organization_id=fx["org"],
        actor_id=fx["qa"],
        held_permissions=QA,
        spec=DecisionInput(decision="approve", stage="approval"),
    )
    assert result["state"] == "approved"
    assert result["route_status"] == "approved"


def test_one_approval_does_not_complete_a_multi_rung_ladder(
    owner_session: Session, testable: dict[str, uuid.UUID]
) -> None:
    """🔴 THE DEFECT I5 CLOSED, ASSERTED DIRECTLY.

    Before I5 `record_decision` wrote `testing.test_decisions` and moved
    `approval_state` itself, so ONE call naming any authority level approved
    the test — §9's ladder was advisory. This asserts the test stays YELLOW
    after a single rung of a four-rung route, which is the observable
    difference between the two implementations.
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
    record_decision(
        owner_session,
        test_id=test_id,
        organization_id=fx["org"],
        actor_id=fx["engineer"],
        held_permissions=DEV,
        spec=DecisionInput(decision="approve", stage="approval"),
    )

    seen = get_test(owner_session, test_id=test_id, organization_id=fx["org"])
    assert seen["final_disposition"]["colour"] == "yellow"
    # And the ladder is visible rather than inferred: four rungs, one decided.
    assert len(seen["approval_route"]) == 4
    assert sum(1 for s in seen["approval_route"] if s["decision"]) == 1


def test_an_approver_without_the_step_permission_is_refused(
    owner_session: Session, testable: dict[str, uuid.UUID]
) -> None:
    """The step names the permission; the caller does not choose it.

    `DecisionInput.authority_level` is no longer consulted for approvals, so a
    caller cannot promote themselves by naming a level. Holding no approval
    permission at all must be refused — otherwise every check above passes for
    the wrong reason.
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

    with pytest.raises(SegregationOfDutiesError):
        record_decision(
            owner_session,
            test_id=test_id,
            organization_id=fx["org"],
            actor_id=fx["technician"],
            held_permissions=frozenset(),
            spec=DecisionInput(decision="approve", stage="approval"),
        )


# ---------------------------------------------------------------------------
# Confirmation
# ---------------------------------------------------------------------------


# The permissions §9's templates name on their steps. Written out because a
# test that passes `frozenset()` would be refused for the right reason by
# accident, and one that passes every permission could not tell a correctly
# gated step from an ungated one.
DEV = frozenset({"test.approve_development"})
LEAD = frozenset({"test.approve_lead"})
QA = frozenset({"test.approve_qa"})


def _approve(session: Session, fx: dict[str, uuid.UUID], test_id: uuid.UUID, **over: str) -> None:
    """Review, then walk the approval ladder to completion.

    🔴 THIS IS NOW A LADDER, NOT A SWITCH (I5). It used to be one call naming
    an authority level, which approved the test outright — bypassing §9's
    template entirely. Approval decisions now go through the shared engine, so
    this walks the route that `_plan`'s default `development` authority opens:
    OVERSIGHT_STANDARD, whose single MANDATORY step is a development approval.
    Its second rung (the lead, on escalation) is optional and does not hold the
    route open, which is what makes it optional rather than merely labelled so.
    """
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
        held_permissions=DEV,
        spec=DecisionInput(
            decision=over.get("decision", "approve"),
            stage="approval",
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


# ---------------------------------------------------------------------------
# I6 — a RED confirmation result opens its Failure Investigation, automatically
#
# CLAUDE.md §10: "A RED confirmation result automatically opens or links a
# Failure Investigation." `open_failure_for_failed_test` implemented that rule
# correctly and HAD NO CALLER, so nothing in the product ever ran it. These
# tests assert the wiring, and — more importantly — assert the two cases where
# it must NOT fire. A rule that fires on everything is not a rule.
# ---------------------------------------------------------------------------


def _failure_rows_for(session: Session, test_id: uuid.UUID) -> list[dict[str, object]]:
    """Read the investigations pointing at one test, straight from the table.

    Deliberately not via the return value of `complete_execution` — that is
    the thing under test, and a test that only reads its own subject's report
    of itself cannot detect a report that is wrong.

    ⚠️ WHAT THIS CANNOT SEE, stated rather than left implied. This reads
    through the SAME session, inside the SAME uncommitted transaction, so it
    observes flushed-but-uncommitted rows. It therefore proves the write
    reached PostgreSQL and survived whatever the subject did next; it does
    NOT prove the request-boundary commit. That gap is deliberate: this
    module's fixtures roll back by contract so the suite can be re-run against
    a developer's database without residue, and committing here would break
    it. Raised by Codex and accepted as a known limit, not closed. The
    commit boundary belongs to an API-level test — TODO I29.
    """
    return [
        dict(r)
        for r in session.execute(
            text(
                "SELECT id, failure_code, status, severity, test_id "
                "FROM quality.failures WHERE test_id = :t"
            ),
            {"t": test_id},
        ).mappings()
    ]


def test_a_failed_confirmation_automatically_opens_a_failure_investigation(
    owner_session: Session, testable: dict[str, uuid.UUID]
) -> None:
    """§10, end to end: complete a failing confirmation, get an investigation."""
    fx = testable
    test_id = _plan(owner_session, fx)
    _measure(owner_session, fx, test_id, ["2.0", "2.1", "1.9"])  # below the 5.0 minimum

    result = complete_execution(
        owner_session, test_id=test_id, organization_id=fx["org"], actor_id=fx["technician"]
    )

    assert result["calculated_result"] == "fail"

    # Reported to the caller...
    assert result["failure_investigation"] is not None
    assert result["failure_investigation"]["status"] == "open"

    # ...and actually in the table.
    rows = _failure_rows_for(owner_session, test_id)
    assert len(rows) == 1, f"expected exactly one investigation, found {len(rows)}"
    assert rows[0]["id"] == result["failure_investigation"]["id"]
    assert rows[0]["severity"] == "major"


def test_a_passing_confirmation_opens_no_investigation(
    owner_session: Session, testable: dict[str, uuid.UUID]
) -> None:
    """The first half of proving the rule can decline.

    Without this, an implementation that opened an investigation for every
    completed test would satisfy the test above.
    """
    fx = testable
    test_id = _plan(owner_session, fx)
    _measure(owner_session, fx, test_id, ["11.9", "12.0", "12.1"])  # inside 5.0-20.0

    result = complete_execution(
        owner_session, test_id=test_id, organization_id=fx["org"], actor_id=fx["technician"]
    )

    assert result["calculated_result"] == "pass"
    assert result["failure_investigation"] is None
    assert _failure_rows_for(owner_session, test_id) == []


def test_a_failed_screening_test_opens_no_investigation(
    owner_session: Session, testable: dict[str, uuid.UUID]
) -> None:
    """🔴 THE DISTINCTION THE RULE ACTUALLY TURNS ON.

    A failed SCREENING test is information, not a verdict on the product:
    screening is preliminary authority and is never confirmation evidence.
    The plan's X11 settles that there is no single global RED rule. An
    implementation keyed on `calculated_result` alone — the obvious reading —
    passes every other test in this section and fails this one.
    """
    fx = testable
    test_id = _plan(owner_session, fx, test_purpose="screening")
    _measure(owner_session, fx, test_id, ["2.0", "2.1", "1.9"])  # the same failing values

    result = complete_execution(
        owner_session, test_id=test_id, organization_id=fx["org"], actor_id=fx["technician"]
    )

    assert result["calculated_result"] == "fail", "the values must still compute to fail"
    assert result["failure_investigation"] is None
    assert _failure_rows_for(owner_session, test_id) == []


def test_the_automatic_open_links_rather_than_opening_a_second(
    owner_session: Session, testable: dict[str, uuid.UUID]
) -> None:
    """ "Opens OR LINKS" — idempotence is part of the rule, not a nicety.

    Two investigations of one failure is two half-answers, and the digital
    thread then has no single place to record the root cause.
    """
    fx = testable
    test_id = _plan(owner_session, fx)
    _measure(owner_session, fx, test_id, ["2.0", "2.1", "1.9"])

    first = complete_execution(
        owner_session, test_id=test_id, organization_id=fx["org"], actor_id=fx["technician"]
    )["failure_investigation"]
    assert first is not None

    # Re-run the helper directly: `complete_execution` refuses a second call,
    # so the only way to exercise the link branch is to invoke it again here.
    again = open_failure_for_failed_test(
        owner_session,
        test_id=test_id,
        organization_id=fx["org"],
        actor_id=fx["technician"],
    )

    assert again is not None
    assert again["id"] == first["id"], "a second investigation was opened for one failure"
    assert len(_failure_rows_for(owner_session, test_id)) == 1


def test_completion_links_to_an_investigation_that_already_existed(
    owner_session: Session, testable: dict[str, uuid.UUID]
) -> None:
    """🔴 "Opens OR LINKS" — the LINK half, exercised through the real caller.

    Raised by Codex against the first version of this commit: the idempotence
    test above proves the helper can rediscover a row IT had just created,
    which is a weaker claim. Here the investigation exists BEFORE the test is
    completed, so `complete_execution` must find and link it rather than open
    a second one.
    """
    fx = testable
    test_id = _plan(owner_session, fx)
    _measure(owner_session, fx, test_id, ["2.0", "2.1", "1.9"])

    pre_existing = owner_session.execute(
        text(
            """
            INSERT INTO quality.failures
                (organization_id, project_id, failure_code, title, description,
                 severity, test_id, opened_by)
            VALUES (:o, :p, :c, 'Opened by hand before completion',
                    'Pre-existing investigation', 'major', :t, :u)
            RETURNING id
            """
        ),
        {
            "o": fx["org"],
            "p": fx["project"],
            "c": f"FI-PRE-{uuid.uuid4().hex[:6]}",
            "t": test_id,
            "u": fx["engineer"],
        },
    ).scalar_one()
    owner_session.flush()

    result = complete_execution(
        owner_session, test_id=test_id, organization_id=fx["org"], actor_id=fx["technician"]
    )

    assert result["failure_investigation"] is not None
    assert result["failure_investigation"]["id"] == pre_existing, (
        "completion opened a new investigation instead of linking the existing one"
    )
    assert len(_failure_rows_for(owner_session, test_id)) == 1


def test_a_squatted_failure_code_does_not_block_completing_a_test(
    owner_session: Session, testable: dict[str, uuid.UUID]
) -> None:
    """🔴 A SQUATTED CODE MUST NOT MAKE A TEST PERMANENTLY UNCOMPLETABLE.

    Raised by the Supervisor. The automatic investigation generates
    `FI-<test_number>`, and `test_number` is caller-supplied. If anything
    already holds that code — a human investigation for a DIFFERENT test — the
    unique constraint refused the INSERT. Because §10's open is deliberately
    not swallowed, `complete_execution` then raised, and raised again on every
    retry: recording that a confirmation test failed became permanently
    impossible for that test, with no recovery short of a database edit.

    `_free_failure_code` now takes the first free suffix instead. The common
    case keeps the readable code; the collision case stays possible rather
    than fatal.
    """
    fx = testable
    test_id = _plan(owner_session, fx)
    _measure(owner_session, fx, test_id, ["2.0", "2.1", "1.9"])

    test_number = owner_session.execute(
        text("SELECT test_number FROM testing.tests WHERE id = :t"), {"t": test_id}
    ).scalar_one()

    # A DIFFERENT test's investigation, squatting on the generated code.
    other_test = _plan(owner_session, fx)
    owner_session.execute(
        text(
            """
            INSERT INTO quality.failures
                (organization_id, project_id, failure_code, title, description,
                 severity, test_id, opened_by)
            VALUES (:o, :p, :c, 'Squatter', 'Holds the generated code',
                    'major', :t, :u)
            """
        ),
        {
            "o": fx["org"],
            "p": fx["project"],
            "c": f"FI-{test_number}",
            "t": other_test,
            "u": fx["engineer"],
        },
    )
    owner_session.flush()

    result = complete_execution(
        owner_session, test_id=test_id, organization_id=fx["org"], actor_id=fx["technician"]
    )

    assert result["execution_status"] == "complete", "the squatted code blocked the completion"
    assert result["failure_investigation"] is not None
    # The suffix, not the base code, and not a failure.
    assert result["failure_investigation"]["failure_code"] == f"FI-{test_number}-2"
    assert len(_failure_rows_for(owner_session, test_id)) == 1


def test_open_failure_savepoint_does_not_destroy_the_callers_work(
    owner_session: Session, testable: dict[str, uuid.UUID]
) -> None:
    """🔴 THE SAVEPOINT, PROVED DIRECTLY.

    `_free_failure_code` now avoids the collision that used to reach
    `open_failure`'s IntegrityError handler through `complete_execution`, so
    the savepoint needs its own test rather than riding on that path.

    A caller does real work, then calls `open_failure` with a code that is
    already taken. The refusal must be a refusal — not a demolition of what
    the caller had already written.

    Before the savepoint, `open_failure` called `session.rollback()`, which
    rolls back the TOPMOST transaction: the completion below was discarded and
    this assertion found no row at all.
    """
    fx = testable
    test_id = _plan(owner_session, fx)
    _measure(owner_session, fx, test_id, ["11.9", "12.0", "12.1"])  # PASSES, so no auto-open

    # The caller's work: a completed test, in this transaction.
    complete_execution(
        owner_session, test_id=test_id, organization_id=fx["org"], actor_id=fx["technician"]
    )

    taken = f"FI-TAKEN-{uuid.uuid4().hex[:6]}"
    open_failure(
        owner_session,
        project_id=fx["project"],
        organization_id=fx["org"],
        actor_id=fx["engineer"],
        spec=FailureInput(failure_code=taken, title="First", description="Holds the code"),
    )
    owner_session.flush()

    with pytest.raises(FailureError) as caught:
        open_failure(
            owner_session,
            project_id=fx["project"],
            organization_id=fx["org"],
            actor_id=fx["engineer"],
            spec=FailureInput(failure_code=taken, title="Second", description="Same code"),
        )
    assert "already used" in str(caught.value)

    # 🔴 THE ASSERTION THAT DISTINGUISHES THE TWO IMPLEMENTATIONS.
    survived = (
        owner_session.execute(
            text("SELECT execution_status FROM testing.tests WHERE id = :t"), {"t": test_id}
        )
        .mappings()
        .one()
    )
    assert survived["execution_status"] == "complete", (
        "the refused INSERT rolled back the caller's earlier work - "
        "the savepoint is not containing it"
    )
    audited = owner_session.execute(
        text(
            "SELECT count(*) FROM audit.events "
            "WHERE entity_type = 'test' AND entity_id = :t AND action = 'test.completed'"
        ),
        {"t": str(test_id)},
    ).scalar_one()
    assert audited == 1, "the caller's audit event was rolled back with the refused INSERT"


def test_two_investigations_cannot_name_the_same_test(
    owner_session: Session, testable: dict[str, uuid.UUID]
) -> None:
    """🔴 "opens OR LINKS" IS NOW A CONSTRAINT, NOT A COMMENT (migration 029).

    Raised by the Supervisor: `quality.failures` had no uniqueness on
    `(organization_id, test_id)` and `POST /api/failures` accepts an arbitrary
    `test_id`, so two engineers could each legitimately open an investigation
    naming the same test. The link lookup then used `.one_or_none()`, which
    raised `MultipleResultsFound` — caught by nothing — and because the
    condition never cleared, **that test could never be completed again.** A
    permanent lockout on the path that records a failed confirmation.

    Raw SQL rather than the service, deliberately: this tests the DATABASE,
    which is the layer that still has to hold when a future caller forgets.
    Two DIFFERENT failure codes, so it is the test_id uniqueness being proved
    and not `failures_org_code_key`.
    """
    fx = testable
    test_id = _plan(owner_session, fx)

    def _insert(code: str) -> None:
        owner_session.execute(
            text(
                """
                INSERT INTO quality.failures
                    (organization_id, project_id, failure_code, title, description,
                     severity, test_id, opened_by)
                VALUES (:o, :p, :c, 'One', 'x', 'major', :t, :u)
                """
            ),
            {
                "o": fx["org"],
                "p": fx["project"],
                "c": code,
                "t": test_id,
                "u": fx["engineer"],
            },
        )

    _insert(f"FI-A-{uuid.uuid4().hex[:6]}")
    owner_session.flush()

    with pytest.raises(IntegrityError) as caught:
        _insert(f"FI-B-{uuid.uuid4().hex[:6]}")  # different CODE, same TEST
        owner_session.flush()

    assert "failures_one_per_test_uk" in str(caught.value.orig)
