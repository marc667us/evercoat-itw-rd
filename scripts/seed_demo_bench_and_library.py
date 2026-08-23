"""Fill the demonstration organization so Laboratory and MSD can be DRIVEN.

Run against the local stack, for the local tunnel. It creates nothing a real
deployment needs and touches exactly one organization.

WHY THIS EXISTS
---------------
The demonstration tenant held **one** batch, already `completed`, and **zero**
knowledge documents. So:

* the Laboratory lifecycle could not be exercised at all — there was nothing in
  `draft` to authorise, nothing `authorized` to start, and nothing in progress
  to weigh. The eleven lifecycle routes had no reachable subject.
* MSD's knowledge search answered every question with "found nothing", which is
  indistinguishable on screen from a broken retriever.

🔴 EVERY ROW HERE IS WRITTEN THROUGH THE PRODUCTION SERVICE FUNCTIONS.
`create_batch`, `authorize_batch`, `start_batch`, `record_weighing` and
`ingest_document` — not raw INSERTs. That is the whole point: seeded data that
bypasses the services proves the screens render and proves nothing about
whether the write paths work. It has also already gone wrong on this project
in the other direction — `seed.py` inserting dangling document rows that the
SDS gate then counted as evidence.

⚠️ THE CONTENT IS SYNTHETIC AND SAYS SO. Every document title carries
"(synthetic)" and every body states it is illustrative. §3 and §7: a fabricated
passage is materially worse than fabricated tabular data, because MSD QUOTES it
back as sourced evidence. Nothing here should ever be mistaken for a real
Evercoat procedure, and nothing here is a laboratory result.

Idempotent: every batch number and document title is suffixed with a run id, so
re-running adds a fresh set rather than colliding or silently updating.
"""

from __future__ import annotations

import os
import sys
import uuid
from decimal import Decimal

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "apps", "api"))

from app.core.embedding import HashingEmbedding  # noqa: E402
from app.domains.knowledge.service import ingest_document  # noqa: E402
from app.domains.laboratory.service import (  # noqa: E402
    BatchInput,
    authorize_batch,
    create_batch,
    record_weighing,
    start_batch,
)

DEMO_ORG = uuid.UUID("c6031e4b-eff3-4aa6-a87b-697b6941c6e9")
DB = os.environ.get(
    "SEED_DATABASE_URL",
    "postgresql+psycopg://evercoat_app:ci-app@localhost:55432/evercoat_itw_rd",
)

# FRM-014 v4 — the approved version, eight components. An approved version is
# required: `create_batch` refuses a draft, which is the control that stops a
# bench working from an unapproved recipe.
APPROVED_VERSION = uuid.UUID("b901dd8c-b82e-4852-993c-4b3f3d266c29")


def _scope(session: Session, actor: uuid.UUID) -> None:
    session.execute(text("SELECT set_config('app.current_org', :o, true)"), {"o": str(DEMO_ORG)})
    session.execute(text("SELECT set_config('app.current_user_id', :u, true)"), {"u": str(actor)})


def _actor(session: Session, role_code: str) -> uuid.UUID:
    """The demo user holding a role, so each step is taken by the right person.

    A single super-user actor would seed data no real workflow could produce —
    §9's segregation of duties is the reason the bench and the review are
    different people.
    """
    # 🔴 THE ORG GUC MUST BE SET BEFORE THIS READ. `core.organization_members`
    # is RLS-protected and `core.rls_permissive()` has returned FALSE since
    # migration 032, so an unscoped lookup here returns ZERO rows — which is
    # exactly what happened on the first run of this script. That is the
    # database failing closed, working correctly; the script was wrong.
    session.execute(
        text("SELECT set_config('app.current_org', :o, true)"), {"o": str(DEMO_ORG)}
    )
    return session.execute(
        text(
            """
            SELECT m.user_id
            FROM core.organization_members m
            JOIN core.member_roles mr ON mr.member_id = m.id
            JOIN core.roles r ON r.id = mr.role_id
            WHERE m.organization_id = :org AND r.code = :role AND m.status = 'active'
            LIMIT 1
            """
        ),
        {"org": DEMO_ORG, "role": role_code},
    ).scalar_one()


