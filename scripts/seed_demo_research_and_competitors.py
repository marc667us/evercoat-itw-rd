"""Fill the demonstration organization so the Research Center can be DRIVEN.

Run against the local stack, for the local tunnel. It creates nothing a real
deployment needs and touches exactly one organization.

WHY THIS EXISTS
---------------
Phase 4 shipped eight `research` tables, 26 routes and a screen, and Phase 5
hung fifteen dashboard widgets off them. The demonstration tenant then held
**zero** investigations, **zero** findings and **zero** proposals — so every one
of those panels read `0`, and a panel reading `0` is byte-identical to a panel
that is broken. The operator could open the Research Center and see nothing
happen, which proves the screen renders and proves nothing else.

🔴 EVERY ROW HERE IS WRITTEN THROUGH THE PRODUCTION SERVICE FUNCTIONS.

`open_investigation`, `record_question`, `record_source`, `record_evidence`,
`record_finding`, `propose_experiment`, `register_product`, `record_benchmark` —
not raw INSERTs. That is the whole point, and it is this repository's existing
rule (`seed_demo_bench_and_library.py` says the same): seeded data that
bypasses the services proves the screens render and proves nothing about
whether the write paths work. It has already gone wrong the other way here —
`seed.py` inserted dangling document rows that the SDS gate then counted as
evidence.

It also means this script is a real exercise of the vertical. When it runs
clean, 15 write paths have just been driven end to end.

⚠️ THE CONTENT IS SYNTHETIC AND SAYS SO. Every investigation title, finding and
competitor claim carries "(synthetic)" or states it is illustrative. §7 and §29
matter more here than in most seeds: a research FINDING is a controlled object
that MSD prioritises when answering technical questions, and a fabricated one
that did not announce itself would be quoted back as sourced evidence. Nothing
here is a real Evercoat result and nothing here is a real competitor analysis.

🔴 AND NOTHING HERE IS APPROVED. Findings are left `draft` or `submitted`, and
proposals `proposed`. Approval is a human act (`CLAUDE.md` §4, spec §20), so a
seed that produced approved findings would be manufacturing the one thing the
product exists to make a person do — and would put unreviewed synthetic text
into the knowledge register on the authority of a shell script.

Idempotent: every code carries a run id, so re-running adds a fresh set rather
than colliding or silently updating. Re-run it as often as you like.

    python scripts/seed_demo_research_and_competitors.py
"""

from __future__ import annotations

import os
import sys
import uuid

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "apps", "api"))

from app.domains.competitor_intelligence.service import (
    EvidenceInput as CompetitorEvidenceInput,
)
from app.domains.competitor_intelligence.service import (
    record_benchmark,
    record_evidence,
    register_product,
    register_sample,
)
from app.domains.research.service import (
    EvidenceInput,
    FindingInput,
    InvestigationInput,
    ProposalInput,
    SourceInput,
    open_investigation,
    propose_experiment,
    record_finding,
    record_hypothesis,
    record_knowledge_gap,
    record_question,
    record_source,
    settle_question,
    submit_finding,
)
from app.domains.research.service import (
    record_evidence as record_research_evidence,
)

DEMO_ORG = uuid.UUID("c6031e4b-eff3-4aa6-a87b-697b6941c6e9")
DB = os.environ.get(
    "SEED_DATABASE_URL",
    "postgresql+psycopg://evercoat_app:ci-app@localhost:55432/evercoat_itw_rd",
)


def _scope(session: Session, actor: uuid.UUID) -> None:
    session.execute(text("SELECT set_config('app.current_org', :o, true)"), {"o": str(DEMO_ORG)})
    session.execute(text("SELECT set_config('app.current_user_id', :u, true)"), {"u": str(actor)})


