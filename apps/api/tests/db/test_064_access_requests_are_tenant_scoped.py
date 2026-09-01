"""064 — an access request belongs to an organization, at the database layer.

🔴 WHY A DATABASE TEST AND NOT ONLY A ROUTE TEST.

`tests/auth/test_admin_access_request_routes.py` proves that one tenant's
administrator cannot READ another tenant's applicant through the API. That is
the behaviour, and it is not the boundary: `CLAUDE.md` §6 requires PostgreSQL to
be an independent barrier, so the question this file asks is what the DATABASE
refuses when the application is out of the way entirely.

The distinction is not academic here. The first draft of 064 wrote the tenant
policy as `TO evercoat_app`, which under FORCE RLS locked `evercoat_owner` —
NOBYPASSRLS since 001 — out of the table completely: every SELECT returned
nothing and every INSERT was refused, and it surfaces as an empty queue rather
than as an error. Both reviewers found it; the route tests found it too, but
only by accident, because their fixture happens to write as the owner.

🔴 EVERY ASSERTION HERE IS FALSIFIED BY BREAKING THE DATABASE, NOT THE CODE.
Dropping `access_requests_org_scope` makes the cross-tenant test pass again;
restoring `TO evercoat_app` makes the owner test fail. Neither is reachable by
editing Python, which is the point.
"""

from __future__ import annotations

import uuid
from collections.abc import Iterator

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

pytestmark = [pytest.mark.db]


@pytest.fixture
def two_tenants(owner_session) -> Iterator[dict[str, uuid.UUID]]:
    """Two organizations and one access request belonging to the first."""
    sfx = uuid.uuid4().hex[:8]
    first = owner_session.execute(
        text("INSERT INTO core.organizations (code, name) VALUES (:c, :n) RETURNING id"),
        {"c": f"T064-A-{sfx}", "n": "Tenant A"},
    ).scalar_one()
    second = owner_session.execute(
        text("INSERT INTO core.organizations (code, name) VALUES (:c, :n) RETURNING id"),
        {"c": f"T064-B-{sfx}", "n": "Tenant B"},
    ).scalar_one()

    owner_session.execute(
        text("SELECT set_config('app.current_org', :org, false)"),
        {"org": str(first)},
    )
    request_id = owner_session.execute(
        text(
            """
            INSERT INTO public_intel.access_requests
                (organization_id, full_name, work_email, company)
            VALUES (:org, 'Tenant A Applicant', :e, 'A Coatings')
            RETURNING id
            """
        ),
        {"org": first, "e": f"t064-{sfx}@t064probe.org"},
    ).scalar_one()
    owner_session.commit()

    try:
        yield {"a": first, "b": second, "request": request_id, "suffix": sfx}
    finally:
        owner_session.rollback()
        owner_session.execute(
            text("SELECT set_config('app.current_org', :org, false)"), {"org": str(first)}
        )
        owner_session.execute(
            text("DELETE FROM public_intel.access_requests WHERE id = :i"),
            {"i": request_id},
        )
        owner_session.execute(
            text("DELETE FROM core.organizations WHERE id IN (:a, :b)"),
            {"a": first, "b": second},
        )
        owner_session.commit()


def test_the_table_is_force_rls_with_both_policies(owner_session) -> None:
    """The shape, asserted from the catalogue rather than from the migration.

    `ENABLE ROW LEVEL SECURITY` without `FORCE` leaves the owner exempt, which
    is how `testing.tests` ended up letting the golden scenario write with no
    tenant GUC at all (2026-08-31). Asserted here so a later migration cannot
    quietly relax it.
    """
    enabled, forced = owner_session.execute(
        text(
            "SELECT relrowsecurity, relforcerowsecurity FROM pg_class "
            "WHERE oid = 'public_intel.access_requests'::regclass"
        )
    ).one()
    assert enabled, "row level security is not enabled on access_requests"
    assert forced, (
        "RLS is enabled but not FORCED, so the owner is exempt -- which is how "
        "testing.tests let the golden scenario write with no tenant GUC at all"
    )

    policies = dict(
        owner_session.execute(
            text(
                "SELECT policyname, roles::text FROM pg_policies "
                "WHERE schemaname = 'public_intel' AND tablename = 'access_requests'"
            )
        ).all()
    )
    # 🔴 `{public}` MEANS "NO TO CLAUSE", i.e. the predicate governs every role.
    # A `TO evercoat_app` here locks the owner out under FORCE RLS — this exact
    # assertion is what the first draft of 064 would have failed.
    assert policies.get("access_requests_org_scope") == "{public}", (
        f"the tenant policy is restricted to {policies.get('access_requests_org_scope')!r}; "
        "a TO clause locks evercoat_owner (NOBYPASSRLS) out of the table"
    )
    assert policies.get("access_requests_public_insert") == "{evercoat_public}"


