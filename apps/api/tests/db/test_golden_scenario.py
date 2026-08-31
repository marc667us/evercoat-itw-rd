"""THE GOLDEN SCENARIO — MVP-1's acceptance spine. TODO I3.

`IMPLEMENTATION_PLAN.md:440`, from master §44:

    Director creates/approves project → Lead assigns team → Chemist creates
    formula → Lead approves lab → Lab creates batch + sample → Engineer
    creates confirmation test → raw results entered → app analyzes → **RED**
    → failure investigation opens → Chemist creates revised formula → new
    batch → retest passes technically → **YELLOW pending approvals** →
    Engineer/Chemist/Lead approve → **GREEN** → validation candidate →
    dashboards update.

    "The YELLOW→GREEN transition is the single most important assertion in
    the suite."

═══════════════════════════════════════════════════════════════════════════
🔴 WHAT THIS FILE IS, AND WHAT IT IS NOT
═══════════════════════════════════════════════════════════════════════════

§44's gate is the scenario passing **on the deployed instance**, with every
arrow asserted **in UI and database state**. This file is the DATABASE half,
driven through the real domain services against a real PostgreSQL.

It is NOT the gate. The UI half needs screens that do not exist for most of
these steps, and "on the deployed instance" needs an API and a Keycloak that
are not deployed (TODO I13 — and measured 2026-08-21 as a plan boundary, not
a technical one). **Do not mark I3 closed on the strength of this file.**

What it IS: the first time the whole digital thread has ever run end to end.
Every previous session tested a link; nothing tested the chain. §2 says the
thread is the product's defining asset and that no record may become an
isolated island — this is the test that would notice if it did.

CLAUDE.md:334 says "eleven of the golden scenario's fifteen steps have no
table, route, service or page". That was true when it was written on
2026-08-18 and is now FALSE: every arrow below resolves to a real service.
Measured before writing this, not assumed.

═══════════════════════════════════════════════════════════════════════════
WHY THE ASSERTIONS ARE WHERE THEY ARE
═══════════════════════════════════════════════════════════════════════════

Each arrow asserts the STATE THE NEXT ARROW DEPENDS ON, not merely that the
call returned. A scenario test that only checks the last assertion proves the
happy path ran; it does not say where it broke when it stops working, and a
fifteen-step chain that fails at step 12 with one assertion is a fifteen-step
debugging problem.

The RED and YELLOW→GREEN transitions are asserted through `get_test`, which
DERIVES the disposition on every read from the five stored axes — so what is
checked is what a screen would show, not what this test computed.
"""

from __future__ import annotations

import io
import pathlib
import uuid
from decimal import Decimal

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.object_storage import FilesystemObjectStore, new_object_key
from app.domains.formulations.service import (
    ComponentInput,
    RevisionInput,
    create_formula,
    decide_version,
    list_formulas,
    revise_version,
    set_components,
    submit_version,
)
from app.domains.laboratory.service import (
    BatchInput,
    SampleInput,
    authorize_batch,
    complete_batch,
    create_batch,
    create_sample,
    list_batches,
    record_weighing,
    start_batch,
)
from app.domains.opportunities.service import (
    OpportunityDecision,
    OpportunityInput,
    convert_to_project,
    create_opportunity,
    decide_opportunity,
    list_opportunities,
    submit_opportunity,
)
from app.domains.projects.members import add_member
from app.domains.requirements.service import verification_matrix
from app.domains.testing.service import (
    DecisionInput,
    ReplicateInput,
    TestInput,
    complete_execution,
    create_test,
    get_test,
    list_tests,
    record_decision,
    record_replicate,
    start_execution,
)

DEV = frozenset({"test.approve_development"})


def _document_store() -> FilesystemObjectStore:
    """A throwaway store for the scenario's documents.

    Under `tmp/` rather than the API's configured root: the scenario is a test
    and must not deposit files into whatever store a developer's API happens to
    be pointed at. The bytes only need to exist and hash consistently -- the
    row's checksum has to describe something real, which is the whole point of
    I41.
    """
    import tempfile

    return FilesystemObjectStore(pathlib.Path(tempfile.gettempdir()) / "evercoat-golden-docs")


