"""Domain events — spec §22. The log, its boundary, and the one wired chain.

🔴 THE TEST THAT MATTERS IS THE CHAIN, NOT THE TABLE.

A table with the right constraints and nothing reacting to it is decoration.
`test_confirming_a_test_updates_the_investigation_that_names_it` drives the
real production path — `confirm_test` — and asserts that an investigation
naming that test is told. Deleting the consumer turns it red.

⚠️ THIS FILE USES `owner_session` FOR SETUP AND THE SERVICES FOR THE ACT.
Asserting the reaction by inserting events by hand would prove the table
accepts rows, which is not the claim.
"""

from __future__ import annotations

import re
import uuid
from pathlib import Path

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DatabaseError

from app.domains.events.service import (
    EVENT_SUBJECTS,
    DomainEventError,
    emit,
    events_for,
)

API_ROOT = Path(__file__).resolve().parents[2]
APP = API_ROOT / "app"
MIGRATION = API_ROOT / "migrations" / "063_domain_events.sql"


@pytest.fixture
def events_org(owner_session):
    """One organization and one person, with the tenant GUC set.

    ⚠️ IT TEARS DOWN EXPLICITLY, and the domain-events rows need the trigger
    disabled to go. That is the append-only design working, not a defect --
    `tests/auth/conftest.py` does the same for `stage_transitions`, which is
    append-only for the same reason. Seventy organizations once leaked from
    exactly this omission, and the note in `test_058_research.py` says so.
    """
    suffix = uuid.uuid4().hex[:8]

    org_id = owner_session.execute(
        text("INSERT INTO core.organizations (code, name) VALUES (:c, :n) RETURNING id"),
        {"c": f"EVT-{suffix}", "n": "Domain Events Test Org"},
    ).scalar_one()
    user_id = owner_session.execute(
        text(
            "INSERT INTO core.users (keycloak_sub, email, display_name) "
            "VALUES (:s, :e, 'Events Tester') RETURNING id"
        ),
        {"s": f"evt-{suffix}", "e": f"evt-{suffix}@example.test"},
    ).scalar_one()

    project_id = owner_session.execute(
        text(
            "INSERT INTO projects.projects (organization_id, project_code, name,"
            " confidentiality, lead_user_id) VALUES (:o, :c, 'Events Project',"
            " 'restricted', :u) RETURNING id"
        ),
        {"o": org_id, "c": f"EVP-{suffix}", "u": user_id},
    ).scalar_one()

    # FORCE RLS applies to the owner too, so the GUC is not optional here.
    owner_session.execute(
        text("SELECT set_config('app.current_org', :o, true)"), {"o": str(org_id)}
    )
    owner_session.execute(
        text("SELECT set_config('app.current_user_id', :u, true)"), {"u": str(user_id)}
    )
    owner_session.flush()

    yield {
        "org_id": org_id,
        "user_id": user_id,
        "project_id": project_id,
        "suffix": suffix,
    }

    owner_session.rollback()
    owner_session.begin()
    owner_session.execute(
        text("SELECT set_config('app.current_org', :o, true)"), {"o": str(org_id)}
    )
    owner_session.execute(
        text("ALTER TABLE workflow.domain_events DISABLE TRIGGER domain_events_no_update")
    )
    for statement in (
        "DELETE FROM workflow.domain_events WHERE organization_id = :o",
        "DELETE FROM research.investigations WHERE organization_id = :o",
        "DELETE FROM testing.tests WHERE organization_id = :o",
        "DELETE FROM testing.test_methods WHERE organization_id = :o",
        "DELETE FROM laboratory.samples WHERE organization_id = :o",
        "DELETE FROM laboratory.batches WHERE organization_id = :o",
        "DELETE FROM formulations.formula_versions WHERE organization_id = :o",
        "DELETE FROM formulations.formulas WHERE organization_id = :o",
        "DELETE FROM projects.projects WHERE organization_id = :o",
        "DELETE FROM core.organizations WHERE id = :o",
    ):
        owner_session.execute(text(statement), {"o": org_id})
    owner_session.execute(
        text("ALTER TABLE workflow.domain_events ENABLE TRIGGER domain_events_no_update")
    )
    owner_session.execute(text("DELETE FROM core.users WHERE id = :u"), {"u": user_id})
    owner_session.commit()


