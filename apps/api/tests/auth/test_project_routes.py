"""Project, pipeline and requirement routes, over real HTTP.

Driven through `TestClient` against the real app rather than by calling
the handlers. Calling a handler proves the function works; it does not
prove the route is *wired* to its dependencies, and a route that forgot
its `Depends(require_project_member())` is precisely the defect worth
catching — it looks completely normal in review.

Every route gets two questions asked of it: does it refuse the wrong
permission, and does it refuse the right permission on the wrong project.
"""

from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

pytestmark = [pytest.mark.db]

ORG_HEADER = "X-Organization-Id"


@pytest.fixture
def client():
    from app.main import app

    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture
def lead_ctx(owner_session):
    """A lead who is a member of one project and not of another.

    The second project is the point: same organization, holds every
    permission, still must not reach it.
    """
    suffix = uuid.uuid4().hex[:8]
    sub = f"routes-{suffix}"

    org_id = owner_session.execute(
        text("INSERT INTO core.organizations (code,name) VALUES (:c,:n) RETURNING id"),
        {"c": f"RT-{suffix}", "n": "Route Test Org"},
    ).scalar_one()
    user_id = owner_session.execute(
        text(
            "INSERT INTO core.users (keycloak_sub,email,display_name) "
            "VALUES (:s,:e,'Route Lead') RETURNING id"
        ),
        {"s": sub, "e": f"{sub}@example.test"},
    ).scalar_one()
    member_id = owner_session.execute(
        text(
            "INSERT INTO core.organization_members (organization_id,user_id) "
            "VALUES (:o,:u) RETURNING id"
        ),
        {"o": org_id, "u": user_id},
    ).scalar_one()
    owner_session.execute(
        text(
            "INSERT INTO core.member_roles (member_id, role_id) "
            "SELECT :m, id FROM core.roles WHERE code='product_development_lead'"
        ),
        {"m": member_id},
    )

    for code, name, seq in [("REQUIREMENTS", "Requirements", 1), ("RESEARCH", "Research", 2)]:
        owner_session.execute(
            text(
                "INSERT INTO workflow.stage_definitions "
                "(organization_id,stage_code,name,sequence) VALUES (:o,:c,:n,:s)"
            ),
            {"o": org_id, "c": code, "n": name, "s": seq},
        )

    mine = owner_session.execute(
        text(
            "INSERT INTO projects.projects (organization_id,project_code,name,"
            "confidentiality) VALUES (:o,:c,'My Project','restricted') RETURNING id"
        ),
        {"o": org_id, "c": f"RDP-MINE-{suffix}"},
    ).scalar_one()
    theirs = owner_session.execute(
        text(
            "INSERT INTO projects.projects (organization_id,project_code,name,"
            "confidentiality) VALUES (:o,:c,'Other Project','restricted') RETURNING id"
        ),
        {"o": org_id, "c": f"RDP-THEIRS-{suffix}"},
    ).scalar_one()
    owner_session.execute(
        text(
            "INSERT INTO projects.project_members "
            "(organization_id,project_id,user_id,project_role) "
            "VALUES (:o,:p,:u,'lead')"
        ),
        {"o": org_id, "p": mine, "u": user_id},
    )
    owner_session.commit()

    yield {"org_id": org_id, "user_id": user_id, "sub": sub, "mine": mine, "theirs": theirs}

    owner_session.rollback()
    # stage_transitions is append-only by trigger -- the same design that
    # makes the history trustworthy also makes it undeletable. Tests must
    # disable the trigger explicitly (as owner) rather than discovering
    # the refusal in teardown, where it cascades: the raise poisons the
    # transaction and every subsequent delete fails, turning one expected
    # refusal into a wall of errors that look like real failures.
    owner_session.execute(
        text("ALTER TABLE workflow.stage_transitions DISABLE TRIGGER stage_transitions_immutable")
    )
    for stmt in [
        "DELETE FROM projects.requirements WHERE organization_id=:o",
        "DELETE FROM workflow.stage_transitions WHERE organization_id=:o",
        "DELETE FROM workflow.project_stages WHERE organization_id=:o",
        "DELETE FROM workflow.stage_definitions WHERE organization_id=:o",
        "DELETE FROM projects.project_members WHERE organization_id=:o",
        "DELETE FROM projects.projects WHERE organization_id=:o",
        "DELETE FROM core.member_roles WHERE member_id=:m",
        "DELETE FROM core.organization_members WHERE id=:m",
        "DELETE FROM core.organizations WHERE id=:o",
    ]:
        owner_session.execute(text(stmt), {"o": org_id, "m": member_id})
    owner_session.execute(text("DELETE FROM core.users WHERE id=:u"), {"u": user_id})
    owner_session.execute(
        text("ALTER TABLE workflow.stage_transitions ENABLE TRIGGER stage_transitions_immutable")
    )
    owner_session.commit()


