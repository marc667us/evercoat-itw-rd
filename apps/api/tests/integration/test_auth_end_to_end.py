"""Authentication against a REAL Keycloak, end to end.

🔴 WHAT HAS NEVER BEEN PROVEN UNTIL THIS FILE

`app/core/security.py` verifies signature, issuer, audience and expiry,
then resolves a principal from the database. Every one of those steps has
been unit-tested with a fabricated token or mocked out entirely. None of
them had ever run against a token an actual identity provider minted,
because no Keycloak had ever run anywhere -- not on Render, not in CI,
not on the development host.

That is not a small gap. A green build is not a working feature, and the
specific failures this file exists to catch are all invisible to a mock:

* the realm ships with **zero users**, so nothing can sign in;
* the seeder writes `keycloak_sub = 'demo-chem.demo'` while a real token
  carries a UUID, so a valid token resolves to no principal;
* a Keycloak access token's `aud` is `["account"]` unless a mapper adds
  the API's client id, so `verify_aud` rejects every genuine token;
* `X-Organization-Id` is required, and nothing had ever supplied one.

Each would present to an operator as "sign-in is broken" with no further
information, and each is invisible to a test that fabricates its own JWT.

These tests SKIP -- loudly -- when no Keycloak is configured, so local
runs without the stack stay usable. A skip is a third state, not a pass:
CI asserts they actually ran.
"""

from __future__ import annotations

import os
import uuid

import httpx
import pytest

KEYCLOAK_URL = os.environ.get("TEST_KEYCLOAK_URL", "")
API_URL = os.environ.get("TEST_API_URL", "")
REALM = os.environ.get("TEST_KEYCLOAK_REALM", "evercoat")
TEST_CLIENT = os.environ.get("TEST_KEYCLOAK_CLIENT", "evercoat-test")
USER_PASSWORD = os.environ.get("TEST_KEYCLOAK_PASSWORD", "")
ORG_ID = os.environ.get("TEST_ORGANIZATION_ID", "")

pytestmark = pytest.mark.skipif(
    not (KEYCLOAK_URL and API_URL and USER_PASSWORD and ORG_ID),
    reason=(
        "needs a running Keycloak and API: set TEST_KEYCLOAK_URL, TEST_API_URL, "
        "TEST_KEYCLOAK_PASSWORD and TEST_ORGANIZATION_ID"
    ),
)


# 🔴 ONE LITERAL, NOT FIVE.
#
# These tests spent a CI run reporting `404 != 401`, `404 != 400` and
# `404 != 403` -- five failures that read as "authentication is broken"
# when the truth was that the URL had never existed. The route is
# `/api/my-work` (router prefix + `@router.get("")`); the tests asked for
# `/api/my-work/tasks`. Five copies of a path in one file is the same
# defect this project has hit repeatedly with nav-vs-router and
# landing-vs-pack literals: two spellings cannot be type-checked into
# agreement, so keep exactly one.
PROTECTED_ENDPOINT = "/api/my-work"


def test_the_endpoint_under_test_actually_exists() -> None:
    """A 404 means the route moved. It does NOT mean auth is broken.

    Without this, a renamed or re-prefixed route makes every other test in
    this file fail with a confusing status mismatch, and the reader spends
    the session debugging authentication that was working the whole time.
    Run first, and say so plainly.
    """
    response = httpx.get(f"{API_URL}{PROTECTED_ENDPOINT}", timeout=30.0)
    assert response.status_code != 404, (
        f"{PROTECTED_ENDPOINT} does not exist on the running API -- so every "
        "other test in this file is measuring a missing route, not "
        f"authentication. Check the router prefix in app/main.py. Body: {response.text}"
    )


def _token(username: str) -> str:
    """A real access token, from a real identity provider."""
    response = httpx.post(
        f"{KEYCLOAK_URL}/realms/{REALM}/protocol/openid-connect/token",
        data={
            "client_id": TEST_CLIENT,
            "username": username,
            "password": USER_PASSWORD,
            "grant_type": "password",
            "scope": "openid",
        },
        timeout=30.0,
    )
    assert response.status_code == 200, (
        f"Keycloak refused the direct grant for {username}: {response.status_code} {response.text}"
    )
    return str(response.json()["access_token"])


def _auth(username: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {_token(username)}",
        "X-Organization-Id": ORG_ID,
    }


