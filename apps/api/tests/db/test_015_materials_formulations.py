"""Migration 015's invariants -- the ones that must hold in the database.

WHAT THIS FILE IS FOR
---------------------
Slice 3's back half puts the composition of a controlled formulation into
PostgreSQL. `CLAUDE.md` section 8 says a released master formula is
read-only **at the database level, not merely hidden in the UI**, and this
project has repeatedly found comments asserting rules the code did not
implement. So every rule 015 claims is exercised here against a real
PostgreSQL, from the role that will actually hold it.

WHICH SESSION, AND WHY IT MATTERS
---------------------------------
`owner_session` builds fixtures and plays the attacker with direct
database access -- and, because `relforcerowsecurity` is FALSE on every
table (migration 001 defers the FORCE cutover), the owner is EXEMPT from
RLS. Any isolation assertion written on `owner_session` would therefore
pass whether or not the policies work.

**Every isolation assertion below uses `app_session`.** The constraint and
trigger tests use `owner_session`, because a constraint applies to the
owner too and the fixtures are cheaper to build there.
"""

from __future__ import annotations

import json
import re
import uuid
from collections.abc import Iterator
from decimal import Decimal
from pathlib import Path

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError, IntegrityError
from sqlalchemy.orm import Session

# apps/api/tests/db/this_file.py -> repo root
REPO_ROOT = Path(__file__).resolve().parents[4]
DEMO_DATA = REPO_ROOT / "apps" / "web" / "lib" / "demo" / "demo-data.json"


def _check_literals(session: Session, table: str, constraint: str) -> set[str]:
    """The quoted values inside a CHECK constraint, read from the catalogue.

    Reading the CONSTRAINT rather than a Python copy of it is the entire
    point: a test that compared two Python lists would prove they agree
    with each other and nothing about the database.
    """
    definition = session.execute(
        text(
            """
            SELECT pg_get_constraintdef(c.oid)
            FROM pg_constraint c
            WHERE c.conrelid = CAST(:table AS regclass) AND c.conname = :name
            """
        ),
        {"table": table, "name": constraint},
    ).scalar_one()
    return set(re.findall(r"'([a-z_]+)'::text", definition))


# ---------------------------------------------------------------------------
# One vocabulary, not three
# ---------------------------------------------------------------------------


def test_the_material_statuses_are_the_ones_the_web_already_renders(
    owner_session: Session,
) -> None:
    """The database CHECK and the shipped web pages must agree.

    `/materials` has been live since Slice 3's front half, rendering
    statuses from `demo-data.json`. If migration 015 had invented its own
    five -- `evaluation`, `lab_approved`, `production_approved` were the
    obvious guess from the permission names -- the API would have started
    returning statuses the deployed UI has no badge for.

    Two literals in two files that nothing can check against each other is
    the recurring root cause in this repository: nav vs router, landing vs
    pack, release.yml vs _deploy-render.yml. This is the check.
    """
    demo = json.loads(DEMO_DATA.read_text(encoding="utf-8"))
    in_web = {m["status"] for m in demo["materials"]}
    in_db = _check_literals(owner_session, "materials.materials", "materials_status_check")

    assert in_web <= in_db, (
        "the web renders material statuses the database would refuse: "
        f"{', '.join(sorted(in_web - in_db))}"
    )


def test_the_material_roles_are_the_ones_the_web_already_renders(
    owner_session: Session,
) -> None:
    """Same rule for the role vocabulary, which the engine also reads.

    `Component.role` in the calculation engine is deliberately a plain
    string rather than a Python enum, precisely so that this table stays
    the single vocabulary. That decision only holds if something checks
    it.
    """
    demo = json.loads(DEMO_DATA.read_text(encoding="utf-8"))
    in_web = {m["role"] for m in demo["materials"]}
    in_db = _check_literals(owner_session, "materials.materials", "materials_role_check")

    assert in_web <= in_db, (
        "the web renders material roles the database would refuse: "
        f"{', '.join(sorted(in_web - in_db))}"
    )


