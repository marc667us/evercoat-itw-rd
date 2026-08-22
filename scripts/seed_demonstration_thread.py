#!/usr/bin/env python3
"""Walk the digital thread once, in the demo organization, so it can be SEEN.

🔴 THIS IS OPT-IN, AND `scripts/seed.py` STILL REFUSES TO INVENT RESULTS.

`seed.py` says, deliberately:

    It does not invent test results. Synthetic data cannot validate scientific
    correctness, and a database pre-populated with plausible adhesion figures
    makes the calculation engine look verified when it is not.

That objection is right and this script does not overturn it. It answers it in
two ways:

1. **Nothing here is a pre-baked answer.** Every disposition is DERIVED by the
   real engine from raw replicate values pushed through `complete_execution`
   and read back through `get_test`. The RED is red because 2.0 MPa is below a
   5.0 MPa minimum, computed at read time by the ordered algorithm in §10 --
   not because a column was set to 'red'. What the screen shows is the engine
   running, which is the opposite of making it look verified.

2. **The records say what they are.** The method, the requirement and the
   batch all carry DEMONSTRATION in their names, exactly as the seeded SDS
   placeholder says "NOT A SAFETY DATA SHEET" inside the file. Nobody should
   be able to mistake this for measured evidence about a real product.

It is a separate script rather than a flag on `seed.py` so the default path
keeps its promise, and running this is a decision somebody made.

WHY IT DOES NOT SHARE CODE WITH THE GOLDEN SCENARIO
---------------------------------------------------
`tests/db/test_golden_scenario.py` walks the same fifteen arrows and asserts
at every one. This asserts almost nothing -- it is a data-loading script, and
importing test helpers into `scripts/` would couple the demonstration data to
a test's fixtures. They overlap by design and are checked by different things:
the test proves the thread WORKS, this makes it VISIBLE.

    python scripts/seed_demonstration_thread.py
"""

from __future__ import annotations

import os
import pathlib
import sys
import uuid
from decimal import Decimal

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "apps" / "api"))

from app.domains.formulations.service import (
    ComponentInput,
    FormulaInput,
    create_formula,
    decide_version,
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
    record_weighing,
    start_batch,
)
from app.domains.testing.service import (
    ReplicateInput,
    TestInput,
    complete_execution,
    create_test,
    get_test,
    record_replicate,
    start_execution,
)
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

DSN = os.getenv(
    "SEED_DATABASE_URL",
    "postgresql+psycopg://postgres:dev-superuser-pw@localhost:55432/evercoat_itw_rd",
).replace("postgresql://", "postgresql+psycopg://")

SUFFIX = uuid.uuid4().hex[:6].upper()


def people(s: Session, org: uuid.UUID) -> dict[str, uuid.UUID]:
    """The seeded demo users, by role. They already exist; this finds them."""
    rows = s.execute(
        text(
            """
            SELECT r.code, u.id
            FROM core.users u
            JOIN core.organization_members m ON m.user_id = u.id
            JOIN core.member_roles mr ON mr.member_id = m.id
            JOIN core.roles r ON r.id = mr.role_id
            WHERE m.organization_id = :o
            """
        ),
        {"o": org},
    ).all()
    by_role = {code: uid for code, uid in rows}
    return {
        "lead": by_role["product_development_lead"],
        "chemist": by_role["product_development_chemist"],
        "engineer": by_role["product_development_engineer"],
        "technician": by_role["laboratory_technician"],
    }


def batch_and_sample(s: Session, org, who, version_id, tag: str) -> uuid.UUID:
    """A batch through its REAL lifecycle, not inserted at 'completed'.

    `complete_batch` refuses until every line has been weighed, and that
    refusal is the control between a sample and a batch nobody made properly.
    Short-cutting it would make the demonstration show less than it appears to.
    """
    batch = create_batch(
        s,
        formula_version_id=version_id,
        organization_id=org,
        actor_id=who["technician"],
        spec=BatchInput(
            batch_number=f"LB-DEMO-{tag}", planned_quantity_kg=Decimal("1.0")
        ),
    )["batch_id"]
    authorize_batch(s, batch_id=batch, organization_id=org, actor_id=who["lead"])
    start_batch(s, batch_id=batch, organization_id=org, actor_id=who["technician"])

    for line in (
        s.execute(
            text(
                "SELECT id, planned_mass_kg FROM laboratory.batch_components "
                "WHERE batch_id = :b AND organization_id = :o ORDER BY id"
            ),
            {"b": batch, "o": org},
        )
        .mappings()
        .all()
    ):
        record_weighing(
            s,
            batch_id=batch,
            component_id=line["id"],
            organization_id=org,
            actor_id=who["technician"],
            actual_mass_kg=line["planned_mass_kg"],
        )
    complete_batch(s, batch_id=batch, organization_id=org, actor_id=who["technician"])
    return create_sample(
        s,
        batch_id=batch,
        organization_id=org,
        actor_id=who["technician"],
        spec=SampleInput(sample_number=f"S-DEMO-{tag}"),
    )


