"""The dashboard ROUTE, over real HTTP. TODO I40.

🔴 WHY THIS FILE EXISTS, AND WHAT ITS ABSENCE COST.

`tests/db/test_role_dashboards.py` calls the dashboard SERVICE functions
directly with hand-supplied permission sets. That proves the queries work. It
cannot prove the route is WIRED to its dependencies — and two HIGH findings
went through the gate for exactly that reason:

* a panel gated on `batch.review`, **a permission that does not exist in
  `core.permissions`**, so it was empty for every real user forever. The
  service test passed because the test handed itself the phantom permission.
  A route test cannot: the permissions come from the database, through the
  token, through `get_principal`.

* the route's `project.view` floor **disclosed the entire innovation
  pipeline**. `innovation.opportunities` carries an organization-only RLS
  policy, while `/api/opportunities` guards the same rows with
  `opportunity.view`. A service test supplies whatever permissions it likes
  and so cannot see that the FLOOR is too low.

Both are invisible to a test that calls the function. Both are trivial for a
test that calls the URL.

These run without Keycloak — `tests/auth/conftest.py` mints its own tokens
against a generated keypair — so they run in CI and locally.
"""

from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from .conftest import ORG_HEADER

pytestmark = [pytest.mark.db]


@pytest.fixture
def client():
    from app.main import app

    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture
def technician_ctx(owner_session):
    """A laboratory_technician: holds `project.view`, NOT `opportunity.view`.

    That combination is the whole point. The dashboard route's floor is
    `project.view`, and `/api/dashboards/director` reads
    `innovation.opportunities` — a table whose RLS policy is
    organization-only, with no project predicate to fall back on.

    So this user is precisely the one who must NOT be able to read the
    Director's decision queue, and precisely the one a service-level test
    could never model.
    """
    suffix = uuid.uuid4().hex[:8]
    sub = f"kc-tech-{suffix}"

    org_id = owner_session.execute(
        text("INSERT INTO core.organizations (code,name) VALUES (:c,:n) RETURNING id"),
        {"c": f"DSHR-{suffix}", "n": "Dashboard route org"},
    ).scalar_one()
    user_id = owner_session.execute(
        text(
            "INSERT INTO core.users (keycloak_sub,email,display_name) "
            "VALUES (:s,:e,'Technician') RETURNING id"
        ),
        {"s": sub, "e": f"tech-{suffix}@example.test"},
    ).scalar_one()
    member_id = owner_session.execute(
        text(
            "INSERT INTO core.organization_members (organization_id, user_id, email,"
            " display_name) SELECT :o, :u, u.email, u.display_name FROM core.users u WHERE u.id"
            " = :u RETURNING id"
        ),
        {"o": org_id, "u": user_id},
    ).scalar_one()
    owner_session.execute(
        text(
            "INSERT INTO core.member_roles (member_id, role_id) "
            "SELECT :m, id FROM core.roles WHERE code='laboratory_technician'"
        ),
        {"m": member_id},
    )

    # An opportunity sitting in the Director's queue, which this user must
    # not be shown. Without a record here the disclosure test would pass
    # against an empty table and prove nothing.
    owner_session.execute(
        text(
            """
            INSERT INTO innovation.opportunities
                (organization_id, opportunity_code, title, status, priority, created_by)
            VALUES (:o, :c, 'Unannounced product line', 'awaiting_decision', 'high', :u)
            """
        ),
        {"o": org_id, "c": f"OPP-R-{suffix}", "u": user_id},
    )
    owner_session.commit()

    yield {"org_id": org_id, "user_id": user_id, "sub": sub, "suffix": suffix}

    owner_session.begin()
    owner_session.execute(
        text("DELETE FROM innovation.opportunities WHERE organization_id=:o"), {"o": org_id}
    )
    owner_session.execute(
        text("DELETE FROM core.member_roles WHERE member_id=:m"), {"m": member_id}
    )
    owner_session.execute(
        text("DELETE FROM core.organization_members WHERE organization_id=:o"), {"o": org_id}
    )
    owner_session.execute(text("DELETE FROM core.users WHERE id=:u"), {"u": user_id})
    owner_session.execute(
        text("DELETE FROM workflow.approval_template_steps WHERE organization_id=:o"),
        {"o": org_id},
    )
    owner_session.execute(
        text("DELETE FROM workflow.approval_templates WHERE organization_id=:o"), {"o": org_id}
    )
    owner_session.execute(text("DELETE FROM core.organizations WHERE id=:o"), {"o": org_id})
    owner_session.commit()