def _a_real_test(owner_session, fx: dict) -> uuid.UUID:
    """A genuine `testing.tests` row, because `investigations.test_id` is a FK.

    🔴 A RANDOM UUID DOES NOT WORK HERE, AND THAT IS THE POINT OF THE COLUMN.

    `investigations_test_fk` is a real, tenant-qualified foreign key, so an
    investigation cannot name a test that does not exist -- the first draft of
    this file used `uuid.uuid4()` and the database refused it. The digital
    thread (§2) means a test cannot exist alone either: it needs a method, a
    sample, a batch, a version and a formula. All six are built here.

    Copied in shape from `_cited_test` in `test_dashboard_research_widgets.py`
    rather than imported: that helper also writes an evidence card, which would
    make this file's assertions about the consumer ambiguous.
    """
    tag = uuid.uuid4().hex[:6]
    formula = owner_session.execute(
        text(
            "INSERT INTO formulations.formulas (organization_id, project_id,"
            " formula_code, name, owner_user_id, created_by)"
            " VALUES (:o, :p, :c, 'Events formula', :u, :u) RETURNING id"
        ),
        {"o": fx["org_id"], "p": fx["project_id"], "c": f"F-E{tag}", "u": fx["user_id"]},
    ).scalar_one()
    version = owner_session.execute(
        text(
            "INSERT INTO formulations.formula_versions (organization_id, project_id,"
            " formula_id, version_number, version_code, status, created_by)"
            " VALUES (:o, :p, :f, 1, :c, 'draft', :u) RETURNING id"
        ),
        {
            "o": fx["org_id"],
            "p": fx["project_id"],
            "f": formula,
            "c": f"F-E{tag}-V1",
            "u": fx["user_id"],
        },
    ).scalar_one()
    batch = owner_session.execute(
        text(
            "INSERT INTO laboratory.batches (organization_id, project_id,"
            " formula_version_id, batch_number, planned_quantity_kg, status, created_by)"
            " VALUES (:o, :p, :v, :b, 2.5, 'draft', :u) RETURNING id"
        ),
        {
            "o": fx["org_id"],
            "p": fx["project_id"],
            "v": version,
            "b": f"LB-E{tag}",
            "u": fx["user_id"],
        },
    ).scalar_one()
    sample = owner_session.execute(
        text(
            "INSERT INTO laboratory.samples (organization_id, project_id, batch_id,"
            " sample_number, taken_by) VALUES (:o, :p, :b, :s, :u) RETURNING id"
        ),
        {
            "o": fx["org_id"],
            "p": fx["project_id"],
            "b": batch,
            "s": f"SA-E{tag}",
            "u": fx["user_id"],
        },
    ).scalar_one()
    method = owner_session.execute(
        text(
            "INSERT INTO testing.test_methods (organization_id, method_code, name,"
            " property_measured, canonical_unit, created_by)"
            " VALUES (:o, :c, 'Sand-through time', 'sanding', 'minutes', :u) RETURNING id"
        ),
        {"o": fx["org_id"], "c": f"TM-E{tag}", "u": fx["user_id"]},
    ).scalar_one()
    return owner_session.execute(
        text(
            "INSERT INTO testing.tests (organization_id, project_id, sample_id,"
            " method_id, test_number, test_purpose, authority_level, created_by)"
            " VALUES (:o, :p, :s, :m, :n, 'screening', 'preliminary', :u) RETURNING id"
        ),
        {
            "o": fx["org_id"],
            "p": fx["project_id"],
            "s": sample,
            "m": method,
            "n": f"T-E{tag}",
            "u": fx["user_id"],
        },
    ).scalar_one()


# ---------------------------------------------------------------------------
# The vocabulary cannot outrun its emitters
# ---------------------------------------------------------------------------