def test_the_blocking_status_set_is_a_real_material_status(owner_session: Session) -> None:
    """`BLOCKING_STATUSES` must name statuses that can actually occur.

    The Python constant drives a HARD submission block. If it named a
    status the CHECK constraint forbids, no material could ever match it
    and the block would be inert -- reading as a real safety control in an
    audit while never firing. That is the "config reads correct while the
    mechanism is INERT" shape already recorded against this platform.
    """
    from app.domains.materials.service import BLOCKING_STATUSES

    in_db = _check_literals(owner_session, "materials.materials", "materials_status_check")
    assert in_db >= BLOCKING_STATUSES, (
        f"BLOCKING_STATUSES names statuses the database cannot hold: "
        f"{', '.join(sorted(BLOCKING_STATUSES - in_db))}"
    )


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def actor(owner_session: Session) -> uuid.UUID:
    return owner_session.execute(
        text(
            """
            INSERT INTO core.users (keycloak_sub, email, display_name)
            VALUES (:s, :e, 'Fixture Chemist') RETURNING id
            """
        ),
        {"s": str(uuid.uuid4()), "e": f"chemist-{uuid.uuid4().hex[:8]}@example.test"},
    ).scalar_one()


def _org(session: Session, label: str) -> uuid.UUID:
    return session.execute(
        text("INSERT INTO core.organizations (code, name) VALUES (:c, :n) RETURNING id"),
        {"c": f"T15-{label}-{uuid.uuid4().hex[:8]}", "n": f"Org {label}"},
    ).scalar_one()


def _project(session: Session, org: uuid.UUID, confidentiality: str = "normal") -> uuid.UUID:
    return session.execute(
        text(
            """
            INSERT INTO projects.projects
                (organization_id, project_code, name, confidentiality)
            VALUES (:o, :c, 'Fixture project', :conf) RETURNING id
            """
        ),
        {"o": org, "c": f"RDP-{uuid.uuid4().hex[:8]}", "conf": confidentiality},
    ).scalar_one()


def _material(
    session: Session,
    org: uuid.UUID,
    actor_id: uuid.UUID,
    *,
    code: str | None = None,
    status: str = "approved",
    role: str = "resin",
    density: str | None = "1.10",
) -> uuid.UUID:
    return session.execute(
        text(
            """
            INSERT INTO materials.materials
                (organization_id, material_code, name, category, role, status,
                 density_g_cm3, restriction_reason, created_by)
            VALUES (:o, :c, 'Fixture material', 'Resin', :role, :status,
                    :density, :reason, :actor)
            RETURNING id
            """
        ),
        {
            "o": org,
            "c": code or f"RM-{uuid.uuid4().hex[:8]}",
            "role": role,
            "status": status,
            "density": density,
            "reason": "fixture" if status == "restricted" else None,
            "actor": actor_id,
        },
    ).scalar_one()


def _formula(
    session: Session, org: uuid.UUID, project: uuid.UUID, actor_id: uuid.UUID
) -> tuple[uuid.UUID, uuid.UUID]:
    code = f"FRM-{uuid.uuid4().hex[:6]}"
    formula_id = session.execute(
        text(
            """
            INSERT INTO formulations.formulas
                (organization_id, project_id, formula_code, name, owner_user_id, created_by)
            VALUES (:o, :p, :c, 'Fixture formula', :a, :a) RETURNING id
            """
        ),
        {"o": org, "p": project, "c": code, "a": actor_id},
    ).scalar_one()
    version_id = session.execute(
        text(
            """
            INSERT INTO formulations.formula_versions
                (organization_id, project_id, formula_id, version_number,
                 version_code, status, created_by)
            VALUES (:o, :p, :f, 1, :vc, 'draft', :a) RETURNING id
            """
        ),
        {"o": org, "p": project, "f": formula_id, "vc": f"{code}-V001", "a": actor_id},
    ).scalar_one()
    return formula_id, version_id


def _component(
    session: Session,
    org: uuid.UUID,
    project: uuid.UUID,
    version: uuid.UUID,
    material: uuid.UUID,
    percentage: str = "50.0000",
) -> uuid.UUID:
    return session.execute(
        text(
            """
            INSERT INTO formulations.formula_components
                (organization_id, project_id, formula_version_id, material_id, percentage)
            VALUES (:o, :p, :v, :m, :pct) RETURNING id
            """
        ),
        {"o": org, "p": project, "v": version, "m": material, "pct": percentage},
    ).scalar_one()


# ---------------------------------------------------------------------------
# References are not reads -- the composite keys
# ---------------------------------------------------------------------------