def _actor(session: Session, role_code: str) -> uuid.UUID:
    """The demo user holding a role, so each step is taken by the right person.

    🔴 THE ORG GUC MUST BE SET BEFORE THIS READ. `core.organization_members` is
    RLS-protected and `core.rls_permissive()` has returned FALSE since migration
    032, so an unscoped lookup returns ZERO rows — the database failing closed,
    working correctly.
    """
    session.execute(text("SELECT set_config('app.current_org', :o, true)"), {"o": str(DEMO_ORG)})
    found = session.execute(
        text(
            """
            SELECT m.user_id
              FROM core.organization_members m
              JOIN core.member_roles mr ON mr.member_id = m.id
              JOIN core.roles r         ON r.id = mr.role_id
             WHERE m.organization_id = :o AND r.code = :role AND m.status = 'active'
             LIMIT 1
            """
        ),
        {"o": str(DEMO_ORG), "role": role_code},
    ).scalar_one_or_none()
    if found is None:
        raise SystemExit(f"no active {role_code} in the demonstration organization")
    return found  # type: ignore[no-any-return]


def _one(session: Session, sql: str) -> uuid.UUID | None:
    return session.execute(text(sql), {"o": str(DEMO_ORG)}).scalar_one_or_none()


def main() -> None:
    run = uuid.uuid4().hex[:6]
    engine = create_engine(DB, future=True)
    session = sessionmaker(bind=engine, future=True)()

    # The chemist opens and works the investigation; the engineer owns the
    # organization-wide one and records the benchmarks. Two actors, because a
    # single super-user would seed data no real workflow could produce -- §9's
    # segregation of duties is why the bench and the review are different
    # people, and the same reasoning applies to a seed.
    chemist = _actor(session, "product_development_chemist")
    engineer = _actor(session, "product_development_engineer")
    _scope(session, chemist)

    project = _one(session, "SELECT id FROM projects.projects WHERE organization_id = :o LIMIT 1")
    version = _one(
        session,
        "SELECT id FROM formulations.formula_versions WHERE organization_id = :o"
        " AND status = 'approved' LIMIT 1",
    )
    test_id = _one(session, "SELECT id FROM testing.tests WHERE organization_id = :o LIMIT 1")
    material = _one(
        session, "SELECT id FROM materials.materials WHERE organization_id = :o LIMIT 1"
    )
    if project is None:
        raise SystemExit("the demonstration organization has no project to attach research to")

    print(f"run {run}: project={project} version={version} test={test_id}")

    # -----------------------------------------------------------------
    # 1 — A PROJECT-SCOPED investigation, worked all the way to a finding
    #     that is SUBMITTED, so the approval queue has something in it and
    #     the "Awaiting review in Approvals" badge has something to show.
    # -----------------------------------------------------------------
    sanding = open_investigation(
        session,
        organization_id=DEMO_ORG,
        actor_id=chemist,
        spec=InvestigationInput(
            title=f"Improving sanding performance of the lightweight filler (synthetic {run})",
            research_question=(
                "What drives sand-through time in the lightweight polyester filler, and "
                "can it be shortened without losing edge feather? SYNTHETIC DEMONSTRATION "
                "DATA — not a real Evercoat investigation."
            ),
            project_id=project,
            search_strategy=(
                "Internal first: released product knowledge, historical formulas, test "
                "results and failure investigations. External literature second, graded."
            ),
            formula_version_id=version,
            material_id=material,
            owner_user_id=chemist,
        ),
    )
    inv = sanding["id"]
    print(f"  {sanding['investigation_code']} opened")

    q1 = record_question(
        session,
        investigation_id=inv,
        organization_id=DEMO_ORG,
        actor_id=chemist,
        question="Does microsphere loading correlate with sand-through time?",
    )
    q2 = record_question(
        session,
        investigation_id=inv,
        organization_id=DEMO_ORG,
        actor_id=chemist,
        question="Is there a loading above which edge feather degrades?",
    )
    record_question(
        session,
        investigation_id=inv,
        organization_id=DEMO_ORG,
        actor_id=chemist,
        question="Does the resin's acid value interact with the effect?",
    )

    # Sources across the A-X range, so the grade column is visibly doing work.
    internal = record_source(
        session,
        investigation_id=inv,
        organization_id=DEMO_ORG,
        actor_id=chemist,
        spec=SourceInput(
            source_kind="laboratory",
            evidence_grade="A",
            title="Our own bench results on the current filler (synthetic)",
            source_locator="Internal bench series, illustrative",
        ),
    )
    paper = record_source(
        session,
        investigation_id=inv,
        organization_id=DEMO_ORG,
        actor_id=chemist,
        spec=SourceInput(
            source_kind="literature",
            evidence_grade="B",
            title="Peer-reviewed work on microsphere loading and abrasion (synthetic)",
            source_locator="Section 4.2",
        ),
    )
    # ⚠️ `literature`, NOT `document`. A source of kind `document` must name a
    # row in the ONE knowledge register (`sources_document_shape` refuses one
    # that does not), and this seed is quoting a supplier datasheet it has not
    # ingested. Choosing the kind that matches what we actually have is the
    # difference between a citation and a claim.
    supplier = record_source(
        session,
        investigation_id=inv,
        organization_id=DEMO_ORG,
        actor_id=chemist,
        spec=SourceInput(
            source_kind="literature",
            evidence_grade="C",
            title="Supplier technical literature for the microsphere grade (synthetic)",
            source_locator="Page 2, typical properties",
        ),
    )

    # 🔴 INCLUDING ONE THAT CONTRADICTS. A register that can only record
    # agreement is a register of conclusions, not of evidence — and the screen's
    # ✕ mark has nothing to render until something disagrees.
    record_research_evidence(
        session,
        investigation_id=inv,
        organization_id=DEMO_ORG,
        actor_id=chemist,
        spec=EvidenceInput(
            summary=(
                "Bench series shows sand-through time falling as microsphere loading rises "
                "from 4% to 7% (synthetic)."
            ),
            stance="supports",
            question_id=q1["id"],
            source_id=internal["id"],
            formula_version_id=version,
            test_id=test_id,
        ),
    )
    record_research_evidence(
        session,
        investigation_id=inv,
        organization_id=DEMO_ORG,
        actor_id=chemist,
        spec=EvidenceInput(
            summary="Published work reports the same direction for comparable systems (synthetic).",
            stance="supports",
            question_id=q1["id"],
            source_id=paper["id"],
        ),
    )
    record_research_evidence(
        session,
        investigation_id=inv,
        organization_id=DEMO_ORG,
        actor_id=chemist,
        spec=EvidenceInput(
            summary=(
                "Supplier literature reports no abrasion benefit above 6% and warns of "
                "edge crumble — this CONTRADICTS the internal trend at the top of the "
                "range (synthetic)."
            ),
            stance="contradicts",
            question_id=q2["id"],
            source_id=supplier["id"],
        ),
    )

    settle_question(
        session,
        question_id=q1["id"],
        organization_id=DEMO_ORG,
        actor_id=chemist,
        status="answered",
    )
    settle_question(
        session,
        question_id=q2["id"],
        organization_id=DEMO_ORG,
        actor_id=chemist,
        status="unanswerable",
    )

    record_knowledge_gap(
        session,
        investigation_id=inv,
        organization_id=DEMO_ORG,
        actor_id=chemist,
        description=(
            "No internal data above 8% microsphere loading, so the top of the range is "
            "extrapolation (synthetic)."
        ),
        impact="high",
        question_id=q2["id"],
    )
    record_knowledge_gap(
        session,
        investigation_id=inv,
        organization_id=DEMO_ORG,
        actor_id=chemist,
        description="Acid-value interaction has never been measured directly (synthetic).",
        impact="moderate",
    )

    finding = record_finding(
        session,
        investigation_id=inv,
        organization_id=DEMO_ORG,
        actor_id=chemist,
        spec=FindingInput(
            subject="Microsphere loading and sand-through time",
            statement=(
                "Raising microsphere loading from 4% to 7% shortens sand-through time in "
                "the lightweight filler, with no measured loss of edge feather below 7%. "
                "SYNTHETIC DEMONSTRATION FINDING — illustrative only."
            ),
            applicability="Lightweight polyester filler family",
            confidence="moderate",
            limitations=(
                "Internal data stops at 8%; supplier literature disagrees above 6%. Not validated."
            ),
        ),
    )
    # Submitted, NOT approved: the route now sits in `/approvals` for a person.
    submit_finding(
        session,
        finding_id=finding["id"],
        organization_id=DEMO_ORG,
        actor_id=chemist,
    )
    print(f"  {finding['finding_code']} drafted and submitted for approval")

    hypothesis = record_hypothesis(
        session,
        investigation_id=inv,
        organization_id=DEMO_ORG,
        actor_id=chemist,
        statement="Raising loading to 6.5% shortens sand-through by ~90 seconds (synthetic).",
        rationale="Extrapolated from the 4-7% bench series; above the supplier's caution.",
        finding_id=finding["id"],
    )

    proposal = propose_experiment(
        session,
        investigation_id=inv,
        organization_id=DEMO_ORG,
        actor_id=chemist,
        spec=ProposalInput(
            objective="Shorten sand-through time without losing edge feather (synthetic)",
            basis=f"{finding['finding_code']} / internal bench series / supplier literature",
            variables="Microsphere loading 5.5%, 6.0%, 6.5%",
            expected_direction="Shorter sand-through time; edge feather unchanged to 6.5%",
            required_tests="Density; working time; sand-through; edge feather; adhesion",
            confidence="moderate",
            controlled_variables="Resin lot, hardener ratio, cure temperature, sanding grit",
            risks="Edge crumble above 6%, per supplier literature. Cost rises with loading.",
            hypothesis_id=hypothesis["id"],
        ),
    )
    print(f"  {proposal['proposal_code']} proposed — inert until a chemist accepts it")

    # -----------------------------------------------------------------
    # 2 — An ORGANIZATION-WIDE investigation, so the nullable project is
    #     visible on screen and the "cannot be sent for approval" refusal
    #     has a subject a person can actually try.
    # -----------------------------------------------------------------
    chemistry = open_investigation(
        session,
        organization_id=DEMO_ORG,
        actor_id=engineer,
        spec=InvestigationInput(
            title=f"Low-odour hardener chemistries, organization-wide (synthetic {run})",
            research_question=(
                "Which hardener chemistries reduce odour without extending working time? "
                "SYNTHETIC — this workspace belongs to the organization, not a project."
            ),
            search_strategy="Literature and patent survey; no internal data yet.",
            owner_user_id=engineer,
        ),
    )
    record_question(
        session,
        investigation_id=chemistry["id"],
        organization_id=DEMO_ORG,
        actor_id=engineer,
        question="Which chemistries are already used in adjacent industries?",
    )
    patent = record_source(
        session,
        investigation_id=chemistry["id"],
        organization_id=DEMO_ORG,
        actor_id=engineer,
        spec=SourceInput(
            source_kind="patent",
            evidence_grade="B",
            title="Patent describing a low-odour amine system (synthetic)",
            source_locator="Claim 1",
        ),
    )
    record_research_evidence(
        session,
        investigation_id=chemistry["id"],
        organization_id=DEMO_ORG,
        actor_id=engineer,
        spec=EvidenceInput(
            summary="The claimed system reports lower odour at equal cure speed (synthetic).",
            stance="related",
            source_id=patent["id"],
        ),
    )
    record_finding(
        session,
        investigation_id=chemistry["id"],
        organization_id=DEMO_ORG,
        actor_id=engineer,
        spec=FindingInput(
            subject="Low-odour hardener candidates",
            statement=(
                "At least one patented amine system reports lower odour at equal cure "
                "speed. SYNTHETIC — no internal work has been done."
            ),
            applicability="Two-component polyester systems",
            confidence="low",
            limitations="External claims only. Nothing measured here.",
        ),
    )
    print(f"  {chemistry['investigation_code']} opened (organization-wide)")

    # -----------------------------------------------------------------
    # 3 — Competitor intelligence: a second product, physical samples, a
    #     composition matrix across the three entry modes, and benchmarks.
    # -----------------------------------------------------------------
    rival = register_product(
        session,
        organization_id=DEMO_ORG,
        actor_id=chemist,
        manufacturer="Northbridge Refinish",
        product_name=f"FeatherLite Gold (synthetic {run})",
        product_code="NB-FLG-2026",
        market_segment="Premium lightweight body filler",
        notes=(
            "SYNTHETIC COMPETITOR RECORD for demonstration. Nothing here is a real "
            "analysis of a real product."
        ),
    )
    sample = register_sample(
        session,
        organization_id=DEMO_ORG,
        actor_id=chemist,
        competitor_product_id=rival["id"],
        sample_reference=f"NB-FLG-{run}",
        batch_marking="Lot 2026-114 (synthetic)",
        observations="Tin purchased at retail; cream-coloured paste, low density.",
    )

    # 🔴 THREE ENTRY MODES AS PEERS, which is the matrix's whole design: a
    # person reading a tin is OBSERVING, not inferring, and neither can reach
    # `verified` because there is nothing anybody else can re-check.
    for spec in (
        CompetitorEvidenceInput(
            component_name="Unsaturated polyester resin",
            evidence_source="manual_observation",
            evidence_grade="C",
            component_function="Binder",
            concentration_low="35.0000",
            concentration_high="45.0000",
            sample_id=sample["id"],
            rationale="Read from the tin's declared composition band (synthetic).",
        ),
        CompetitorEvidenceInput(
            component_name="Glass microspheres",
            evidence_source="laboratory",
            evidence_grade="B",
            component_function="Lightweight filler",
            concentration_low="5.0000",
            concentration_high="9.0000",
            sample_id=sample["id"],
            rationale="Ash and density on the retail sample (synthetic).",
        ),
        CompetitorEvidenceInput(
            component_name="Talc",
            evidence_source="inference",
            evidence_grade="D",
            component_function="Extender",
            concentration_low="10.0000",
            concentration_high="20.0000",
            rationale="Inferred from density and sanding feel. NOT a measurement.",
        ),
        CompetitorEvidenceInput(
            component_name="Styrene",
            evidence_source="literature",
            evidence_grade="C",
            component_function="Reactive diluent",
            concentration_low="8.0000",
            concentration_high="14.0000",
            rationale="Typical for the class; synthetic illustration.",
        ),
    ):
        record_evidence(
            session,
            organization_id=DEMO_ORG,
            actor_id=chemist,
            competitor_product_id=rival["id"],
            spec=spec,
        )

    record_benchmark(
        session,
        organization_id=DEMO_ORG,
        actor_id=engineer,
        competitor_product_id=rival["id"],
        project_id=project,
        attribute="Sand-through time",
        gap_summary="Theirs sands about four minutes sooner at 20 C (synthetic).",
        competitor_value="6 min",
        our_value="10 min",
        formula_version_id=version,
        test_id=test_id,
    )
    record_benchmark(
        session,
        organization_id=DEMO_ORG,
        actor_id=engineer,
        competitor_product_id=rival["id"],
        project_id=project,
        attribute="Density",
        gap_summary="Comparable; ours marginally denser (synthetic).",
        competitor_value="1.05 g/cm3",
        our_value="1.09 g/cm3",
        formula_version_id=version,
    )
    print(f"  competitor {rival['id']} registered with 4 claims and 2 benchmarks")

    session.commit()

    # 🔴 RE-SCOPE BEFORE COUNTING. `set_config(..., true)` is TRANSACTION-local,
    # so the commit above discarded it — and the first version of this summary
    # then reported "0 investigations, 0 findings, 0 competitor products" over
    # rows it had just written, because RLS was correctly showing an unscoped
    # session nothing at all.
    #
    # It read exactly like a seed that had done nothing. That is this project's
    # own most-repeated trap wearing a print statement: a query returning zero
    # because it CANNOT SEE is indistinguishable from one returning zero
    # because there is nothing there.
    _scope(session, chemist)

    counts = session.execute(
        text(
            """
            SELECT (SELECT count(*) FROM research.investigations WHERE organization_id = :o),
                   (SELECT count(*) FROM research.findings WHERE organization_id = :o),
                   (SELECT count(*) FROM research.experiment_proposals WHERE organization_id = :o),
                   (SELECT count(*) FROM research.knowledge_gaps WHERE organization_id = :o),
                   (SELECT count(*) FROM competitors.products WHERE organization_id = :o),
                   (SELECT count(*) FROM competitors.benchmarks WHERE organization_id = :o)
            """
        ),
        {"o": str(DEMO_ORG)},
    ).one()
    print(
        "\ndemonstration organization now holds: "
        f"{counts[0]} investigations, {counts[1]} findings, {counts[2]} proposals, "
        f"{counts[3]} knowledge gaps, {counts[4]} competitor products, "
        f"{counts[5]} benchmarks"
    )
    session.close()


if __name__ == "__main__":
    main()
