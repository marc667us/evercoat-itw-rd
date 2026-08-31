"""THE RESEARCH GOLDEN SCENARIO — spec §39, and §38's cross-module cases.

`IMPLEMENTATION_PLAN_MATERIAL_SAFETY_DATA.md` §10 lists this as the last part
of Phase 5. Spec §39's chain, in its own words:

    EXISTING PROJECT → Existing Product Requirement → "Research Solution" →
    Material Safety Data & Research Center → ... → Research Finding generated
    → Experiment Proposal generated → Existing Approval Engine → Chemist
    accepts → EXISTING FORMULATION MODULE creates Formula Version → EXISTING
    LAB MODULE creates Batch/Samples → EXISTING TEST MODULE performs analysis
    → RED → EXISTING FAILURE MODULE → Research Center investigates → ... →
    Research Finding approved → EXISTING KNOWLEDGE LIBRARY

═══════════════════════════════════════════════════════════════════════════
🔴 §39'S ACCEPTANCE CRITERION IS AN ABSENCE, AND THE ABSENCE IS TESTED
═══════════════════════════════════════════════════════════════════════════

The spec does not ask "did the chain run". It says:

    "If any step creates a parallel Project, Formula, Batch, Test, Approval,
    Document or Knowledge record outside its owning module, the integration
    is wrong."

That is a claim about what must NOT exist, and a scenario that only walks
forward cannot see it. `test_no_step_created_a_parallel_record` counts the
seven record classes §39 names, before and after, and asserts each grew by
exactly the number the OWNING module was asked for. A research module that
quietly inserted its own `formula_versions` row would pass every forward
assertion in this file and fail that one.

═══════════════════════════════════════════════════════════════════════════
⚠️ WHAT THIS FILE DOES NOT CLAIM
═══════════════════════════════════════════════════════════════════════════

This is the DATABASE half, like `test_golden_scenario.py` before it. §39's
own gate would be the scenario on the deployed instance asserted in UI and
database state, and the Research Center's screens do not cover every hop.
**Do not mark §39 closed on the strength of this file.**

And three of §39's steps have no service to call, so they are NOT walked and
NOT faked:

  · "Existing Materials searched" / "Existing formulas searched" ARE walked —
    `global_search` shipped this session (spec §29).
  · "Competitor Sample registered → SDS linked → Safety data extracted" is a
    separate vertical with its own tests (`test_056`, `test_059`); walking it
    again here would duplicate coverage, not add it.
  · "DOE → Research Finding" has no DOE module at all (full-build Slice 12).

Writing a step that calls nothing, or asserting a record this file inserted by
hand, would make the scenario report on itself.
"""

from __future__ import annotations

import io
import uuid
from decimal import Decimal

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.object_storage import new_object_key
from app.domains.formulations.service import (
    ComponentInput,
    FormulaInput,
    create_formula,
    decide_version,
    set_components,
    submit_version,
)
from app.domains.research.service import (
    EvidenceInput,
    FindingInput,
    InvestigationInput,
    ProposalInput,
    SourceInput,
    accept_experiment_proposal,
    open_investigation,
    propose_experiment,
    record_evidence,
    record_finding,
    record_source,
    submit_finding,
)
from app.domains.search.service import global_search
from app.domains.testing.service import (
    TestInput,
    complete_execution,
    create_test,
    get_test,
)

# Reused rather than re-written. §12: do not rebuild infrastructure per module,
# and a second `_people` would drift from the first in exactly the way this
# repository keeps finding.
from tests.db.test_golden_scenario import (
    _batch_and_sample,
    _document_store,
    _measure,
    _method,
    _people,
    _requirement,
)

#: The seven record classes §39 forbids a step from creating in parallel.
PARALLEL_RECORD_TABLES = {
    "project": "projects.projects",
    "formula": "formulations.formulas",
    "formula_version": "formulations.formula_versions",
    "batch": "laboratory.batches",
    "test": "testing.tests",
    "approval": "workflow.approval_routes",
    "knowledge_document": "knowledge.documents",
}


