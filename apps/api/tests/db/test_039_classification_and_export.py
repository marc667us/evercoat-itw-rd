"""I48 the classification lattice, and I43 export as its own permission.

The two are one change because I43 cannot exist without I48: "refuse to export
above a level" needs levels that are ordered.
"""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import text

from app.domains.formulations.service import (
    EXPORT_WITHOUT_SECOND_APPROVAL_CEILING,
    ComponentInput,
    FormulaExportRefusedError,
    FormulaInput,
    create_formula,
    export_version,
    set_classification,
    set_components,
)
from app.domains.materials.service import MaterialInput, create_material

ALL_LEVELS = (
    "PUBLIC",
    "INTERNAL",
    "CONFIDENTIAL",
    "R&D_RESTRICTED",
    "FORMULA_RESTRICTED",
    "DIRECTOR_CONTROLLED",
)


# ---------------------------------------------------------------------------
# I48 — the lattice
# ---------------------------------------------------------------------------


def test_the_lattice_is_totally_ordered(owner_session) -> None:
    """🔴 The outbound AI gate is defined as "PUBLIC only" (ADR-029).

    That sentence means nothing unless the levels are ordered and PUBLIC is
    the bottom. The source folder defined classification twice with two
    vocabularies and only ONE contained PUBLIC at all.
    """
    rows = owner_session.execute(
        text("SELECT code, rank FROM core.classifications ORDER BY rank")
    ).all()
    codes = [r[0] for r in rows]
    ranks = [r[1] for r in rows]

    assert codes == list(ALL_LEVELS), f"the lattice is not the reconciled one: {codes}"
    assert ranks == sorted(set(ranks)), "ranks are not strictly increasing or not unique"
    assert codes[0] == "PUBLIC", "PUBLIC must be the floor; the AI gate is defined on it"
    assert codes[-1] == "DIRECTOR_CONTROLLED", "the ceiling must be the most restrictive"


def test_an_unknown_level_has_no_rank_so_a_caller_must_deny(owner_session) -> None:
    """NULL compares as neither above nor below. Callers treat it as DENY."""
    unknown = owner_session.execute(
        text("SELECT core.classification_rank('NO_SUCH_LEVEL')")
    ).scalar()
    assert unknown is None


def test_a_row_cannot_carry_a_level_that_does_not_exist(owner_session, two_orgs) -> None:
    """The FK is what makes the lattice data rather than a suggestion."""
    org, _ = two_orgs
    user = owner_session.execute(
        text(
            "INSERT INTO core.users (keycloak_sub,email,display_name) "
            "VALUES (:s,:e,'Cls') RETURNING id"
        ),
        {"s": str(uuid.uuid4()), "e": f"{uuid.uuid4().hex[:8]}@example.test"},
    ).scalar_one()
    # `create_material` checks the actor is an active member -- the cross-tenant
    # author guard. Membership is a precondition of the test, not its subject.
    owner_session.execute(
        text(
            "INSERT INTO core.organization_members (organization_id,user_id,status) "
            "VALUES (:o,:u,'active')"
        ),
        {"o": org, "u": user},
    )
    material = create_material(
        owner_session,
        organization_id=org,
        actor_id=user,
        spec=MaterialInput(
            material_code=f"RM-{uuid.uuid4().hex[:6]}", name="Resin", category="Resin"
        ),
    )
    with pytest.raises(Exception, match="classification"):
        owner_session.execute(
            text(
                """
                INSERT INTO materials.material_documents
                    (organization_id, material_id, document_type, title, storage_key,
                     uploaded_by, classification)
                VALUES (:o,:m,'SDS','bad level','k-'||gen_random_uuid(),:u,'TOP_SECRET')
                """
            ),
            {"o": org, "m": material, "u": user},
        )
        owner_session.flush()
    owner_session.rollback()


def test_unset_is_the_ceiling_not_the_middle(owner_session) -> None:
    """🔴 Fail closed.

    A NULL defaulting to the middle of a lattice is a disclosure waiting for
    the first row somebody forgets to label. Anything created without a
    decision must be maximally restricted.
    """
    default = owner_session.execute(
        text(
            "SELECT column_default FROM information_schema.columns "
            "WHERE table_schema='formulations' AND table_name='formulas' "
            "AND column_name='classification'"
        )
    ).scalar_one()
    assert "DIRECTOR_CONTROLLED" in default, (
        f"formulas default to {default!r}; an unlabelled formula must be "
        "maximally restricted, not conveniently readable"
    )


