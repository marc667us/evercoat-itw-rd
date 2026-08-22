"""I19 — the database refuses rows when no tenant context is set.

Before migration 032, `core.rls_permissive()` returned TRUE and every policy
read `USING (core.rls_permissive() AND core.current_org_id() IS NULL OR
<predicate>)`. With no GUC the left branch was TRUE, so the runtime role read
**every tenant's rows**: 119 organizations and 137 projects when measured on
2026-08-22.

These tests are written against the *behaviour a connection sees*, not against
the function's return value, because the return value is a detail and the
behaviour is the security property. `test_the_hatch_itself_is_shut` is the one
exception, and it exists to name the cause when the behavioural tests fail.
"""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import text

# Tables chosen for spread rather than convenience: one core table, one
# project-scoped table, and one deep in the digital thread. A policy fixed on
# `core` and missed on `testing` would pass a narrower test.
TENANT_TABLES = [
    "core.organizations",
    "projects.projects",
    "formulations.formulas",
    "testing.tests",
]


def test_the_hatch_itself_is_shut(owner_session) -> None:
    """`core.rls_permissive()` is FALSE.

    Not the security property -- the behavioural tests below are that. This
    exists so that when they fail, the failure names the cause in one line
    instead of sending the next reader through eight migrations of policy
    predicates.
    """
    value = owner_session.execute(text("SELECT core.rls_permissive()")).scalar_one()
    assert value is False, (
        "core.rls_permissive() is TRUE. Every RLS policy in this database "
        "admits every row whenever the app.current_org GUC is absent, so the "
        "runtime role can read every tenant. See migration 032."
    )


@pytest.mark.parametrize("table", TENANT_TABLES)
def test_no_tenant_context_means_no_rows(app_engine, table: str) -> None:
    """The runtime role, with no GUC, sees nothing.

    This is I19 stated as an observation. It runs as `evercoat_app`, which
    does not own the tables and does not hold BYPASSRLS, so policies apply.

    🔴 Proved by falsification: with `core.rls_permissive()` restored to
    SELECT TRUE, this returns 119 for core.organizations and 137 for
    projects.projects instead of 0.
    """
    with app_engine.connect() as conn:
        # Deliberately no `SET LOCAL app.current_org`. That absence is the
        # entire test: it simulates any code path that reaches a connection
        # without going through session_scope().
        # S608 is suppressed below: a table NAME cannot be a bind parameter in
        # SQL, and `table` comes from the hardcoded TENANT_TABLES list above,
        # never from input. Parametrising the value here is not possible.
        count = conn.execute(text(f"SELECT count(*) FROM {table}")).scalar_one()  # noqa: S608

    assert count == 0, (
        f"{table} returned {count} rows to evercoat_app with NO organization "
        "context set. Any code path that reaches a connection without "
        "session_scope() -- a worker, a health probe, an exception handler, a "
        "future route -- reads across every tenant."
    )


def test_setting_the_tenant_reveals_exactly_that_tenant(app_engine, owner_session) -> None:
    """Closing the hatch must not close the door.

    A fail-closed database that is closed to everybody is not a security
    improvement, it is an outage. This asserts the positive half: with the GUC
    set, the runtime role sees that organization and only that organization.
    """
    orgs = owner_session.execute(
        text("SELECT id FROM core.organizations ORDER BY created_at LIMIT 2")
    ).all()
    if len(orgs) < 2:
        pytest.skip(
            "needs two seeded organizations to prove isolation rather than merely visibility"
        )
    first, second = orgs[0][0], orgs[1][0]

    with app_engine.connect() as conn:
        conn.execute(text("SELECT set_config('app.current_org', :o, false)"), {"o": str(first)})
        visible = conn.execute(text("SELECT id FROM core.organizations")).scalars().all()

    assert first in visible, (
        "the runtime role could not see its OWN organization with the GUC "
        "set. Migration 032 has closed the database to everyone, not just to "
        "callers without context."
    )
    assert second not in visible, (
        "another organization was visible while scoped to the first. The "
        "policy predicate is not filtering on organization_id."
    )
    assert len(visible) == 1, f"expected exactly 1 organization, saw {len(visible)}"