def test_the_event_vocabulary_matches_the_database(owner_session):
    """Two literals in two places cannot be type-checked into agreement.

    `EVENT_SUBJECTS` and migration 063's CHECK carry the same strings. A name in
    Python that the database refuses fails at runtime, in a write path that has
    already changed a controlled record; a name in the database that Python
    cannot produce is a value with no writer.
    """
    definition = owner_session.execute(
        text(
            "SELECT pg_get_constraintdef(oid) FROM pg_constraint "
            "WHERE conname = 'domain_events_type_check'"
        )
    ).scalar_one()

    in_database = set(re.findall(r"'([A-Za-z]+)'::text", definition))
    # 🔴 GUARD THE GUARD. A parse that stopped matching would compare an empty
    # set with an empty set and pass.
    assert len(in_database) >= 3, f"parsed {in_database} from {definition!r} -- the parse broke"

    assert in_database == set(EVENT_SUBJECTS), (
        f"in Python only: {sorted(set(EVENT_SUBJECTS) - in_database)}; "
        f"in the database only: {sorted(in_database - set(EVENT_SUBJECTS))}"
    )


def test_every_declared_event_type_has_an_emitter():
    """🔴 A DECLARED EVENT NOBODY EMITS IS A VALUE WITH NO WRITER.

    The first draft of migration 063 declared seven types while three had a
    writer — §22 names four chains and reserving the names felt tidy. Four
    values no code can produce reads as capability and is decoration, which is
    the defect this repository has counted twenty-three of.

    So: every name in `EVENT_SUBJECTS` must appear in application source
    OUTSIDE the events module itself. Being defined is not being emitted.
    """
    emitters = ""
    for path in APP.rglob("*.py"):
        if "domains/events" in path.as_posix() or "domains\\events" in str(path):
            continue
        emitters += path.read_text(encoding="utf-8")

    assert "confirm_test" in emitters, "read no application source -- the scan broke"

    constants = {
        "FormulaVersionCreated": "FORMULA_VERSION_CREATED",
        "TestResultFinalized": "TEST_RESULT_FINALIZED",
        "ResearchInvestigationUpdatedByTestResult": "INVESTIGATION_UPDATED_BY_TEST",
        # 066. Emitted by `material_safety.on_formula_version_created`, which
        # lives outside the events module, so the constant appears in
        # application source and this scan finds it.
        "SafetyReviewRequired": "SAFETY_REVIEW_REQUIRED",
    }
    assert set(constants) == set(EVENT_SUBJECTS), (
        "this test's own map has drifted from EVENT_SUBJECTS; update both"
    )

    for event_type, constant in constants.items():
        # `TestResultFinalized` and the investigation event are emitted through
        # `announce_test_result_finalized`, which lives in the events module --
        # so the CALLER is what proves the emitter is reachable.
        reachable = constant in emitters or "announce_test_result_finalized" in emitters
        assert reachable, f"{event_type} has no emitter outside the events module"


def test_an_undeclared_event_type_is_refused_before_it_reaches_the_database(
    owner_session, events_org
):
    """The refusal is in Python, so the message names the fix.

    The CHECK would refuse it too, as an opaque constraint violation inside a
    transaction that has already changed something.
    """
    with pytest.raises(DomainEventError) as caught:
        emit(
            owner_session,
            organization_id=events_org["org_id"],
            event_type="SomethingNobodyDeclared",
            subject_id=uuid.uuid4(),
        )
    assert "not a declared domain event" in str(caught.value)


# ---------------------------------------------------------------------------
# The log's boundary
# ---------------------------------------------------------------------------


def test_the_log_is_append_only_even_for_the_owner(owner_session, events_org):
    """🔴 A TRIGGER, NOT ONLY A REVOKED GRANT.

    A revoked UPDATE stops `evercoat_app` and stops nothing else — not a
    migration, not a backfill, not a future role. This repository has a standing
    note that a REVOKE against a broader GRANT does nothing.

    Asserted as the OWNER, which is the account somebody would use to "fix" a
    row, and the one a grant-only guard would not stop.
    """
    event_id = emit(
        owner_session,
        organization_id=events_org["org_id"],
        event_type="TestResultFinalized",
        subject_id=uuid.uuid4(),
        payload={"probe": True},
    )
    owner_session.flush()

    # `match=` rather than a bare `raises(Exception)`: the refusal must come
    # from the append-only trigger and not from some other error that happens
    # to be raised on the way -- a permission problem would satisfy a broad
    # catch and prove nothing about the trigger.
    with pytest.raises(DatabaseError, match="append-only"):
        owner_session.execute(
            text("UPDATE workflow.domain_events SET event_type = :e WHERE id = :i"),
            {"e": "FormulaVersionCreated", "i": event_id},
        )
    owner_session.rollback()


