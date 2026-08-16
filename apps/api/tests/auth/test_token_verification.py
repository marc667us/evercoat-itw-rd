"""Token verification.

Every one of these is a token a real Keycloak would never issue, which is
exactly why they need testing: the question is not "does a valid token
work" but "does an invalid one get refused". A verifier that accepts
anything passes the happy path perfectly.

`SECURITY.md` §2 requires signature, issuer, audience AND expiry to all
be verified. Each is asserted separately below, so a regression names the
specific check that lapsed rather than just "auth broke".
"""

from __future__ import annotations

import time

import pytest
from fastapi import HTTPException
from jose import jwt

from app.core.security import _decode

pytestmark = pytest.mark.asyncio


async def test_valid_token_decodes(make_token):
    token = make_token(sub="user-123")
    claims = await _decode(token)
    assert claims["sub"] == "user-123"


async def test_expired_token_is_refused(make_token):
    # The single most important negative case: an access token that
    # outlives its expiry is a stolen credential with no shelf life.
    token = make_token(expires_in=-60)
    with pytest.raises(HTTPException) as exc:
        await _decode(token)
    assert exc.value.status_code == 401


async def test_wrong_audience_is_refused(make_token):
    # A token minted for the web client must not be accepted by the API.
    # Keycloak issues both; only the audience distinguishes them, which
    # is why the realm needs an explicit audience mapper.
    token = make_token(audience="some-other-client")
    with pytest.raises(HTTPException) as exc:
        await _decode(token)
    assert exc.value.status_code == 401


async def test_wrong_issuer_is_refused(make_token):
    # Guards against a token from a different realm -- or a different
    # Keycloak entirely -- being accepted because the signature happens
    # to validate against a shared key.
    token = make_token(issuer="http://evil.example/realms/other")
    with pytest.raises(HTTPException) as exc:
        await _decode(token)
    assert exc.value.status_code == 401


async def test_token_signed_by_another_key_is_refused(make_token, jwks):
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import rsa

    attacker = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    pem = attacker.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode()

    now = int(time.time())
    forged = jwt.encode(
        {
            "sub": "attacker",
            "iss": "http://localhost:18080/realms/evercoat",
            "aud": "evercoat-api",
            "iat": now,
            "exp": now + 300,
        },
        pem,
        algorithm="RS256",
        headers={"kid": "test-key-1"},  # claims to be our key
    )

    with pytest.raises(HTTPException) as exc:
        await _decode(forged)
    assert exc.value.status_code == 401


async def test_unsigned_token_is_refused():
    """The alg=none attack.

    A verifier that honours the token's own algorithm header can be told
    not to check the signature at all. `_decode` pins
    ``algorithms=["RS256"]``, so this must fail — and if someone ever
    widens that list to include "none", this test is what catches it.

    Hand-built rather than minted with python-jose, because python-jose
    refuses to *encode* alg=none. That refusal is a good default and
    proves nothing about our verifier: an attacker does not use our
    library. The wire format is just
    ``base64url(header).base64url(payload).`` with an empty signature,
    which is trivial to produce with a text editor.
    """
    import base64
    import json

    def b64(data: dict[str, object]) -> str:
        raw = json.dumps(data, separators=(",", ":")).encode()
        return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()

    header = b64({"alg": "none", "typ": "JWT"})
    payload = b64(
        {
            "sub": "attacker",
            "iss": "http://localhost:18080/realms/evercoat",
            "aud": "evercoat-api",
            "exp": int(time.time()) + 300,
        }
    )
    unsigned = f"{header}.{payload}."

    with pytest.raises(HTTPException) as exc:
        await _decode(unsigned)
    assert exc.value.status_code == 401


async def test_garbage_is_refused():
    with pytest.raises(HTTPException) as exc:
        await _decode("not-a-jwt-at-all")
    assert exc.value.status_code == 401


async def test_refusal_does_not_leak_why(make_token):
    """The 401 body must not distinguish failure modes.

    "expired" versus "wrong audience" versus "bad signature" tells an
    attacker which part of the token to fix next. All three return the
    same opaque detail.
    """
    cases = [
        make_token(expires_in=-60),
        make_token(audience="wrong"),
        make_token(issuer="http://wrong"),
    ]
    details = set()
    for token in cases:
        with pytest.raises(HTTPException) as exc:
            await _decode(token)
        details.add(exc.value.detail)

    assert details == {"invalid token"}, (
        f"401 detail varies by failure mode and leaks which check failed: {details}"
    )