def test_a_component_cannot_reference_another_organizations_material(
    owner_session: Session, actor: uuid.UUID
) -> None:
    """RLS hides another tenant's material; it does not stop a reference.

    Referential integrity bypasses RLS even under FORCE. Without the
    composite `(material_id, organization_id)` foreign key, Org A could
    build a formula out of Org B's material library -- and the component
    row would then join to a material the reader cannot see, so the
    formula would render with blank lines rather than raising anything.
    """
    org_a, org_b = _org(owner_session, "A"), _org(owner_session, "B")
    project_a = _project(owner_session, org_a)
    foreign_material = _material(owner_session, org_b, actor)
    _, version_a = _formula(owner_session, org_a, project_a, actor)
    owner_session.flush()

    with pytest.raises(IntegrityError) as caught:
        _component(owner_session, org_a, project_a, version_a, foreign_material)

    assert "formula_components_material_fk" in str(caught.value.orig)


def test_a_version_cannot_be_attached_to_another_projects_formula(
    owner_session: Session, actor: uuid.UUID
) -> None:
    """The three-column key, doing the job a two-column key cannot.

    `(id, organization_id)` proves a version belongs to the same TENANT as
    its formula and says nothing about the PROJECT. Formulas inherit their
    project's confidentiality, so a version spliced onto a formula in
    another project would carry a `project_id` that no longer matches the
    composition's real owner -- and the RLS policy reads `project_id`.
    """
    org = _org(owner_session, "A")
    project_one = _project(owner_session, org)
    project_two = _project(owner_session, org)
    formula_id, _ = _formula(owner_session, org, project_one, actor)
    owner_session.flush()

    with pytest.raises(IntegrityError) as caught:
        owner_session.execute(
            text(
                """
                INSERT INTO formulations.formula_versions
                    (organization_id, project_id, formula_id, version_number,
                     version_code, status, created_by)
                VALUES (:o, :p2, :f, 2, :vc, 'draft', :a)
                """
            ),
            {
                "o": org,
                "p2": project_two,  # <- a DIFFERENT project, same tenant
                "f": formula_id,
                "vc": f"X-{uuid.uuid4().hex[:6]}",
                "a": actor,
            },
        )

    assert "formula_versions_formula_fk" in str(caught.value.orig)


# ---------------------------------------------------------------------------
# Immutability -- section 8, at the database level
# ---------------------------------------------------------------------------


@pytest.fixture
def approved_version(
    owner_session: Session, actor: uuid.UUID
) -> tuple[uuid.UUID, uuid.UUID, uuid.UUID, uuid.UUID]:
    """A version carrying one component, moved out of draft.

    Returns (org, project, version_id, material_id).
    """
    org = _org(owner_session, "A")
    project = _project(owner_session, org)
    material = _material(owner_session, org, actor)
    _, version = _formula(owner_session, org, project, actor)
    _component(owner_session, org, project, version, material)
    owner_session.execute(
        text(
            """
            UPDATE formulations.formula_versions
            SET status = 'approved', approved_by = :a, approved_at = now()
            WHERE id = :v
            """
        ),
        {"a": actor, "v": version},
    )
    owner_session.flush()
    return org, project, version, material


def test_a_component_cannot_be_added_to_a_frozen_version(
    owner_session: Session, actor: uuid.UUID, approved_version: tuple[uuid.UUID, ...]
) -> None:
    org, project, version, _ = approved_version
    other_material = _material(owner_session, org, actor)
    owner_session.flush()

    with pytest.raises(DBAPIError) as caught:
        _component(owner_session, org, project, version, other_material)

    assert "frozen" in str(caught.value.orig)


def test_a_component_of_a_frozen_version_cannot_be_edited(
    owner_session: Session, approved_version: tuple[uuid.UUID, ...]
) -> None:
    """The half that actually protects the composition.

    Freezing the version ROW while leaving its component rows writable
    would let an approved formula be changed without a single column of
    the version ever being touched -- and the audit trail would show
    nothing.
    """
    org, _, version, _ = approved_version

    with pytest.raises(DBAPIError) as caught:
        owner_session.execute(
            text(
                """
                UPDATE formulations.formula_components
                SET percentage = 99.0000
                WHERE formula_version_id = :v AND organization_id = :o
                """
            ),
            {"v": version, "o": org},
        )

    assert "frozen" in str(caught.value.orig)