def test_the_log_is_owned_by_evercoat_owner_not_the_superuser(owner_session):
    """The migration runs as `postgres`, so ownership is load-bearing.

    Without the explicit `ALTER TABLE ... OWNER TO`, the table is owned by
    `postgres` while every other table in `workflow` is owned by
    `evercoat_owner`, and the symptom arrives much later as "permission denied"
    from the owner role. Commit `0108d7d` is the previous instance of exactly
    this.
    """
    owner = owner_session.execute(
        text(
            "SELECT pg_get_userbyid(relowner) FROM pg_class "
            "WHERE oid = 'workflow.domain_events'::regclass"
        )
    ).scalar_one()
    assert owner == "evercoat_owner"


def test_the_agent_role_may_read_the_thread_and_never_announce_on_it(owner_session):
    """An agent must not be able to manufacture a fact another module reacts to.

    Asserted as a PRIVILEGE, never as the GRANT statement — the statement having
    run proves nothing about what the role ended up holding.
    """
    may_select, may_insert = owner_session.execute(
        text(
            "SELECT has_table_privilege('evercoat_agent','workflow.domain_events','SELECT'),"
            "       has_table_privilege('evercoat_agent','workflow.domain_events','INSERT')"
        )
    ).one()
    assert may_select is True
    assert may_insert is False

    # And the other direction: the application role CAN announce, or nothing
    # would ever be recorded and the assertion above would be vacuous.
    app_insert = owner_session.execute(
        text("SELECT has_table_privilege('evercoat_app','workflow.domain_events','INSERT')")
    ).scalar_one()
    assert app_insert is True


def test_the_migration_states_why_this_is_not_the_audit_log():
    """The design decision is recorded where the next reader will look.

    This repository rejected a second document repository for the shape this
    table could have. The migration must say why this one is different, or the
    next reviewer has to re-derive it.
    """
    sql = MIGRATION.read_text(encoding="utf-8")
    assert "audit.events" in sql
    # ⚠️ The shorter substring, because the sentence is WRAPPED across two
    # comment lines in the migration and the full phrase never appears
    # contiguously. A test that asserts a string a formatter can break is a
    # test about line width.
    assert "unreachable from ordinary UI" in sql


# ---------------------------------------------------------------------------
# 🔴 THE CHAIN — §22's second one, driven through the real production path
# ---------------------------------------------------------------------------


def test_confirming_a_test_updates_the_investigation_that_names_it(owner_session, events_org):
    """§22: `TestResultFinalized` -> Research Center -> related investigation updated.

    Driven through `announce_test_result_finalized`, the function `confirm_test`
    calls, against a real investigation carrying a real `test_id`.

    🔴 BOTH DIRECTIONS. An investigation that names a DIFFERENT test must not be
    told — without that half, a consumer that notified every investigation in
    the organization would pass.
    """
    from app.domains.events.service import announce_test_result_finalized

    org_id = events_org["org_id"]
    suffix = uuid.uuid4().hex[:8]
    the_test = _a_real_test(owner_session, events_org)
    another_test = _a_real_test(owner_session, events_org)

    mine = owner_session.execute(
        text(
            """
            INSERT INTO research.investigations
                (organization_id, investigation_code, title, research_question,
                 status, test_id, opened_by, owner_user_id)
            VALUES (:o, :c, 'Why did it fail?', 'What drove the failure?',
                    'active', :t, :u, :u)
            RETURNING id
            """
        ),
        {"o": org_id, "c": f"RI-{suffix}", "t": the_test, "u": events_org["user_id"]},
    ).scalar_one()
    theirs = owner_session.execute(
        text(
            """
            INSERT INTO research.investigations
                (organization_id, investigation_code, title, research_question,
                 status, test_id, opened_by, owner_user_id)
            VALUES (:o, :c, 'Unrelated', 'Something else entirely',
                    'active', :t, :u, :u)
            RETURNING id
            """
        ),
        {"o": org_id, "c": f"RX-{suffix}", "t": another_test, "u": events_org["user_id"]},
    ).scalar_one()
    owner_session.flush()

    result = announce_test_result_finalized(
        owner_session,
        organization_id=org_id,
        test_id=the_test,
        actor_id=events_org["user_id"],
        payload={"test_number": f"T-{suffix}", "project_id": None, "calculated_result": "fail"},
    )
    owner_session.flush()

    # Direction 1 -- the investigation naming this test was told.
    assert result["investigations_notified"] == [f"RI-{suffix}"]

    told = events_for(
        owner_session,
        organization_id=org_id,
        subject_type="research_investigation",
        subject_id=mine,
    )
    assert [e["event_type"] for e in told] == ["ResearchInvestigationUpdatedByTestResult"]
    assert told[0]["payload"]["calculated_result"] == "fail"
    assert told[0]["payload"]["test_number"] == f"T-{suffix}"
    # A reaction has no person behind it.
    assert told[0]["actor_id"] is None

    # Direction 2 -- the investigation naming a different test was NOT.
    assert (
        events_for(
            owner_session,
            organization_id=org_id,
            subject_type="research_investigation",
            subject_id=theirs,
        )
        == []
    )

    # And the fact itself was announced against the test, with an actor.
    about_test = events_for(
        owner_session, organization_id=org_id, subject_type="test", subject_id=the_test
    )
    assert [e["event_type"] for e in about_test] == ["TestResultFinalized"]
    assert about_test[0]["actor_id"] == str(events_org["user_id"])

    owner_session.rollback()


