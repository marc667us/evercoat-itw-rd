"""The three defects Codex found in the Slice 3 services, each with a test.

A fix with no test is a fix that comes back. All three of these were
authorization defects that every type check, lint and unit test passed
straight over, so the only thing that can hold them closed is a test that
exercises the real rule against a real database.

WHICH SESSION. The formula-creation test uses `app_session`: it is an
authorization assertion, and `owner_session` is exempt from RLS while
`relforcerowsecurity` is FALSE, so the same test written on the owner
would pass whether or not the fix worked. The transition tests use
`owner_session`, because a status transition is a service rule rather than
a row-visibility one and the owner is subject to it identically.
"""

from __future__ import annotations

import uuid
from collections.abc import Iterator

import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.domains.formulations.service import FormulaInput, FormulaNotFoundError, create_formula
from app.domains.materials.service import (
    ALLOWED_TRANSITIONS,
    MATERIAL_STATUSES,
    MaterialInput,
    MaterialInvalidError,
    create_material,
    set_material_status,
)

# ---------------------------------------------------------------------------
# The matrix itself -- no database needed
# ---------------------------------------------------------------------------


def test_the_transition_matrix_covers_every_status() -> None:
    """Every status must appear as a source, and every target must exist.

    A status missing from the matrix keys would raise `KeyError` inside the
    error path -- the one branch nobody exercises by hand -- and a target
    that is not a real status would be a transition nothing could ever
    complete.
    """
    assert set(ALLOWED_TRANSITIONS) == set(MATERIAL_STATUSES)
    for source, targets in ALLOWED_TRANSITIONS.items():
        unknown = targets - set(MATERIAL_STATUSES)
        assert not unknown, f"{source} may move to statuses that do not exist: {unknown}"
        assert source not in targets, f"{source} lists itself as a transition"


def test_production_approval_cannot_be_reached_from_development() -> None:
    """The matrix says what the permissions alone did not.

    QA holds BOTH `material.restrict` and, since migration 016,
    `material.approve_production`. Permission alone therefore let QA take a
    brand-new material straight to `preferred`, skipping `approved` and the
    Lead who holds `material.approve_lab` entirely. Asserted here as a
    property of the matrix so the rule cannot be relaxed silently.
    """
    assert "preferred" not in ALLOWED_TRANSITIONS["development"]
    assert "preferred" in ALLOWED_TRANSITIONS["approved"]


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def org_and_actor(owner_session: Session) -> tuple[uuid.UUID, uuid.UUID]:
    suffix = uuid.uuid4().hex[:8]
    org = owner_session.execute(
        text("INSERT INTO core.organizations (code, name) VALUES (:c, :n) RETURNING id"),
        {"c": f"SR-{suffix}", "n": "Service Rules Org"},
    ).scalar_one()
    user = owner_session.execute(
        text(
            """
            INSERT INTO core.users (keycloak_sub, email, display_name)
            VALUES (:s, :e, 'Service Rules Actor') RETURNING id
            """
        ),
        {"s": str(uuid.uuid4()), "e": f"sr-{suffix}@example.test"},
    ).scalar_one()
    owner_session.execute(
        text(
            """
            INSERT INTO core.organization_members (organization_id, user_id, status)
            VALUES (:o, :u, 'active')
            """
        ),
        {"o": org, "u": user},
    )
    owner_session.flush()
    return org, user


# ---------------------------------------------------------------------------
# Codex finding 3 -- the status transition matrix
# ---------------------------------------------------------------------------


