"""Requirements: structure, immutability, and the Verification Matrix.

The rules under test are the ones that make automatic test evaluation
possible and keep it honest afterwards. An approved requirement that can
be edited in place turns every existing test result into a claim about a
criterion that no longer exists.
"""

from __future__ import annotations

import uuid
from decimal import Decimal

import pytest
from sqlalchemy import text

from app.domains.requirements.service import (
    RequirementImmutableError,
    RequirementInput,
    RequirementInvalidError,
    approve_requirement,
    create_requirement,
    revise_requirement,
    verification_matrix,
)

pytestmark = pytest.mark.db


@pytest.fixture
def req_project(owner_session):
    suffix = uuid.uuid4().hex[:8]
    org_id = owner_session.execute(
        text("INSERT INTO core.organizations (code,name) VALUES (:c,:n) RETURNING id"),
        {"c": f"REQ-{suffix}", "n": "Requirements Test Org"},
    ).scalar_one()
    actor_id = owner_session.execute(
        text(
            "INSERT INTO core.users (keycloak_sub,email,display_name) "
            "VALUES (:s,:e,'Req Actor') RETURNING id"
        ),
        {"s": f"req-{suffix}", "e": f"req-{suffix}@example.test"},
    ).scalar_one()
    project_id = owner_session.execute(
        text(
            "INSERT INTO projects.projects (organization_id,project_code,name,"
            "confidentiality) VALUES (:o,:c,'Req Project','normal') RETURNING id"
        ),
        {"o": org_id, "c": f"RDP-R-{suffix}"},
    ).scalar_one()
    owner_session.commit()

    yield {"org_id": org_id, "project_id": project_id, "actor_id": actor_id}

    owner_session.rollback()
    owner_session.execute(
        text("DELETE FROM projects.requirements WHERE organization_id=:o"), {"o": org_id}
    )
    owner_session.execute(
        text("DELETE FROM projects.projects WHERE organization_id=:o"), {"o": org_id}
    )
    owner_session.execute(text("DELETE FROM core.users WHERE id=:u"), {"u": actor_id})
    owner_session.execute(text("DELETE FROM core.organizations WHERE id=:o"), {"o": org_id})
    owner_session.commit()


def _adhesion(**overrides) -> RequirementInput:
    base = {
        "requirement_code": "REQ-ADH-001",
        "name": "Adhesion",
        "minimum_value": Decimal("6.0"),
        "target_value": Decimal("7.0"),
        "canonical_unit": "MPa",
        "criticality": "critical",
    }
    base.update(overrides)
    return RequirementInput(**base)


def _create(session, ctx, spec=None):
    return create_requirement(
        session,
        project_id=ctx["project_id"],
        organization_id=ctx["org_id"],
        actor_id=ctx["actor_id"],
        spec=spec or _adhesion(),
    )


# ---------------------------------------------------------------------------
# Structure
# ---------------------------------------------------------------------------


def test_numeric_requirement_without_a_unit_is_refused(owner_session, req_project):
    """'adhesion >= 6' is ambiguous between MPa and N/mm² by 1000x."""
    with pytest.raises(RequirementInvalidError, match="needs a unit"):
        _create(owner_session, req_project, _adhesion(canonical_unit=None))


def test_unsatisfiable_bounds_are_refused(owner_session, req_project):
    """min > max can never be met, and nobody notices until a test fails."""
    with pytest.raises(RequirementInvalidError, match="unsatisfiable"):
        _create(
            owner_session,
            req_project,
            _adhesion(
                minimum_value=Decimal("9.0"), maximum_value=Decimal("6.0"), target_value=None
            ),
        )


def test_target_outside_bounds_is_refused(owner_session, req_project):
    with pytest.raises(RequirementInvalidError, match="below minimum"):
        _create(owner_session, req_project, _adhesion(target_value=Decimal("5.0")))