def test_a_component_of_a_frozen_version_cannot_be_deleted(
    owner_session: Session, approved_version: tuple[uuid.UUID, ...]
) -> None:
    """DELETE is the case an INSERT/UPDATE-only guard would miss.

    A rule enforced on UPDATE only is already a recorded defect on this
    platform. Emptying an approved formula changes it just as completely
    as editing it.
    """
    org, _, version, _ = approved_version

    with pytest.raises(DBAPIError) as caught:
        owner_session.execute(
            text(
                """
                DELETE FROM formulations.formula_components
                WHERE formula_version_id = :v AND organization_id = :o
                """
            ),
            {"v": version, "o": org},
        )

    assert "frozen" in str(caught.value.orig)


def test_a_draft_version_is_a_workspace(owner_session: Session, actor: uuid.UUID) -> None:
    """The trigger must PERMIT what it is not there to stop.

    A guard that refuses everything passes every "it refuses" test and
    makes the product unusable. Verified in both directions, on purpose.
    """
    org = _org(owner_session, "A")
    project = _project(owner_session, org)
    material = _material(owner_session, org, actor)
    _, version = _formula(owner_session, org, project, actor)
    component = _component(owner_session, org, project, version, material)
    owner_session.flush()

    owner_session.execute(
        text("UPDATE formulations.formula_components SET percentage = 42.5 WHERE id = :c"),
        {"c": component},
    )
    owner_session.execute(
        text("DELETE FROM formulations.formula_components WHERE id = :c"), {"c": component}
    )
    remaining = owner_session.execute(
        text("SELECT count(*) FROM formulations.formula_components WHERE formula_version_id = :v"),
        {"v": version},
    ).scalar_one()
    assert remaining == 0


def test_a_formula_code_is_immutable_once_issued(owner_session: Session, actor: uuid.UUID) -> None:
    """Section 8, first line. Every component points at this identity."""
    org = _org(owner_session, "A")
    project = _project(owner_session, org)
    formula_id, _ = _formula(owner_session, org, project, actor)
    owner_session.flush()

    with pytest.raises(DBAPIError) as caught:
        owner_session.execute(
            text("UPDATE formulations.formulas SET formula_code = 'RENAMED' WHERE id = :f"),
            {"f": formula_id},
        )

    assert "immutable" in str(caught.value.orig)


def test_a_released_version_cannot_change_status(owner_session: Session, actor: uuid.UUID) -> None:
    """Nothing un-releases a master formula.

    A released version is what production records and field performance
    point at. Moving it back to draft would silently re-open a composition
    that physical product has already been made from.
    """
    org = _org(owner_session, "A")
    project = _project(owner_session, org)
    _, version = _formula(owner_session, org, project, actor)
    owner_session.execute(
        text(
            """
            UPDATE formulations.formula_versions
            SET status = 'released', approved_by = :a, approved_at = now()
            WHERE id = :v
            """
        ),
        {"a": actor, "v": version},
    )
    owner_session.flush()

    with pytest.raises(DBAPIError) as caught:
        owner_session.execute(
            text("UPDATE formulations.formula_versions SET status = 'draft' WHERE id = :v"),
            {"v": version},
        )

    assert "released" in str(caught.value.orig)


def test_the_observed_effect_of_a_frozen_version_stays_writable(
    owner_session: Session, approved_version: tuple[uuid.UUID, ...]
) -> None:
    """The one field section 8 requires to keep moving after freezing.

    Every version records an expected effect and, AFTER TESTING, an
    observed one. A trigger that froze this column too would make the
    digital thread one-way: the hypothesis preserved forever and the
    answer to it impossible to record.
    """
    _, _, version, _ = approved_version

    owner_session.execute(
        text(
            """
            UPDATE formulations.formula_versions
            SET observed_effect = 'density fell to 1.09 as predicted'
            WHERE id = :v
            """
        ),
        {"v": version},
    )
    stored = owner_session.execute(
        text("SELECT observed_effect FROM formulations.formula_versions WHERE id = :v"),
        {"v": version},
    ).scalar_one()
    assert stored == "density fell to 1.09 as predicted"


# ---------------------------------------------------------------------------
# Composition invariants
# ---------------------------------------------------------------------------