def test_a_tenant_cannot_read_another_tenants_request(owner_session, two_tenants) -> None:
    """The cross-tenant refusal, asserted BOTH ways.

    A one-directional assertion cannot tell "the policy works" apart from "the
    row does not exist" — this project has caught six guards that could not
    fail. So the same connection reads the same row twice, differing only in
    which tenant it claims to be.
    """
    owner_session.rollback()

    owner_session.execute(
        text("SELECT set_config('app.current_org', :org, false)"),
        {"org": str(two_tenants["a"])},
    )
    mine = owner_session.execute(
        text("SELECT count(*) FROM public_intel.access_requests WHERE id = :i"),
        {"i": two_tenants["request"]},
    ).scalar_one()
    assert mine == 1, "the owning tenant cannot see its own access request"

    owner_session.execute(
        text("SELECT set_config('app.current_org', :org, false)"),
        {"org": str(two_tenants["b"])},
    )
    theirs = owner_session.execute(
        text("SELECT count(*) FROM public_intel.access_requests WHERE id = :i"),
        {"i": two_tenants["request"]},
    ).scalar_one()
    assert theirs == 0, "another tenant can read this applicant's name and address"


def test_a_tenant_cannot_write_a_request_into_another_tenant(owner_session, two_tenants) -> None:
    """RLS stops the WRITE as well, which `WITH CHECK` is what provides.

    A policy with only `USING` filters reads and permits a caller to insert
    rows it then cannot see — a write-only hole that looks like nothing at all.
    """
    owner_session.rollback()
    owner_session.execute(
        text("SELECT set_config('app.current_org', :org, false)"),
        {"org": str(two_tenants["a"])},
    )
    with pytest.raises(DBAPIError) as refused:
        owner_session.execute(
            text(
                "INSERT INTO public_intel.access_requests"
                " (organization_id, full_name, work_email, company)"
                " VALUES (:org, 'Planted', 'planted@t064probe.org', 'Elsewhere')"
            ),
            {"org": two_tenants["b"]},
        )
    assert "row-level security" in str(refused.value).lower()
    owner_session.rollback()


def test_a_null_owner_is_readable_by_nobody(owner_session, two_tenants) -> None:
    """The pre-064 rows, and why they are refused by the predicate itself.

    `NULL = anything` is NULL, which a policy treats as false. That is the
    whole mechanism — there is no second rule anybody has to remember, and no
    route that pretends to count them.

    ⚠️ The row is planted as the SUPERUSER, because the policy that refuses it
    would also refuse its creation. That is the guard being consistent rather
    than an inconvenience.
    """
    owner_session.rollback()
    superuser_url = _superuser_url()
    if superuser_url is None:
        pytest.skip("MIGRATION_DATABASE_URL is not set, so no superuser connection exists")

    import psycopg

    planted: uuid.UUID
    with psycopg.connect(superuser_url) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO public_intel.access_requests"
                " (organization_id, full_name, work_email, company)"
                " VALUES (NULL, 'Unattributable', %s, 'Nowhere') RETURNING id",
                (f"t064-null-{two_tenants['suffix']}@t064probe.org",),
            )
            planted = cur.fetchone()[0]
        conn.commit()

    try:
        for tenant in ("a", "b"):
            owner_session.execute(
                text("SELECT set_config('app.current_org', :org, false)"),
                {"org": str(two_tenants[tenant])},
            )
            seen = owner_session.execute(
                text("SELECT count(*) FROM public_intel.access_requests WHERE id = :i"),
                {"i": planted},
            ).scalar_one()
            assert seen == 0, f"tenant {tenant} can read an unattributable request"
    finally:
        owner_session.rollback()
        with psycopg.connect(superuser_url) as conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM public_intel.access_requests WHERE id = %s", (planted,))
            conn.commit()