# ---------------------------------------------------------------------------
# The knowledge library
# ---------------------------------------------------------------------------
#
# ⚠️ `source` IS A CLOSED VOCABULARY, not free text: `documents_source_check`
# in migration 042 allows only internal_note / material_document / standard /
# procedure / external, and the route mirrors it in `SOURCES`. The first draft
# of this list used "finding" and "method" and the database refused both —
# correctly. The two literals are already guarded by a drift test; this script
# is a third copy and simply uses the real values.
#
# Chosen so the RAG has something to be RIGHT and something to be WRONG about.
# A library where every document answers every question cannot demonstrate a
# relevance threshold, and `MAX_DISTANCE` exists precisely to refuse an
# unrelated question rather than quote four confident irrelevant passages.
LIBRARY: list[dict[str, str]] = [
    {
        "title": "Post-cure schedule for lightweight polyester fillers (synthetic)",
        "source": "procedure",
        "classification": "INTERNAL",
        "body": (
            "This document is SYNTHETIC demonstration content and is not an "
            "Evercoat procedure.\n\n"
            "Lightweight polyester body fillers containing glass microspheres "
            "require a post-cure of 40 minutes at 60 C before any sanding "
            "operation. Sanding below full cure causes surface porosity, "
            "because the resin has not yet reached the hardness at which the "
            "microspheres are held rather than torn out of the surface.\n\n"
            "Where ambient cure is used instead, allow 24 hours at 20 C. "
            "Cure time is temperature dependent and is not linear: a 10 C drop "
            "roughly doubles the time to full hardness."
        ),
    },
    {
        "title": "Sanding performance and microsphere loading (synthetic)",
        "source": "internal_note",
        "classification": "INTERNAL",
        "body": (
            "This document is SYNTHETIC demonstration content.\n\n"
            "Increasing glass microsphere loading improves sandability and "
            "lowers density, but reduces adhesion to bare steel above roughly "
            "18 percent by weight. The effect is attributed to reduced resin "
            "available at the substrate interface.\n\n"
            "Where both low density and adhesion are required, a coupling "
            "agent on the filler surface recovers part of the adhesion loss. "
            "This has not been validated on galvanised substrates."
        ),
    },
    {
        "title": "Weigh-up tolerance and batch acceptance (synthetic)",
        "source": "procedure",
        "classification": "INTERNAL",
        "body": (
            "This document is SYNTHETIC demonstration content.\n\n"
            "Each component of a laboratory batch is weighed against the "
            "planned mass on the issued weigh-up sheet. A line outside the "
            "batch tolerance does not by itself fail the batch; it is recorded "
            "as a deviation and the reviewing chemist decides whether the "
            "batch may proceed to testing.\n\n"
            "A batch may not be closed while any line is unweighed. An "
            "unweighed line is not a zero deviation."
        ),
    },
    {
        "title": "Adhesion test method notes for body filler systems (synthetic)",
        "source": "standard",
        "classification": "CONFIDENTIAL",
        "body": (
            "This document is SYNTHETIC demonstration content and is not a "
            "test method.\n\n"
            "Adhesion is reported in MPa. Replicates are run in fives and the "
            "coefficient of variation is checked against the method limit "
            "before a result is graded. A result whose variability exceeds the "
            "limit is amber and awaits review; it is not a failure and it is "
            "not a pass.\n\n"
            "Substrate preparation dominates the result. Abrade to a uniform "
            "profile and degrease immediately before application."
        ),
    },
    {
        "title": "Vacuum de-aeration during mixing (synthetic)",
        "source": "procedure",
        "classification": "INTERNAL",
        "body": (
            "This document is SYNTHETIC demonstration content.\n\n"
            "Entrained air raises apparent volume and produces pinholes on "
            "sanding. Apply vacuum during the final mixing stage and record "
            "the vacuum level as a process parameter with its unit.\n\n"
            "Mixing speed is not linear with scale. Tip speed, not RPM, is "
            "the quantity that carries across vessel sizes, and assuming "
            "otherwise is the most common scale-up error in this product "
            "family."
        ),
    },
]


def seed_library(session: Session) -> int:
    lead = _actor(session, "product_development_lead")
    _scope(session, lead)
    embedder = HashingEmbedding()
    run = uuid.uuid4().hex[:6]
    made = 0
    for doc in LIBRARY:
        result = ingest_document(
            session,
            organization_id=DEMO_ORG,
            actor_id=lead,
            title=f"{doc['title']} [{run}]",
            body=doc["body"],
            source=doc["source"],
            embedder=embedder,
            project_id=None,
            classification=doc["classification"],
        )
        made += 1
        print(f"  ingested {result['chunks']:>2} chunk(s)  {doc['title']}")
    return made


