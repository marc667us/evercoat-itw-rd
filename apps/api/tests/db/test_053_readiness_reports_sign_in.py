"""`/health/ready` must refuse a deployment that cannot sign anybody in.

Migration 053 revoked EXECUTE on the two sign-in lookups from `evercoat_app`
(I109), so the API needs a second connection. An environment that omits it
starts cleanly, serves `/health/live`, and returns 403 for every authenticated
request — which reads like a broken realm or a bad token and sends whoever is
on call to Keycloak.

Readiness is the right place to say so: "can this serve traffic" is false where
nobody can log in. `_check_migrations` makes the same argument about a database
that answers `SELECT 1` with no RLS.

🔴 THIS FILE EXISTS BECAUSE THE FIRST VERSION OF THAT CHECK HAD TWO DEFECTS,
BOTH FOUND BY CODEX AND BOTH REPRODUCED HERE:

  * it checked ONE of the two functions the API calls, so revoking EXECUTE on
    `memberships_for_subject` left readiness green while `/api/me` — the first
    thing the browser calls after sign-in — was broken;
  * it accepted ANY role that could execute, so pointing `AUTH_DATABASE_URL` at
    `evercoat_owner` reported ok while handing an unscoped pool full table
    access. That is a bigger hole than the one 053 closed, reachable by a
    plausible copy-paste.

A check that passes on a broken deployment is worse than no check, because it
is consulted instead of looking.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api import health
from app.core import db as core_db

pytestmark = [pytest.mark.db]

HOST = "localhost:55432/evercoat_itw_rd"
APP_URL = f"postgresql+psycopg://evercoat_app:ci-app@{HOST}"
AUTH_URL = f"postgresql+psycopg://evercoat_auth:ci-auth@{HOST}"
OWNER_URL = f"postgresql+psycopg://evercoat_owner:ci-owner@{HOST}"


@pytest.fixture
def auth_url(monkeypatch: pytest.MonkeyPatch) -> Iterator[object]:
    """Point the sign-in pool somewhere, and rebuild it for every case.

    `get_auth_engine` memoises, which is right in production and wrong here:
    without resetting, the second case would silently reuse the first case's
    connection and every assertion after it would be about the wrong role.
    """

    def _set(url: str | None) -> None:
        monkeypatch.setattr(core_db.settings, "auth_database_url", url, raising=False)
        if core_db._auth_engine is not None:
            core_db._auth_engine.dispose()
        monkeypatch.setattr(core_db, "_auth_engine", None, raising=False)
        monkeypatch.setattr(core_db, "_auth_session_factory", None, raising=False)

    yield _set

    if core_db._auth_engine is not None:
        core_db._auth_engine.dispose()
    core_db._auth_engine = None
    core_db._auth_session_factory = None


def test_a_correctly_configured_sign_in_connection_is_ready(auth_url) -> None:
    """The control. Everything below is satisfied by a check that always fails."""
    auth_url(AUTH_URL)
    ok, detail = health._check_sign_in()
    assert ok is True, f"a correct configuration was reported as {detail!r}"
    assert detail == "ok"


def test_a_missing_setting_is_not_ready(auth_url) -> None:
    """The commonest failure: the migration applied, the environment not updated."""
    auth_url(None)
    ok, detail = health._check_sign_in()
    assert ok is False
    assert detail == "not configured", (
        f"a missing AUTH_DATABASE_URL reported {detail!r}. It should name the "
        "setting, not the database, because that is where the fix goes."
    )


def test_pointing_it_at_the_runtime_role_is_not_ready(auth_url) -> None:
    """The plausible copy-paste: reuse `DATABASE_URL`.

    It connects perfectly, and then cannot sign anybody in. Without this the
    check would pass on exactly the misconfiguration it exists to catch.
    """
    auth_url(APP_URL)
    ok, detail = health._check_sign_in()
    assert ok is False
    assert "cannot execute" in detail
    # BOTH, so the operator sees "this role is wrong" rather than hunting for
    # one missing grant.
    assert "principal_for_subject" in detail, f"the report named {detail!r}"
    assert "memberships_for_subject" in detail, f"the report named {detail!r}"


def test_an_over_privileged_connection_is_not_ready(auth_url) -> None:
    """🔴 REPORTED HEALTHY BY THE FIRST VERSION, AND IT IS THE WORSE FAILURE.

    Pointing `AUTH_DATABASE_URL` at `evercoat_owner` satisfies "can execute".
    But this pool NEVER sets a tenant GUC, so a role that can also read tables
    reads every tenant's rows with no isolation at all — larger than the
    disclosure 053 closed. The emptiness of the sign-in role is what makes a
    separate pool safe, so readiness asserts it.
    """
    auth_url(OWNER_URL)
    ok, detail = health._check_sign_in()
    assert ok is False, (
        "a connection as evercoat_owner was reported ready. It can execute the "
        "lookups AND read every table on a session with no tenant context."
    )
    assert "more than sign-in privileges" in detail
    # ⚠️ AND IT MUST NOT NAME THE ROLE. Which role is misconfigured is operator
    # information; the body of a readiness probe is a poor place to publish it.
    assert "evercoat_owner" not in detail


def test_half_the_capability_is_not_ready(auth_url, owner_session: Session) -> None:
    """🔴 THE SPLIT THE FIRST VERSION COULD NOT SEE.

    `get_principal` calls `principal_for_subject`; `/api/me` calls
    `memberships_for_subject`. Checking one leaves readiness green while the
    other route is broken for everybody — and `/api/me` is what the browser
    calls immediately after sign-in, so the outage looks like sign-in failing.

    Revokes a real grant and puts it back, rather than mocking the answer: the
    thing under test is whether the check reads the database, and a mock would
    assert only that the code has an `if`.
    """
    auth_url(AUTH_URL)
    owner_session.execute(
        text("REVOKE EXECUTE ON FUNCTION core.memberships_for_subject(TEXT) FROM evercoat_auth")
    )
    owner_session.commit()
    try:
        ok, detail = health._check_sign_in()
        assert ok is False, (
            "readiness reported ok while the sign-in role could not execute "
            "memberships_for_subject, so /api/me was broken for every user."
        )
        assert "memberships_for_subject" in detail
        assert "principal_for_subject" not in detail, (
            f"the report named a capability that is present: {detail!r}"
        )
    finally:
        owner_session.rollback()
        owner_session.execute(
            text("GRANT EXECUTE ON FUNCTION core.memberships_for_subject(TEXT) TO evercoat_auth")
        )
        owner_session.commit()

    # And it recovers, so the failure above was about the grant and not about
    # the connection this fixture built.
    ok, detail = health._check_sign_in()
    assert (ok, detail) == (True, "ok")