@pytest.fixture
def auth(make_token, lead_ctx):
    return {
        "Authorization": f"Bearer {make_token(sub=lead_ctx['sub'])}",
        ORG_HEADER: str(lead_ctx["org_id"]),
    }


# ---------------------------------------------------------------------------
# Listing and visibility
# ---------------------------------------------------------------------------


def test_list_shows_only_projects_the_caller_may_see(client, auth, lead_ctx):
    """RLS filters the list; there is no WHERE clause doing it.

    The restricted project the lead is not a member of must not appear,
    even though they hold project.view and are in the same organization.
    """
    r = client.get("/api/projects", headers=auth)
    assert r.status_code == 200

    codes = {p["id"] for p in r.json()}
    assert str(lead_ctx["mine"]) in codes
    assert str(lead_ctx["theirs"]) not in codes, (
        "a restricted project the caller is not a member of appeared in the "
        "list — RLS is not filtering, or the list query bypassed it"
    )


def test_detail_of_a_non_member_project_is_refused(client, auth, lead_ctx):
    r = client.get(f"/api/projects/{lead_ctx['theirs']}", headers=auth)
    assert r.status_code == 403


def test_detail_of_a_member_project_is_allowed(client, auth, lead_ctx):
    r = client.get(f"/api/projects/{lead_ctx['mine']}", headers=auth)
    assert r.status_code == 200
    assert r.json()["name"] == "My Project"


# ---------------------------------------------------------------------------
# Creation
# ---------------------------------------------------------------------------


def test_creating_a_project_makes_the_creator_a_member(client, auth):
    """Otherwise a restricted project vanishes from its own creator.

    RLS would be doing exactly the right thing, and the result would look
    like the save silently failed.
    """
    code = f"RDP-NEW-{uuid.uuid4().hex[:6]}"
    r = client.post(
        "/api/projects",
        headers=auth,
        json={"project_code": code, "name": "Created Project", "confidentiality": "restricted"},
    )
    assert r.status_code == 201
    project_id = r.json()["id"]

    follow_up = client.get(f"/api/projects/{project_id}", headers=auth)
    assert follow_up.status_code == 200, "the creator cannot open the project they just created"


def test_duplicate_project_code_is_refused(client, auth, lead_ctx):
    code = f"RDP-DUP-{uuid.uuid4().hex[:6]}"
    first = client.post("/api/projects", headers=auth, json={"project_code": code, "name": "First"})
    assert first.status_code == 201
    second = client.post(
        "/api/projects", headers=auth, json={"project_code": code, "name": "Second"}
    )
    assert second.status_code == 409


# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------


def test_advance_requires_project_membership(client, auth, lead_ctx):
    """Holding project.advance_stage does not grant advancing ANY project."""
    r = client.post(
        f"/api/projects/{lead_ctx['theirs']}/pipeline/advance",
        headers=auth,
        json={"to_stage_code": "REQUIREMENTS", "reason": "attempting someone else's"},
    )
    assert r.status_code == 403


def test_advance_then_history_records_it(client, auth, lead_ctx):
    r = client.post(
        f"/api/projects/{lead_ctx['mine']}/pipeline/advance",
        headers=auth,
        json={"to_stage_code": "REQUIREMENTS", "reason": "project authorized"},
    )
    assert r.status_code == 200
    assert r.json()["to_stage"] == "REQUIREMENTS"
    assert r.json()["is_rework"] is False

    history = client.get(f"/api/projects/{lead_ctx['mine']}/pipeline/history", headers=auth)
    assert history.status_code == 200
    entries = history.json()["history"]
    assert len(entries) == 1
    assert entries[0]["reason"] == "project authorized"


