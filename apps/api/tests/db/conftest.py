"""Fixtures for database tests.

Two session flavours, because the tests need both sides of the boundary:

``owner_session``  connects as ``evercoat_owner`` — can create fixtures,
                   inspect the catalogue, and (for the tamper test)
                   deliberately act as an attacker with direct database
                   access.
``app_session``    connects as ``evercoat_app`` — the runtime role,
                   subject to RLS. Assertions about what a user can see
                   must use this one. A suite that runs as superuser would
                   pass against a schema with no isolation whatsoever.

Every fixture rolls back. These tests must be runnable against a
developer's local database repeatedly without leaving residue.
"""

from __future__ import annotations

import os
import uuid
from collections.abc import Iterator

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker


def _url(user_env: str, pass_env: str, default_user: str) -> str:
    host = os.getenv("TEST_DB_HOST", "localhost")
    port = os.getenv("TEST_DB_PORT", "5432")
    name = os.getenv("POSTGRES_DB", "evercoat_itw_rd")
    user = os.getenv(user_env, default_user)
    password = os.getenv(pass_env, "")
    return f"postgresql+psycopg://{user}:{password}@{host}:{port}/{name}"


def _connect_or_explain(engine, *, env_name: str, role: str, label: str) -> None:
    """Prove the connection works, or say which of two very different things is wrong.

    🔴 A SUPPLIED-BUT-REJECTED PASSWORD IS A MISCONFIGURATION, NOT AN ABSENCE.

    These fixtures used to `pytest.skip` on ANY exception. That is right when
    nobody configured the role — a machine with no database should not fail a
    suite it was never asked to run — and it is wrong, silently and expensively,
    when the credential was supplied and refused.

    On 2026-08-31 that difference cost 24 tests. `evercoat_public` and
    `evercoat_agent` authenticate as `dev-public-pw` / `dev-agent-pw` on the
    development host while the documented incantation carried CI's `ci-public` /
    `ci-agent`. Every case in `test_059_public_surface.py` and
    `test_060_agent_boundary.py` reported SKIPPED, and three consecutive
    handovers quoted "0 failed / 35 skipped" as though that 35 were deliberate.
    With the right passwords the same suite is 1036 / 0 / 11.

    Those two files are the ONLY proof that an anonymous caller cannot reach a
    tenant row and that the agent role cannot publish. Skipping them quietly is
    the worst available outcome: the suite reports green over the exact claims
    it exists to defend.

    So: no password in the environment at all -> skip, and name the variable.
    A password that was given and refused -> fail.
    """
    supplied = os.getenv(env_name, "") != ""
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
    except Exception as exc:
        if not supplied:
            pytest.skip(f"{label}: {env_name} is not set, so this role was never configured")
        raise AssertionError(
            f"{label}: {env_name} WAS supplied and {role} refused it. This is a "
            f"misconfiguration, not an absent capability -- these tests are the "
            f"only proof of this role's boundary, and skipping them would report "
            f"green over the claim they exist to defend. "
            f"⚠️ Verify from the HOST over TCP, not with `docker exec` (the "
            f"container's local socket accepts either password). {exc}"
        ) from exc


@pytest.fixture(scope="session")
def db_urls() -> dict[str, str]:
    """The three connection URLs, built from the SAME env the engines use.

    🔴 A TEST THAT HARDCODES A HOST OR A PORT IS A TEST THAT ONLY RUNS HERE.

    `test_053_readiness_reports_sign_in.py` hardcoded `localhost:55432` --
    this developer host's port. CI runs PostgreSQL on 5432, so every case in
    that file connected to a dead port and reported the readiness check as
    `unavailable`, which is a truthful answer to the wrong question. Caught by
    CI, which is exactly the direction the standing note about `TEST_DB_PORT`
    warns in, mirrored.

    Exposed as a fixture so anything needing a URL rather than an engine gets
    the same values `_url` gives the engines, from the same variables.
    """
    return {
        "owner": _url("TEST_OWNER_USER", "TEST_OWNER_PASSWORD", "evercoat_owner"),
        "app": _url("APP_DB_USER", "APP_DB_PASSWORD", "evercoat_app"),
        "auth": _url("AUTH_DB_USER", "AUTH_DB_PASSWORD", "evercoat_auth"),
        "public": _url("PUBLIC_DB_USER", "PUBLIC_DB_PASSWORD", "evercoat_public"),
        "agent": _url("AGENT_DB_USER", "AGENT_DB_PASSWORD", "evercoat_agent"),
    }


@pytest.fixture(scope="session")
def owner_engine():
    engine = create_engine(
        _url("TEST_OWNER_USER", "TEST_OWNER_PASSWORD", "evercoat_owner"),
        pool_pre_ping=True,
    )
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
    except Exception as exc:  # noqa: BLE001
        pytest.skip(f"no database available for db tests: {exc}")
    yield engine
    engine.dispose()