def test_a_real_token_resolves_to_a_principal() -> None:
    """The whole chain, in one assertion.

    Keycloak mints it, the API verifies the signature against JWKS
    fetched over the network, checks issuer and audience, then finds the
    matching `core.users` row by `keycloak_sub` and reads that user's
    real roles and permissions out of the database.

    If `scripts/keycloak-bind-subs.py` has not run, this fails with 403
    rather than 401 -- the token is perfectly valid and simply matches
    nobody. That distinction is the single most useful thing this test
    reports.
    """
    response = httpx.get(f"{API_URL}{PROTECTED_ENDPOINT}", headers=_auth("lead.demo"), timeout=30.0)

    assert response.status_code != 401, (
        "a token minted by Keycloak itself was rejected as invalid. Check the "
        "audience mapper: a Keycloak access token carries aud=['account'] "
        "unless a mapper adds 'evercoat-api'."
    )
    assert response.status_code != 403, (
        "the token verified but resolved to no principal. core.users.keycloak_sub "
        "still holds the seeder's placeholders -- run scripts/keycloak-bind-subs.py."
    )
    assert response.status_code == 200, response.text


def test_no_token_is_refused() -> None:
    """The negative half. A suite that only ever sends valid tokens
    cannot tell an enforced route from an unprotected one."""
    response = httpx.get(f"{API_URL}{PROTECTED_ENDPOINT}", timeout=30.0)
    assert response.status_code == 401, response.text


def test_a_forged_token_is_refused() -> None:
    """Signature verification is real, not decorative.

    A well-formed JWT with the right claims and a signature from the
    wrong key must be refused. This is the check a mocked verifier
    silently skips.
    """
    forged = (
        "eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9."
        "eyJzdWIiOiJhdHRhY2tlciIsImF1ZCI6ImV2ZXJjb2F0LWFwaSJ9."
        "bm90LWEtcmVhbC1zaWduYXR1cmU"
    )
    response = httpx.get(
        f"{API_URL}{PROTECTED_ENDPOINT}",
        headers={"Authorization": f"Bearer {forged}", "X-Organization-Id": ORG_ID},
        timeout=30.0,
    )
    assert response.status_code == 401, response.text


def test_the_organization_header_is_required() -> None:
    """A valid token alone does not select a tenant.

    Defaulting to "the user's only organization" would be convenient and
    would silently pick one for a user who belongs to several -- writing
    records into whichever tenant happened to sort first.
    """
    response = httpx.get(
        f"{API_URL}{PROTECTED_ENDPOINT}",
        headers={"Authorization": f"Bearer {_token('lead.demo')}"},
        timeout=30.0,
    )
    assert response.status_code == 400, response.text


def test_a_foreign_organization_is_refused() -> None:
    """The header is a REQUEST to use a tenant, not a statement of fact.

    A real token plus somebody else's organization id must be refused by
    the membership lookup, not honoured because the token was valid.
    """
    response = httpx.get(
        f"{API_URL}{PROTECTED_ENDPOINT}",
        headers={
            "Authorization": f"Bearer {_token('lead.demo')}",
            # A syntactically valid UUID that is nobody's organization.
            "X-Organization-Id": "00000000-0000-0000-0000-0000000000ff",
        },
        timeout=30.0,
    )
    assert response.status_code == 403, response.text


def test_permissions_come_from_the_database_not_the_token() -> None:
    """`executive_viewer` is a read-only role.

    Its Keycloak token carries the realm role, but the API reads
    permissions from `core.role_permissions` -- so a write must be
    refused even though the token itself is entirely valid. This is the
    difference between authentication and authorization, asserted rather
    than assumed.
    """
    response = httpx.post(
        f"{API_URL}/api/projects",
        headers=_auth("exec.demo"),
        json={
            "project_code": "AUTH-PROBE-001",
            "name": "should never be created",
            "project_type": "new_product",
        },
        timeout=30.0,
    )
    assert response.status_code in (403, 422), (
        "an executive_viewer created a project. Permissions are being taken "
        f"from the token rather than the database. Got {response.status_code}: "
        f"{response.text}"
    )


# ---------------------------------------------------------------------
# GET /api/me -- identity BEFORE a tenant has been chosen
# ---------------------------------------------------------------------
#
# 🔴 THE GAP THESE TESTS EXIST FOR
#
# Every other route in this application requires `X-Organization-Id`, and
# until this one existed nothing told the browser what to put in it. A
# user could sign in successfully and then receive 400 from every request
# they were capable of making.
#
# These tests could not have caught it in that state either, because the
# CI workflow computes TEST_ORGANIZATION_ID from the seeder and injects
# it -- the suite was handed the answer a real browser has no way to get.
# So the assertions below deliberately do NOT send the header.


