"""Fixtures for authorization tests.

These run without Keycloak. A generated RSA keypair signs tokens and a
patched JWKS serves the public half, which tests the verification path
*more* thoroughly than pointing at a real server would: it can mint the
tokens a real Keycloak will not issue on demand — expired, wrong
audience, wrong issuer, unsigned, signed by the wrong key.

CI has no Keycloak service either, so this is also the only way these
paths get exercised there.
"""

from __future__ import annotations

import time
import uuid
from typing import Any

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from jose import jwt

TEST_ISSUER = "http://localhost:18080/realms/evercoat"
TEST_AUDIENCE = "evercoat-api"
KID = "test-key-1"


@pytest.fixture(scope="session")
def rsa_key() -> rsa.RSAPrivateKey:
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


@pytest.fixture(scope="session")
def private_pem(rsa_key: rsa.RSAPrivateKey) -> str:
    return rsa_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode()


@pytest.fixture(scope="session")
def jwks(rsa_key: rsa.RSAPrivateKey) -> dict[str, Any]:
    """The public half, in the shape Keycloak publishes."""
    import base64

    numbers = rsa_key.public_key().public_numbers()

    def b64(value: int) -> str:
        raw = value.to_bytes((value.bit_length() + 7) // 8, "big")
        return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()

    return {
        "keys": [
            {
                "kty": "RSA",
                "use": "sig",
                "alg": "RS256",
                "kid": KID,
                "n": b64(numbers.n),
                "e": b64(numbers.e),
            }
        ]
    }


@pytest.fixture
def make_token(private_pem: str):
    """Mint a token, with every claim overridable.

    Defaults are a valid token; each test overrides exactly the one claim
    it is attacking, so a failure names the specific check that lapsed.
    """

    def _make(
        *,
        sub: str | None = None,
        issuer: str = TEST_ISSUER,
        audience: str = TEST_AUDIENCE,
        expires_in: int = 300,
        algorithm: str = "RS256",
        extra: dict[str, Any] | None = None,
    ) -> str:
        now = int(time.time())
        claims: dict[str, Any] = {
            "sub": sub or str(uuid.uuid4()),
            "iss": issuer,
            "aud": audience,
            "iat": now,
            "exp": now + expires_in,
            "sid": str(uuid.uuid4()),
        }
        if extra:
            claims.update(extra)
        return jwt.encode(claims, private_pem, algorithm=algorithm, headers={"kid": KID})

    return _make


@pytest.fixture(autouse=True)
def _patch_jwks(monkeypatch, jwks: dict[str, Any]):
    """Serve the generated JWKS instead of fetching from Keycloak.

    Patched at the module boundary rather than by stubbing HTTP, so the
    real ``jwt.decode`` call — signature, issuer, audience and expiry —
    still runs. Stubbing the decode itself would test nothing.
    """
    import app.core.security as security

    async def _fake_jwks() -> dict[str, Any]:
        return jwks

    monkeypatch.setattr(security, "_get_jwks", _fake_jwks)
    monkeypatch.setattr(security.settings, "keycloak_issuer", TEST_ISSUER)
    monkeypatch.setattr(security.settings, "keycloak_audience", TEST_AUDIENCE)


# ---------------------------------------------------------------------------
# Database fixtures for the authorization tests
# ---------------------------------------------------------------------------
# Imported from the db suite so there is one definition of how a test
# database connection is made. Two definitions would drift, and the
# tenancy rules they encode are not the kind of thing to have two
# versions of.
from tests.db.conftest import (  # noqa: E402,F401
    app_engine,
    app_session,
    owner_engine,
    owner_session,
)


@pytest.fixture
def seeded_org(owner_session):  # noqa: F811 - pytest fixture injection
    """One organization, one chemist member, two projects.

    The member belongs to the first project and NOT the second. That
    second project is the whole point: it is a project inside the user's
    own organization that they must still be unable to open (Codex F32).
    """
    from sqlalchemy import text

    suffix = uuid.uuid4().hex[:8]
    sub = f"kc-{suffix}"

    org_id = owner_session.execute(
        text("INSERT INTO core.organizations (code, name) VALUES (:c,:n) RETURNING id"),
        {"c": f"AUTH-{suffix}", "n": "Auth Test Org"},
    ).scalar_one()

    user_id = owner_session.execute(
        text(
            "INSERT INTO core.users (keycloak_sub, email, display_name) "
            "VALUES (:s,:e,'Auth Probe') RETURNING id"
        ),
        {"s": sub, "e": f"auth-{suffix}@example.test"},
    ).scalar_one()

    member_id = owner_session.execute(
        text(
            "INSERT INTO core.organization_members (organization_id, user_id) "
            "VALUES (:o,:u) RETURNING id"
        ),
        {"o": org_id, "u": user_id},
    ).scalar_one()

    owner_session.execute(
        text(
            "INSERT INTO core.member_roles (member_id, role_id) "
            "SELECT :m, id FROM core.roles WHERE code = 'product_development_chemist'"
        ),
        {"m": member_id},
    )

    member_project_id = owner_session.execute(
        text(
            "INSERT INTO projects.projects (organization_id, project_code, name, "
            "confidentiality) VALUES (:o,:c,'Member project','restricted') RETURNING id"
        ),
        {"o": org_id, "c": f"RDP-M-{suffix}"},
    ).scalar_one()

    other_project_id = owner_session.execute(
        text(
            "INSERT INTO projects.projects (organization_id, project_code, name, "
            "confidentiality) VALUES (:o,:c,'Other team project','restricted') RETURNING id"
        ),
        {"o": org_id, "c": f"RDP-O-{suffix}"},
    ).scalar_one()

    owner_session.execute(
        text(
            "INSERT INTO projects.project_members "
            "(organization_id, project_id, user_id, project_role) "
            "VALUES (:o,:p,:u,'chemist')"
        ),
        {"o": org_id, "p": member_project_id, "u": user_id},
    )

    owner_session.commit()

    yield {
        "org_id": org_id,
        "user_id": user_id,
        "member_id": member_id,
        "keycloak_sub": sub,
        "member_project_id": member_project_id,
        "other_project_id": other_project_id,
    }

    # Children before parents: every FK in the thread is RESTRICT.
    owner_session.begin()
    for stmt, params in [
        ("DELETE FROM projects.project_members WHERE organization_id=:o", {"o": org_id}),
        ("DELETE FROM projects.projects WHERE organization_id=:o", {"o": org_id}),
        ("DELETE FROM core.member_roles WHERE member_id=:m", {"m": member_id}),
        ("DELETE FROM core.organization_members WHERE id=:m", {"m": member_id}),
        ("DELETE FROM core.users WHERE id=:u", {"u": user_id}),
        ("DELETE FROM core.organizations WHERE id=:o", {"o": org_id}),
    ]:
        owner_session.execute(text(stmt), params)
    owner_session.commit()