@pytest.fixture(scope="session")
def app_engine():
    engine = create_engine(
        _url("APP_DB_USER", "APP_DB_PASSWORD", "evercoat_app"),
        pool_pre_ping=True,
        pool_reset_on_return="rollback",
    )
    _connect_or_explain(
        engine, env_name="APP_DB_PASSWORD", role="evercoat_app", label="the application role"
    )
    yield engine
    engine.dispose()


@pytest.fixture(scope="session")
def auth_engine():
    """The sign-in role's connection (I109, migration 053).

    `core.principal_for_subject` and `core.memberships_for_subject` take a
    SUBJECT AS AN ARGUMENT and cannot check their caller, so migration 053
    moved EXECUTE off `evercoat_app` and onto `evercoat_auth`, reachable only
    on a separate pool.

    🔴 SIGN-IN TESTS MUST USE THIS, NOT `owner_session` AND NOT `app_engine`.
    The owner bypasses non-forced RLS, so a test written against it stays green
    even if the function were changed to SECURITY INVOKER -- Codex raised
    exactly that about `test_sign_in_still_works`. `app_engine` no longer holds
    EXECUTE at all, so it now proves the revoke rather than the sign-in path.
    This role is the one production authenticates with.
    """
    engine = create_engine(
        _url("AUTH_DB_USER", "AUTH_DB_PASSWORD", "evercoat_auth"),
        pool_pre_ping=True,
        pool_reset_on_return="rollback",
    )
    _connect_or_explain(
        engine, env_name="AUTH_DB_PASSWORD", role="evercoat_auth", label="the sign-in role"
    )
    yield engine
    engine.dispose()


@pytest.fixture(scope="session")
def public_engine():
    """The anonymous public read connection (migration 059).

    🔴 PUBLIC-SURFACE TESTS MUST USE THIS, NOT `owner_engine` AND NOT
    `app_engine`. The whole claim being tested is that a caller with no
    identity cannot reach a tenant row, and that claim is a property of THIS
    ROLE. Asserting it over the owner would pass no matter what 059 granted,
    which is the same trap `auth_engine` exists to avoid.
    """
    engine = create_engine(
        _url("PUBLIC_DB_USER", "PUBLIC_DB_PASSWORD", "evercoat_public"),
        pool_pre_ping=True,
        pool_reset_on_return="rollback",
    )
    _connect_or_explain(
        engine,
        env_name="PUBLIC_DB_PASSWORD",
        role="evercoat_public",
        label="the anonymous public role",
    )
    yield engine
    engine.dispose()


@pytest.fixture(scope="session")
def agent_engine():
    """The agent tier's curation connection (migration 060).

    🔴 THE DRAFT-ONLY BOUNDARY TESTS MUST USE THIS AND NOTHING ELSE. The
    trigger reads `session_user`, so a test written against `owner_engine` or
    `app_engine` would find the boundary absent and report it as passing —
    the same trap `auth_engine` and `public_engine` exist to avoid.
    """
    engine = create_engine(
        _url("AGENT_DB_USER", "AGENT_DB_PASSWORD", "evercoat_agent"),
        pool_pre_ping=True,
        pool_reset_on_return="rollback",
    )
    _connect_or_explain(
        engine, env_name="AGENT_DB_PASSWORD", role="evercoat_agent", label="the agent role"
    )
    yield engine
    engine.dispose()


@pytest.fixture
def auth_session(auth_engine) -> Iterator[Session]:
    """Sign-in-role session. Rolls back, like every other session fixture.

    Asserts the role is not a superuser first, for the same reason
    ``app_session`` does: a misconfigured database that handed this role
    superuser would make every privilege assertion here vacuous, and vacuous
    green is worse than not running.
    """
    session = sessionmaker(bind=auth_engine)()
    session.begin()

    is_super = session.execute(
        text("SELECT rolsuper FROM pg_roles WHERE rolname = current_user")
    ).scalar_one()
    if is_super:
        session.rollback()
        session.close()
        pytest.fail(
            "the sign-in role is a superuser; it is supposed to hold EXECUTE "
            "on two functions and no table privilege at all"
        )

    try:
        yield session
    finally:
        session.rollback()
        session.close()


@pytest.fixture
def owner_session(owner_engine) -> Iterator[Session]:
    session = sessionmaker(bind=owner_engine)()
    session.begin()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


