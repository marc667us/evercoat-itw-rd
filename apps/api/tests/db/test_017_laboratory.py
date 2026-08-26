"""Migration 017's invariants, and the batch flow's rules.

A laboratory batch is the record of physical work: which lot of which
material was weighed, by whom, to what mass. `CLAUDE.md` §5 ends its
traceability rule at "no test result without traceability to the physical
sample", and this schema is the link that makes that possible — so its
guarantees are exercised against a real PostgreSQL rather than asserted
in a comment.

WHICH SESSION. `owner_session` for constraints and triggers, which apply
to the owner identically. Isolation assertions would need `app_session`,
because `relforcerowsecurity` is FALSE and the owner is exempt — there are
none in this file, and that absence is deliberate rather than an
oversight: migration 017 reuses migration 005's policy shape verbatim,
which `test_015_materials_formulations.py` already exercises.
"""

from __future__ import annotations

import uuid
from decimal import Decimal

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError, IntegrityError
from sqlalchemy.orm import Session

from app.domains.laboratory.service import (
    BatchInput,
    BatchStateError,
    SampleInput,
    authorize_batch,
    complete_batch,
    create_batch,
    create_sample,
    get_batch,
    record_weighing,
    review_batch,
    start_batch,
)

# ---------------------------------------------------------------------------
# Fixtures — an approved formula with a real composition
# ---------------------------------------------------------------------------


