"""Authorization — permissions, resource scope, and the API surface.

Codex's F32 (BLOCKER) established that organization-level RLS with
project scope left to application code makes the "three independent
layers" claim false. ADR-016 fixed the database half; these assert the
application half, and that the two agree.

The tests use a real FastAPI app and real HTTP calls through
``TestClient`` rather than calling the dependency functions directly.
Calling a dependency in isolation proves the function works; it does not
prove the route is *wired* to it — and an endpoint that forgot its
`Depends` is exactly the defect this suite exists to catch.
"""

from __future__ import annotations

import uuid

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.core.security import (
    Principal,
    get_principal,
    require_permission,
    require_project_member,
)

pytestmark = [pytest.mark.db]

ORG_HEADER = "X-Organization-Id"


@pytest.fixture
def api(seeded_org):
    """A minimal app exposing one route per authorization pattern."""
    app = FastAPI()

    @app.get("/open")
    def open_route(p: Principal = Depends(get_principal)) -> dict[str, str]:
        return {"user": str(p.user_id)}

    @app.get("/needs-formula-create")
    def needs_create(
        p: Principal = Depends(require_permission("formula.create")),
    ) -> dict[str, bool]:
        return {"ok": True}

    @app.get("/needs-release")
    def needs_release(
        p: Principal = Depends(require_permission("product.release")),
    ) -> dict[str, bool]:
        return {"ok": True}

    @app.get("/projects/{project_id}/detail")
    def project_detail(
        project_id: uuid.UUID,
        p: Principal = Depends(require_project_member()),
    ) -> dict[str, bool]:
        return {"ok": True}

    return TestClient(app, raise_server_exceptions=False)


# ---------------------------------------------------------------------------
# Authentication boundary
# ---------------------------------------------------------------------------


def test_no_token_is_rejected(api, seeded_org):
    r = api.get("/open", headers={ORG_HEADER: str(seeded_org["org_id"])})
    assert r.status_code == 401


def test_missing_organization_header_is_rejected(api, make_token, seeded_org):
    # The organization is not inferable from the token: a user may belong
    # to several. Guessing one would be a cross-tenant read waiting to
    # happen, so the request is refused rather than defaulted.
    token = make_token(sub=seeded_org["keycloak_sub"])
    r = api.get("/open", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 400


def test_membership_of_another_organization_is_refused(api, make_token, seeded_org):
    """Claiming an organization you do not belong to.

    The answer is 403 with the same body as "no such organization" --
    a distinct 404 would confirm the organization exists, which is itself
    a disclosure.
    """
    token = make_token(sub=seeded_org["keycloak_sub"])
    r = api.get(
        "/open",
        headers={
            "Authorization": f"Bearer {token}",
            ORG_HEADER: str(uuid.uuid4()),
        },
    )
    assert r.status_code == 403


def test_valid_member_is_admitted(api, make_token, seeded_org):
    token = make_token(sub=seeded_org["keycloak_sub"])
    r = api.get(
        "/open",
        headers={
            "Authorization": f"Bearer {token}",
            ORG_HEADER: str(seeded_org["org_id"]),
        },
    )
    assert r.status_code == 200
    assert r.json()["user"] == str(seeded_org["user_id"])


# ---------------------------------------------------------------------------
# Permissions
# ---------------------------------------------------------------------------


def test_held_permission_allows(api, make_token, seeded_org):
    # The seeded member is a chemist, who holds formula.create.
    token = make_token(sub=seeded_org["keycloak_sub"])
    r = api.get(
        "/needs-formula-create",
        headers={
            "Authorization": f"Bearer {token}",
            ORG_HEADER: str(seeded_org["org_id"]),
        },
    )
    assert r.status_code == 200


def test_absent_permission_denies(api, make_token, seeded_org):
    """A Chemist must not be able to release a product.

    The source states this as a hard rule, and it is enforced by the
    ABSENCE of product.release from the chemist role rather than by a
    hidden button. This is the test that proves the difference.
    """
    token = make_token(sub=seeded_org["keycloak_sub"])
    r = api.get(
        "/needs-release",
        headers={
            "Authorization": f"Bearer {token}",
            ORG_HEADER: str(seeded_org["org_id"]),
        },
    )
    assert r.status_code == 403


def test_revoking_membership_takes_effect_immediately(api, make_token, seeded_org, owner_session):
    """A live token must stop working when membership is revoked.

    Permissions are read from the database per request rather than
    trusted from token claims precisely so that revocation bites now
    rather than whenever the access token happens to expire. A 5-minute
    window in which a removed user retains formulation access is not
    acceptable.
    """
    token = make_token(sub=seeded_org["keycloak_sub"])
    headers = {
        "Authorization": f"Bearer {token}",
        ORG_HEADER: str(seeded_org["org_id"]),
    }
    assert api.get("/open", headers=headers).status_code == 200

    owner_session.execute(
        text("UPDATE core.organization_members SET status = 'inactive' WHERE id = :mid"),
        {"mid": seeded_org["member_id"]},
    )
    owner_session.commit()

    # Same token, same request, now refused.
    assert api.get("/open", headers=headers).status_code == 403


# ---------------------------------------------------------------------------
# Resource scope -- the F32 half
# ---------------------------------------------------------------------------


def test_project_member_may_open_the_project(api, make_token, seeded_org):
    token = make_token(sub=seeded_org["keycloak_sub"])
    r = api.get(
        f"/projects/{seeded_org['member_project_id']}/detail",
        headers={
            "Authorization": f"Bearer {token}",
            ORG_HEADER: str(seeded_org["org_id"]),
        },
    )
    assert r.status_code == 200


def test_non_member_is_refused_a_project_in_their_own_organization(api, make_token, seeded_org):
    """The defect F32 named.

    Same organization, holds the permission, is simply not on the
    project. Before ADR-016 nothing but application code stopped this,
    so a single missing dependency exposed another team's formulations
    to a colleague.
    """
    token = make_token(sub=seeded_org["keycloak_sub"])
    r = api.get(
        f"/projects/{seeded_org['other_project_id']}/detail",
        headers={
            "Authorization": f"Bearer {token}",
            ORG_HEADER: str(seeded_org["org_id"]),
        },
    )
    assert r.status_code == 403


def test_nonexistent_project_is_indistinguishable_from_a_forbidden_one(api, make_token, seeded_org):
    """ "You may not see it" and "it does not exist" must look identical.

    Otherwise the status code becomes an oracle for enumerating other
    teams' project ids.
    """
    token = make_token(sub=seeded_org["keycloak_sub"])
    headers = {
        "Authorization": f"Bearer {token}",
        ORG_HEADER: str(seeded_org["org_id"]),
    }
    forbidden = api.get(f"/projects/{seeded_org['other_project_id']}/detail", headers=headers)
    missing = api.get(f"/projects/{uuid.uuid4()}/detail", headers=headers)

    assert forbidden.status_code == missing.status_code == 403
    assert forbidden.json() == missing.json()