def test_one_line_per_material(owner_session: Session, actor: uuid.UUID) -> None:
    """Two lines for one material make the percentage ambiguous.

    The engine refuses to scale such a formula, because its result is
    keyed by material code and the two lines silently overwrite each
    other -- masses that sum to LESS than the batch. Refusing the state
    here means it cannot be stored in the first place.
    """
    org = _org(owner_session, "A")
    project = _project(owner_session, org)
    material = _material(owner_session, org, actor)
    _, version = _formula(owner_session, org, project, actor)
    _component(owner_session, org, project, version, material, "30.0")
    owner_session.flush()

    with pytest.raises(IntegrityError) as caught:
        _component(owner_session, org, project, version, material, "20.0")

    assert "formula_components_one_line_per_material" in str(caught.value.orig)


def test_two_children_of_one_parent_is_a_branch_and_is_permitted(
    owner_session: Session, actor: uuid.UUID
) -> None:
    """F004-A / F004-B. The plan requires branches to be expressible.

    A constraint that allowed only one revision per version would make a
    branch impossible, and would do it silently -- the second chemist
    would see a unique-violation about version numbers and conclude the
    system was broken rather than that branching was forbidden.
    """
    org = _org(owner_session, "A")
    project = _project(owner_session, org)
    formula_id, parent = _formula(owner_session, org, project, actor)
    owner_session.flush()

    for number in (2, 3):
        owner_session.execute(
            text(
                """
                INSERT INTO formulations.formula_versions
                    (organization_id, project_id, formula_id, version_number, version_code,
                     parent_version_id, status, change_reason, technical_hypothesis, created_by)
                VALUES (:o, :p, :f, :n, :vc, :parent, 'draft',
                        'branch trial', 'two routes to the same target', :a)
                """
            ),
            {
                "o": org,
                "p": project,
                "f": formula_id,
                "n": number,
                "vc": f"BR-{uuid.uuid4().hex[:6]}",
                "parent": parent,
                "a": actor,
            },
        )

    children = owner_session.execute(
        text(
            """
            SELECT count(*) FROM formulations.formula_versions
            WHERE parent_version_id = :parent
            """
        ),
        {"parent": parent},
    ).scalar_one()
    assert children == 2


def test_a_revision_must_say_why_it_exists(owner_session: Session, actor: uuid.UUID) -> None:
    """Section 8 requires change_reason and technical_hypothesis on every
    version after the first.

    Without the constraint, a genealogy records what changed and never
    why -- which is the half a failure investigation actually needs.
    """
    org = _org(owner_session, "A")
    project = _project(owner_session, org)
    formula_id, parent = _formula(owner_session, org, project, actor)
    owner_session.flush()

    with pytest.raises(IntegrityError) as caught:
        owner_session.execute(
            text(
                """
                INSERT INTO formulations.formula_versions
                    (organization_id, project_id, formula_id, version_number, version_code,
                     parent_version_id, status, created_by)
                VALUES (:o, :p, :f, 2, :vc, :parent, 'draft', :a)
                """
            ),
            {
                "o": org,
                "p": project,
                "f": formula_id,
                "vc": f"NR-{uuid.uuid4().hex[:6]}",
                "parent": parent,
                "a": actor,
            },
        )

    assert "formula_versions_revision_is_explained" in str(caught.value.orig)


def test_an_approved_version_must_name_its_approver(
    owner_session: Session, actor: uuid.UUID
) -> None:
    """Status and evidence cannot disagree.

    A version reading `approved` with no `approved_by` is an
    unattributable approval, and an approval nobody signed is the one
    record a governance audit cannot accept.
    """
    org = _org(owner_session, "A")
    project = _project(owner_session, org)
    _, version = _formula(owner_session, org, project, actor)
    owner_session.flush()

    with pytest.raises(IntegrityError) as caught:
        owner_session.execute(
            text("UPDATE formulations.formula_versions SET status = 'approved' WHERE id = :v"),
            {"v": version},
        )

    assert "approved_states_have_an_approver" in str(caught.value.orig)