def _people(session: Session, org: uuid.UUID, suffix: str) -> dict[str, uuid.UUID]:
    """Five people, because §44's cast has five distinct roles and the rules
    under test are about WHO did what: the approver may not be the submitter,
    the reviewer may not be the executor, and independent approval must be
    independent."""
    people: dict[str, uuid.UUID] = {}
    for role in ("director", "lead", "chemist", "engineer", "technician"):
        uid = session.execute(
            text(
                "INSERT INTO core.users (keycloak_sub, email, display_name) "
                "VALUES (:s, :e, :n) RETURNING id"
            ),
            {"s": str(uuid.uuid4()), "e": f"{role}-{suffix}@example.test", "n": role},
        ).scalar_one()
        session.execute(
            text(
                "INSERT INTO core.organization_members (organization_id, user_id, status,"
                " email, display_name) SELECT :o, :u, 'active', u.email, u.display_name FROM"
                " core.users u WHERE u.id = :u"
            ),
            {"o": org, "u": uid},
        )
        people[role] = uid
    return people


def test_the_golden_scenario_runs_end_to_end(owner_session: Session) -> None:
    """Fifteen arrows, each asserted in database state."""
    s = owner_session
    suffix = uuid.uuid4().hex[:8]

    org = s.execute(
        text("INSERT INTO core.organizations (code, name) VALUES (:c, :n) RETURNING id"),
        {"c": f"GOLD-{suffix}", "n": "Golden Org"},
    ).scalar_one()

    # 🔴 THE TENANT GUC, BECAUSE THE THREAD NOW CROSSES A FORCE-RLS TABLE.
    #
    # Step 12 confirms a test, and `confirm_test` announces
    # `TestResultFinalized` into `workflow.domain_events` (migration 063, spec
    # §22). That table is born FORCE RLS like every table since 058, so the
    # owner is NOT exempt and an unset `app.current_org` denies the insert.
    #
    # `app/core/db.py:514` sets this on every real request. The scenario claims
    # to walk the path production walks, so it should have been setting it all
    # along -- it only got away without it because the older tables it touches
    # are RLS-enabled but not forced.
    s.execute(text("SELECT set_config('app.current_org', :o, false)"), {"o": str(org)})

    who = _people(s, org, suffix)
    s.flush()

    # ── 1. Director creates the opportunity ──────────────────────────────
    opportunity = create_opportunity(
        s,
        data=OpportunityInput(
            opportunity_code=f"OPP-{suffix}",
            title="Faster-sanding polyester body filler",
            market_need="Bodyshops lose billable time waiting for cure.",
            product_family="polyester_filler",
        ),
        actor_id=who["director"],
        organization_id=org,
    )

    # ── 2. ...submits it for a gate decision ─────────────────────────────
    # 🔴 THIS STEP HAD NO PRODUCTION PATH. `create_opportunity` wrote `draft`
    # and `decide_opportunity` refused anything outside
    # {feasibility, awaiting_decision, on_hold} -- and NOTHING wrote those. So
    # every opportunity ever created was undecidable, and the first arrow of
    # this scenario was unreachable. Found by writing this test.
    submit_opportunity(s, opportunity_id=opportunity, organization_id=org, actor_id=who["chemist"])

    # ── 3. Director APPROVES it. Rule 4: humans approve. ─────────────────
    status = decide_opportunity(
        s,
        opportunity_id=opportunity,
        decision=OpportunityDecision(
            decision="approve", rationale="Clear demand and we hold the resin chemistry."
        ),
        actor_id=who["director"],
        organization_id=org,
    )
    assert status == "approved", "an unapproved opportunity must not become a project"

    # ── 3. ...and it becomes a project, KEEPING THE LINK (§2). ───────────
    project = convert_to_project(
        s,
        opportunity_id=opportunity,
        project_code=f"RDP-{suffix}",
        name="Faster-sanding filler",
        lead_user_id=who["lead"],
        actor_id=who["director"],
        organization_id=org,
    )
    s.flush()

    origin = s.execute(
        text("SELECT opportunity_id FROM projects.projects WHERE id = :p"), {"p": project}
    ).scalar_one()
    assert origin == opportunity, (
        "the project does not point back at the opportunity it came from - "
        "the first link of the digital thread is already broken"
    )

    # ── 4. Lead assigns the team ─────────────────────────────────────────
    for role, project_role in (
        ("chemist", "chemist"),
        ("engineer", "engineer"),
        ("technician", "technician"),
    ):
        add_member(
            s,
            project_id=project,
            organization_id=org,
            actor_id=who["lead"],
            user_id=who[role],
            project_role=project_role,
        )
    s.flush()

    # ── 5. Chemist creates the formula and its first version ─────────────
    material = s.execute(
        text(
            """
            INSERT INTO materials.materials
                (organization_id, material_code, name, category, role, status, created_by,
                 density_g_cm3, solids_fraction, voc_fraction, cost_per_kg)
            VALUES (:o, :c, 'Orthophthalic resin', 'Resin', 'resin', 'approved', :u,
                    1.1000, 0.6500, 0.3500, 4.20)
            RETURNING id
            """
        ),
        {"o": org, "c": f"RM-{suffix}", "u": who["chemist"]},
    ).scalar_one()

    # 🔴 THE SDS IS ATTACHED, NOT SWITCHED OFF.
    # `requires_sds` defaults TRUE, and `submit_version` hard-blocks a formula
    # containing a material that needs one without it -- correctly, and §8
    # says a critical safety check cannot be waived at submission. Setting
    # `requires_sds = false` to get this scenario moving would have quietly
    # disabled the exact control the scenario is supposed to demonstrate
    # working. A real chemist files the sheet.
    #
    # ⚠️ AND UNTIL I41 THIS INSERT WAS ITSELF THE DEFECT IN MINIATURE.
    #
    # It wrote a row naming `sds/<suffix>.pdf` and stored nothing, because
    # nothing could store anything. So the acceptance scenario -- the artefact
    # that decides whether MVP-1 is done -- POSITIVELY CANONISED the broken
    # evidence model: it proved the gate could be satisfied by a row, which is
    # exactly what made the gate worthless. Codex named this while reviewing
    # the extension plan.
    #
    # The scenario now stores real bytes through the real port, so the arrow it
    # asserts is the one the application actually requires. `usable_documents`
    # (migration 037) refuses anything less.
    sds_bytes = b"%PDF-1.4\n% golden scenario synthetic safety data sheet\n"
    stored = _document_store().put(
        new_object_key(org, "SDS"), io.BytesIO(sds_bytes), "application/pdf"
    )
    s.execute(
        text(
            """
            INSERT INTO materials.material_documents
                (organization_id, material_id, document_type, title, storage_key,
                 uploaded_by, content_type, byte_size, checksum_sha256,
                 status, scan_status, scanner_name, scanner_version, scanned_at)
            VALUES (:o, :m, 'SDS', 'Safety data sheet', :k, :u,
                    'application/pdf', :size, :checksum,
                    'approved', 'clean', 'golden-scenario', 'n/a', now())
            """
        ),
        {
            "o": org,
            "m": material,
            "k": stored.key,
            "u": who["chemist"],
            "size": stored.byte_size,
            "checksum": stored.checksum_sha256,
        },
    )
    s.flush()

    formula = create_formula(
        s,
        project_id=project,
        organization_id=org,
        actor_id=who["chemist"],
        spec=_formula_input(suffix),
    )
    version_one = formula["version_id"]

    set_components(
        s,
        version_id=version_one,
        organization_id=org,
        actor_id=who["chemist"],
        components=[ComponentInput(material_id=material, percentage=Decimal("100.0000"))],
    )
    submit_version(s, version_id=version_one, organization_id=org, actor_id=who["chemist"])

    # ── 6. Lead approves it for the lab. The approver is NOT the submitter.
    decide_version(
        s,
        version_id=version_one,
        organization_id=org,
        actor_id=who["lead"],
        decision="approve",
        note="Proceed to lab batch.",
    )
    s.flush()

    approved = s.execute(
        text("SELECT status FROM formulations.formula_versions WHERE id = :v"),
        {"v": version_one},
    ).scalar_one()
    assert approved == "approved", "a batch cannot be made from an unapproved formula"

    # ── 7. Lab makes the batch and takes a sample ────────────────────────
    sample_one = _batch_and_sample(s, org, who, version_one, f"{suffix}-1")

    # ── 8. Engineer plans a CONFIRMATION test against a requirement ──────
    requirement = _requirement(s, org, project, who, suffix)
    method = _method(s, org, who, suffix)

    test_one = create_test(
        s,
        organization_id=org,
        actor_id=who["engineer"],
        spec=TestInput(
            test_number=f"T-{suffix}-1",
            sample_id=sample_one,
            method_id=method,
            requirement_id=requirement,
            test_purpose="confirmation",
            authority_level="development",
        ),
    )["id"]

    # ── 9. Technician enters the RAW replicates. Never an aggregate (§10).
    _measure(s, org, who, test_one, ["2.0", "2.1", "1.9"])  # below the 5.0 MPa minimum

    # ── 10. The APP analyses. The result is COMPUTED, never supplied. ────
    completed = complete_execution(
        s, test_id=test_one, organization_id=org, actor_id=who["technician"]
    )
    assert completed["calculated_result"] == "fail"

    red = get_test(s, test_id=test_one, organization_id=org)
    assert red["final_disposition"]["colour"] == "red", (
        f"a confirmation test below its requirement must be RED, got "
        f"{red['final_disposition']['colour']}"
    )

    # ── 11. ...and a FAILURE INVESTIGATION OPENS AUTOMATICALLY (§10). ────
    assert completed["failure_investigation"] is not None, (
        "a RED confirmation result did not open a Failure Investigation"
    )
    investigation = completed["failure_investigation"]["id"]

    # ── 12. Chemist revises the formula, RECORDING WHAT DROVE IT (§29) ───
    revision = revise_version(
        s,
        version_id=version_one,
        organization_id=org,
        actor_id=who["chemist"],
        spec=RevisionInput(
            change_reason="Raise the resin fraction to recover flexural strength.",
            technical_hypothesis="The filler loading is embrittling the cured matrix.",
            driver_type="failure",
            driver_failure_id=investigation,
        ),
    )
    version_two = revision["version_id"]
    s.flush()

    # 🔴 THE HOLE §29 EXISTS TO CLOSE: "why was this version created?"
    driver = s.execute(
        text(
            "SELECT failure_id FROM formulations.formula_version_drivers "
            "WHERE formula_version_id = :v AND driver_type = 'failure'"
        ),
        {"v": version_two},
    ).scalar_one()
    assert driver == investigation, (
        "the revision does not name the failure that caused it - the thread has a "
        "hole exactly where §2 says it must not"
    )
    parent = s.execute(
        text("SELECT parent_version_id FROM formulations.formula_versions WHERE id = :v"),
        {"v": version_two},
    ).scalar_one()
    assert parent == version_one, "the revision lost its genealogy"

    # ── 13. New batch from the revised formula, and a retest ────────────
    set_components(
        s,
        version_id=version_two,
        organization_id=org,
        actor_id=who["chemist"],
        components=[ComponentInput(material_id=material, percentage=Decimal("100.0000"))],
    )
    submit_version(s, version_id=version_two, organization_id=org, actor_id=who["chemist"])
    decide_version(
        s,
        version_id=version_two,
        organization_id=org,
        actor_id=who["lead"],
        decision="approve",
        note="Revised composition approved for lab.",
    )
    sample_two = _batch_and_sample(s, org, who, version_two, f"{suffix}-2")

    test_two = create_test(
        s,
        organization_id=org,
        actor_id=who["engineer"],
        spec=TestInput(
            test_number=f"T-{suffix}-2",
            sample_id=sample_two,
            method_id=method,
            requirement_id=requirement,
            test_purpose="confirmation",
            authority_level="development",
        ),
    )["id"]
    _measure(s, org, who, test_two, ["12.0", "12.1", "11.9"])  # inside 5.0-20.0

    retest = complete_execution(
        s, test_id=test_two, organization_id=org, actor_id=who["technician"]
    )
    assert retest["calculated_result"] == "pass"
    assert retest["failure_investigation"] is None, (
        "a PASSING confirmation opened a failure investigation"
    )

    # ── 14. 🔴 YELLOW PENDING APPROVALS ─────────────────────────────────
    # Rule 6 of the seven non-negotiables: a technically PASSING test stays
    # YELLOW while mandatory approvals are incomplete. This is the assertion
    # §44 calls the most important in the suite, and it has two halves.
    yellow = get_test(s, test_id=test_two, organization_id=org)
    assert yellow["automatic_evaluation"]["calculated_result"] == "pass"
    assert yellow["final_disposition"]["colour"] == "yellow", (
        "a passing test went straight to GREEN with its approvals outstanding - "
        "rule 6 is not being applied"
    )

    # ── 15. Engineer reviews, Lead approves → GREEN ─────────────────────
    record_decision(
        s,
        test_id=test_two,
        organization_id=org,
        actor_id=who["engineer"],
        spec=DecisionInput(decision="approve", stage="review"),
    )
    approval = record_decision(
        s,
        test_id=test_two,
        organization_id=org,
        actor_id=who["lead"],
        held_permissions=DEV,
        spec=DecisionInput(decision="approve", stage="approval"),
    )
    assert approval["state"] == "approved"

    green = get_test(s, test_id=test_two, organization_id=org)
    assert green["final_disposition"]["colour"] == "green", (
        f"the YELLOW->GREEN transition did not happen: "
        f"{green['final_disposition']['colour']} - {green['final_disposition']['reason']}"
    )
    # GREEN is AUTHORITY-QUALIFIED (§10), never a bare tick.
    assert green["final_disposition"]["reason"], "a GREEN with no stated authority"

    # ── The thread, walked backwards from the released result ───────────
    # §2's real test is not that each arrow was written, but that the chain
    # can be TRAVERSED: from the approved test back to the opportunity that
    # started it. A record that cannot be walked back to is the isolated
    # island the rule forbids.
    walked = s.execute(
        text(
            """
            SELECT o.opportunity_code
            FROM testing.tests t
            JOIN laboratory.samples sm ON sm.id = t.sample_id
            JOIN laboratory.batches b  ON b.id = sm.batch_id
            JOIN formulations.formula_versions v ON v.id = b.formula_version_id
            JOIN formulations.formula_versions parent ON parent.id = v.parent_version_id
            JOIN formulations.formula_version_drivers d
              ON d.formula_version_id = v.id AND d.driver_type = 'failure'
            JOIN quality.failures f ON f.id = d.failure_id
            JOIN testing.tests failed_test ON failed_test.id = f.test_id
            JOIN projects.projects p ON p.id = t.project_id
            JOIN innovation.opportunities o ON o.id = p.opportunity_id
            WHERE t.id = :t
            """
        ),
        {"t": test_two},
    ).scalar_one()

    assert walked == f"OPP-{suffix}", (
        "the approved result cannot be traced back to the opportunity that "
        "started it - the digital thread does not hold end to end"
    )

    # ── The thread can also say WHEN each arrow was drawn ────────────────
    #
    # Owner instruction, 2026-08-30: every action and event on the pipeline
    # must carry its date — added, defined, created, executed, started.
    #
    # 🔴 THE COLUMNS EXISTED THE WHOLE TIME; THE PROJECTIONS DID NOT RETURN
    # THEM. Four of the five list endpoints stored `created_at` and selected
    # everything except it, so every pipeline screen could say what STAGE a
    # record was at and never when it got there. Nothing failed, because
    # nothing asked.
    #
    # ⚠️ ASSERTED HERE, IN THE SCENARIO, RATHER THAN IN A TEST OF ITS OWN.
    # A standalone test would call these five functions against whatever org
    # it could find, and an org with no rows returns `[]` — over which every
    # assertion below passes while checking nothing. This scenario has just
    # built one of each entity, so the lists are guaranteed non-empty, and
    # that is asserted before anything is read out of them.
    #
    # ⚠️ NOT A TEST THAT THE VALUE IS "RIGHT". A timestamp default cannot be
    # wrong in an interesting way. What can regress — and did, silently, for
    # the whole life of these endpoints — is the field being ABSENT from the
    # projection. That is what this measures.
    projections = {
        "opportunities": list_opportunities(s, organization_id=org),
        "projects": _project_rows(s, org),
        "formulas": list_formulas(s, organization_id=org),
        "batches": list_batches(s, organization_id=org),
        "tests": list_tests(s, organization_id=org),
        "requirements": verification_matrix(s, project_id=project, organization_id=org)[
            "requirements"
        ],
    }

    for name, rows in projections.items():
        assert rows, (
            f"{name} returned no rows, so asserting anything about their shape "
            f"proves nothing - the scenario above built one of each"
        )
        missing = [i for i, row in enumerate(rows) if "created_at" not in dict(row)]
        assert not missing, (
            f"{name}: rows {missing} carry no created_at, so the view that "
            f"lists them cannot say when the record was created"
        )
        undated = [i for i, row in enumerate(rows) if dict(row)["created_at"] is None]
        assert not undated, (
            f"{name}: rows {undated} have a NULL created_at - a record that "
            f"exists was created at some point, so this is bad data rather "
            f"than a step that has not happened yet"
        )


