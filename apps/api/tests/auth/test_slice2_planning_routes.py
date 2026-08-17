"""Milestone, risk and project-member routes, over real HTTP.

These are the write halves that Slice 2 shipped without. `milestones` and
`risks` had tables, indexes, RLS policies and dashboard counters, and no
writer anywhere in the repository -- `milestones` did not even have a test
fixture, so its counters had never been non-zero even under test.
`project.assign_member` was a granted permission that no route used.

Driven through `TestClient` rather than by calling the service functions.
Calling a service proves the function works; it does not prove the route
is wired to `require_permission` and `require_project_member`, and a route
that forgot one looks entirely normal in review.

The dashboard assertions are the ones that matter most. A create endpoint
that returns 201 while the dashboard still reads zero would be a feature
that exists and shows nothing -- which is the state this work is fixing,
not a state it may reintroduce.
"""

from __future__ import annotations

import datetime as dt
import uuid

import pytest
from fastapi.testclient import TestClient

pytestmark = [pytest.mark.db]


@pytest.fixture
def client():
    from app.main import app

    return TestClient(app, raise_server_exceptions=False)


def _future(days: int = 30) -> str:
    return (dt.date.today() + dt.timedelta(days=days)).isoformat()


def _past(days: int = 30) -> str:
    return (dt.date.today() - dt.timedelta(days=days)).isoformat()


# ---------------------------------------------------------------------------
# Milestones
# ---------------------------------------------------------------------------


def test_a_created_milestone_reaches_the_dashboard_counter(client, auth, lead_ctx):
    """The whole point: the counter must stop being structurally zero."""
    before = client.get(f"/api/projects/{lead_ctx['mine']}/dashboard", headers=auth)
    assert before.status_code == 200
    assert before.json()["milestones"]["total"] == 0

    created = client.post(
        f"/api/projects/{lead_ctx['mine']}/milestones",
        headers=auth,
        json={"name": "Formulation freeze", "planned_date": _future()},
    )
    assert created.status_code == 201, created.text

    after = client.get(f"/api/projects/{lead_ctx['mine']}/dashboard", headers=auth)
    assert after.json()["milestones"]["total"] == 1, (
        "the milestone was created but the dashboard still counts zero — a "
        "create endpoint whose result is invisible is not a working feature"
    )


def test_a_milestone_past_its_planned_date_counts_as_overdue(client, auth, lead_ctx):
    """`overdue` is derived, and the list and the KPI must agree on it."""
    client.post(
        f"/api/projects/{lead_ctx['mine']}/milestones",
        headers=auth,
        json={"name": "Late gate", "planned_date": _past()},
    )

    dashboard = client.get(f"/api/projects/{lead_ctx['mine']}/dashboard", headers=auth).json()
    listing = client.get(f"/api/projects/{lead_ctx['mine']}/milestones", headers=auth).json()

    assert dashboard["milestones"]["overdue"] == 1
    assert [m["is_overdue"] for m in listing["milestones"]] == [True], (
        "the list and the dashboard tile disagree about the same milestone"
    )


def test_closing_a_milestone_records_the_date_and_clears_overdue(client, auth, lead_ctx):
    created = client.post(
        f"/api/projects/{lead_ctx['mine']}/milestones",
        headers=auth,
        json={"name": "Closed gate", "planned_date": _past()},
    )
    milestone_id = created.json()["milestone_id"]

    moved = client.patch(
        f"/api/projects/{lead_ctx['mine']}/milestones/{milestone_id}/status",
        headers=auth,
        json={"status": "met", "reason": "gate passed at review"},
    )
    assert moved.status_code == 200, moved.text
    assert moved.json()["new_actual_date"] is not None, (
        "a milestone recorded as met carries no date it was met on"
    )

    dashboard = client.get(f"/api/projects/{lead_ctx['mine']}/dashboard", headers=auth).json()
    assert dashboard["milestones"]["met"] == 1
    assert dashboard["milestones"]["overdue"] == 0, (
        "a met milestone is still counted as overdue — the overdue filter is "
        "reading a status it should have excluded"
    )