def test_classification_is_not_the_project_access_scope(owner_session) -> None:
    """The two axes stay separate, deliberately.

    `projects.confidentiality` answers "is membership required to see this
    project" -- an ACCESS scope. Classification answers "how sensitive is this
    thing" -- a property of the DATA. Collapsing them is the §6 defect this
    project has found six times, a role standing in for an authorization.
    """
    values = owner_session.execute(
        text(
            "SELECT pg_get_constraintdef(oid) FROM pg_constraint "
            "WHERE conname LIKE '%confidentiality%'"
        )
    ).scalar_one()
    assert "normal" in values
    assert "restricted" in values
    for level in ALL_LEVELS:
        assert level not in values, (
            "the project access scope has absorbed a classification level; "
            "they are different questions and must stay separate columns"
        )


# ---------------------------------------------------------------------------
# I43 — export
# ---------------------------------------------------------------------------


@pytest.fixture
def a_formula(owner_session, two_orgs):
    """A formula with one component, in a real organization."""
    org, _ = two_orgs
    user = owner_session.execute(
        text(
            "INSERT INTO core.users (keycloak_sub,email,display_name) "
            "VALUES (:s,:e,'Exporter') RETURNING id"
        ),
        {"s": str(uuid.uuid4()), "e": f"{uuid.uuid4().hex[:8]}@example.test"},
    ).scalar_one()
    owner_session.execute(
        text(
            "INSERT INTO core.organization_members (organization_id,user_id,status) "
            "VALUES (:o,:u,'active')"
        ),
        {"o": org, "u": user},
    )
    project = owner_session.execute(
        text(
            """
            INSERT INTO projects.projects
                (organization_id, project_code, name, current_stage, lead_user_id)
            VALUES (:o,:c,'Export test','REQUIREMENTS',:u) RETURNING id
            """
        ),
        {"o": org, "c": f"RDP-{uuid.uuid4().hex[:6]}", "u": user},
    ).scalar_one()
    material = create_material(
        owner_session,
        organization_id=org,
        actor_id=user,
        spec=MaterialInput(
            material_code=f"RM-{uuid.uuid4().hex[:6]}", name="Resin", category="Resin"
        ),
    )
    # `create_formula` returns the formula AND its first version, so there is
    # no second query to get out of step with it.
    created = create_formula(
        owner_session,
        project_id=project,
        organization_id=org,
        actor_id=user,
        spec=FormulaInput(formula_code=f"F-{uuid.uuid4().hex[:6]}", name="Export test"),
    )
    formula = created["formula_id"]
    version = created["version_id"]
    set_components(
        owner_session,
        version_id=version,
        organization_id=org,
        actor_id=user,
        components=[ComponentInput(material_id=material, percentage="100.0000")],
    )
    owner_session.flush()
    return {"org": org, "user": user, "formula": formula, "version": version}


def _classify(session, formula_id, level: str) -> None:
    session.execute(
        text("UPDATE formulations.formulas SET classification = :c WHERE id = :f"),
        {"c": level, "f": formula_id},
    )
    session.flush()


def test_an_export_is_recorded_in_the_audit_trail(owner_session, a_formula) -> None:
    """🔴 The half that did not exist: export used to leave no trace at all.

    Anyone with `formula.view` could remove a proprietary recipe and nothing
    anywhere recorded it.
    """
    _classify(owner_session, a_formula["formula"], "R&D_RESTRICTED")

    result = export_version(
        owner_session,
        version_id=a_formula["version"],
        organization_id=a_formula["org"],
        actor_id=a_formula["user"],
    )
    assert result["components"], "the export returned no composition"

    event = (
        owner_session.execute(
            text(
                "SELECT action, new_state FROM audit.events "
                "WHERE entity_id = :e AND action = 'formula.exported' "
                "ORDER BY id DESC LIMIT 1"
            ),
            {"e": str(a_formula["version"])},
        )
        .mappings()
        .one_or_none()
    )

    assert event is not None, "a full formula export wrote no audit event"
    assert event["new_state"]["classification"] == "R&D_RESTRICTED"
    assert event["new_state"]["component_count"] == 1, (
        "the audit event must record WHAT left, not merely that something did"
    )