# ---------------------------------------------------------------------------
# Helpers — deliberately thin. A scenario test whose setup is hidden behind
# helpers stops being readable as a scenario.
# ---------------------------------------------------------------------------


def test_a_project_created_through_the_route_comes_back_dated(
    owner_session: Session,
) -> None:
    """POST /api/projects must answer with the creation date it just wrote.

    🔴 A DEFAULT AND A MISSING COLUMN CANCEL EACH OTHER OUT.

    `ProjectSummary.created_at` is DEFAULTED, so a `RETURNING` clause that
    omits the column does not fail: the route answers 201 with
    `created_at: null`, and the grid renders "—" beside a project created one
    second earlier. Nothing raises, nothing logs, and both halves look correct
    read on their own. Found by reading the create path after fixing the list
    path — the list was the reported problem, and this was the same defect one
    route over.

    ⚠️ THE ROUTE FUNCTION, NOT THE SQL. Asserting the query text would pass
    over exactly the failure this exists to catch, because the model is what
    decides what reaches the client.
    """
    from app.api.projects import ProjectCreate, create_project
    from app.core.security import Principal

    s = owner_session
    suffix = uuid.uuid4().hex[:8]
    org = s.execute(
        text("INSERT INTO core.organizations (code, name) VALUES (:c, :n) RETURNING id"),
        {"c": f"DATE-{suffix}", "n": "Dated Org"},
    ).scalar_one()
    who = _people(s, org, suffix)
    s.flush()

    created = create_project(
        payload=ProjectCreate(
            project_code=f"RDP-{suffix}",
            name="A project that knows its own birthday",
        ),
        principal=Principal(
            user_id=who["lead"],
            organization_id=org,
            keycloak_sub=f"sub-{suffix}",
            email=f"lead-{suffix}@example.invalid",
            display_name="Lead",
        ),
        session=s,
    )

    assert created.created_at is not None, (
        "the create route answered without a creation date, so a project is "
        "undated on the screen that lists it until something re-reads it"
    )