# ---------------------------------------------------------------------------
# The bench
# ---------------------------------------------------------------------------


def seed_bench(session: Session) -> None:
    """Three batches, deliberately left at three different stages.

    One of each so the workspace's whole lifecycle has a subject: something to
    authorise, something to start, and something part-weighed to finish. A
    single batch could only ever demonstrate one transition.
    """
    chemist = _actor(session, "product_development_chemist")
    technician = _actor(session, "laboratory_technician")
    run = uuid.uuid4().hex[:6].upper()

    def make(suffix: str, qty: str, purpose: str) -> uuid.UUID:
        _scope(session, chemist)
        batch = create_batch(
            session,
            formula_version_id=APPROVED_VERSION,
            organization_id=DEMO_ORG,
            actor_id=chemist,
            spec=BatchInput(
                batch_number=f"LB-{run}-{suffix}",
                planned_quantity_kg=Decimal("5.0000"),
                tolerance_percent=Decimal("2.0000"),
                purpose=purpose,
                mixing_procedure=(
                    "Disperse fillers into resin under low shear, then apply "
                    "vacuum for the final two minutes. Synthetic demonstration "
                    "procedure."
                ),
                notes=None,
            ),
        )
        _ = qty
        # `create_batch` returns `batch_id`, not `id` — measured, after the
        # first run raised KeyError('id'). The detail route's response uses
        # `id`; the create service's does not. Two shapes, one entity.
        return uuid.UUID(str(batch["batch_id"]))

    # 1. Left in DRAFT — "Issue weigh-up sheet" is the next action.
    draft = make("A", "5.0000", "Demonstration batch left in draft, awaiting authorisation.")
    print(f"  draft       LB-{run}-A")

    # 2. AUTHORIZED — "Start execution" is the next action.
    authorized = make("B", "5.0000", "Demonstration batch authorised, not yet started.")
    _scope(session, chemist)
    authorize_batch(
        session, batch_id=authorized, organization_id=DEMO_ORG, actor_id=chemist
    )
    print(f"  authorized  LB-{run}-B")

    # 3. IN PROGRESS with roughly half the sheet weighed, so the workspace can
    #    show weighed lines, unweighed lines, a deviation INSIDE tolerance and
    #    one OUTSIDE it side by side. A sheet that is all-green demonstrates
    #    nothing about how an out-of-tolerance line reads.
    running = make("C", "5.0000", "Demonstration batch part-weighed at the bench.")
    _scope(session, chemist)
    authorize_batch(session, batch_id=running, organization_id=DEMO_ORG, actor_id=chemist)
    _scope(session, technician)
    start_batch(session, batch_id=running, organization_id=DEMO_ORG, actor_id=technician)

    lines = session.execute(
        text(
            """
            SELECT id, planned_mass_kg
            FROM laboratory.batch_components
            WHERE batch_id = :b AND organization_id = :o
            ORDER BY display_order
            """
        ),
        {"b": running, "o": DEMO_ORG},
    ).mappings().all()

    for index, line in enumerate(lines[: max(1, len(lines) // 2)]):
        planned = Decimal(str(line["planned_mass_kg"]))
        # The second line is deliberately out of tolerance (+5% against a 2%
        # limit) so the screen has a red deviation to render. Everything else
        # lands on plan.
        actual = planned * (Decimal("1.05") if index == 1 else Decimal("1"))
        record_weighing(
            session,
            batch_id=running,
            component_id=line["id"],
            organization_id=DEMO_ORG,
            actor_id=technician,
            actual_mass_kg=actual.quantize(Decimal("0.0001")),
            material_lot_id=None,
        )
    print(f"  in progress LB-{run}-C  ({max(1, len(lines) // 2)} of {len(lines)} lines weighed)")
    _ = draft


def main() -> None:
    engine = create_engine(DB)
    session = sessionmaker(bind=engine)()
    try:
        print("Knowledge library:")
        made = seed_library(session)
        print("Bench:")
        seed_bench(session)
        session.commit()
        print(f"\nDone. {made} documents ingested, 3 batches created.")
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


if __name__ == "__main__":
    main()