def test_an_in_flight_milestone_cannot_carry_a_completion_date(client, auth, lead_ctx):
    """422, not a 500 from the CHECK constraint.

    The database refuses this combination either way; the question is
    whether the client is told why.
    """
    created = client.post(
        f"/api/projects/{lead_ctx['mine']}/milestones",
        headers=auth,
        json={"name": "Still running", "planned_date": _future()},
    )
    milestone_id = created.json()["milestone_id"]

    r = client.patch(
        f"/api/projects/{lead_ctx['mine']}/milestones/{milestone_id}/status",
        headers=auth,
        json={
            "status": "in_progress",
            "actual_date": _past(1),
            "reason": "attempting an incoherent combination",
        },
    )
    assert r.status_code == 422, r.text


def test_milestones_on_a_non_member_project_are_refused(client, auth, lead_ctx):
    """Same organization, every permission held, still not a member."""
    r = client.post(
        f"/api/projects/{lead_ctx['theirs']}/milestones",
        headers=auth,
        json={"name": "Should not exist", "planned_date": _future()},
    )
    assert r.status_code == 403

    assert (
        client.get(f"/api/projects/{lead_ctx['theirs']}/milestones", headers=auth).status_code
        == 403
    )


# ---------------------------------------------------------------------------
# Risks
# ---------------------------------------------------------------------------


def test_a_raised_risk_reaches_the_dashboard_counter(client, auth, lead_ctx):
    before = client.get(f"/api/projects/{lead_ctx['mine']}/dashboard", headers=auth).json()
    assert before["risks"]["open"] == 0

    created = client.post(
        f"/api/projects/{lead_ctx['mine']}/risks",
        headers=auth,
        json={
            "risk_code": f"R-{uuid.uuid4().hex[:6]}",
            "title": "Single-sourced resin",
            "probability": "high",
            "impact": "high",
            "category": "supply",
        },
    )
    assert created.status_code == 201, created.text

    after = client.get(f"/api/projects/{lead_ctx['mine']}/dashboard", headers=auth).json()
    assert after["risks"]["open"] == 1
    assert after["risks"]["high_high"] == 1, (
        "a high/high risk did not reach the tile that exists specifically to "
        "surface high/high risks"
    )


def test_a_duplicate_risk_code_is_refused(client, auth, lead_ctx):
    code = f"R-{uuid.uuid4().hex[:6]}"
    body = {"risk_code": code, "title": "First", "probability": "low", "impact": "low"}

    assert (
        client.post(f"/api/projects/{lead_ctx['mine']}/risks", headers=auth, json=body).status_code
        == 201
    )
    second = client.post(
        f"/api/projects/{lead_ctx['mine']}/risks",
        headers=auth,
        json={**body, "title": "Second"},
    )
    assert second.status_code == 409


def test_a_risk_cannot_be_owned_by_a_user_in_another_organization(client, auth, lead_ctx):
    """RLS gives no protection here at all.

    `risks.owner_user_id` is a plain FK to `core.users`, users are not
    tenant-scoped, and referential integrity bypasses RLS even under
    FORCE. Only the explicit membership check stands between this request
    and another tenant's user being named on this dashboard.
    """
    r = client.post(
        f"/api/projects/{lead_ctx['mine']}/risks",
        headers=auth,
        json={
            "risk_code": f"R-{uuid.uuid4().hex[:6]}",
            "title": "Foreign owner",
            "probability": "low",
            "impact": "low",
            "owner_user_id": str(lead_ctx["foreign_user_id"]),
        },
    )
    assert r.status_code == 422, r.text
    assert "not an active member" in r.json()["detail"]


def test_moving_a_risk_to_mitigating_requires_a_stated_mitigation(client, auth, lead_ctx):
    """422 rather than a 500 from the CHECK constraint.

    A risk marked as being handled, with nothing saying how, reads as
    covered on the dashboard while nobody owns an action.
    """
    created = client.post(
        f"/api/projects/{lead_ctx['mine']}/risks",
        headers=auth,
        json={
            "risk_code": f"R-{uuid.uuid4().hex[:6]}",
            "title": "Unmitigated",
            "probability": "medium",
            "impact": "high",
        },
    )
    risk_id = created.json()["risk_id"]

    bare = client.patch(
        f"/api/projects/{lead_ctx['mine']}/risks/{risk_id}",
        headers=auth,
        json={"status": "mitigating", "reason": "claiming to handle it"},
    )
    assert bare.status_code == 422, bare.text

    with_plan = client.patch(
        f"/api/projects/{lead_ctx['mine']}/risks/{risk_id}",
        headers=auth,
        json={
            "status": "mitigating",
            "mitigation": "Qualify a second supplier before the pilot batch",
            "reason": "mitigation agreed at review",
        },
    )
    assert with_plan.status_code == 200, with_plan.text