@pytest.fixture
def app_session(app_engine) -> Iterator[Session]:
    """Runtime-role session.

    Explicitly asserts the role is not a superuser before yielding. A
    misconfigured test database that hands out superuser would make every
    RLS assertion below vacuously pass, which is worse than the tests not
    running at all — they would report green while proving nothing.
    """
    session = sessionmaker(bind=app_engine)()
    session.begin()

    is_super = session.execute(
        text("SELECT rolsuper FROM pg_roles WHERE rolname = current_user")
    ).scalar_one()
    if is_super:
        session.rollback()
        session.close()
        pytest.fail(
            "the application role is a superuser; RLS is bypassed and every "
            "isolation assertion in this suite would pass vacuously"
        )

    try:
        yield session
    finally:
        session.rollback()
        session.close()


@pytest.fixture
def two_orgs(owner_session) -> tuple[uuid.UUID, uuid.UUID]:
    suffix = uuid.uuid4().hex[:8]
    ids = []
    for label in ("A", "B"):
        ids.append(
            owner_session.execute(
                text(
                    """
                    INSERT INTO core.organizations (code, name)
                    VALUES (:code, :name) RETURNING id
                    """
                ),
                {"code": f"TEST-{label}-{suffix}", "name": f"Test Org {label}"},
            ).scalar_one()
        )
    owner_session.flush()
    return ids[0], ids[1]


@pytest.fixture
def seeded_projects(owner_session) -> Iterator[tuple[uuid.UUID, uuid.UUID, uuid.UUID, uuid.UUID]]:
    """One organization, a normal project, a restricted project, a non-member.

    This fixture COMMITS, unlike the others, and cleans up explicitly.

    It has to. The visibility tests read through ``app_session``, which is
    a different connection — so uncommitted rows written by
    ``owner_session`` are invisible to it, and the test fails claiming RLS
    hid a project that was in fact never readable by anyone. That looks
    exactly like a policy bug and is not one, which is the sort of false
    signal that erodes trust in a suite.
    """
    suffix = uuid.uuid4().hex[:8]

    org_id = owner_session.execute(
        text("INSERT INTO core.organizations (code, name) VALUES (:c, :n) RETURNING id"),
        {"c": f"TEST-S-{suffix}", "n": "Scope Test Org"},
    ).scalar_one()

    normal = owner_session.execute(
        text(
            """
            INSERT INTO projects.projects
                (organization_id, project_code, name, confidentiality)
            VALUES (:o, :c, 'Normal project', 'normal') RETURNING id
            """
        ),
        {"o": org_id, "c": f"RDP-N-{suffix}"},
    ).scalar_one()

    restricted = owner_session.execute(
        text(
            """
            INSERT INTO projects.projects
                (organization_id, project_code, name, confidentiality)
            VALUES (:o, :c, 'Restricted project', 'restricted') RETURNING id
            """
        ),
        {"o": org_id, "c": f"RDP-R-{suffix}"},
    ).scalar_one()

    non_member = owner_session.execute(
        text(
            """
            INSERT INTO core.users (keycloak_sub, email, display_name)
            VALUES (:s, :e, 'Non Member') RETURNING id
            """
        ),
        {"s": str(uuid.uuid4()), "e": f"nonmember-{suffix}@example.test"},
    ).scalar_one()

    owner_session.commit()

    yield org_id, normal, restricted, non_member

    # Explicit teardown, because the commit above means rollback will not
    # do it. Order matters: children before parents, since every FK in the
    # thread is RESTRICT by design.
    owner_session.begin()
    owner_session.execute(
        text("DELETE FROM projects.project_members WHERE organization_id = :o"),
        {"o": org_id},
    )
    owner_session.execute(
        text("DELETE FROM projects.projects WHERE organization_id = :o"), {"o": org_id}
    )
    owner_session.execute(text("DELETE FROM core.users WHERE id = :u"), {"u": non_member})
    owner_session.execute(text("DELETE FROM core.organizations WHERE id = :o"), {"o": org_id})
    owner_session.commit()


@pytest.fixture
def one_audit_row(owner_session) -> int:
    return owner_session.execute(
        text(
            """
            INSERT INTO audit.events
                (action, entity_type, entity_id, reason, prev_hash, row_hash)
            VALUES ('test.seed', 'fixture', :eid, 'fixture row', '', '')
            RETURNING id
            """
        ),
        {"eid": str(uuid.uuid4())},
    ).scalar_one()


@pytest.fixture
def audit_chain(owner_session) -> list[int]:
    """Three linked events, so a break in the middle is detectable."""
    ids = []
    for i in range(3):
        ids.append(
            owner_session.execute(
                text(
                    """
                    INSERT INTO audit.events
                        (action, entity_type, entity_id, reason, prev_hash, row_hash)
                    VALUES ('test.chain', 'fixture', :eid, :reason, '', '')
                    RETURNING id
                    """
                ),
                {"eid": str(uuid.uuid4()), "reason": f"chain link {i}"},
            ).scalar_one()
        )
    owner_session.flush()
    return ids
