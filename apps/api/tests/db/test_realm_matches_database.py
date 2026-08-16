"""The Keycloak realm and the database must agree on role names.

This is the failure a running Keycloak would have caught, closed without
one.

The mismatch is silent and nasty. Keycloak issues a perfectly valid token
naming a realm role; the principal query joins `core.roles` on that code,
finds nothing, and returns an empty permission set. The user signs in
successfully and sees an application with no navigation, no data and no
error message anywhere — in the API log, the browser console, or
Keycloak. It looks like an authorization bug, a seeding bug and a
frontend bug simultaneously, and it is none of them.

Two literals in two files cannot be type-checked into agreement, so they
are asserted instead. `services/keycloak/realm/evercoat-realm.json` ships
to every environment; `002_seed_roles_permissions.sql` builds every
database. Nothing else connects them.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest
from sqlalchemy import text

pytestmark = pytest.mark.db

# tests/db -> tests -> api -> apps -> <app root>
_REALM_FILE = (
    Path(__file__).resolve().parents[4] / "services" / "keycloak" / "realm" / "evercoat-realm.json"
)


def _realm() -> dict:
    assert _REALM_FILE.exists(), f"realm file missing: {_REALM_FILE}"
    # The file carries "_comment" keys, which are not valid Keycloak
    # config but are ignored on import. json.loads handles them fine.
    return json.loads(_REALM_FILE.read_text(encoding="utf-8"))


def test_realm_roles_match_seeded_roles_exactly(owner_session):
    realm_roles = {r["name"] for r in _realm()["roles"]["realm"]}
    db_roles = {r[0] for r in owner_session.execute(text("SELECT code FROM core.roles")).all()}

    missing_in_realm = db_roles - realm_roles
    missing_in_db = realm_roles - db_roles

    assert not missing_in_realm, (
        "roles seeded in the database but absent from the Keycloak realm — "
        f"nobody can ever be granted these: {sorted(missing_in_realm)}"
    )
    assert not missing_in_db, (
        "roles in the Keycloak realm with no matching core.roles row — "
        "a user holding one signs in to an empty application with no error: "
        f"{sorted(missing_in_db)}"
    )


def test_realm_declares_the_audience_mapper(owner_session):
    """Without it every request fails as invalid_audience.

    Keycloak issues the web client's token with `aud` naming only the web
    client. The API validates `aud == evercoat-api` and refuses it. The
    user sees a login that appears to succeed and an application that
    401s on everything — which reads as a broken backend, not a missing
    protocol mapper.
    """
    web = next(c for c in _realm()["clients"] if c["clientId"] == "evercoat-web")
    mappers = web.get("protocolMappers", [])
    audience = [m for m in mappers if m.get("protocolMapper") == "oidc-audience-mapper"]

    assert audience, "evercoat-web has no audience mapper"
    assert audience[0]["config"]["included.client.audience"] == "evercoat-api", (
        "audience mapper does not target evercoat-api"
    )
    assert audience[0]["config"]["access.token.claim"] == "true", (
        "audience mapper does not write to the access token"
    )


def test_web_client_is_public_with_pkce_and_no_password_grant():
    web = next(c for c in _realm()["clients"] if c["clientId"] == "evercoat-web")

    assert web["publicClient"] is True, (
        "a browser cannot keep a secret; a confidential web client only "
        "creates the illusion of confidentiality"
    )
    assert web["attributes"]["pkce.code.challenge.method"] == "S256", (
        "PKCE is what actually protects the authorization code for a public client"
    )
    assert web.get("directAccessGrantsEnabled", False) is False, (
        "the password grant on a public client is a credential-stuffing "
        "target and bypasses PKCE entirely"
    )
    assert web.get("implicitFlowEnabled", False) is False


def test_api_client_is_bearer_only_with_no_service_account():
    api = next(c for c in _realm()["clients"] if c["clientId"] == "evercoat-api")

    assert api["bearerOnly"] is True
    assert api.get("serviceAccountsEnabled", False) is False, (
        "an API able to mint its own privileged token has a path around "
        "the entire authorization chain"
    )


def test_redirect_uris_are_exact_with_no_wildcards():
    """A wildcard redirect URI is an open redirect and a code-interception path."""
    web = next(c for c in _realm()["clients"] if c["clientId"] == "evercoat-web")
    for uri in web["redirectUris"]:
        assert "*" not in uri, f"wildcard redirect URI: {uri}"
        assert re.match(r"^https?://[^*]+/", uri), f"suspicious redirect URI: {uri}"


def test_realm_seeds_no_users():
    """Users in a realm import exist in every environment it touches.

    Including, eventually, one that becomes production. Demo users are
    created by scripts/seed.sh and labelled as demo data.
    """
    assert _realm().get("users", []) == [], (
        "the realm import seeds users; identical credentials would then "
        "exist in every environment this file is imported into"
    )


def test_realm_has_a_password_policy():
    policy = _realm().get("passwordPolicy", "")
    assert "length(" in policy, "no minimum password length"
    assert "notUsername" in policy, "password may equal the username"