def test_a_master_formulation_cannot_be_exported_by_one_person(owner_session, a_formula) -> None:
    """🔴 §32: a highly sensitive formula needs a second approval.

    Above the ceiling the export is refused. There is no way to obtain that
    second approval yet (I67), which is deliberate: failing closed on a
    released master formulation is the right default.
    """
    _classify(owner_session, a_formula["formula"], "FORMULA_RESTRICTED")

    with pytest.raises(FormulaExportRefusedError, match="FORMULA_RESTRICTED"):
        export_version(
            owner_session,
            version_id=a_formula["version"],
            organization_id=a_formula["org"],
            actor_id=a_formula["user"],
        )


def test_a_refused_export_is_also_recorded(owner_session, a_formula) -> None:
    """The event a security review most wants to see.

    Recording only successes would hide the attempt to remove a master
    formulation, which is the more interesting of the two.
    """
    _classify(owner_session, a_formula["formula"], "DIRECTOR_CONTROLLED")

    with pytest.raises(FormulaExportRefusedError):
        export_version(
            owner_session,
            version_id=a_formula["version"],
            organization_id=a_formula["org"],
            actor_id=a_formula["user"],
        )

    refused = owner_session.execute(
        text(
            "SELECT count(*) FROM audit.events "
            "WHERE entity_id = :e AND action = 'formula.export_refused'"
        ),
        {"e": str(a_formula["version"])},
    ).scalar_one()
    assert refused == 1, "a refused export left no trace"


def test_the_ceiling_permits_what_it_is_not_there_to_stop(owner_session, a_formula) -> None:
    """A control that refuses everything is an outage with a reassuring name.

    Every level up to and including the ceiling must export cleanly -- this
    project has already shipped one safety check whose only possible answer
    was BLOCKED.
    """
    ceiling_rank = owner_session.execute(
        text("SELECT rank FROM core.classifications WHERE code = :c"),
        {"c": EXPORT_WITHOUT_SECOND_APPROVAL_CEILING},
    ).scalar_one()
    permitted = (
        owner_session.execute(
            text("SELECT code FROM core.classifications WHERE rank <= :r ORDER BY rank"),
            {"r": ceiling_rank},
        )
        .scalars()
        .all()
    )

    assert len(permitted) >= 4, "the ceiling has been lowered to near-nothing"

    for level in permitted:
        _classify(owner_session, a_formula["formula"], level)
        result = export_version(
            owner_session,
            version_id=a_formula["version"],
            organization_id=a_formula["org"],
            actor_id=a_formula["user"],
        )
        assert result["classification"] == level


def test_export_is_a_permission_the_chemist_does_not_hold(owner_session) -> None:
    """🔴 The separation is only a separation because it is ASYMMETRIC.

    §31: the Director does not get access by rank, and export is the
    exfiltration act itself. A Chemist may read and edit a formula and may not
    take it out. If a later migration grants this to everyone "for
    convenience", the rule is gone and this is where that shows up.
    """
    holders = set(
        owner_session.execute(
            text(
                """
                SELECT r.code FROM core.roles r
                JOIN core.role_permissions rp ON rp.role_id = r.id
                JOIN core.permissions p ON p.id = rp.permission_id
                WHERE p.code = 'formula.export'
                """
            )
        ).scalars()
    )

    assert holders, "formula.export is held by nobody; a permission with no holder does not exist"
    for excluded in (
        "product_development_chemist",
        "product_development_director",
        "laboratory_technician",
        "executive_viewer",
    ):
        assert excluded not in holders, (
            f"{excluded} holds formula.export. Export is the exfiltration act; "
            "§31 says seniority is not a reason to hold it."
        )
    # And the roles that own the controlled record do hold it.
    assert "product_development_lead" in holders
    assert "qa_compliance_officer" in holders


def test_view_and_export_are_not_the_same_permission(owner_session) -> None:
    """The five-permission rule, asserted rather than assumed."""
    codes = set(
        owner_session.execute(
            text("SELECT code FROM core.permissions WHERE code LIKE 'formula.%'")
        ).scalars()
    )
    assert {"formula.view", "formula.export"} <= codes
    assert "formula.view" != "formula.export"