def test_a_restricted_material_must_state_why(owner_session: Session, actor: uuid.UUID) -> None:
    """A restriction hard-blocks every formula using the material.

    The chemist whose submission it blocks cannot tell a regulatory limit
    from a supply failure from a safety finding without the reason, and
    the block cannot be waived at submission.
    """
    org = _org(owner_session, "A")
    owner_session.flush()

    with pytest.raises(IntegrityError) as caught:
        owner_session.execute(
            text(
                """
                INSERT INTO materials.materials
                    (organization_id, material_code, name, category, status, created_by)
                VALUES (:o, :c, 'Restricted thing', 'Solvent', 'restricted', :a)
                """
            ),
            {"o": org, "c": f"RM-{uuid.uuid4().hex[:8]}", "a": actor},
        )

    assert "materials_restriction_has_a_reason" in str(caught.value.orig)


def test_at_most_one_primary_supplier_per_material(
    owner_session: Session, actor: uuid.UUID
) -> None:
    """Enforced across rows, in the database.

    "The form only lets you tick one" is not a mechanism: two concurrent
    requests each pass that check and both commit.
    """
    org = _org(owner_session, "A")
    material = _material(owner_session, org, actor)
    suppliers = [
        owner_session.execute(
            text(
                """
                INSERT INTO materials.suppliers
                    (organization_id, supplier_code, name, created_by)
                VALUES (:o, :c, 'Fixture supplier', :a) RETURNING id
                """
            ),
            {"o": org, "c": f"SUP-{uuid.uuid4().hex[:6]}", "a": actor},
        ).scalar_one()
        for _ in range(2)
    ]
    owner_session.flush()

    for supplier in suppliers[:1]:
        owner_session.execute(
            text(
                """
                INSERT INTO materials.material_suppliers
                    (organization_id, material_id, supplier_id, is_primary)
                VALUES (:o, :m, :s, TRUE)
                """
            ),
            {"o": org, "m": material, "s": supplier},
        )
    owner_session.flush()

    with pytest.raises(IntegrityError) as caught:
        owner_session.execute(
            text(
                """
                INSERT INTO materials.material_suppliers
                    (organization_id, material_id, supplier_id, is_primary)
                VALUES (:o, :m, :s, TRUE)
                """
            ),
            {"o": org, "m": material, "s": suppliers[1]},
        )

    assert "material_suppliers_one_primary_idx" in str(caught.value.orig)


# ---------------------------------------------------------------------------
# RLS -- on app_session, because the owner is exempt
# ---------------------------------------------------------------------------


@pytest.fixture
def committed_scope(owner_session: Session) -> Iterator[dict[str, uuid.UUID]]:
    """Two organizations and a restricted project, COMMITTED.

    Committed for the reason `seeded_projects` documents: `app_session` is
    a different connection, so uncommitted rows are invisible to it and
    the test would fail claiming RLS hid something that was never readable
    by anybody. That looks exactly like a policy bug and is not one.
    """
    suffix = uuid.uuid4().hex[:8]
    org_a = _org(owner_session, f"RA{suffix}")
    org_b = _org(owner_session, f"RB{suffix}")
    user = owner_session.execute(
        text(
            """
            INSERT INTO core.users (keycloak_sub, email, display_name)
            VALUES (:s, :e, 'Outsider') RETURNING id
            """
        ),
        {"s": str(uuid.uuid4()), "e": f"outsider-{suffix}@example.test"},
    ).scalar_one()

    material_a = _material(owner_session, org_a, user, code=f"RM-A-{suffix}")
    material_b = _material(owner_session, org_b, user, code=f"RM-B-{suffix}")

    restricted = _project(owner_session, org_a, confidentiality="restricted")
    _, restricted_version = _formula(owner_session, org_a, restricted, user)
    normal = _project(owner_session, org_a, confidentiality="normal")
    _, normal_version = _formula(owner_session, org_a, normal, user)

    owner_session.commit()

    yield {
        "org_a": org_a,
        "org_b": org_b,
        "user": user,
        "material_a": material_a,
        "material_b": material_b,
        "restricted_version": restricted_version,
        "normal_version": normal_version,
    }

    owner_session.begin()
    for org in (org_a, org_b):
        owner_session.execute(
            text("DELETE FROM formulations.formula_versions WHERE organization_id = :o"),
            {"o": org},
        )
        owner_session.execute(
            text("DELETE FROM formulations.formulas WHERE organization_id = :o"), {"o": org}
        )
        owner_session.execute(
            text("DELETE FROM materials.materials WHERE organization_id = :o"), {"o": org}
        )
        owner_session.execute(
            text("DELETE FROM projects.projects WHERE organization_id = :o"), {"o": org}
        )
    owner_session.execute(text("DELETE FROM core.users WHERE id = :u"), {"u": user})
    for org in (org_a, org_b):
        owner_session.execute(text("DELETE FROM core.organizations WHERE id = :o"), {"o": org})
    owner_session.commit()