def test_advance_without_a_reason_is_refused_by_the_schema(client, auth, lead_ctx):
    """422 from Pydantic, not a 500 from the domain exception.

    The contract shows the requirement rather than discovering it at
    runtime.
    """
    r = client.post(
        f"/api/projects/{lead_ctx['mine']}/pipeline/advance",
        headers=auth,
        json={"to_stage_code": "REQUIREMENTS", "reason": ""},
    )
    assert r.status_code == 422


def test_unknown_stage_is_404_and_state_conflict_is_409(client, auth, lead_ctx):
    missing = client.post(
        f"/api/projects/{lead_ctx['mine']}/pipeline/advance",
        headers=auth,
        json={"to_stage_code": "NO_SUCH_STAGE", "reason": "typo"},
    )
    assert missing.status_code == 404

    client.post(
        f"/api/projects/{lead_ctx['mine']}/pipeline/advance",
        headers=auth,
        json={"to_stage_code": "REQUIREMENTS", "reason": "start"},
    )
    conflict = client.post(
        f"/api/projects/{lead_ctx['mine']}/pipeline/advance",
        headers=auth,
        json={"to_stage_code": "REQUIREMENTS", "reason": "again"},
    )
    # 409 rather than 400: the request is well-formed and the refusal is
    # a state conflict the client can retry later.
    assert conflict.status_code == 409


def test_pipeline_lists_every_configured_stage(client, auth, lead_ctx):
    r = client.get(f"/api/projects/{lead_ctx['mine']}/pipeline", headers=auth)
    assert r.status_code == 200
    assert [s["stage_code"] for s in r.json()["stages"]] == ["REQUIREMENTS", "RESEARCH"]


# ---------------------------------------------------------------------------
# Requirements
# ---------------------------------------------------------------------------


def test_requirement_without_a_unit_is_422(client, auth, lead_ctx):
    r = client.post(
        f"/api/projects/{lead_ctx['mine']}/requirements",
        headers=auth,
        json={"requirement_code": "REQ-ADH-001", "name": "Adhesion", "minimum_value": "6.0"},
    )
    assert r.status_code == 422
    assert "unit" in r.json()["detail"]


def test_requirement_lifecycle_through_the_api(client, auth, lead_ctx):
    created = client.post(
        f"/api/projects/{lead_ctx['mine']}/requirements",
        headers=auth,
        json={
            "requirement_code": "REQ-ADH-001",
            "name": "Adhesion",
            "minimum_value": "6.0",
            "target_value": "7.0",
            "canonical_unit": "MPa",
            "criticality": "critical",
        },
    )
    assert created.status_code == 201
    rid = created.json()["requirement_id"]

    approved = client.post(
        f"/api/projects/{lead_ctx['mine']}/requirements/{rid}/approve", headers=auth
    )
    assert approved.status_code == 204

    # Approving twice is a state conflict, not a validation error.
    again = client.post(
        f"/api/projects/{lead_ctx['mine']}/requirements/{rid}/approve", headers=auth
    )
    assert again.status_code == 409

    revised = client.post(
        f"/api/projects/{lead_ctx['mine']}/requirements/{rid}/revise",
        headers=auth,
        json={
            "requirement_code": "REQ-ADH-001",
            "name": "Adhesion",
            "minimum_value": "8.0",
            "target_value": "9.0",
            "canonical_unit": "MPa",
            "criticality": "critical",
            "reason": "customer raised the floor",
        },
    )
    assert revised.status_code == 201
    assert revised.json()["requirement_id"] != rid, "a revision is a new record"


def test_matrix_reports_blocking_and_admits_tests_are_unavailable(client, auth, lead_ctx):
    client.post(
        f"/api/projects/{lead_ctx['mine']}/requirements",
        headers=auth,
        json={
            "requirement_code": "REQ-ADH-001",
            "name": "Adhesion",
            "minimum_value": "6.0",
            "canonical_unit": "MPa",
            "criticality": "critical",
        },
    )
    r = client.get(f"/api/projects/{lead_ctx['mine']}/requirements/matrix", headers=auth)
    assert r.status_code == 200

    body = r.json()
    assert body["tests_available"] is False, (
        "the matrix must state that no test evidence exists — 'nothing has "
        "passed' and 'we cannot yet tell' are different claims"
    )
    assert body["summary"]["blocking_validation"] == 1
    assert body["requirements"][0]["acceptance"] == "≥ 6 MPa"