def main() -> None:
    engine = create_engine(DSN)
    with Session(engine) as s:
        s.begin()
        org = s.execute(
            text("SELECT id FROM core.organizations WHERE code = 'EVERCOAT-DEMO'")
        ).scalar_one_or_none()
        if org is None:
            sys.exit("the demo organization is absent -- run scripts/seed.py first")

        if s.execute(
            text("SELECT count(*) FROM testing.tests WHERE organization_id = :o"), {"o": org}
        ).scalar_one():
            print("a demonstration thread already exists; nothing to do")
            return

        who = people(s, org)
        project = s.execute(
            text(
                "SELECT id FROM projects.projects WHERE organization_id = :o "
                "ORDER BY created_at LIMIT 1"
            ),
            {"o": org},
        ).scalar_one()
        material = s.execute(
            text(
                "SELECT id FROM materials.materials WHERE organization_id = :o "
                "ORDER BY material_code LIMIT 1"
            ),
            {"o": org},
        ).scalar_one()

        # The acceptance criterion the test is measured against. Named
        # DEMONSTRATION so it cannot be read as a real product requirement.
        requirement = s.execute(
            text(
                """
                INSERT INTO projects.requirements
                    (organization_id, project_id, requirement_code, category, name,
                     minimum_value, maximum_value, canonical_unit, warning_threshold,
                     criticality, verification_method, status, created_by)
                VALUES (:o, :p, :c, 'technical',
                        'Flexural strength (DEMONSTRATION)',
                        5.0, 20.0, 'MPa', 5.0, 'major', 'test', 'approved', :u)
                RETURNING id
                """
            ),
            {"o": org, "p": project, "c": f"REQ-DEMO-{SUFFIX}", "u": who["engineer"]},
        ).scalar_one()

        method = s.execute(
            text(
                """
                INSERT INTO testing.test_methods
                    (organization_id, method_code, name, property_measured,
                     canonical_unit, replicates_required, cv_limit, created_by)
                VALUES (:o, :c, 'Three-point flexure (DEMONSTRATION METHOD)',
                        'flexural_strength', 'MPa', 3, 15.0, :u)
                RETURNING id
                """
            ),
            {"o": org, "c": f"TM-DEMO-{SUFFIX}", "u": who["engineer"]},
        ).scalar_one()

        created = create_formula(
            s,
            project_id=project,
            organization_id=org,
            actor_id=who["chemist"],
            spec=FormulaInput(
                formula_code=f"FRM-DEMO-{SUFFIX}",
                name="Demonstration filler (synthetic)",
            ),
        )
        version = created["version_id"]
        set_components(
            s,
            version_id=version,
            organization_id=org,
            actor_id=who["chemist"],
            components=[ComponentInput(material_id=material, percentage="100.0000")],
        )
        submit_version(s, version_id=version, organization_id=org, actor_id=who["chemist"])
        # The approver is NOT the submitter -- §9's segregation of duties.
        decide_version(
            s,
            version_id=version,
            organization_id=org,
            actor_id=who["lead"],
            decision="approve",
            note="Approved for laboratory work (demonstration).",
        )
        print(f"  formula FRM-DEMO-{SUFFIX} approved for the lab")

        sample = batch_and_sample(s, org, who, version, SUFFIX)
        print(f"  batch LB-DEMO-{SUFFIX} completed, sample S-DEMO-{SUFFIX} taken")

        test_id = create_test(
            s,
            organization_id=org,
            actor_id=who["engineer"],
            spec=TestInput(
                test_number=f"T-DEMO-{SUFFIX}",
                sample_id=sample,
                method_id=method,
                requirement_id=requirement,
                test_purpose="confirmation",
                authority_level="development",
            ),
        )["id"]

        # 🔴 RAW REPLICATES, NEVER AN AGGREGATE (§10). 2.0/2.1/1.9 MPa against
        # a 5.0 MPa minimum -- the engine decides what that means, not this
        # script.
        start_execution(s, test_id=test_id, organization_id=org, actor_id=who["technician"])
        for n, value in enumerate(("2.0", "2.1", "1.9"), start=1):
            record_replicate(
                s,
                test_id=test_id,
                organization_id=org,
                actor_id=who["technician"],
                spec=ReplicateInput(
                    replicate_number=n, measured_value=Decimal(value), unit="MPa"
                ),
            )

        completed = complete_execution(
            s, test_id=test_id, organization_id=org, actor_id=who["technician"]
        )
        shown = get_test(s, test_id=test_id, organization_id=org)
        colour = shown["final_disposition"]["colour"]
        print(
            f"  test T-DEMO-{SUFFIX}: calculated_result="
            f"{completed['calculated_result']}, disposition={colour.upper()} "
            f"(DERIVED, not written)"
        )
        if completed.get("failure_investigation"):
            print(
                "  failure investigation opened AUTOMATICALLY "
                f"({completed['failure_investigation'].get('failure_code')})"
            )

        s.commit()
        print(
            "\ndemonstration thread seeded. Every figure is synthetic and every "
            "record says so."
        )


if __name__ == "__main__":
    main()