def _counts(s: Session, org: uuid.UUID) -> dict[str, int]:
    """How many of each §39 record class this organization holds.

    ⚠️ Built from `PARALLEL_RECORD_TABLES` with LITERAL table names in one
    statement per entry rather than interpolated: `avoid-sqlalchemy-text`
    blocked commit `5209298` on this repository for exactly the loop this
    would otherwise be, and the rule is right about the shape even when the
    values are constants.
    """
    return {
        "project": s.execute(
            text("SELECT count(*) FROM projects.projects WHERE organization_id = :o"),
            {"o": org},
        ).scalar_one(),
        "formula": s.execute(
            text("SELECT count(*) FROM formulations.formulas WHERE organization_id = :o"),
            {"o": org},
        ).scalar_one(),
        "formula_version": s.execute(
            text("SELECT count(*) FROM formulations.formula_versions WHERE organization_id = :o"),
            {"o": org},
        ).scalar_one(),
        "batch": s.execute(
            text("SELECT count(*) FROM laboratory.batches WHERE organization_id = :o"),
            {"o": org},
        ).scalar_one(),
        "test": s.execute(
            text("SELECT count(*) FROM testing.tests WHERE organization_id = :o"),
            {"o": org},
        ).scalar_one(),
        "approval": s.execute(
            text("SELECT count(*) FROM workflow.approval_routes WHERE organization_id = :o"),
            {"o": org},
        ).scalar_one(),
        "knowledge_document": s.execute(
            text("SELECT count(*) FROM knowledge.documents WHERE organization_id = :o"),
            {"o": org},
        ).scalar_one(),
    }


def _material_with_sds(s: Session, org: uuid.UUID, who: dict, suffix: str) -> uuid.UUID:
    """A material with a real, stored SDS.

    🔴 THE SDS IS ATTACHED, NOT SWITCHED OFF. `requires_sds` defaults TRUE and
    `submit_version` hard-blocks a formula containing a material that needs one
    without it. Setting `requires_sds = false` to get this scenario moving would
    disable the exact control the scenario exists to demonstrate -- the same
    point `test_golden_scenario.py` makes at length, and the same reason it
    stores real bytes through the real port rather than writing a row that
    names a file nobody wrote.
    """
    material = s.execute(
        text(
            """
            INSERT INTO materials.materials
                (organization_id, material_code, name, category, role, status,
                 created_by, density_g_cm3, solids_fraction, voc_fraction, cost_per_kg)
            VALUES (:o, :c, :n, 'Resin', 'resin', 'approved', :u,
                    1.1000, 0.6500, 0.3500, 4.20)
            RETURNING id
            """
        ),
        {
            "o": org,
            "c": f"RM-{suffix}",
            "n": f"Low-shrink resin {suffix}",
            "u": who["chemist"],
        },
    ).scalar_one()

    sds_bytes = b"%PDF-1.4\n% research golden scenario synthetic safety data sheet\n"
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
                    'approved', 'clean', 'research-golden-scenario', 'n/a', now())
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
    return material