def test_unreachable_warning_threshold_is_refused(owner_session, req_project):
    """A threshold outside the acceptance band can never fire.

    Worse than not setting one, because it reads as configured — the
    PASS WITH LOW MARGIN rule would silently never apply.
    """
    with pytest.raises(RequirementInvalidError, match="could never fire"):
        _create(owner_session, req_project, _adhesion(warning_threshold=Decimal("3.0")))


def test_numeric_precision_survives_the_round_trip(owner_session, req_project):
    """NUMERIC, not float.

    6.0 stored as a float and compared against a measured 5.9999999 is a
    false failure — and in this system a false failure opens a failure
    investigation.
    """
    _create(owner_session, req_project, _adhesion(minimum_value=Decimal("6.000001")))
    stored = owner_session.execute(
        text(
            "SELECT minimum_value FROM projects.requirements "
            "WHERE requirement_code = 'REQ-ADH-001' AND project_id = :p"
        ),
        {"p": req_project["project_id"]},
    ).scalar_one()
    assert stored == Decimal("6.000001")
    assert isinstance(stored, Decimal)


# ---------------------------------------------------------------------------
# Immutability
# ---------------------------------------------------------------------------


def test_approved_requirement_cannot_be_approved_twice(owner_session, req_project):
    rid = _create(owner_session, req_project)
    approve_requirement(
        owner_session,
        requirement_id=rid,
        organization_id=req_project["org_id"],
        actor_id=req_project["actor_id"],
    )
    with pytest.raises(RequirementImmutableError, match="already approved"):
        approve_requirement(
            owner_session,
            requirement_id=rid,
            organization_id=req_project["org_id"],
            actor_id=req_project["actor_id"],
        )


def test_revision_supersedes_rather_than_edits(owner_session, req_project):
    """The original must survive intact.

    Editing an approved requirement in place would retroactively change
    what every existing test was measured against: a result recorded as
    passing 'adhesion >= 6.0' would silently become a result against
    '>= 8.0', and the pass would be a lie.
    """
    rid = _create(owner_session, req_project)
    approve_requirement(
        owner_session,
        requirement_id=rid,
        organization_id=req_project["org_id"],
        actor_id=req_project["actor_id"],
    )

    new_id = revise_requirement(
        owner_session,
        requirement_id=rid,
        organization_id=req_project["org_id"],
        actor_id=req_project["actor_id"],
        spec=_adhesion(minimum_value=Decimal("8.0"), target_value=Decimal("9.0")),
        reason="customer raised the adhesion floor",
    )

    rows = (
        owner_session.execute(
            text(
                "SELECT id, revision, status, minimum_value FROM projects.requirements "
                "WHERE requirement_code = 'REQ-ADH-001' AND project_id = :p "
                "ORDER BY revision"
            ),
            {"p": req_project["project_id"]},
        )
        .mappings()
        .all()
    )

    assert len(rows) == 2, "the original revision must survive"
    assert rows[0]["revision"] == 1
    assert rows[0]["status"] == "superseded"
    assert rows[0]["minimum_value"] == Decimal("6.0"), (
        "the original acceptance criterion was mutated — every test "
        "recorded against it is now describing a criterion that never existed"
    )
    assert rows[1]["id"] == new_id
    assert rows[1]["revision"] == 2
    assert rows[1]["minimum_value"] == Decimal("8.0")


def test_revision_requires_a_reason(owner_session, req_project):
    rid = _create(owner_session, req_project)
    with pytest.raises(RequirementInvalidError, match="reason is required"):
        revise_requirement(
            owner_session,
            requirement_id=rid,
            organization_id=req_project["org_id"],
            actor_id=req_project["actor_id"],
            spec=_adhesion(),
            reason="",
        )


def test_revision_cannot_change_the_code(owner_session, req_project):
    """A different code is a different requirement, not a revision."""
    rid = _create(owner_session, req_project)
    with pytest.raises(RequirementInvalidError, match="different requirement"):
        revise_requirement(
            owner_session,
            requirement_id=rid,
            organization_id=req_project["org_id"],
            actor_id=req_project["actor_id"],
            spec=_adhesion(requirement_code="REQ-SAG-001"),
            reason="rename",
        )


