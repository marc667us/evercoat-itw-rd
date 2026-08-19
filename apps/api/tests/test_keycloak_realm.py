"""The realm file must be importable. It was not, for three slices.

🔴 WHAT THIS CATCHES

`services/keycloak/realm/evercoat-realm.json` carried three top-level
`_comment*` keys documenting the design. Keycloak's importer refuses any
field it does not recognise, and it does not warn and skip -- it aborts:

    ERROR: Failed to run import
    ERROR: Unrecognized field "_comment" (class RealmRepresentation),
           not marked as ignorable (144 known properties)
    ERROR: Failed to start server in (development) mode

So that realm had **never once been imported**. Every `docker compose up`
since Slice 1 produced a Keycloak that either died on boot or came up
with no `evercoat` realm, and nothing noticed, because nothing had ever
asked it for a token. It surfaced the first time CI actually ran
Keycloak -- which is the entire argument for running it in CI.

The commentary now lives in `services/keycloak/realm/README.md`, where it
costs nothing. These tests stop the file growing unimportable keys again,
and they need no Keycloak and no database to run.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

REALM_PATH = Path(__file__).resolve().parents[3] / "services" / "keycloak" / "realm"
REALM_FILE = REALM_PATH / "evercoat-realm.json"


def _realm() -> dict[str, Any]:
    assert REALM_FILE.is_file(), f"the realm file is missing at {REALM_FILE}"
    data: dict[str, Any] = json.loads(REALM_FILE.read_text(encoding="utf-8"))
    return data


def _underscore_keys(node: Any, path: str = "") -> list[str]:
    """Every key beginning with an underscore, at any depth.

    Depth matters: Keycloak rejects unknown fields on nested
    representations too, so a `_comment` tucked inside a client is exactly
    as fatal as one at the top and considerably harder to spot.
    """
    found: list[str] = []
    if isinstance(node, dict):
        for key, value in node.items():
            here = f"{path}.{key}" if path else key
            if isinstance(key, str) and key.startswith("_"):
                found.append(here)
            found.extend(_underscore_keys(value, here))
    elif isinstance(node, list):
        for index, value in enumerate(node):
            found.extend(_underscore_keys(value, f"{path}[{index}]"))
    return found


def test_the_realm_carries_no_keys_keycloak_would_reject() -> None:
    offenders = _underscore_keys(_realm())
    assert offenders == [], (
        "Keycloak's importer aborts on an unrecognised field -- it does not "
        f"warn and skip. These keys would stop the realm importing: {offenders}. "
        "Documentation belongs in services/keycloak/realm/README.md."
    )


def test_the_realm_is_the_one_the_application_expects() -> None:
    """The issuer path is built from this name.

    `KEYCLOAK_ISSUER` ends in `/realms/evercoat`, and `verify_iss` is on.
    Renaming the realm would make every token fail issuer validation, and
    python-jose reports that as the same flat "invalid token" it reports
    for a forged signature.
    """
    realm = _realm()
    assert realm["realm"] == "evercoat"
    assert realm["enabled"] is True


def test_a_client_that_talks_to_the_api_carries_the_audience_mapper() -> None:
    """🔴 THE MAPPER IS LOAD-BEARING.

    A Keycloak access token carries `aud: ["account"]` by default. The API
    decodes with `verify_aud: True` against `evercoat-api`. Without a
    mapper adding that audience, every genuine token is rejected -- and
    the rejection is indistinguishable from a forged one.

    `evercoat-web` is the browser client, so it is the one that must have
    it. This test is what stops somebody "tidying up" the mapper.
    """
    clients = {c["clientId"]: c for c in _realm()["clients"]}
    web = clients.get("evercoat-web")
    assert web is not None, "the browser client evercoat-web is missing"

    audiences = {
        mapper.get("config", {}).get("included.client.audience")
        for mapper in web.get("protocolMappers", [])
        if mapper.get("protocolMapper") == "oidc-audience-mapper"
    }
    assert "evercoat-api" in audiences, (
        "evercoat-web has no audience mapper for evercoat-api. Every token it "
        "issues would be rejected by the API for the one reason nobody checks "
        "first."
    )


def test_no_users_and_no_credentials_are_shipped_in_the_realm() -> None:
    """A realm import with users means the same credentials exist in every
    environment it is imported into -- including any that later becomes
    production.

    The ten demo users are created at bootstrap time by
    `scripts/keycloak-bootstrap.sh` instead, with a password supplied per
    run.
    """
    realm = _realm()
    assert realm.get("users", []) == [], "the shipped realm must not contain users"

    for client in realm["clients"]:
        if client.get("publicClient"):
            assert not client.get("secret"), (
                f"{client['clientId']} is public and carries a secret; a public "
                "client's secret is not a secret"
            )


@pytest.mark.parametrize(
    "expected_role",
    [
        "product_development_chemist",
        "product_development_engineer",
        "product_development_lead",
        "product_development_director",
        "qa_compliance_officer",
        "laboratory_technician",
        "procurement_specialist",
        "production_engineer",
        "executive_viewer",
        "administrator",
    ],
)
def test_every_role_the_bootstrap_assigns_exists_in_the_realm(expected_role: str) -> None:
    """`scripts/keycloak-bootstrap.sh` assigns one realm role per user.

    A role named there but absent here fails at bootstrap time with a
    message about role mapping -- three steps from the cause. These are
    the same ten codes `test_002_roles_permissions.py` checks against
    `core.roles`, asserted from the other side.
    """
    roles = {r["name"] for r in _realm()["roles"]["realm"]}
    assert expected_role in roles, (
        f"the bootstrap script grants '{expected_role}' and the realm does not define it"
    )