def test_the_research_golden_scenario_runs_end_to_end(owner_session: Session) -> None:
    """§39, walked through the owning module at every hop.

    Each step asserts THE STATE THE NEXT STEP DEPENDS ON, not merely that the
    call returned — a chain that fails at step 9 with one assertion at the end
    is a nine-step debugging problem.
    """
    s = owner_session
    suffix = uuid.uuid4().hex[:8]

    org = s.execute(
        text("INSERT INTO core.organizations (code, name) VALUES (:c, :n) RETURNING id"),
        {"c": f"RGOLD-{suffix}", "n": "Research Golden Org"},
    ).scalar_one()
    # Every table since 058 is born FORCE RLS, and this scenario writes to
    # `workflow.domain_events` through `confirm_test`. Production sets this on
    # every request (`app/core/db.py:514`).
    s.execute(text("SELECT set_config('app.current_org', :o, false)"), {"o": str(org)})
    who = _people(s, org, suffix)
    s.flush()

    # ── 1. AN EXISTING PROJECT, and an existing product requirement ──────
    project = s.execute(
        text(
            "INSERT INTO projects.projects (organization_id, project_code, name,"
            " confidentiality, lead_user_id, director_user_id)"
            " VALUES (:o, :c, 'Faster-sanding filler', 'restricted', :l, :d) RETURNING id"
        ),
        {"o": org, "c": f"RDP-{suffix}", "l": who["lead"], "d": who["director"]},
    ).scalar_one()
    for person in ("lead", "chemist", "engineer", "technician", "director"):
        s.execute(
            text(
                "INSERT INTO projects.project_members (organization_id, project_id,"
                " user_id, project_role) VALUES (:o, :p, :u, :r)"
            ),
            {
                "o": org,
                "p": project,
                "u": who[person],
                "r": {
                    "lead": "lead",
                    "chemist": "chemist",
                    "engineer": "engineer",
                    "technician": "technician",
                    "director": "director",
                }[person],
            },
        )
    requirement = _requirement(s, org, project, who, suffix)
    s.flush()

    # 🔴 THE ACTING USER, NOT ONLY THE ORGANIZATION.
    #
    # `research.investigations` is FORCE RLS (058) and its policy is a PROJECT
    # MEMBERSHIP predicate, not just a tenant one -- so with `app.current_org`
    # set and `app.current_user_id` unset, `open_investigation` refuses with
    # "this record names a project you cannot reach". That refusal is correct
    # and it is the boundary working: the owner is not exempt from a forced
    # policy, and a caller with no identity is a member of nothing.
    #
    # Production sets both on every request (`app/core/db.py:514`). The chemist
    # performs every Research Center act below; the lead's `decide_version` and
    # the engineer's `create_test` touch modules whose tables predate FORCE RLS
    # and are therefore unaffected -- which is itself worth knowing, because it
    # is why this line was not needed in `test_golden_scenario.py`.
    s.execute(
        text("SELECT set_config('app.current_user_id', :u, false)"),
        {"u": str(who["chemist"])},
    )
    s.flush()

    before = _counts(s, org)

    # ── 2. "RESEARCH SOLUTION" — the Research Center opens a workspace ────
    #
    # ⚠️ THE LINK IS THE PROJECT, NOT THE REQUIREMENT, AND THAT IS A REAL GAP.
    # §25 lists "Research Solution" as an entry point FROM a Product
    # Requirement, but `research.investigations` has no `requirement_id`
    # column (migration 058 carries project, formula version, material, test,
    # failure and opportunity). So the requirement that motivated this work is
    # reachable only through the project. Recorded rather than papered over.
    investigation = open_investigation(
        s,
        organization_id=org,
        actor_id=who["chemist"],
        spec=InvestigationInput(
            title="Why does sanding time exceed the requirement?",
            research_question="Which filler chemistry reduces sand-through time?",
            project_id=project,
        ),
    )
    s.flush()
    assert investigation["investigation_code"], "the workspace got no code"

    # ── 3. EXISTING MATERIALS AND FORMULAS SEARCHED, through §29 ─────────
    #
    # §39 says "Existing Materials searched" and "Existing formulas searched".
    # Global search shipped this session, so this is the real call rather than
    # a hand-written query standing in for one.
    material = _material_with_sds(s, org, who, suffix)

    found = global_search(
        s,
        organization_id=org,
        permissions=frozenset({"material.view", "project.view", "formula.view"}),
        question=suffix,
    )
    hits = {(h["record_type"], h["id"]) for h in found["results"]}
    assert ("material", str(material)) in hits, "the Research Center could not find the material"
    assert ("project", str(project)) in hits, "the Research Center could not find the project"

    # ── 4. EVIDENCE, then a RESEARCH FINDING ─────────────────────────────
    # 🔴 A CARD MUST CITE SOMETHING, AND THE FIRST DRAFT OF THIS TEST DID NOT.
    #
    # `record_evidence` refused it: "an evidence card must cite something: a
    # source, a formula version, a test or a failure. A card that cites nothing
    # is an opinion." The rule is right and the scenario was wrong -- so the
    # source is recorded first, which is the order a researcher works in
    # anyway. Grade B on the A-X scale of migration 058.
    source = record_source(
        s,
        investigation_id=investigation["id"],
        organization_id=org,
        actor_id=who["chemist"],
        spec=SourceInput(
            source_kind="laboratory",
            evidence_grade="B",
            title="2025 sand-through trials",
            source_locator="internal trial log, 2025-04",
        ),
    )
    s.flush()

    evidence = record_evidence(
        s,
        investigation_id=investigation["id"],
        organization_id=org,
        actor_id=who["chemist"],
        spec=EvidenceInput(
            summary="Low-shrink resins reduced sand-through in the 2025 trials.",
            stance="supports",
            source_id=source["id"],
        ),
    )
    s.flush()
    assert evidence["id"]

    finding = record_finding(
        s,
        investigation_id=investigation["id"],
        organization_id=org,
        actor_id=who["chemist"],
        spec=FindingInput(
            subject="Low-shrink resin reduces sand-through time",
            statement="Substituting the binder shortens sand-through by roughly a fifth.",
            applicability="polyester fillers at ambient cure",
            confidence="moderate",
        ),
    )
    s.flush()

    # ── 5. THE EXISTING APPROVAL ENGINE, not a second one ────────────────
    submitted = submit_finding(
        s, finding_id=finding["id"], organization_id=org, actor_id=who["chemist"]
    )
    s.flush()
    route_id = s.execute(
        text(
            "SELECT id FROM workflow.approval_routes"
            " WHERE organization_id = :o AND entity_type = 'research_finding'"
            "   AND entity_id = :e"
        ),
        {"o": org, "e": str(finding["id"])},
    ).scalar_one_or_none()
    assert route_id is not None, (
        "submitting a finding did not open a route in the ONE approval engine "
        "-- §9 forbids a second notion of signed off, and §39 forbids a "
        "parallel Approval record"
    )
    assert submitted["id"] == finding["id"]

    # ── 6. AN EXPERIMENT PROPOSAL, accepted into a FORMULA VERSION ───────
    formula = create_formula(
        s,
        organization_id=org,
        project_id=project,
        actor_id=who["chemist"],
        spec=FormulaInput(
            formula_code=f"FRM-{suffix}",
            name="Faster-sanding filler",
            product_family="polyester_filler",
        ),
    )
    s.flush()
    first_version = formula["version_id"]
    set_components(
        s,
        version_id=first_version,
        organization_id=org,
        actor_id=who["chemist"],
        components=[ComponentInput(material_id=material, percentage=Decimal("100.0000"))],
    )
    s.flush()

    proposal = propose_experiment(
        s,
        investigation_id=investigation["id"],
        organization_id=org,
        actor_id=who["chemist"],
        spec=ProposalInput(
            objective="Substitute the binder and re-measure sand-through.",
            basis="The finding above.",
            variables="binder type",
            expected_direction="sand-through time decreases",
            required_tests="three-point flexure",
            confidence="moderate",
        ),
    )
    s.flush()

    accepted = accept_experiment_proposal(
        s,
        proposal_id=proposal["id"],
        organization_id=org,
        actor_id=who["chemist"],
        version_id=first_version,
        change_reason="Accepting the experiment proposal from the Research Center.",
        technical_hypothesis="A low-shrink binder shortens sand-through time.",
    )
    s.flush()
    # The proposal returns `formula_version_id`, not `version_id` -- the key is
    # named for what it points AT rather than for the caller, which is right.
    revised_version = accepted["formula_version_id"]

    # 🔴 THE FORMULA VERSION CAME FROM THE FORMULATION MODULE, and the thread
    # runs BACKWARD from it to the investigation. Migration 058 refuses a
    # `research` driver that names no proposal, so this cannot degrade into an
    # unlinked category without the database objecting.
    driver = (
        s.execute(
            text(
                "SELECT driver_type, experiment_proposal_id FROM"
                " formulations.formula_version_drivers"
                " WHERE organization_id = :o AND formula_version_id = :v"
            ),
            {"o": org, "v": revised_version},
        )
        .mappings()
        .one()
    )
    assert driver["driver_type"] == "research"
    assert driver["experiment_proposal_id"] == proposal["id"]

    # ── 7. LAB AND TEST MODULES, and a RED result ────────────────────────
    # The revision inherits the parent's components, so this is the shape the
    # engine will actually weigh. Submitting an empty version is refused, and
    # correctly -- §8 hard-blocks submission when the total is out of tolerance.
    set_components(
        s,
        version_id=revised_version,
        organization_id=org,
        actor_id=who["chemist"],
        components=[ComponentInput(material_id=material, percentage=Decimal("100.0000"))],
    )
    submit_version(s, version_id=revised_version, organization_id=org, actor_id=who["chemist"])

    # 🔴 THE APPROVER IS NOT THE SUBMITTER. `decide_version`, the one call the
    # formulation module exposes -- there is no `approve_for_lab`, and writing
    # one here would be the parallel path §39 forbids.
    decide_version(
        s,
        version_id=revised_version,
        organization_id=org,
        actor_id=who["lead"],
        decision="approve",
        note="Proceed to lab batch.",
    )
    s.flush()
    sample = _batch_and_sample(s, org, who, revised_version, suffix)
    method = _method(s, org, who, suffix)
    s.flush()

    the_test = create_test(
        s,
        organization_id=org,
        actor_id=who["engineer"],
        spec=TestInput(
            # No `project_id`: `TestInput` derives it from the SAMPLE, which is
            # the correct direction -- a test belongs to the project its sample
            # came from, and letting a caller state a different one would be a
            # way to detach a result from its own thread.
            test_number=f"T-{suffix}",
            sample_id=sample,
            method_id=method,
            requirement_id=requirement,
            test_purpose="confirmation",
            authority_level="controlled",
        ),
    )
    s.flush()
    # Values chosen to miss the requirement, so the engine derives a FAIL. The
    # test does not state the result: §10 makes it derived and server-owned.
    # Below the requirement's 5.0 MPa minimum, so the engine derives a FAIL.
    # The values are chosen; the RESULT is not -- §10 forbids stating it.
    _measure(s, org, who, the_test["id"], ["2.0", "2.1", "1.9"])
    s.flush()

    # 🔴 THE APP ANALYSES. The result is COMPUTED, never supplied -- §10 makes
    # `calculated_result` derived and server-owned, and `TestInput` has no field
    # for it. Recording replicates is not the same as finishing the test:
    # `complete_execution` is what runs the engine.
    completed = complete_execution(
        s, test_id=the_test["id"], organization_id=org, actor_id=who["technician"]
    )
    assert completed["calculated_result"] == "fail", (
        f"expected the engine to derive a failure, got {completed['calculated_result']!r}"
    )

    graded = get_test(s, test_id=the_test["id"], organization_id=org)
    assert graded["final_disposition"]["colour"] == "red", (
        "a confirmation test below its requirement must be RED, got "
        f"{graded['final_disposition']['colour']}"
    )

    # ── 8. THE FAILURE MODULE, and the Research Center investigating it ──
    failure_id = s.execute(
        text("SELECT id FROM quality.failures WHERE organization_id = :o AND test_id = :t"),
        {"o": org, "t": the_test["id"]},
    ).scalar_one_or_none()
    assert failure_id is not None, (
        "a RED confirmation result did not open a failure investigation (§10)"
    )

    second = open_investigation(
        s,
        organization_id=org,
        actor_id=who["chemist"],
        spec=InvestigationInput(
            title="What caused the flexural failure?",
            research_question="Which change drove the strength loss?",
            project_id=project,
            failure_id=failure_id,
        ),
    )
    s.flush()

    # 🔴 THE THREAD RUNS BACKWARD: the second investigation names the failure,
    # the failure names the test, the test names the sample, the sample its
    # batch, the batch the version, and the version the proposal that produced
    # it. §2: no record may become an isolated island.
    walked = s.execute(
        text(
            """
            SELECT d.experiment_proposal_id
              FROM research.investigations i
              JOIN quality.failures f
                ON f.id = i.failure_id AND f.organization_id = i.organization_id
              JOIN testing.tests t
                ON t.id = f.test_id AND t.organization_id = f.organization_id
              JOIN laboratory.samples sa
                ON sa.id = t.sample_id AND sa.organization_id = t.organization_id
              JOIN laboratory.batches b
                ON b.id = sa.batch_id AND b.organization_id = sa.organization_id
              JOIN formulations.formula_version_drivers d
                ON d.formula_version_id = b.formula_version_id
               AND d.organization_id = b.organization_id
             WHERE i.id = :i AND i.organization_id = :o
            """
        ),
        {"i": second["id"], "o": org},
    ).scalar_one()
    assert walked == proposal["id"], (
        "the thread does not run backward from the failure investigation to the "
        "experiment proposal that started it"
    )

    # ── 9. §39'S ACCEPTANCE CRITERION — no parallel records ──────────────
    after = _counts(s, org)
    grew = {k: after[k] - before[k] for k in after}

    assert grew == {
        # One project existed before the scenario opened; none was added.
        "project": 0,
        # One formula, created through `create_formula`.
        "formula": 1,
        # TWO versions: the formula's first, and the revision the ACCEPTED
        # PROPOSAL produced through `revise_version`. If the research module
        # inserted its own, this is 3 and every forward assertion above still
        # passes.
        "formula_version": 2,
        "batch": 1,
        "test": 1,
        # ONE route, opened by submitting the finding into the one engine.
        "approval": 1,
        # None: promotion to the Knowledge Library happens only after approval,
        # which this scenario does not reach.
        "knowledge_document": 0,
    }, f"a step created a parallel record: {grew}"

    s.rollback()