def test_a_closed_investigation_is_not_told(owner_session, events_org):
    """A workspace somebody finished is not woken up by a late result.

    The consumer filters on `status <> 'closed'`; without this the filter could
    be deleted and every other assertion in this file would still pass.
    """
    from app.domains.events.service import announce_test_result_finalized

    org_id = events_org["org_id"]
    suffix = uuid.uuid4().hex[:8]
    the_test = _a_real_test(owner_session, events_org)

    # `investigations_closure_complete` is
    # `(status = 'closed') = (closed_at IS NOT NULL)`, so a closed workspace must
    # carry the moment it closed. The constraint is right: a closed record with no
    # closing time is not closed, it is mislabelled.
    owner_session.execute(
        text(
            """
            INSERT INTO research.investigations
                (organization_id, investigation_code, title, research_question,
                 status, test_id, opened_by, owner_user_id, closed_at)
            VALUES (:o, :c, 'Finished', 'Answered long ago', 'closed', :t, :u, :u, now())
            """
        ),
        {"o": org_id, "c": f"RC-{suffix}", "t": the_test, "u": events_org["user_id"]},
    )
    owner_session.flush()

    result = announce_test_result_finalized(
        owner_session,
        organization_id=org_id,
        test_id=the_test,
        actor_id=events_org["user_id"],
        payload={"test_number": f"T-{suffix}", "project_id": None, "calculated_result": "pass"},
    )
    assert result["investigations_notified"] == []
    owner_session.rollback()


# ---------------------------------------------------------------------------
# §22 chain 1 (066) — an event with no reader is not an integration
# ---------------------------------------------------------------------------