def test_a_signed_in_user_can_discover_their_organizations() -> None:
    """The one call a browser can make before it knows its tenant.

    No `X-Organization-Id` here, on purpose. If this route ever starts
    requiring one, sign-in is circular again and the deployed application
    is unusable while every test still passes.
    """
    response = httpx.get(
        f"{API_URL}/api/me",
        headers={"Authorization": f"Bearer {_token('lead.demo')}"},
        timeout=30.0,
    )
    assert response.status_code == 200, response.text

    body = response.json()
    assert body["email"], "a principal with no email is not a usable identity"
    assert body["organizations"], (
        "a valid token resolved to a user with NO organizations. A browser "
        "cannot proceed from here -- it has nothing to put in the header that "
        "every other route demands."
    )

    org = body["organizations"][0]
    assert uuid.UUID(org["organization_id"])
    assert org["name"], "an organization with no name cannot be offered in a picker"

    # 🔴 THE PERMISSIONS ARE PART OF THE CONTRACT NOW (I79), AND THIS IS THE
    # ONLY PLACE THE PYTHON/SQL RESPONSE EDGE IS ASSERTED END TO END.
    #
    # Raised by Codex against migration 045: the web tier maps a missing
    # `permissions` field to `[]`, which is the right failure mode and also
    # means the field could silently disappear -- from a bad migration, a
    # dropped column, a rewritten query -- and every screen would quietly
    # gate on nothing while this suite stayed green.
    #
    # `roles` is asserted beside it because 045 added two one-to-many joins
    # underneath it, and a missing DISTINCT there would repeat every role
    # once per permission.
    assert "permissions" in org, (
        "GET /api/me no longer returns permissions. Every workspace then "
        "gates on an empty set and a signed-in user sees an empty sidebar."
    )
    assert org["permissions"], (
        "a lead resolved to ZERO permissions. Either the role_permissions "
        "join in migration 045 is broken, or this user holds no roles -- "
        "and both render as an application with nothing in it."
    )
    assert org["permissions"] == sorted(set(org["permissions"])), (
        "permissions are not sorted-unique, so the 045 aggregate lost its DISTINCT or its ORDER BY"
    )
    assert org["roles"] == sorted(set(org["roles"])), (
        "roles are not sorted-unique -- 045's one-to-many joins are multiplying them"
    )


def test_the_organization_from_me_is_accepted_by_a_real_route() -> None:
    """🔴 THE WHOLE POINT: the value handed out must actually work.

    A route that returns a plausible organization id which `get_principal`
    then rejects would be worse than no route at all -- it would look
    correct and fail one step later, which is the shape of defect this
    project keeps catching. So the id is taken from `/api/me` and spent
    immediately on a route that enforces membership.
    """
    token = _token("lead.demo")
    me = httpx.get(
        f"{API_URL}/api/me",
        headers={"Authorization": f"Bearer {token}"},
        timeout=30.0,
    )
    assert me.status_code == 200, me.text
    organization_id = me.json()["organizations"][0]["organization_id"]

    response = httpx.get(
        f"{API_URL}{PROTECTED_ENDPOINT}",
        headers={
            "Authorization": f"Bearer {token}",
            "X-Organization-Id": organization_id,
        },
        timeout=30.0,
    )
    assert response.status_code == 200, (
        "the organization id from /api/me was refused by a real route, so the "
        f"sign-in path is still broken. Got {response.status_code}: {response.text}"
    )


def test_me_refuses_an_absent_token() -> None:
    """Identity without a tenant is still identity, and still requires one."""
    response = httpx.get(f"{API_URL}/api/me", timeout=30.0)
    assert response.status_code in (401, 403), response.text


def test_me_refuses_a_forged_token() -> None:
    """SECURITY DEFINER sits behind this route. The signature check is what
    keeps it safe, so assert it rather than assuming it."""
    forged = (
        "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9."
        "eyJzdWIiOiJhdHRhY2tlciIsImF1ZCI6ImV2ZXJjb2F0LWFwaSJ9."
        "bm90LWEtcmVhbC1zaWduYXR1cmU"
    )
    response = httpx.get(
        f"{API_URL}/api/me",
        headers={"Authorization": f"Bearer {forged}"},
        timeout=30.0,
    )
    assert response.status_code == 401, response.text