def _project_rows(s: Session, org: uuid.UUID) -> list[dict[str, object]]:
    """The projects list AS THE ROUTE RETURNS IT, not as its SQL selects it.

    🔴 THE MODEL IS THE CONTRACT HERE, NOT THE QUERY. `list_projects` builds
    `ProjectSummary(**row)`, and that model DROPS any key it does not declare
    while supplying a default for one the query omits. So a projection change
    and a schema change can each silently undo the other, and reading the
    SELECT would show neither. This calls the route function itself.

    `principal` is unused by the body (`_ = principal`), so nothing is
    authorized here — RLS on the owner session is what governs visibility, and
    only the SHAPE of the rows is being asserted.
    """
    from app.api.projects import list_projects

    return [
        row.model_dump()
        for row in list_projects(principal=None, session=s)  # type: ignore[arg-type]
        if row.id is not None
    ]


def _formula_input(suffix: str):  # type: ignore[no-untyped-def]
    from app.domains.formulations.service import FormulaInput

    return FormulaInput(
        formula_code=f"FRM-{suffix}",
        name="Faster-sanding filler",
        product_family="polyester_filler",
    )


def _requirement(
    s: Session, org: uuid.UUID, project: uuid.UUID, who: dict[str, uuid.UUID], suffix: str
) -> uuid.UUID:
    return s.execute(
        text(
            """
            INSERT INTO projects.requirements
                (organization_id, project_id, requirement_code, category, name,
                 minimum_value, maximum_value, canonical_unit, warning_threshold,
                 criticality, verification_method, status, created_by)
            -- 'technical', not 'mechanical'. The vocabulary is
            -- ('technical','application','process','safety','commercial',
            -- 'regulatory') -- read from the constraint, not guessed. The
            -- first draft of this file guessed a plausible word, exactly as
            -- test_018's fixture once did.
            VALUES (:o, :p, :c, 'technical', 'Flexural strength',
                    5.0, 20.0, 'MPa', 5.0, 'major', 'test', 'approved', :u)
            RETURNING id
            """
        ),
        {"o": org, "p": project, "c": f"REQ-{suffix}", "u": who["engineer"]},
    ).scalar_one()