def test_another_organizations_materials_are_invisible(
    app_session: Session, committed_scope: dict[str, uuid.UUID]
) -> None:
    """The material library is org-wide reference data -- within one org.

    Materials are deliberately NOT project-scoped: a chemist on any
    project must see the whole library or they cannot formulate.
    Confidentiality lives on the formulas that USE a material. That makes
    the organization boundary the only thing protecting a competitor's raw
    material list, so it is asserted from the runtime role.
    """
    app_session.execute(
        text("SELECT set_config('app.current_org', :o, true)"),
        {"o": str(committed_scope["org_a"])},
    )
    visible = {
        row[0] for row in app_session.execute(text("SELECT id FROM materials.materials")).all()
    }

    assert committed_scope["material_a"] in visible
    assert committed_scope["material_b"] not in visible, (
        "a material belonging to another organization was readable by the runtime role"
    )


def test_a_restricted_projects_formula_is_invisible_to_a_non_member(
    app_session: Session, committed_scope: dict[str, uuid.UUID]
) -> None:
    """The composition of a restricted project's formulation is the single
    most sensitive record in this product.

    Organization isolation alone would leave it readable by any colleague.
    The policy tests project membership, and this asserts it from a
    session that is scoped to the organization and belongs to no project.
    """
    app_session.execute(
        text("SELECT set_config('app.current_org', :o, true)"),
        {"o": str(committed_scope["org_a"])},
    )
    app_session.execute(
        text("SELECT set_config('app.current_user_id', :u, true)"),
        {"u": str(committed_scope["user"])},
    )
    visible = {
        row[0]
        for row in app_session.execute(text("SELECT id FROM formulations.formula_versions")).all()
    }

    assert committed_scope["normal_version"] in visible, (
        "a normal project's formula must be visible to colleagues in the same organization"
    )
    assert committed_scope["restricted_version"] not in visible, (
        "a restricted project's formula version was readable by a non-member"
    )


def test_the_percentage_column_is_numeric_not_float(owner_session: Session) -> None:
    """CLAUDE.md section 5: NUMERIC, never float, for a controlled quantity.

    Checked in the catalogue rather than trusted from the migration text.
    `double precision` here would silently defeat the entire `Decimal`
    discipline the engine enforces at its own boundary -- 34.75 survives
    the round trip and 0.1 does not.
    """
    types = dict(
        owner_session.execute(
            text(
                """
                SELECT column_name, data_type
                FROM information_schema.columns
                WHERE table_schema = 'formulations' AND table_name = 'formula_components'
                  AND column_name IN ('percentage')
                """
            )
        ).all()
    )
    assert types["percentage"] == "numeric"


def test_the_engine_accepts_what_the_database_returns(
    owner_session: Session, actor: uuid.UUID
) -> None:
    """The boundary both sides claim to protect, exercised once for real.

    The engine REFUSES a Python float. The columns are NUMERIC so psycopg
    returns `Decimal`. Both statements are true separately; this is the
    test that they are true together, because a column quietly changed to
    `double precision` would make every calculation raise a TypeError at
    runtime while every unit test of the engine still passed.
    """
    from app.calculations.formulation import Component, total_percentage

    org = _org(owner_session, "A")
    project = _project(owner_session, org)
    material = _material(owner_session, org, actor)
    _, version = _formula(owner_session, org, project, actor)
    _component(owner_session, org, project, version, material, "38.0000")
    owner_session.flush()

    stored = owner_session.execute(
        text(
            """
            SELECT c.percentage, m.material_code, m.role
            FROM formulations.formula_components c
            JOIN materials.materials m ON m.id = c.material_id
            WHERE c.formula_version_id = :v
            """
        ),
        {"v": version},
    ).one()

    assert isinstance(stored[0], Decimal)
    component = Component(material_code=stored[1], percentage=stored[0], role=stored[2])
    assert total_percentage([component]) == Decimal("38.0000")