def test_a_development_material_cannot_be_promoted_straight_to_preferred(
    owner_session: Session, org_and_actor: tuple[uuid.UUID, uuid.UUID]
) -> None:
    org, actor = org_and_actor
    material_id = create_material(
        owner_session,
        organization_id=org,
        actor_id=actor,
        spec=MaterialInput(
            material_code=f"RM-{uuid.uuid4().hex[:6]}", name="New resin", category="Resin"
        ),
    )

    with pytest.raises(MaterialInvalidError) as caught:
        set_material_status(
            owner_session,
            material_id=material_id,
            organization_id=org,
            actor_id=actor,
            status="preferred",
            reason="skipping the laboratory approval",
        )

    assert "cannot move straight to" in str(caught.value)

    # And the material did not move. A refusal that still wrote the row
    # would be the worst of both.
    still = owner_session.execute(
        text("SELECT status FROM materials.materials WHERE id = :m"), {"m": material_id}
    ).scalar_one()
    assert still == "development"


def test_the_legal_promotion_path_works_end_to_end(
    owner_session: Session, org_and_actor: tuple[uuid.UUID, uuid.UUID]
) -> None:
    """The guard must PERMIT what it is not there to stop.

    A matrix that refused everything would pass the test above and make
    the product unusable, so the happy path is asserted in the same file.
    """
    org, actor = org_and_actor
    material_id = create_material(
        owner_session,
        organization_id=org,
        actor_id=actor,
        spec=MaterialInput(
            material_code=f"RM-{uuid.uuid4().hex[:6]}", name="Good resin", category="Resin"
        ),
    )

    for target in ("approved", "preferred"):
        set_material_status(
            owner_session,
            material_id=material_id,
            organization_id=org,
            actor_id=actor,
            status=target,
            reason=f"promoted to {target}",
        )

    final = owner_session.execute(
        text("SELECT status FROM materials.materials WHERE id = :m"), {"m": material_id}
    ).scalar_one()
    assert final == "preferred"


def test_restricting_a_material_is_reachable_from_any_status(
    owner_session: Session, org_and_actor: tuple[uuid.UUID, uuid.UUID]
) -> None:
    """A safety finding does not wait for a convenient state.

    The matrix exists to stop a promotion skipping a stage; it must never
    stop a material being taken OUT of circulation.
    """
    org, actor = org_and_actor
    material_id = create_material(
        owner_session,
        organization_id=org,
        actor_id=actor,
        spec=MaterialInput(
            material_code=f"RM-{uuid.uuid4().hex[:6]}", name="Suspect resin", category="Resin"
        ),
    )
    set_material_status(
        owner_session,
        material_id=material_id,
        organization_id=org,
        actor_id=actor,
        status="restricted",
        restriction_reason="supplier CoA does not match the incoming lot",
        reason="restricted pending investigation",
    )
    row = owner_session.execute(
        text("SELECT status, restriction_reason FROM materials.materials WHERE id = :m"),
        {"m": material_id},
    ).one()
    assert row[0] == "restricted"
    assert row[1] is not None


# ---------------------------------------------------------------------------
# Codex finding 1 -- a non-member could WRITE into a restricted project
# ---------------------------------------------------------------------------