def test_updating_only_the_status_does_not_blank_the_mitigation(client, auth, lead_ctx):
    """`None` means "leave unchanged", not "clear it".

    Otherwise a PATCH that moves a risk to 'closed' silently destroys the
    record of how it was handled.
    """
    created = client.post(
        f"/api/projects/{lead_ctx['mine']}/risks",
        headers=auth,
        json={
            "risk_code": f"R-{uuid.uuid4().hex[:6]}",
            "title": "Has a plan",
            "probability": "low",
            "impact": "low",
            "mitigation": "Second supplier qualified",
        },
    )
    risk_id = created.json()["risk_id"]

    client.patch(
        f"/api/projects/{lead_ctx['mine']}/risks/{risk_id}",
        headers=auth,
        json={"status": "closed", "reason": "supplier qualified"},
    )

    listing = client.get(f"/api/projects/{lead_ctx['mine']}/risks", headers=auth).json()
    stored = next(r for r in listing["risks"] if r["id"] == risk_id)
    assert stored["mitigation"] == "Second supplier qualified"
    assert stored["status"] == "closed"


# ---------------------------------------------------------------------------
# Project members
# ---------------------------------------------------------------------------


def test_a_colleague_can_be_added_and_then_sees_the_project(client, auth, lead_ctx, make_token):
    """Membership IS the RLS predicate, so this is the access grant.

    Asserted from the colleague's own token rather than from the list
    endpoint: a members row that does not actually change what the person
    can open would be a convincing-looking no-op.
    """
    project = lead_ctx["mine"]
    colleague_headers = {
        "Authorization": f"Bearer {make_token(sub=lead_ctx['colleague_sub'])}",
        "X-Organization-Id": str(lead_ctx["org_id"]),
    }

    before = client.get(f"/api/projects/{project}", headers=colleague_headers)
    assert before.status_code == 403, "the colleague could already open a restricted project"

    added = client.post(
        f"/api/projects/{project}/members",
        headers=auth,
        json={"user_id": str(lead_ctx["colleague_id"]), "project_role": "chemist"},
    )
    assert added.status_code == 201, added.text

    after = client.get(f"/api/projects/{project}", headers=colleague_headers)
    assert after.status_code == 200, (
        "the member row was written but the colleague still cannot open the "
        "project — membership is not reaching the RLS predicate"
    )


def test_a_user_from_another_organization_cannot_be_added(client, auth, lead_ctx):
    r = client.post(
        f"/api/projects/{lead_ctx['mine']}/members",
        headers=auth,
        json={"user_id": str(lead_ctx["foreign_user_id"]), "project_role": "chemist"},
    )
    assert r.status_code == 422, r.text


def test_removing_a_member_revokes_their_access_but_keeps_the_record(
    client, auth, lead_ctx, make_token
):
    project = lead_ctx["mine"]
    colleague_headers = {
        "Authorization": f"Bearer {make_token(sub=lead_ctx['colleague_sub'])}",
        "X-Organization-Id": str(lead_ctx["org_id"]),
    }

    client.post(
        f"/api/projects/{project}/members",
        headers=auth,
        json={"user_id": str(lead_ctx["colleague_id"]), "project_role": "chemist"},
    )
    assert client.get(f"/api/projects/{project}", headers=colleague_headers).status_code == 200

    removed = client.post(
        f"/api/projects/{project}/members/{lead_ctx['colleague_id']}/remove",
        headers=auth,
        json={"reason": "moved to another programme"},
    )
    assert removed.status_code == 204, removed.text

    assert client.get(f"/api/projects/{project}", headers=colleague_headers).status_code == 403

    listing = client.get(f"/api/projects/{project}/members", headers=auth).json()
    row = next(m for m in listing["members"] if m["user_id"] == str(lead_ctx["colleague_id"]))
    assert row["status"] == "inactive", (
        "the membership was deleted rather than deactivated — the record of "
        "who once had access is the first thing asked for after an incident"
    )