def test_every_declared_event_type_has_a_consumer_or_is_named_as_terminal() -> None:
    """🔴 THE MIRROR OF `test_every_declared_event_type_has_an_emitter`.

    That test catches a name nobody can produce. This one catches a fact
    nobody reacts to — which is what `FormulaVersionCreated` was for the whole
    life of migration 063: announced by `revise_version`, consumed by nothing,
    and reading like integration.

    ⚠️ NOT EVERY EVENT NEEDS A CONSUMER, so this is not "everything must be
    subscribed". Two of the four are TERMINAL by design — the end of a chain,
    recorded for a screen and a later reader rather than to drive another
    module. They are named individually so a fifth type forces a decision
    rather than silently joining them.
    """
    from app.domains.events.service import EVENT_SUBJECTS, subscribers
    from app.domains.events.wiring import wire_domain_events

    wire_domain_events()

    # 🔴 THREE SHAPES, NAMED SEPARATELY, BECAUSE THEY ARE NOT THE SAME THING.
    #
    # The first draft of this test had two and went red on
    # `TestResultFinalized` -- which IS consumed, just not through the
    # registry. Collapsing that into "terminal" would have hidden the most
    # interesting fact in the file.
    terminal = {
        # End of chain 2: the investigation has been told. Nothing reacts to
        # the telling.
        "ResearchInvestigationUpdatedByTestResult",
        # End of chain 1: a review is required. A screen reads it; no module
        # reacts, and `safety_alerts` belongs to the SDS chain (§23) and is
        # written by a permissioned act rather than by a reaction.
        "SafetyReviewRequired",
    }
    # ⚠️ CONSUMED, BUT NOT DECOUPLED. `announce_test_result_finalized` emits
    # this AND performs the reaction, in one function, inside the events
    # module -- so `domains/events` itself knows about `research.investigations`.
    # That is 063's shape and it works; it is simply not what §22 asks for,
    # because the coupling moved into the events module rather than going
    # away. Migrating it to the registry is chain 2's own slice.
    reaction_lives_in_the_events_module = {"TestResultFinalized"}

    for event_type in EVENT_SUBJECTS:
        if event_type in terminal:
            assert not subscribers(event_type), (
                f"{event_type} is named terminal here but something now reacts "
                "to it — decide which it is and say so."
            )
            continue
        if event_type in reaction_lives_in_the_events_module:
            continue
        assert subscribers(event_type), (
            f"{event_type} is announced and nothing consumes it. An event with "
            "no reader reads as integration and is a log entry. Either wire a "
            "reaction in domains/events/wiring.py or name it above."
        )


