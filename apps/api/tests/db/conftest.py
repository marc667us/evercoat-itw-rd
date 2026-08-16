# -*- coding: utf-8 -*-
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
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
    except Exception as exc:  # noqa: BLE001
        pytest.skip(f"no application-role connection available: {exc}")
    yield engine
    engine.dispose()


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
    owner_session.execute(
        text("DELETE FROM core.organizations WHERE id = :o"), {"o": org_id}
    )
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