def test_a_removed_member_can_be_added_back(client, auth, lead_ctx):
    """`project_members_unique` means the old row is still there.

    A plain INSERT would fail with a duplicate key on the most ordinary
    action there is.
    """
    project = lead_ctx["mine"]
    body = {"user_id": str(lead_ctx["colleague_id"]), "project_role": "chemist"}

    client.post(f"/api/projects/{project}/members", headers=auth, json=body)
    client.post(
        f"/api/projects/{project}/members/{lead_ctx['colleague_id']}/remove",
        headers=auth,
        json={"reason": "temporary reassignment"},
    )

    again = client.post(f"/api/projects/{project}/members", headers=auth, json=body)
    assert again.status_code == 201, again.text


def test_the_project_lead_cannot_be_removed_from_their_own_project(client, auth, lead_ctx):
    """Migration 006 rescues the lead's view of the project row only.

    Every child policy — milestones, risks, requirements, stages, tasks —
    tests `core.is_project_member` and nothing else, so removing the lead
    from a restricted project leaves them the header and none of its
    contents. That presents as "the project is empty", not as a
    permission error.
    """
    r = client.post(
        f"/api/projects/{lead_ctx['mine']}/members/{lead_ctx['user_id']}/remove",
        headers=auth,
        json={"reason": "attempting to strand the lead"},
    )
    assert r.status_code == 409, r.text


def test_member_routes_on_a_non_member_project_are_refused(client, auth, lead_ctx):
    r = client.post(
        f"/api/projects/{lead_ctx['theirs']}/members",
        headers=auth,
        json={"user_id": str(lead_ctx["colleague_id"]), "project_role": "chemist"},
    )
    assert r.status_code == 403


# ---------------------------------------------------------------------------
# Cross-project binding (Codex review, finding 3)
# ---------------------------------------------------------------------------
# The most serious finding of the review. `require_project_member()`
# authorises the project in the PATH; the service then has to actually USE
# that project. Filtering on child id + organization alone let a member of
# project A mutate project B's milestone by passing A in the URL, and RLS
# does not repair it — the child policy admits rows from any `normal`
# project in the organization.


def test_a_milestone_cannot_be_moved_through_another_projects_url(client, auth, lead_ctx):
    """Both projects are reachable by this caller. The binding is what refuses it."""
    created = client.post(
        f"/api/projects/{lead_ctx['mine2']}/milestones",
        headers=auth,
        json={"name": "Belongs to project two", "planned_date": _future()},
    )
    assert created.status_code == 201, created.text
    milestone_id = created.json()["milestone_id"]

    smuggled = client.patch(
        f"/api/projects/{lead_ctx['mine']}/milestones/{milestone_id}/status",
        headers=auth,
        json={"status": "met", "reason": "reaching through the wrong project"},
    )
    assert smuggled.status_code == 404, (
        "a milestone belonging to another project was mutated through this "
        f"project's URL (got {smuggled.status_code}) — the service is not "
        "bound to the project the caller was authorised for"
    )

    # And the milestone is untouched.
    listing = client.get(f"/api/projects/{lead_ctx['mine2']}/milestones", headers=auth).json()
    assert listing["milestones"][0]["status"] == "planned"


def test_a_risk_cannot_be_updated_through_another_projects_url(client, auth, lead_ctx):
    created = client.post(
        f"/api/projects/{lead_ctx['mine2']}/risks",
        headers=auth,
        json={
            "risk_code": f"R-{uuid.uuid4().hex[:6]}",
            "title": "Belongs to project two",
            "probability": "low",
            "impact": "low",
        },
    )
    assert created.status_code == 201, created.text
    risk_id = created.json()["risk_id"]

    smuggled = client.patch(
        f"/api/projects/{lead_ctx['mine']}/risks/{risk_id}",
        headers=auth,
        json={"status": "closed", "reason": "reaching through the wrong project"},
    )
    assert smuggled.status_code == 404, (
        "a risk belonging to another project was updated through this "
        f"project's URL (got {smuggled.status_code})"
    )