def _method(s: Session, org: uuid.UUID, who: dict[str, uuid.UUID], suffix: str) -> uuid.UUID:
    return s.execute(
        text(
            """
            INSERT INTO testing.test_methods
                (organization_id, method_code, name, property_measured,
                 canonical_unit, replicates_required, cv_limit, created_by)
            VALUES (:o, :c, 'Three-point flexure', 'flexural_strength',
                    'MPa', 3, 15.0, :u)
            RETURNING id
            """
        ),
        {"o": org, "c": f"TM-{suffix}", "u": who["engineer"]},
    ).scalar_one()


def _batch_and_sample(
    s: Session,
    org: uuid.UUID,
    who: dict[str, uuid.UUID],
    version_id: uuid.UUID,
    suffix: str,
) -> uuid.UUID:
    """A batch taken through its real lifecycle, not inserted at 'completed'.

    Migration 015's trigger freezes a version's composition once it leaves
    draft, and the batch has its own state machine. Short-cutting either
    would make this scenario prove less than it appears to.
    """
    batch = create_batch(
        s,
        formula_version_id=version_id,
        organization_id=org,
        actor_id=who["technician"],
        spec=BatchInput(batch_number=f"LB-{suffix}", planned_quantity_kg=Decimal("1.0")),
    )["batch_id"]
    authorize_batch(s, batch_id=batch, organization_id=org, actor_id=who["lead"])
    start_batch(s, batch_id=batch, organization_id=org, actor_id=who["technician"])

    # Every line on the weigh-up sheet is actually WEIGHED. `complete_batch`
    # refuses otherwise -- "a batch cannot be completed until every line has
    # been weighed or a deviation raised" -- and that refusal is the control
    # standing between a sample and a batch nobody made properly. Recording
    # the weighings is what a lab does; skipping completion to avoid the rule
    # would step around the thing the scenario is meant to exercise.
    lines = (
        s.execute(
            text(
                "SELECT id, planned_mass_kg FROM laboratory.batch_components "
                "WHERE batch_id = :b AND organization_id = :o ORDER BY id"
            ),
            {"b": batch, "o": org},
        )
        .mappings()
        .all()
    )
    for line in lines:
        record_weighing(
            s,
            batch_id=batch,
            component_id=line["id"],
            organization_id=org,
            actor_id=who["technician"],
            actual_mass_kg=line["planned_mass_kg"],
        )
    sample = create_sample(
        s,
        batch_id=batch,
        organization_id=org,
        actor_id=who["technician"],
        spec=SampleInput(sample_number=f"SMP-{suffix}", quantity_g=Decimal("50")),
    )
    complete_batch(s, batch_id=batch, organization_id=org, actor_id=who["technician"])
    s.flush()
    return sample


def _measure(
    s: Session,
    org: uuid.UUID,
    who: dict[str, uuid.UUID],
    test_id: uuid.UUID,
    values: list[str],
) -> None:
    start_execution(s, test_id=test_id, organization_id=org, actor_id=who["technician"])
    for n, value in enumerate(values, start=1):
        record_replicate(
            s,
            test_id=test_id,
            organization_id=org,
            actor_id=who["technician"],
            spec=ReplicateInput(replicate_number=n, measured_value=Decimal(value), unit="MPa"),
        )