def test_an_unknown_tenant_reveals_nothing(app_engine) -> None:
    """A GUC set to a tenant that does not exist yields zero rows, not all rows.

    The failure mode being ruled out is a predicate that treats "no match" as
    "no filter" -- which is how the hatch behaved, and is a mistake easy to
    reintroduce when a policy is rewritten by hand.
    """
    with app_engine.connect() as conn:
        conn.execute(
            text("SELECT set_config('app.current_org', :o, false)"),
            {"o": str(uuid.uuid4())},
        )
        count = conn.execute(text("SELECT count(*) FROM projects.projects")).scalar_one()

    assert count == 0, f"an organization id that exists nowhere returned {count} projects."


def test_sign_in_still_works(owner_session) -> None:
    """🔴 The thing migration 032 was shaped to avoid breaking.

    `core.memberships_for_subject` is the ONE lookup that runs before a tenant
    is chosen -- it is what tells a signed-in browser which organizations it
    may ask for, and every other route requires `X-Organization-Id`. It is
    SECURITY DEFINER and owned by `evercoat_owner`, so it is exempt from
    policies **only while FORCE ROW LEVEL SECURITY is off**.

    That is why 032 changes `rls_permissive()` and does NOT enable FORCE.

    ⚠️ THIS TEST BUILDS ITS OWN SUBJECT. The first version read a seeded user
    and **failed in CI**, whose database is migrated but not seeded -- and it
    failed with the message *"sign-in is broken"*, which was false. A test that
    reports a security regression when the real cause is an empty table is
    worse than no test: it sends the next reader hunting a defect that is not
    there. Everything it needs is created here and rolled back.
    """
    sub = f"kc-{uuid.uuid4().hex[:12]}"
    org = owner_session.execute(
        text(
            "INSERT INTO core.organizations (code, name) VALUES (:c, 'Sign-in probe') RETURNING id"
        ),
        {"c": f"SIGNIN-{uuid.uuid4().hex[:8]}"},
    ).scalar_one()
    user = owner_session.execute(
        text(
            "INSERT INTO core.users (keycloak_sub, email, display_name) "
            "VALUES (:s, :e, 'Sign-in probe') RETURNING id"
        ),
        {"s": sub, "e": f"{sub}@example.invalid"},
    ).scalar_one()
    owner_session.execute(
        text(
            "INSERT INTO core.organization_members (organization_id, user_id, status) "
            "VALUES (:o, :u, 'active')"
        ),
        {"o": org, "u": user},
    )
    owner_session.flush()

    rows = owner_session.execute(
        text("SELECT * FROM core.memberships_for_subject(:s)"), {"s": sub}
    ).all()

    assert rows, (
        "core.memberships_for_subject returned NOTHING for a subject that is "
        "an active member of an active organization. Sign-in is broken: "
        "/api/me will 404 for every user and no browser can learn an "
        "organization id. If FORCE ROW LEVEL SECURITY was just enabled, that "
        "is the cause -- grant evercoat_owner BYPASSRLS or add a policy "
        "admitting this lookup, in the same migration."
    )


def test_the_owner_is_still_exempt(owner_session) -> None:
    """Migrations, backfills and the seeder must keep working.

    `evercoat_owner` owns every table and FORCE is off, so it is exempt from
    its own policies. 032's safety argument rests entirely on this. If it ever
    stops being true, every migration that backfills data breaks at once --
    the failure this project already logged as "LOCAL IS SUPERUSER, RENDER IS
    NOT".

    ⚠️ Writes its own row for the same reason as the test above: the first
    version counted seeded organizations and **failed in CI on an unseeded
    database**, announcing that the owner exemption was gone when it was
    intact.
    """
    code = f"EXEMPT-{uuid.uuid4().hex[:8]}"
    owner_session.execute(
        text("INSERT INTO core.organizations (code, name) VALUES (:c, 'Owner exemption probe')"),
        {"c": code},
    )
    owner_session.flush()

    # No GUC is set anywhere in this test. The owner must still see its row.
    seen = owner_session.execute(
        text("SELECT count(*) FROM core.organizations WHERE code = :c"), {"c": code}
    ).scalar_one()

    assert seen == 1, (
        "evercoat_owner cannot read a row it just wrote, with no GUC set. The "
        "owner exemption is gone -- check whether FORCE ROW LEVEL SECURITY was "
        "enabled. Every migration backfill and scripts/seed.py depend on it."
    )