@pytest.fixture
def version_missing_its_sds(owner_session, events_org):
    """A draft version whose only material REQUIRES an SDS and has none.

    That is the exact state `formulations._safety_checks` refuses at
    submission, so it is the state the safety module must react to when the
    version is created.
    """
    suffix = events_org["suffix"]
    org = events_org["org_id"]
    project = events_org["project_id"]
    user = events_org["user_id"]

    material = owner_session.execute(
        text(
            """
            INSERT INTO materials.materials
                (organization_id, material_code, name, category, role, status,
                 density_g_cm3, requires_sds, created_by)
            VALUES (:o, :c, :c, 'Fixture', 'resin', 'approved', 1.2000, true, :u)
            RETURNING id
            """
        ),
        {"o": org, "c": f"RM-SDS-{suffix}", "u": user},
    ).scalar_one()

    formula = owner_session.execute(
        text(
            """
            INSERT INTO formulations.formulas
                (organization_id, project_id, formula_code, name, owner_user_id, created_by)
            VALUES (:o, :p, :c, 'Chain 1 fixture', :u, :u) RETURNING id
            """
        ),
        {"o": org, "p": project, "c": f"FRM-E-{suffix}", "u": user},
    ).scalar_one()

    version = owner_session.execute(
        text(
            """
            INSERT INTO formulations.formula_versions
                (organization_id, project_id, formula_id, version_number, version_code,
                 status, created_by)
            VALUES (:o, :p, :f, 1, :vc, 'draft', :u) RETURNING id
            """
        ),
        {"o": org, "p": project, "f": formula, "vc": f"FRM-E-{suffix}-V001", "u": user},
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

    yield {"version_id": version, "material_id": material, "formula_id": formula}

    owner_session.execute(
        text("DELETE FROM formulations.formula_components WHERE formula_version_id = :v"),
        {"v": version},
    )
    owner_session.execute(
        text("DELETE FROM formulations.formula_versions WHERE id = :v"), {"v": version}
    )
    owner_session.execute(text("DELETE FROM formulations.formulas WHERE id = :f"), {"f": formula})
    owner_session.execute(text("DELETE FROM materials.materials WHERE id = :m"), {"m": material})


def test_a_new_version_missing_an_sds_announces_that_a_review_is_required(
    owner_session, events_org, version_missing_its_sds
) -> None:
    """§22 chain 1, end to end, through the REAL dispatch.

    🔴 ASSERTED ON THE SECOND EVENT, NOT THE FIRST. `FormulaVersionCreated`
    was being written before this chain existed; asserting it proves nothing
    about the reaction. What is new is that the safety module ANSWERED.

    Falsified by removing the `subscribe` call in `wiring.py`: the first event
    is still written and this goes red — verified before it was committed.
    """
    from app.domains.events.service import (
        FORMULA_VERSION_CREATED,
        SAFETY_REVIEW_REQUIRED,
        dispatch,
    )
    from app.domains.events.wiring import wire_domain_events

    wire_domain_events()

    org = events_org["org_id"]
    version_id = version_missing_its_sds["version_id"]

    results = dispatch(
        owner_session,
        organization_id=org,
        event_type=FORMULA_VERSION_CREATED,
        subject_id=version_id,
        project_id=events_org["project_id"],
        payload={"version_code": "F001-v2"},
        actor_id=events_org["user_id"],
    )

    assert results, "nothing reacted to FormulaVersionCreated"
    outcome = results[0]

    assert outcome["blocks"], (
        "the safety module found nothing wrong with a version whose only "
        "material requires an SDS and has none — which is the exact state "
        "submission refuses"
    )
    assert outcome["event_id"] is not None

    announced = owner_session.execute(
        text(
            """
            SELECT payload FROM workflow.domain_events
             WHERE organization_id = :org AND event_type = :etype AND subject_id = :sid
            """
        ),
        {"org": org, "etype": SAFETY_REVIEW_REQUIRED, "sid": version_id},
    ).scalar_one()

    # 🔴 THE REASONS TRAVEL WITH THE EVENT. "2 problems" sends the reader
    # looking; the sentence names the material.
    assert announced["reasons"], "the announcement carried no reason"
    assert any("safety data sheet" in reason for reason in announced["reasons"])


def test_a_version_whose_materials_have_their_sheets_announces_nothing(
    owner_session, events_org
) -> None:
    """The other direction, and the one that makes the test above mean something.

    A reaction that announced on every revision would pass the test above
    while being useless — an event stream that always fires trains its readers
    to ignore it, which is why `raise_alerts_for_revision` also refuses to
    raise on "no substantive change".

    Here the version has no components at all, so there is no unmet SDS
    requirement and nothing should be said.
    """
    from app.domains.events.service import (
        FORMULA_VERSION_CREATED,
        SAFETY_REVIEW_REQUIRED,
        dispatch,
    )
    from app.domains.events.wiring import wire_domain_events

    wire_domain_events()

    suffix = events_org["suffix"]
    org = events_org["org_id"]
    project = events_org["project_id"]
    user = events_org["user_id"]

    formula = owner_session.execute(
        text(
            """
            INSERT INTO formulations.formulas
                (organization_id, project_id, formula_code, name, owner_user_id, created_by)
            VALUES (:o, :p, :c, 'Chain 1 clean', :u, :u) RETURNING id
            """
        ),
        {"o": org, "p": project, "c": f"FRM-C-{suffix}", "u": user},
    ).scalar_one()
    version = owner_session.execute(
        text(
            """
            INSERT INTO formulations.formula_versions
                (organization_id, project_id, formula_id, version_number, version_code,
                 status, created_by)
            VALUES (:o, :p, :f, 1, :vc, 'draft', :u) RETURNING id
            """
        ),
        {"o": org, "p": project, "f": formula, "vc": f"FRM-C-{suffix}-V001", "u": user},
    ).scalar_one()

    try:
        results = dispatch(
            owner_session,
            organization_id=org,
            event_type=FORMULA_VERSION_CREATED,
            subject_id=version,
            project_id=project,
            payload={"version_code": "F002-v1"},
            actor_id=user,
        )
        assert results[0]["blocks"] == []
        assert results[0]["event_id"] is None

        announced = owner_session.execute(
            text(
                "SELECT count(*) FROM workflow.domain_events "
                " WHERE organization_id = :org AND event_type = :etype AND subject_id = :sid"
            ),
            {"org": org, "etype": SAFETY_REVIEW_REQUIRED, "sid": version},
        ).scalar_one()
        assert announced == 0, "a review was announced for a version with nothing wrong"
    finally:
        owner_session.execute(
            text("DELETE FROM formulations.formula_versions WHERE id = :v"), {"v": version}
        )
        owner_session.execute(
            text("DELETE FROM formulations.formulas WHERE id = :f"), {"f": formula}
        )