@pytest.fixture
def approved_formula(owner_session: Session) -> dict[str, uuid.UUID]:
    """An organization, two members, and a formula version approved for lab.

    Two users because segregation of duties is one of the rules under
    test: the person who executes a batch may not review it, and a
    fixture with one user could not tell a working rule from a broken one.
    """
    suffix = uuid.uuid4().hex[:8]
    org = owner_session.execute(
        text("INSERT INTO core.organizations (code, name) VALUES (:c, :n) RETURNING id"),
        {"c": f"LAB-{suffix}", "n": "Laboratory Test Org"},
    ).scalar_one()

    users: dict[str, uuid.UUID] = {}
    for label in ("chemist", "technician", "engineer"):
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
            VALUES (:o, :c, 'Lab fixture project', 'normal') RETURNING id
            """
        ),
        {"o": org, "c": f"RDP-L-{suffix}"},
    ).scalar_one()

    materials: dict[str, uuid.UUID] = {}
    for code, role in (("RESIN", "resin"), ("FILLER", "filler")):
        materials[code] = owner_session.execute(
            text(
                """
                INSERT INTO materials.materials
                    (organization_id, material_code, name, category, role, status,
                     density_g_cm3, created_by)
                VALUES (:o, :c, :c, 'Fixture', :role, 'approved', 1.2000, :u)
                RETURNING id
                """
            ),
            {"o": org, "c": f"{code}-{suffix}", "role": role, "u": users["chemist"]},
        ).scalar_one()

    formula = owner_session.execute(
        text(
            """
            INSERT INTO formulations.formulas
                (organization_id, project_id, formula_code, name, owner_user_id, created_by)
            VALUES (:o, :p, :c, 'Lab fixture formula', :u, :u) RETURNING id
            """
        ),
        {"o": org, "p": project, "c": f"FRM-L-{suffix}", "u": users["chemist"]},
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
        {"o": org, "p": project, "f": formula, "vc": f"FRM-L-{suffix}-V001", "u": users["chemist"]},
    ).scalar_one()

    for code, pct in (("RESIN", "60.0000"), ("FILLER", "40.0000")):
        owner_session.execute(
            text(
                """
                INSERT INTO formulations.formula_components
                    (organization_id, project_id, formula_version_id, material_id, percentage)
                VALUES (:o, :p, :v, :m, :pct)
                """
            ),
            {"o": org, "p": project, "v": version, "m": materials[code], "pct": pct},
        )

    # Approve it: a batch can only be made from an approved version, and
    # the trigger permits this move because the version is still a draft.
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
    owner_session.flush()

    return {
        "org": org,
        "project": project,
        "version": version,
        "resin": materials["RESIN"],
        "filler": materials["FILLER"],
        **users,
    }


def _create(session: Session, fx: dict[str, uuid.UUID], qty: str = "10.000") -> uuid.UUID:
    result = create_batch(
        session,
        formula_version_id=fx["version"],
        organization_id=fx["org"],
        actor_id=fx["chemist"],
        spec=BatchInput(
            batch_number=f"LB-{uuid.uuid4().hex[:8]}",
            planned_quantity_kg=Decimal(qty),
        ),
    )
    return result["batch_id"]


# ---------------------------------------------------------------------------
# Creation
# ---------------------------------------------------------------------------


def test_the_weigh_up_sheet_sums_exactly_to_the_batch_quantity(
    owner_session: Session, approved_formula: dict[str, uuid.UUID]
) -> None:
    """THE INVARIANT A TECHNICIAN RECONCILES AGAINST.

    The engine guarantees it and this asserts it survives the round trip
    through NUMERIC(14,4) storage. A sheet whose lines sum to 9.999 kg for
    a 10 kg batch sends somebody looking for a discrepancy the software
    created.
    """
    batch_id = _create(owner_session, approved_formula, "10.000")

    total = owner_session.execute(
        text(
            """
            SELECT sum(planned_mass_kg) FROM laboratory.batch_components
            WHERE batch_id = :b
            """
        ),
        {"b": batch_id},
    ).scalar_one()

    assert total == Decimal("10.0000")


def test_a_batch_cannot_be_made_from_an_unapproved_version(
    owner_session: Session, approved_formula: dict[str, uuid.UUID]
) -> None:
    """`CLAUDE.md` §11: approve lab -> create batch.

    Checked inside the INSERT rather than before it, so a version approved
    when the check ran and superseded when the insert landed cannot
    produce a batch of a formula nobody approved.
    """
    owner_session.execute(
        text("UPDATE formulations.formula_versions SET status = 'superseded' WHERE id = :v"),
        {"v": approved_formula["version"]},
    )
    owner_session.flush()

    with pytest.raises(BatchStateError, match="approved"):
        _create(owner_session, approved_formula)


# ---------------------------------------------------------------------------
# The lot must be a lot of the right material
# ---------------------------------------------------------------------------


def test_a_lot_of_the_wrong_material_cannot_be_charged(
    owner_session: Session, approved_formula: dict[str, uuid.UUID]
) -> None:
    """🔴 THE MOST CONSEQUENTIAL MISTAKE AVAILABLE AT A WEIGH-UP BENCH.

    A plain `REFERENCES material_lots(id)` proves the lot exists and says
    nothing about whether it is a lot OF THIS LINE'S MATERIAL. The
    application could compare them; an application comparison is a check
    somebody can forget. The three-column foreign key is a mechanism.
    """
    fx = approved_formula
    batch_id = _create(owner_session, fx)

    # A released lot — of the FILLER.
    filler_lot = owner_session.execute(
        text(
            """
            INSERT INTO materials.material_lots
                (organization_id, material_id, lot_number, status, created_by)
            VALUES (:o, :m, :n, 'released', :u) RETURNING id
            """
        ),
        {"o": fx["org"], "m": fx["filler"], "n": f"LOT-{uuid.uuid4().hex[:6]}", "u": fx["chemist"]},
    ).scalar_one()

    resin_line = owner_session.execute(
        text(
            """
            SELECT id FROM laboratory.batch_components
            WHERE batch_id = :b AND material_id = :m
            """
        ),
        {"b": batch_id, "m": fx["resin"]},
    ).scalar_one()
    owner_session.flush()

    with pytest.raises(IntegrityError) as caught:
        owner_session.execute(
            text(
                """
                UPDATE laboratory.batch_components
                SET material_lot_id = :lot, actual_mass_kg = 6.0,
                    weighed_by = :u, weighed_at = now()
                WHERE id = :c
                """
            ),
            {"lot": filler_lot, "c": resin_line, "u": fx["technician"]},
        )

    assert "batch_components_lot_fk" in str(caught.value.orig)


def test_only_a_released_lot_may_be_charged(
    owner_session: Session, approved_formula: dict[str, uuid.UUID]
) -> None:
    """A quarantined lot is material nobody has cleared for use.

    A batch made from one produces results that mean nothing, and the
    traceability chain would record it as though it were fine.
    """
    fx = approved_formula
    batch_id = _create(owner_session, fx)
    authorize_batch(
        owner_session, batch_id=batch_id, organization_id=fx["org"], actor_id=fx["chemist"]
    )
    start_batch(
        owner_session, batch_id=batch_id, organization_id=fx["org"], actor_id=fx["technician"]
    )

    quarantined = owner_session.execute(
        text(
            """
            INSERT INTO materials.material_lots
                (organization_id, material_id, lot_number, status, created_by)
            VALUES (:o, :m, :n, 'quarantine', :u) RETURNING id
            """
        ),
        {"o": fx["org"], "m": fx["resin"], "n": f"LOT-{uuid.uuid4().hex[:6]}", "u": fx["chemist"]},
    ).scalar_one()

    line = owner_session.execute(
        text("SELECT id FROM laboratory.batch_components WHERE batch_id = :b AND material_id = :m"),
        {"b": batch_id, "m": fx["resin"]},
    ).scalar_one()
    owner_session.flush()

    with pytest.raises(BatchStateError, match="quarantine"):
        record_weighing(
            owner_session,
            batch_id=batch_id,
            component_id=line,
            organization_id=fx["org"],
            actor_id=fx["technician"],
            actual_mass_kg=Decimal("6.000"),
            material_lot_id=quarantined,
        )


# ---------------------------------------------------------------------------
# The sheet freezes when it is issued
# ---------------------------------------------------------------------------


def test_the_planned_quantities_freeze_when_the_sheet_is_issued(
    owner_session: Session, approved_formula: dict[str, uuid.UUID]
) -> None:
    """An instruction that was issued cannot be rewritten afterwards.

    Otherwise a line weighed 200 g heavy could be "corrected" by moving
    the plan, and the reconciliation would show a perfect batch.
    """
    fx = approved_formula
    batch_id = _create(owner_session, fx)
    authorize_batch(
        owner_session, batch_id=batch_id, organization_id=fx["org"], actor_id=fx["chemist"]
    )

    line = owner_session.execute(
        text("SELECT id FROM laboratory.batch_components WHERE batch_id = :b LIMIT 1"),
        {"b": batch_id},
    ).scalar_one()

    with pytest.raises(DBAPIError) as caught:
        owner_session.execute(
            text("UPDATE laboratory.batch_components SET planned_mass_kg = 99.0 WHERE id = :c"),
            {"c": line},
        )

    assert "issued" in str(caught.value.orig)


def test_a_line_cannot_be_added_to_an_issued_sheet(
    owner_session: Session, approved_formula: dict[str, uuid.UUID]
) -> None:
    """Adding a component after issue changes the formula that was made.

    The INSERT case, which an UPDATE-only guard would miss — a rule
    enforced on UPDATE only is already a recorded defect here.
    """
    fx = approved_formula
    batch_id = _create(owner_session, fx)
    authorize_batch(
        owner_session, batch_id=batch_id, organization_id=fx["org"], actor_id=fx["chemist"]
    )
    owner_session.flush()

    with pytest.raises(DBAPIError) as caught:
        owner_session.execute(
            text(
                """
                INSERT INTO laboratory.batch_components
                    (organization_id, project_id, batch_id, material_id, planned_mass_kg)
                VALUES (:o, :p, :b, :m, 1.0)
                """
            ),
            {"o": fx["org"], "p": fx["project"], "b": batch_id, "m": fx["filler"]},
        )

    assert "issued" in str(caught.value.orig)


def test_a_batch_number_is_immutable_once_issued(
    owner_session: Session, approved_formula: dict[str, uuid.UUID]
) -> None:
    """Every test result will eventually cite it."""
    batch_id = _create(owner_session, approved_formula)
    owner_session.flush()

    with pytest.raises(DBAPIError) as caught:
        owner_session.execute(
            text("UPDATE laboratory.batches SET batch_number = 'RENAMED' WHERE id = :b"),
            {"b": batch_id},
        )

    assert "immutable" in str(caught.value.orig)


# ---------------------------------------------------------------------------
# Completion and review
# ---------------------------------------------------------------------------


def test_a_batch_cannot_complete_with_an_unweighed_line(
    owner_session: Session, approved_formula: dict[str, uuid.UUID]
) -> None:
    """A batch whose composition is unknown taints every test traced to it.

    The check counts NULLs rather than reading a flag somebody sets, so
    it cannot be satisfied by ticking a box.
    """
    fx = approved_formula
    batch_id = _create(owner_session, fx)
    authorize_batch(
        owner_session, batch_id=batch_id, organization_id=fx["org"], actor_id=fx["chemist"]
    )
    start_batch(
        owner_session, batch_id=batch_id, organization_id=fx["org"], actor_id=fx["technician"]
    )

    # Weigh only one of the two lines.
    line = owner_session.execute(
        text("SELECT id FROM laboratory.batch_components WHERE batch_id = :b AND material_id = :m"),
        {"b": batch_id, "m": fx["resin"]},
    ).scalar_one()
    record_weighing(
        owner_session,
        batch_id=batch_id,
        component_id=line,
        organization_id=fx["org"],
        actor_id=fx["technician"],
        actual_mass_kg=Decimal("6.000"),
    )

    with pytest.raises(BatchStateError, match="no recorded weight"):
        complete_batch(
            owner_session,
            batch_id=batch_id,
            organization_id=fx["org"],
            actor_id=fx["technician"],
        )


def _weigh_everything(session: Session, fx: dict[str, uuid.UUID], batch_id: uuid.UUID) -> None:
    lines = session.execute(
        text(
            """
            SELECT id, planned_mass_kg FROM laboratory.batch_components
            WHERE batch_id = :b ORDER BY display_order
            """
        ),
        {"b": batch_id},
    ).all()
    for line_id, planned in lines:
        record_weighing(
            session,
            batch_id=batch_id,
            component_id=line_id,
            organization_id=fx["org"],
            actor_id=fx["technician"],
            actual_mass_kg=planned,
        )


def test_the_executor_may_not_review_their_own_batch(
    owner_session: Session, approved_formula: dict[str, uuid.UUID]
) -> None:
    """Segregation of duties, enforced in the UPDATE's own predicate.

    A technician signing off their own weighing removes the only check on
    it. In the WHERE clause rather than in a preceding SELECT, so two
    racing requests cannot both pass.
    """
    fx = approved_formula
    batch_id = _create(owner_session, fx)
    authorize_batch(
        owner_session, batch_id=batch_id, organization_id=fx["org"], actor_id=fx["chemist"]
    )
    start_batch(
        owner_session, batch_id=batch_id, organization_id=fx["org"], actor_id=fx["technician"]
    )
    _weigh_everything(owner_session, fx, batch_id)
    complete_batch(
        owner_session, batch_id=batch_id, organization_id=fx["org"], actor_id=fx["technician"]
    )

    with pytest.raises(Exception, match="may not review"):
        review_batch(
            owner_session,
            batch_id=batch_id,
            organization_id=fx["org"],
            actor_id=fx["technician"],  # the same person who executed it
            decision="accept",
        )

    # And somebody else can.
    result = review_batch(
        owner_session,
        batch_id=batch_id,
        organization_id=fx["org"],
        actor_id=fx["engineer"],
        decision="accept",
    )
    assert result["status"] == "accepted"


def test_a_rejected_batch_must_say_what_went_wrong(
    owner_session: Session, approved_formula: dict[str, uuid.UUID]
) -> None:
    """ "Rejected" with no stated deviation is a verdict nobody can learn
    from, and the next person to make this formula needs to know."""
    fx = approved_formula
    batch_id = _create(owner_session, fx)
    authorize_batch(
        owner_session, batch_id=batch_id, organization_id=fx["org"], actor_id=fx["chemist"]
    )
    start_batch(
        owner_session, batch_id=batch_id, organization_id=fx["org"], actor_id=fx["technician"]
    )
    _weigh_everything(owner_session, fx, batch_id)
    complete_batch(
        owner_session, batch_id=batch_id, organization_id=fx["org"], actor_id=fx["technician"]
    )

    with pytest.raises(Exception, match="deviation"):
        review_batch(
            owner_session,
            batch_id=batch_id,
            organization_id=fx["org"],
            actor_id=fx["engineer"],
            decision="reject",
        )


def test_a_reviewed_batch_cannot_change_its_outcome(
    owner_session: Session, approved_formula: dict[str, uuid.UUID]
) -> None:
    """A closed record. Re-opening it would let a rejected batch quietly
    become an accepted one after its results were known."""
    fx = approved_formula
    batch_id = _create(owner_session, fx)
    authorize_batch(
        owner_session, batch_id=batch_id, organization_id=fx["org"], actor_id=fx["chemist"]
    )
    start_batch(
        owner_session, batch_id=batch_id, organization_id=fx["org"], actor_id=fx["technician"]
    )
    _weigh_everything(owner_session, fx, batch_id)
    complete_batch(
        owner_session, batch_id=batch_id, organization_id=fx["org"], actor_id=fx["technician"]
    )
    review_batch(
        owner_session,
        batch_id=batch_id,
        organization_id=fx["org"],
        actor_id=fx["engineer"],
        decision="accept",
    )
    owner_session.flush()

    with pytest.raises(DBAPIError) as caught:
        owner_session.execute(
            text("UPDATE laboratory.batches SET status = 'rejected' WHERE id = :b"),
            {"b": batch_id},
        )

    assert "reviewed" in str(caught.value.orig)


# ---------------------------------------------------------------------------
# Reading
# ---------------------------------------------------------------------------


def test_an_unweighed_line_reports_no_deviation_rather_than_zero(
    owner_session: Session, approved_formula: dict[str, uuid.UUID]
) -> None:
    """🔴 ABSENCE MUST NOT PRESENT AS SUCCESS.

    Reporting an unweighed line as 0.00% within tolerance would make an
    incomplete batch look finished — the same failure as the empty
    requirement set that once rendered "ALL REQUIREMENTS PASSED".
    """
    fx = approved_formula
    batch_id = _create(owner_session, fx)
    batch = get_batch(owner_session, batch_id=batch_id, organization_id=fx["org"])

    assert len(batch["components"]) == 2
    for line in batch["components"]:
        assert line["actual_mass_kg"] is None
        assert line["deviation"] is None


def test_a_weighed_line_carries_its_deviation(
    owner_session: Session, approved_formula: dict[str, uuid.UUID]
) -> None:
    """Derived at read time, never stored.

    A stored delta is a second source of truth that goes stale the moment
    a correction lands — the defect already found here where a status
    function called itself "derived" and read a stored string.
    """
    fx = approved_formula
    batch_id = _create(owner_session, fx, "10.000")
    authorize_batch(
        owner_session, batch_id=batch_id, organization_id=fx["org"], actor_id=fx["chemist"]
    )
    start_batch(
        owner_session, batch_id=batch_id, organization_id=fx["org"], actor_id=fx["technician"]
    )

    line = owner_session.execute(
        text(
            """
            SELECT id, planned_mass_kg FROM laboratory.batch_components
            WHERE batch_id = :b AND material_id = :m
            """
        ),
        {"b": batch_id, "m": fx["resin"]},
    ).one()

    # 100 g heavy on a 6 kg line: 1.67%, outside the default 1% band.
    result = record_weighing(
        owner_session,
        batch_id=batch_id,
        component_id=line[0],
        organization_id=fx["org"],
        actor_id=fx["technician"],
        actual_mass_kg=line[1] + Decimal("0.100"),
    )

    assert result["delta_kg"] == Decimal("0.100")
    assert result["within_tolerance"] is False


def test_a_sample_cannot_be_taken_from_a_batch_that_was_never_executed(
    owner_session: Session, approved_formula: dict[str, uuid.UUID]
) -> None:
    """A sample from a draft batch is a sample of nothing, and every test
    result citing it would inherit that."""
    fx = approved_formula
    batch_id = _create(owner_session, fx)

    # The exact phrase, not an alternation. Hedging between two possible
    # messages is a test that passes if either is right — and therefore
    # one that stops noticing when the message stops meaning what it said.
    with pytest.raises(BatchStateError, match="no material to sample"):
        create_sample(
            owner_session,
            batch_id=batch_id,
            organization_id=fx["org"],
            actor_id=fx["technician"],
            spec=SampleInput(sample_number=f"SMP-{uuid.uuid4().hex[:6]}"),
        )
