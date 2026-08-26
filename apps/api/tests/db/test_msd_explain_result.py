"""MSD explains a test result. Concept Note §17, closing half of I23.

🔴 THE PROPERTY UNDER TEST IS THAT MSD DOES NOT DO THE ARITHMETIC.

§10's disposition comes from an ordered fourteen-rule algorithm, run on every
read by `get_test`. A chat capability that recomputed a mean, re-decided a
colour, or re-read a threshold would be a **second implementation of the
safety algorithm reachable from a chat box** -- and when the two disagreed, the
one the user had been told would be the one nobody could account for.

So these tests assert agreement with the engine rather than the correctness of
any number: whatever `get_test` derives is what the explanation says.
"""

from __future__ import annotations

import uuid
from decimal import Decimal

import pytest
from sqlalchemy import text

from app.agents.conductors.msd_conductor import (
    _compose_test_explanation,
    _test_number_in,
    classify,
)
from app.agents.tools.testing import explain_test
from app.domains.testing.service import get_test


@pytest.fixture
def a_failed_test(owner_session):
    """A test whose result the engine derives as RED.

    Built through the real services -- replicates recorded, then
    `complete_execution` -- so the disposition is DERIVED. Inserting a row with
    `calculated_result = 'fail'` would make this test agree with itself rather
    than with the engine.
    """
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
    from app.domains.materials.service import MaterialInput, create_material
    from app.domains.testing.service import (
        ReplicateInput,
        TestInput,
        complete_execution,
        create_test,
        record_replicate,
        start_execution,
    )

    s = owner_session
    tag = uuid.uuid4().hex[:6]
    org = s.execute(
        text("INSERT INTO core.organizations (code,name) VALUES (:c,'MSD') RETURNING id"),
        {"c": f"MSDX-{tag}"},
    ).scalar_one()
    who = {}
    for role in ("lead", "chemist", "engineer", "technician"):
        uid = s.execute(
            text(
                "INSERT INTO core.users (keycloak_sub,email,display_name) "
                "VALUES (:s,:e,:n) RETURNING id"
            ),
            {"s": str(uuid.uuid4()), "e": f"{role}-{tag}@example.test", "n": role},
        ).scalar_one()
        s.execute(
            text(
                "INSERT INTO core.organization_members (organization_id, user_id, status,"
                " email, display_name) SELECT :o, :u, 'active', u.email, u.display_name FROM"
                " core.users u WHERE u.id = :u"
            ),
            {"o": org, "u": uid},
        )
        who[role] = uid
    project = s.execute(
        text(
            "INSERT INTO projects.projects "
            "(organization_id,project_code,name,current_stage,lead_user_id) "
            "VALUES (:o,:c,'MSD','REQUIREMENTS',:u) RETURNING id"
        ),
        {"o": org, "c": f"RDP-{tag}", "u": who["lead"]},
    ).scalar_one()
    material = create_material(
        s,
        organization_id=org,
        actor_id=who["chemist"],
        spec=MaterialInput(
            material_code=f"RM-{tag}",
            name="Resin",
            category="Resin",
            # 🔴 A DENSITY, BECAUSE THE ENGINE REFUSES WITHOUT ONE.
            # `submit_version` blocks with "RM-x has no density, so theoretical
            # density cannot be calculated" -- a real control, and the same one
            # that refused the golden scenario while it was being written.
            # Supplying the datum is what a chemist does; switching the check
            # off would make this fixture prove less than it appears to.
            density_g_cm3=Decimal("1.10"),
            requires_sds=False,
        ),
    )
    requirement = s.execute(
        text(
            """
            INSERT INTO projects.requirements
                (organization_id, project_id, requirement_code, category, name,
                 minimum_value, maximum_value, canonical_unit, warning_threshold,
                 criticality, verification_method, status, created_by)
            VALUES (:o,:p,:c,'technical','Flexural strength',
                    5.0, 20.0, 'MPa', 5.0, 'major', 'test', 'approved', :u)
            RETURNING id
            """
        ),
        {"o": org, "p": project, "c": f"REQ-{tag}", "u": who["engineer"]},
    ).scalar_one()
    method = s.execute(
        text(
            """
            INSERT INTO testing.test_methods
                (organization_id, method_code, name, property_measured,
                 canonical_unit, replicates_required, cv_limit, created_by)
            VALUES (:o,:c,'Flexure','flexural_strength','MPa',3,15.0,:u)
            RETURNING id
            """
        ),
        {"o": org, "c": f"TM-{tag}", "u": who["engineer"]},
    ).scalar_one()

    created = create_formula(
        s,
        project_id=project,
        organization_id=org,
        actor_id=who["chemist"],
        spec=FormulaInput(formula_code=f"FRM-{tag}", name="MSD test"),
    )
    set_components(
        s,
        version_id=created["version_id"],
        organization_id=org,
        actor_id=who["chemist"],
        components=[ComponentInput(material_id=material, percentage="100.0000")],
    )
    # `requires_sds=False` is set at creation above rather than UPDATEd here:
    # I41's control counts usable SDS documents, and this fixture is about the
    # disposition algorithm, not about hazard documentation. Declaring it up
    # front is the honest form -- reaching in afterwards to switch a safety
    # flag off reads as bypassing a control.
    submit_version(
        s, version_id=created["version_id"], organization_id=org, actor_id=who["chemist"]
    )
    decide_version(
        s,
        version_id=created["version_id"],
        organization_id=org,
        actor_id=who["lead"],
        decision="approve",
        note="ok",
    )
    batch = create_batch(
        s,
        formula_version_id=created["version_id"],
        organization_id=org,
        actor_id=who["technician"],
        spec=BatchInput(batch_number=f"LB-{tag}", planned_quantity_kg=Decimal("1.0")),
    )["batch_id"]
    authorize_batch(s, batch_id=batch, organization_id=org, actor_id=who["lead"])
    start_batch(s, batch_id=batch, organization_id=org, actor_id=who["technician"])
    for line in (
        s.execute(
            text(
                "SELECT id, planned_mass_kg FROM laboratory.batch_components "
                "WHERE batch_id = :b ORDER BY id"
            ),
            {"b": batch},
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
    sample = create_sample(
        s,
        batch_id=batch,
        organization_id=org,
        actor_id=who["technician"],
        spec=SampleInput(sample_number=f"S-{tag}"),
    )

    number = f"T-{tag.upper()}"
    test_id = create_test(
        s,
        organization_id=org,
        actor_id=who["engineer"],
        spec=TestInput(
            test_number=number,
            sample_id=sample,
            method_id=method,
            requirement_id=requirement,
            test_purpose="confirmation",
            authority_level="development",
        ),
    )["id"]
    start_execution(s, test_id=test_id, organization_id=org, actor_id=who["technician"])
    for n, value in enumerate(("2.0", "2.1", "1.9"), start=1):
        record_replicate(
            s,
            test_id=test_id,
            organization_id=org,
            actor_id=who["technician"],
            spec=ReplicateInput(replicate_number=n, measured_value=Decimal(value), unit="MPa"),
        )
    complete_execution(s, test_id=test_id, organization_id=org, actor_id=who["technician"])
    s.flush()
    return {"org": org, "test_id": test_id, "number": number}


def test_the_explanation_agrees_with_the_engine(owner_session, a_failed_test) -> None:
    """🔴 MSD reports the derivation; it does not perform one.

    Every figure in the explanation must be the one `get_test` derived. If the
    tool ever recomputed a mean or re-decided a colour, this is where the two
    would part company.
    """
    truth = get_test(
        owner_session, test_id=a_failed_test["test_id"], organization_id=a_failed_test["org"]
    )
    explained = explain_test(
        owner_session, organization_id=a_failed_test["org"], query=a_failed_test["number"]
    )

    assert explained is not None
    assert explained["final_disposition"] == truth["final_disposition"]
    assert explained["automatic_evaluation"] == truth["automatic_evaluation"]
    assert explained["statistics"] == truth["statistics"]
    assert len(explained["replicates"]) == len(truth["replicates"])


def test_the_composed_answer_states_both_fields_separately(owner_session, a_failed_test) -> None:
    """§10: the automatic evaluation and the final disposition are two things.

    A low-margin pass awaiting approval is both a pass and not final, and one
    sentence cannot say that. The composer must name both.
    """
    explained = explain_test(
        owner_session, organization_id=a_failed_test["org"], query=a_failed_test["number"]
    )
    body = _compose_test_explanation(a_failed_test["number"], explained)

    assert "Automatic evaluation:" in body
    assert "Final disposition:" in body
    assert "RED" in body
    # The rule number is what makes "why" checkable rather than plausible.
    assert "rule" in body.lower()
    # Raw measurements, because §10 says the aggregate alone is not the record.
    assert "2.0" in body
    assert "1.9" in body
    # The acceptance criterion it was measured against.
    assert "5.0" in body


def test_an_unresolvable_test_says_so_rather_than_explaining_nothing(owner_session) -> None:
    """ "I could not find it" and "it has no result" are different statements."""
    body = _compose_test_explanation("T-NOSUCH", None)
    assert "could not find" in body.lower()
    # And it must not imply absence -- the caller may simply not be a member.
    assert "not the same as it not existing" in body.lower()


def test_a_test_in_another_organization_is_not_explained(owner_session, a_failed_test) -> None:
    """The boundary, at the tool.

    MSD operates under exactly the caller's authorization. Asking about a test
    number that exists elsewhere must resolve to nothing.
    """
    other = owner_session.execute(
        text("INSERT INTO core.organizations (code,name) VALUES (:c,'Other') RETURNING id"),
        {"c": f"OTHX-{uuid.uuid4().hex[:6]}"},
    ).scalar_one()
    owner_session.flush()

    assert explain_test(owner_session, organization_id=other, query=a_failed_test["number"]) is None


def test_a_named_test_beats_general_guidance(owner_session) -> None:
    """🔴 The ordering decision, asserted.

    "Why did the test fail" is a question about the application. "Why did
    T-0001 fail" is a question about T-0001, and answering it with a general
    explanation of RED reads as an answer while being none.
    """
    assert classify("why did T-DEMO-01 fail?") == "explain_result"
    assert _test_number_in("why did t-demo-01 fail?") == "T-DEMO-01"

    # ...and without an identifier, guidance still wins.
    assert classify("why did the test fail") == "guidance"
    assert classify("what does yellow mean?") == "guidance"


def test_the_other_intents_still_route(owner_session) -> None:
    """A new branch checked FIRST is a chance to shadow every other one."""
    assert classify("what is waiting for me?") == "pending_work"
    assert classify("compare FRM-009 and FRM-014") == "compare_formulas"
    assert classify("is RM-ADD-01 safe to use?") == "material_safety"
    assert classify("what is the density of FRM-014") == "formula_figures"