@pytest.fixture
def restricted_project(owner_session: Session) -> Iterator[dict[str, uuid.UUID]]:
    """A restricted project and an organization member who is NOT on it.

    Committed, because the assertion runs on `app_session`, which is a
    different connection and cannot see uncommitted rows -- the test would
    otherwise fail claiming the fix worked when the project was simply
    never there.
    """
    suffix = uuid.uuid4().hex[:8]
    org = owner_session.execute(
        text("INSERT INTO core.organizations (code, name) VALUES (:c, :n) RETURNING id"),
        {"c": f"RP-{suffix}", "n": "Restricted Project Org"},
    ).scalar_one()
    outsider = owner_session.execute(
        text(
            """
            INSERT INTO core.users (keycloak_sub, email, display_name)
            VALUES (:s, :e, 'Outsider') RETURNING id
            """
        ),
        {"s": str(uuid.uuid4()), "e": f"outsider-{suffix}@example.test"},
    ).scalar_one()
    owner_session.execute(
        text(
            """
            INSERT INTO core.organization_members (organization_id, user_id, status)
            VALUES (:o, :u, 'active')
            """
        ),
        {"o": org, "u": outsider},
    )
    restricted = owner_session.execute(
        text(
            """
            INSERT INTO projects.projects
                (organization_id, project_code, name, confidentiality)
            VALUES (:o, :c, 'Confidential work', 'restricted') RETURNING id
            """
        ),
        {"o": org, "c": f"RDP-R-{suffix}"},
    ).scalar_one()
    normal = owner_session.execute(
        text(
            """
            INSERT INTO projects.projects
                (organization_id, project_code, name, confidentiality)
            VALUES (:o, :c, 'Ordinary work', 'normal') RETURNING id
            """
        ),
        {"o": org, "c": f"RDP-N-{suffix}"},
    ).scalar_one()
    owner_session.commit()

    yield {"org": org, "outsider": outsider, "restricted": restricted, "normal": normal}

    owner_session.begin()
    owner_session.execute(
        text("DELETE FROM formulations.formula_versions WHERE organization_id = :o"), {"o": org}
    )
    owner_session.execute(
        text("DELETE FROM formulations.formulas WHERE organization_id = :o"), {"o": org}
    )
    owner_session.execute(
        text("DELETE FROM projects.projects WHERE organization_id = :o"), {"o": org}
    )
    owner_session.execute(
        text("DELETE FROM core.organization_members WHERE organization_id = :o"), {"o": org}
    )
    owner_session.execute(text("DELETE FROM core.users WHERE id = :u"), {"u": outsider})
    owner_session.execute(text("DELETE FROM core.organizations WHERE id = :o"), {"o": org})
    owner_session.commit()


def _scope(session: Session, org: uuid.UUID, user: uuid.UUID) -> None:
    session.execute(text("SELECT set_config('app.current_org', :o, true)"), {"o": str(org)})
    session.execute(text("SELECT set_config('app.current_user_id', :u, true)"), {"u": str(user)})


def test_a_non_member_cannot_create_a_formula_in_a_restricted_project(
    app_session: Session, restricted_project: dict[str, uuid.UUID]
) -> None:
    """The defect Codex found, asserted from the runtime role.

    RLS could not stop this. Migration 005 deliberately made the
    project-scoped WITH CHECK organization-only, because requiring
    membership in order to WRITE makes the first row of a restricted
    project impossible to create -- so an INSERT naming a restricted
    project SUCCEEDED for a non-member and simply became invisible to
    them afterwards. Invisible is not refused: the row landed in another
    team's confidential project.
    """
    _scope(app_session, restricted_project["org"], restricted_project["outsider"])

    with pytest.raises(FormulaNotFoundError):
        create_formula(
            app_session,
            project_id=restricted_project["restricted"],
            organization_id=restricted_project["org"],
            actor_id=restricted_project["outsider"],
            spec=FormulaInput(formula_code=f"FRM-{uuid.uuid4().hex[:5]}", name="Intruder"),
        )

    written = app_session.execute(
        text(
            """
            SELECT count(*) FROM formulations.formulas
            WHERE project_id = :p
            """
        ),
        {"p": restricted_project["restricted"]},
    ).scalar_one()
    assert written == 0, "a formula was written into a restricted project by a non-member"


def test_a_colleague_can_still_create_a_formula_in_a_normal_project(
    app_session: Session, restricted_project: dict[str, uuid.UUID]
) -> None:
    """Verified in both directions.

    A guarded INSERT that refused everything would pass the test above and
    make the formulation workspace unusable for every ordinary project --
    which is the majority of them.
    """
    _scope(app_session, restricted_project["org"], restricted_project["outsider"])

    result = create_formula(
        app_session,
        project_id=restricted_project["normal"],
        organization_id=restricted_project["org"],
        actor_id=restricted_project["outsider"],
        spec=FormulaInput(formula_code=f"FRM-{uuid.uuid4().hex[:5]}", name="Ordinary work"),
    )
    assert result["version_code"].endswith("-V001")