def test_the_parallel_record_guard_can_actually_fail(owner_session: Session) -> None:
    """🔴 GUARD THE GUARD — §39's criterion is the one that must be able to fail.

    `test_the_research_golden_scenario_runs_end_to_end` ends by asserting that
    seven record classes grew by exact amounts. If `_counts` were broken — a
    typo'd table, a wrong tenant predicate — it would return the same numbers
    before and after, every delta would be zero, and the assertion would fail
    for the wrong reason or, worse, pass if the expectations were also zero.

    So: insert one row of a §39 class by hand and prove the counter sees it.
    That is the mechanism the scenario's final assertion rests on.
    """
    s = owner_session
    suffix = uuid.uuid4().hex[:8]
    org = s.execute(
        text("INSERT INTO core.organizations (code, name) VALUES (:c, :n) RETURNING id"),
        {"c": f"RGRD-{suffix}", "n": "Guard Org"},
    ).scalar_one()
    s.flush()

    before = _counts(s, org)
    assert before["project"] == 0, "a fresh organization should hold no projects"

    s.execute(
        text(
            "INSERT INTO projects.projects (organization_id, project_code, name,"
            " confidentiality) VALUES (:o, :c, 'Parallel', 'restricted')"
        ),
        {"o": org, "c": f"RGP-{suffix}"},
    )
    s.flush()

    after = _counts(s, org)
    assert after["project"] == before["project"] + 1, (
        "_counts does not see a project that was just inserted, so the "
        "scenario's parallel-record assertion proves nothing"
    )
    s.rollback()


def test_the_scenario_names_the_steps_it_does_not_walk() -> None:
    """An unwalked step must be declared, not quietly absent.

    §39 lists more hops than this file walks — the competitor/SDS vertical has
    its own tests and DOE has no module at all. A scenario that silently
    skipped them would read as complete coverage of §39, which is the
    "a suite that ran nothing has not passed" failure one level up.
    """
    from pathlib import Path

    source = Path(__file__).read_text(encoding="utf-8")
    assert "WHAT THIS FILE DOES NOT CLAIM" in source
    assert "DOE" in source
    assert "no `requirement_id` column" in source or "no `requirement_id`" in source