@pytest.fixture
def tech_auth(make_token, technician_ctx):
    return {
        "Authorization": f"Bearer {make_token(sub=technician_ctx['sub'])}",
        ORG_HEADER: str(technician_ctx["org_id"]),
    }


def test_the_innovation_pipeline_is_not_disclosed_to_a_technician(client, tech_auth) -> None:
    """🔴 THE DISCLOSURE THE ROUTE'S FLOOR ALLOWED.

    A laboratory_technician holds `project.view` and not `opportunity.view`.
    Before the fix, calling the DIRECTOR dashboard handed them every
    unannounced opportunity in the organization — including the whole
    decision queue — because `innovation.opportunities` is organization-scoped
    and the route's own docstring assumed RLS would handle it.

    The role in the path is a VIEW, not a privilege. This asserts the
    difference is enforced by permissions rather than by nobody thinking to
    ask for that URL.
    """
    r = client.get("/api/dashboards/director", headers=tech_auth)
    assert r.status_code == 200, r.text

    panels = r.json()["panels"]

    pipeline = panels["innovation_pipeline"]
    assert pipeline["available"] is False, (
        "the innovation pipeline was disclosed to a caller without opportunity.view"
    )
    assert pipeline["rows"] == []
    assert "opportunity.view" in pipeline["reason"]

    queue = panels["projects_awaiting_approval"]
    assert queue["available"] is False, (
        "the Director's decision queue was disclosed to a technician"
    )
    assert queue["rows"] == []

    # And the seeded opportunity's title appears NOWHERE in the response.
    # The panels above could be right while some other panel leaked it.
    assert "Unannounced product line" not in r.text


def test_a_panel_the_caller_cannot_act_on_says_so_over_http(client, tech_auth) -> None:
    """The third panel state, end to end.

    A technician holds `batch.execute` and `batch.complete` but not
    `test.review`. The reviews panel must come back `available: false` naming
    the permission — not an empty list, which is byte-identical to a
    genuinely empty queue.
    """
    r = client.get("/api/dashboards/engineer", headers=tech_auth)
    assert r.status_code == 200, r.text
    panels = r.json()["panels"]

    reviews = panels["engineering_reviews"]
    assert reviews["available"] is False
    assert "test.review" in reviews["reason"]

    # 🔴 AND THE DEVIATIONS PANEL IS AVAILABLE, because a technician DOES hold
    # batch.execute. This is the assertion that catches a phantom permission:
    # gate this on something no role holds and it flips to unavailable here,
    # where no test can hand itself the missing permission.
    deviations = panels["process_deviations"]
    assert deviations["available"] is True, (
        "a technician holds batch.execute, so the deviations panel must be "
        "available - if it is not, the gate names a permission nobody has"
    )


def test_every_role_dashboard_is_reachable_over_http(client, tech_auth) -> None:
    """The router is mounted and each role answers.

    A prefix typo or an unmounted router is invisible to every service-level
    test in the suite.
    """
    for role in ("chemist", "engineer", "lead", "director"):
        r = client.get(f"/api/dashboards/{role}", headers=tech_auth)
        assert r.status_code == 200, f"{role}: {r.text}"
        body = r.json()
        assert body["role"] == role
        assert body["panels"], f"{role} returned no panels"


def test_an_unknown_role_is_a_404_naming_the_real_ones(client, tech_auth) -> None:
    """The 404 branch, which no service test can reach.

    It names the valid roles rather than echoing the path segment back —
    reflecting arbitrary input into an error message is a habit worth not
    having.
    """
    r = client.get("/api/dashboards/wizard", headers=tech_auth)
    assert r.status_code == 404
    detail = r.json()["detail"]
    assert "chemist" in detail
    assert "director" in detail
    assert "wizard" not in detail, "the error echoes caller-supplied input back"


def test_an_anonymous_caller_is_refused(client) -> None:
    """No token, no dashboard.

    §6's chain starts at authentication, and a route that forgot its
    dependency answers 200 to anybody. That is exactly the defect a
    service-level test cannot see, because it never goes through the
    dependency at all.
    """
    r = client.get("/api/dashboards/lead")
    assert r.status_code in (401, 403), (
        f"an unauthenticated caller got {r.status_code} from a dashboard"
    )