def _superuser_url() -> str | None:
    """The `MIGRATION_DATABASE_URL` role, as a libpq URL.

    Reading an unattributable row is a superuser act — `evercoat_owner` is
    NOBYPASSRLS and is governed by the same predicate, so it cannot see one
    either. An earlier comment in `admin.py` said "on the owner connection" and
    was wrong for exactly that reason.
    """
    import os

    raw = os.environ.get("MIGRATION_DATABASE_URL")
    if not raw:
        return None
    return raw.replace("postgresql+psycopg://", "postgresql://")


# ---------------------------------------------------------------------------
# 065 — the cross-tenant WRITE 064 left open
# ---------------------------------------------------------------------------


def test_the_public_role_can_only_write_into_an_opted_in_organization(
    owner_session, public_engine, two_tenants
) -> None:
    """🔴 064 CLOSED THE CROSS-TENANT READ AND LEFT THE WRITE OPEN.

    Codex, second pass: 064's public policy was
    `WITH CHECK (organization_id IS NOT NULL)`, and permissive policies are
    ORed — so the anonymous role could plant an applicant row into any
    organization it could name, bypassing the tenant predicate entirely. That
    is the half-a-boundary shape this project has closed before: a `USING`
    without a matching `WITH CHECK` filters reads and permits writes.

    065 narrows it to organizations that have said they accept public access
    requests. The database cannot ask `evercoat_public` "is this YOUR
    organization" — it has no identity and any GUC it could set it could also
    lie about — but it can ask whether the TARGET opted in, which is a property
    of the organization and not of the caller.

    🔴 ASSERTED IN BOTH DIRECTIONS, because a refusal test alone cannot tell
    "the policy works" from "the insert was broken anyway".
    """
    marker = f"opt-in-{uuid.uuid4()}@t065probe.org"

    # Neither tenant has opted in yet: both must be refused.
    for tenant in ("a", "b"):
        with (
            public_engine.begin() as conn,
            pytest.raises(DBAPIError, match="row-level security"),
        ):
            conn.execute(
                text(
                    "INSERT INTO public_intel.access_requests"
                    " (organization_id, full_name, work_email, company)"
                    " VALUES (:o, 'T', :e, 'C')"
                ),
                {"o": two_tenants[tenant], "e": marker},
            )

    # Opt ONE of them in, and only that one becomes writable.
    owner_session.rollback()
    owner_session.execute(
        text("UPDATE core.organizations SET accepts_public_access_requests = true WHERE id = :o"),
        {"o": two_tenants["a"]},
    )
    owner_session.commit()

    try:
        with public_engine.begin() as conn:
            conn.execute(
                text(
                    "INSERT INTO public_intel.access_requests"
                    " (organization_id, full_name, work_email, company)"
                    " VALUES (:o, 'T', :e, 'C')"
                ),
                {"o": two_tenants["a"], "e": marker},
            )

        # ...and the one that did NOT opt in is still refused, on the same
        # connection, in the same run. This is the half that makes the test
        # falsifiable: dropping the opt-in check makes it go red while the
        # positive case above stays green.
        with (
            public_engine.begin() as conn,
            pytest.raises(DBAPIError, match="row-level security"),
        ):
            conn.execute(
                text(
                    "INSERT INTO public_intel.access_requests"
                    " (organization_id, full_name, work_email, company)"
                    " VALUES (:o, 'T', :e, 'C')"
                ),
                {"o": two_tenants["b"], "e": marker},
            )
    finally:
        owner_session.rollback()
        owner_session.execute(
            text("SELECT set_config('app.current_org', :o, false)"),
            {"o": str(two_tenants["a"])},
        )
        owner_session.execute(
            text("DELETE FROM public_intel.access_requests WHERE work_email = :e"),
            {"e": marker},
        )
        owner_session.commit()


def test_the_anonymous_role_cannot_read_the_organization_list(public_engine) -> None:
    """The opt-in check must not have handed the public role a tenant directory.

    065 could have been written as `EXISTS (SELECT 1 FROM core.organizations ...)`
    inside the policy — but a policy predicate runs with the CALLER's
    privileges, so that would have required granting `evercoat_public` SELECT
    on `core.organizations`: giving the anonymous role a readable list of every
    tenant in order to stop it writing to them. The SECURITY DEFINER function
    exists so that grant is not needed, and this asserts it was not made.
    """
    with (
        public_engine.connect() as conn,
        pytest.raises(DBAPIError, match="permission denied"),
    ):
        conn.execute(text("SELECT count(*) FROM core.organizations"))