# ---------------------------------------------------------------------------
# Verification Matrix
# ---------------------------------------------------------------------------


def test_matrix_orders_critical_requirements_first(owner_session, req_project):
    _create(
        owner_session,
        req_project,
        _adhesion(
            requirement_code="REQ-SND-001",
            name="Sanding",
            criticality="minor",
            minimum_value=None,
            target_value=Decimal("18"),
            canonical_unit="minutes",
        ),
    )
    _create(owner_session, req_project)  # critical adhesion

    matrix = verification_matrix(
        owner_session,
        project_id=req_project["project_id"],
        organization_id=req_project["org_id"],
    )
    assert [r["criticality"] for r in matrix["requirements"]] == ["critical", "minor"]


def test_matrix_states_that_tests_are_unavailable(owner_session, req_project):
    """The gap must be explicit.

    'No requirement has passed' and 'we cannot yet tell' are different
    claims, and a matrix that silently omits the distinction is one
    nobody notices is empty.
    """
    _create(owner_session, req_project)
    matrix = verification_matrix(
        owner_session,
        project_id=req_project["project_id"],
        organization_id=req_project["org_id"],
    )
    assert matrix["tests_available"] is False
    assert "Slice 5" in matrix["note"]
    assert all(r["verification_status"] == "not_verified" for r in matrix["requirements"])


def test_unverified_critical_requirements_block_validation(owner_session, req_project):
    """The operative column: what stops a validation candidate."""
    _create(owner_session, req_project)  # critical
    _create(
        owner_session,
        req_project,
        _adhesion(
            requirement_code="REQ-DEN-001",
            name="Density",
            criticality="major",
            minimum_value=Decimal("1.20"),
            maximum_value=Decimal("1.30"),
            target_value=Decimal("1.25"),
            canonical_unit="g/cm3",
        ),
    )

    matrix = verification_matrix(
        owner_session,
        project_id=req_project["project_id"],
        organization_id=req_project["org_id"],
    )
    blocking = [r for r in matrix["requirements"] if r["blocking_validation"]]
    assert len(blocking) == 1
    assert blocking[0]["criticality"] == "critical"
    assert matrix["summary"]["blocking_validation"] == 1


def test_matrix_excludes_superseded_revisions(owner_session, req_project):
    """A superseded requirement is history, not an outstanding obligation."""
    rid = _create(owner_session, req_project)
    revise_requirement(
        owner_session,
        requirement_id=rid,
        organization_id=req_project["org_id"],
        actor_id=req_project["actor_id"],
        spec=_adhesion(minimum_value=Decimal("8.0"), target_value=Decimal("9.0")),
        reason="raised",
    )
    matrix = verification_matrix(
        owner_session,
        project_id=req_project["project_id"],
        organization_id=req_project["org_id"],
    )
    assert matrix["summary"]["total"] == 1
    assert matrix["requirements"][0]["revision"] == 2


def test_acceptance_renders_readably(owner_session, req_project):
    _create(owner_session, req_project)  # >= 6.0 MPa
    _create(
        owner_session,
        req_project,
        _adhesion(
            requirement_code="REQ-DEN-001",
            name="Density",
            minimum_value=Decimal("1.20"),
            maximum_value=Decimal("1.30"),
            target_value=Decimal("1.25"),
            canonical_unit="g/cm3",
        ),
    )

    matrix = verification_matrix(
        owner_session,
        project_id=req_project["project_id"],
        organization_id=req_project["org_id"],
    )
    rendered = {r["requirement_code"]: r["acceptance"] for r in matrix["requirements"]}
    assert rendered["REQ-ADH-001"] == "≥ 6 MPa"
    assert rendered["REQ-DEN-001"] == "1.2–1.3 g/cm3"  # noqa: RUF001 - EN DASH is the range
