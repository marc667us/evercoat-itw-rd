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

import pathlib
import uuid
from collections.abc import Iterator

import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.domains.formulations.service import FormulaInput, FormulaNotFoundError, create_formula
from app.domains.materials.service import (
    ALLOWED_TRANSITIONS,
    MATERIAL_STATUSES,
    TRANSITION_PERMISSION,
    MaterialInput,
    MaterialInvalidError,
    MaterialPermissionError,
    create_material,
    set_material_status,
)

# Every permission the matrix mentions. Tests that are asserting a
# TRANSITION rule rather than an authorization rule pass this, so that a
# refusal can only ever be the transition rule refusing.
ALL_MATERIAL_PERMISSIONS = frozenset(TRANSITION_PERMISSION.values())

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
            "INSERT INTO core.organization_members (organization_id, user_id, status, email,"
            " display_name) SELECT :o, :u, 'active', u.email, u.display_name FROM core.users u"
            " WHERE u.id = :u"
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
            held_permissions=ALL_MATERIAL_PERMISSIONS,
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
            held_permissions=ALL_MATERIAL_PERMISSIONS,
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
        held_permissions=ALL_MATERIAL_PERMISSIONS,
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
def restricted_project(
    owner_session: Session, app_session: Session
) -> Iterator[dict[str, uuid.UUID]]:
    """A restricted project and an organization member who is NOT on it.

    Committed, because the assertion runs on `app_session`, which is a
    different connection and cannot see uncommitted rows -- the test would
    otherwise fail claiming the fix worked when the project was simply
    never there.

    🔴 IT ALSO TAKES `app_session`, AND ROLLS IT BACK BEFORE CLEANING UP.
    THIS IS WHY CI HUNG.

    pytest tears fixtures down in reverse order of setup, so this
    fixture's teardown runs while `app_session` still holds its open
    transaction. A test that successfully creates a formula leaves that
    session holding a row lock on `projects.projects` (an FK reference
    takes one), and the teardown's `DELETE FROM projects.projects` then
    waits for a transaction that will not be rolled back until AFTER this
    teardown finishes. Neither side can move.

    The first CI run on this change sat in the Tests step until it was
    cancelled -- not failing, not passing, just stopped, which is the
    worst outcome a suite can produce because it reports nothing at all.

    Two changes, and both are deliberate: the session is rolled back here
    so the locks are gone before the deletes start, and a `lock_timeout`
    is set so that if this ever happens again the suite FAILS IN FIVE
    SECONDS with a lock error instead of hanging until the job's six-hour
    ceiling.
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
            "INSERT INTO core.organization_members (organization_id, user_id, status, email,"
            " display_name) SELECT :o, :u, 'active', u.email, u.display_name FROM core.users u"
            " WHERE u.id = :u"
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

    # Release the runtime session's locks BEFORE deleting anything.
    app_session.rollback()

    owner_session.begin()
    # Fail fast rather than hang if a lock is still held: a suite
    # that stops reports nothing, and nothing is worse than red.
    owner_session.execute(text("SET LOCAL lock_timeout = '5s'"))
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


# ---------------------------------------------------------------------------
# Supervisor finding -- a QA restriction could be lifted by anyone
# ---------------------------------------------------------------------------


def test_lifting_a_restriction_needs_the_restricting_authority(
    owner_session: Session, org_and_actor: tuple[uuid.UUID, uuid.UUID]
) -> None:
    """The authority that imposes a block is the only one that may lift it.

    The first transition table was keyed by DESTINATION, and `development`
    was reachable with `material.edit`. So a Chemist or a Procurement
    Specialist could take a material QA had restricted for a safety
    finding, move it back to `development` -- which also clears
    `restriction_reason` -- and unblock every formula that used it. QA,
    holding `material.restrict` and not `material.edit`, could not even
    undo that. Raised by the Supervisor.
    """
    org, actor = org_and_actor
    material_id = create_material(
        owner_session,
        organization_id=org,
        actor_id=actor,
        spec=MaterialInput(
            material_code=f"RM-{uuid.uuid4().hex[:6]}", name="Hazard resin", category="Resin"
        ),
    )
    set_material_status(
        owner_session,
        material_id=material_id,
        organization_id=org,
        actor_id=actor,
        held_permissions=frozenset({"material.restrict"}),
        status="restricted",
        restriction_reason="isocyanate content above the declared limit",
        reason="safety finding",
    )

    # The editor's authority is not enough.
    with pytest.raises(MaterialPermissionError):
        set_material_status(
            owner_session,
            material_id=material_id,
            organization_id=org,
            actor_id=actor,
            held_permissions=frozenset({"material.edit", "material.approve_lab"}),
            status="development",
            reason="I would like my formula to work again",
        )

    still = owner_session.execute(
        text("SELECT status, restriction_reason FROM materials.materials WHERE id = :m"),
        {"m": material_id},
    ).one()
    assert still[0] == "restricted"
    assert still[1] is not None, "the restriction reason was cleared by a refused transition"

    # The restricting authority can.
    set_material_status(
        owner_session,
        material_id=material_id,
        organization_id=org,
        actor_id=actor,
        held_permissions=frozenset({"material.restrict"}),
        status="development",
        reason="re-evaluated; the lot was mislabelled",
    )
    lifted = owner_session.execute(
        text("SELECT status FROM materials.materials WHERE id = :m"), {"m": material_id}
    ).scalar_one()
    assert lifted == "development"


def test_every_edge_names_a_permission_that_exists(owner_session: Session) -> None:
    """A transition guarded by a permission nobody can hold is a dead edge.

    The same failure as `material.approve_production` having no holder,
    one layer up: the move would be legal, the permission real in the
    table and absent from the database, and every attempt would 403 with
    no way to tell that from a correct refusal.
    """
    seeded = {
        row[0] for row in owner_session.execute(text("SELECT code FROM core.permissions")).all()
    }
    missing = sorted(set(TRANSITION_PERMISSION.values()) - seeded)
    assert missing == [], f"transitions require permissions that do not exist: {missing}"


# ---------------------------------------------------------------------------
# Supervisor finding -- NO FORMULA COULD EVER BE SUBMITTED
# ---------------------------------------------------------------------------


def test_a_material_requiring_an_sds_blocks_submission_until_one_is_registered(
    owner_session: Session, org_and_actor: tuple[uuid.UUID, uuid.UUID]
) -> None:
    """The check must be satisfiable, or it is an outage with a nice name.

    `requires_sds` defaults to TRUE and `_safety_checks` blocks submission
    when no SDS row exists. `materials.material_documents` had NO WRITER
    anywhere in the codebase -- one read, in that safety check, and nothing
    else -- so every formula built through the API was unsubmittable
    forever. Raised by the Supervisor.

    Asserted in both directions in one test on purpose: the block must
    fire, AND registering the document must clear it. Either half alone
    would have passed against the broken version.
    """
    import tempfile

    from app.core.malware import AlwaysCleanScanner
    from app.core.object_storage import FilesystemObjectStore
    from app.domains.materials.service import DocumentInput, store_document

    org, actor = org_and_actor
    material_id = create_material(
        owner_session,
        organization_id=org,
        actor_id=actor,
        spec=MaterialInput(
            material_code=f"RM-{uuid.uuid4().hex[:6]}",
            name="Styrene-bearing resin",
            category="Resin",
            requires_sds=True,
        ),
    )

    def sds_rows() -> int:
        # 🔴 COUNTS `usable_documents`, NOT `material_documents`.
        #
        # This is the difference I41 turned on. The old version counted raw
        # rows, which is exactly what the submission gate did -- so the test
        # agreed with the defect and could never have caught it. A row now has
        # to carry bytes the store actually wrote and a clean scan before it
        # counts as hazard documentation.
        return owner_session.execute(
            text(
                """
                SELECT count(*) FROM materials.usable_documents
                WHERE material_id = :m AND document_type = 'SDS'
                """
            ),
            {"m": material_id},
        ).scalar_one()

    assert sds_rows() == 0

    store_document(
        owner_session,
        material_id=material_id,
        organization_id=org,
        actor_id=actor,
        spec=DocumentInput(document_type="SDS", title="SDS rev 4"),
        data=b"%PDF-1.4\n% synthetic safety data sheet for a service-rule test\n",
        filename="SDS rev 4.pdf",
        store=FilesystemObjectStore(pathlib.Path(tempfile.gettempdir()) / "evercoat-test-docs"),
        scanner=AlwaysCleanScanner(),
    )

    assert sds_rows() == 1, "the document register still has no writer"

    # 🔴 AND THE HALF THAT DID NOT EXIST BEFORE: a row without bytes must NOT
    # count. Without this, the test above passes against a `usable_documents`
    # definition that simply selects everything -- which is the state the
    # application was in for six slices.
    owner_session.execute(
        text(
            """
            INSERT INTO materials.material_documents
                (organization_id, material_id, document_type, title, storage_key,
                 uploaded_by, status, scan_status)
            VALUES (:o, :m, 'SDS', 'A claim with no file', :k, :u,
                    'legacy_unverified', 'not_scanned')
            """
        ),
        {"o": org, "m": material_id, "k": f"sds/{uuid.uuid4().hex}.pdf", "u": actor},
    )
    owner_session.flush()

    assert sds_rows() == 1, (
        "a document row carrying no bytes was counted as hazard documentation. "
        "That is I41: the safety gate counting rows rather than files."
    )