# ---------------------------------------------------------------------------
# I48's missing writer — migration 040
# ---------------------------------------------------------------------------


def test_a_new_formula_is_exportable_by_its_own_rules(owner_session, a_formula) -> None:
    """🔴 THE TEST THAT WOULD HAVE CAUGHT MIGRATION 039'S DEFECT.

    039 gave the column a ceiling default and no writer, so every new formula
    was `DIRECTOR_CONTROLLED` while `export_version` refuses above
    `R&D_RESTRICTED`. Every formula created from that commit onward could never
    be exported, by anybody, with no path to change it -- and CI was green,
    because nothing asserted that the two ends agreed.

    This is the "safety check that could only say BLOCKED" shape recorded on
    materials/service.py, and restated in I67's own note two hours before I
    shipped it one column over. So it is instrumented now rather than
    restated again.
    """
    classification = owner_session.execute(
        text("SELECT classification FROM formulations.formulas WHERE id = :f"),
        {"f": a_formula["formula"]},
    ).scalar_one()

    assert classification != "DIRECTOR_CONTROLLED", (
        "a newly created formula carries the column's ceiling DEFAULT rather "
        "than a decision, so it can never be exported and nothing can change "
        "that. create_formula must classify deliberately."
    )

    # And it is genuinely exportable, not merely differently labelled.
    export_version(
        owner_session,
        version_id=a_formula["version"],
        organization_id=a_formula["org"],
        actor_id=a_formula["user"],
    )


def test_a_reclassification_is_recorded_with_both_levels(owner_session, a_formula) -> None:
    """Lowering is the dangerous direction, so the event names it."""
    set_classification(
        owner_session,
        formula_id=a_formula["formula"],
        organization_id=a_formula["org"],
        actor_id=a_formula["user"],
        classification="INTERNAL",
        reason="published in the product datasheet",
    )

    event = (
        owner_session.execute(
            text(
                "SELECT previous_state, new_state, reason FROM audit.events "
                "WHERE entity_id = :e AND action = 'formula.reclassified' "
                "ORDER BY id DESC LIMIT 1"
            ),
            {"e": str(a_formula["formula"])},
        )
        .mappings()
        .one_or_none()
    )

    assert event is not None, "a reclassification wrote no audit event"
    assert event["previous_state"]["classification"] == "R&D_RESTRICTED"
    assert event["new_state"]["classification"] == "INTERNAL"
    assert event["new_state"]["lowered"] is True, (
        "the event must say that the classification was LOWERED -- that is the "
        "direction a security review comes looking for"
    )
    assert event["reason"]


def test_a_reclassification_must_state_why(owner_session, a_formula) -> None:
    from app.domains.formulations.service import FormulaError

    with pytest.raises(FormulaError, match="state why"):
        set_classification(
            owner_session,
            formula_id=a_formula["formula"],
            organization_id=a_formula["org"],
            actor_id=a_formula["user"],
            classification="PUBLIC",
            reason="   ",
        )


def test_an_unknown_level_cannot_be_applied(owner_session, a_formula) -> None:
    from app.domains.formulations.service import FormulaError

    with pytest.raises(FormulaError, match="not a classification level"):
        set_classification(
            owner_session,
            formula_id=a_formula["formula"],
            organization_id=a_formula["org"],
            actor_id=a_formula["user"],
            classification="TOP_SECRET",
            reason="trying an invented level",
        )


def test_classify_and_export_are_held_by_exactly_the_same_roles(owner_session) -> None:
    """🔴 A wider classify grant hands the export ceiling to a broader group.

    Lowering a classification is the PRECONDITION for exporting, so if a role
    can reclassify but not export -- or the two sets drift for any reason --
    the ceiling becomes something that group steps over in two requests.
    Migration 040 refuses to complete if they differ; this is the same
    assertion where a reviewer will look for it.
    """

    def holders(permission: str) -> set[str]:
        return set(
            owner_session.execute(
                text(
                    """
                    SELECT r.code FROM core.roles r
                    JOIN core.role_permissions rp ON rp.role_id = r.id
                    JOIN core.permissions p ON p.id = rp.permission_id
                    WHERE p.code = :p
                    """
                ),
                {"p": permission},
            ).scalars()
        )

    assert holders("formula.classify") == holders("formula.export") != set()
