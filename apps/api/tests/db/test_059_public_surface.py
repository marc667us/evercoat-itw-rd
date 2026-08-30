"""Migration 059 — the anonymous public surface, asserted against a real database.

🔴 EVERY TEST HERE ASSERTS BOTH DIRECTIONS.

A test that only proves `evercoat_public` cannot read `competitors.products`
passes for a role that can read nothing at all -- including the catalogue it
exists to serve. A test that only proves the views return rows passes for a
role that can also read every tenant. Neither half is a guard on its own.

The falsification for the privilege cases is a DATABASE change, not a code
change: granting USAGE on `core` and watching these go red. Recorded in
`reviews/adjudication-059-public-landing-2026-08-30.md`.
"""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError, ProgrammingError

pytestmark = pytest.mark.db


# The complete set of relations `evercoat_public` may touch, mirroring the
# allowlist the migration asserts. Duplicated deliberately: if a future
# migration widens the grant and updates its own allowlist to match, this
# independent copy still fails.
ALLOWED = {
    ("public_intel", "v_manufacturers"),
    ("public_intel", "v_products"),
    ("public_intel", "v_product_documents"),
    ("public_intel", "v_news_categories"),
    ("public_intel", "v_news_items"),
    ("public_intel", "access_requests"),
}

TENANT_TABLES = [
    "competitors.products",
    "materials.materials",
    "core.users",
    "formulations.formulas",
    "projects.projects",
]


@pytest.mark.parametrize("table", TENANT_TABLES)
def test_public_role_cannot_read_any_tenant_table(public_engine, table: str) -> None:
    """The refusal half. A public connection has no tenant to be scoped to.

    🔴 `match=` IS NOT DECORATION HERE. Without it this passes when the table
    does not exist, when the schema was renamed, or when the connection is
    broken -- all of which raise, and none of which prove a privilege boundary.
    The refusal has to come from the GRANT.

    ⚠️ AND THIS TEST IS DEFENCE IN DEPTH, NOT THE LOAD-BEARING GUARD. Measured
    while falsifying it: granting `evercoat_public` USAGE on `core` AND SELECT
    on `core.users` did **not** turn this red. The read still failed -- with
    "permission denied for table organization_members", because `core.users`'
    RLS policy reads that table and evaluating the policy needs privilege on it
    too. So a real, dangerous grant can leave this case green by accident.

    What actually caught it was
    :func:`test_public_role_reaches_nothing_outside_its_allowlist`, which asks
    the catalogue what the role can touch rather than trying one read. Keep
    both, and know which one is doing the work.
    """
    with (
        public_engine.connect() as conn,
        pytest.raises(ProgrammingError, match="permission denied"),
    ):
        conn.execute(text(f"SELECT count(*) FROM {table}"))  # noqa: S608 - module constant


@pytest.mark.parametrize(
    "view",
    [
        "v_manufacturers",
        "v_products",
        "v_product_documents",
        "v_news_categories",
        "v_news_items",
    ],
)
def test_public_role_can_read_every_published_view(public_engine, view: str) -> None:
    """The serving half — without which the refusals above prove nothing."""
    with public_engine.connect() as conn:
        conn.execute(
            # The suppression sits on the interpolation itself: `view`
            # comes from this file's own parametrize list, never a caller.
            text(f"SELECT count(*) FROM public_intel.{view}")  # noqa: S608
        ).scalar_one()


def test_public_role_cannot_read_the_base_tables_behind_the_views(public_engine) -> None:
    """The views are the projection boundary, so the tables stay unreachable.

    If the base tables were readable, the `publication_status` predicate in the
    view would be a suggestion: a caller would simply select around it and read
    every draft.
    """
    for table in ("products", "manufacturers", "news_items", "product_documents"):
        with (
            public_engine.connect() as conn,
            pytest.raises(ProgrammingError, match="permission denied"),
        ):
            conn.execute(
                text(f"SELECT count(*) FROM public_intel.{table}")  # noqa: S608
            )


def test_the_access_request_queue_is_insert_only(public_engine, owner_engine) -> None:
    """Anonymous callers may apply; they may not read who else has.

    SELECT here would be an enumeration primitive over names, work addresses
    and employers -- personal data, submitted by people who are not users.
    """
    with (
        public_engine.connect() as conn,
        pytest.raises(ProgrammingError, match="permission denied"),
    ):
        conn.execute(text("SELECT count(*) FROM public_intel.access_requests"))

    # And the write it IS allowed actually lands, so the refusal above is not
    # simply "this role can do nothing with this table".
    marker = f"insert-only-{uuid.uuid4()}@example.test"
    with public_engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO public_intel.access_requests "
                "(full_name, work_email, company) VALUES ('T', :e, 'C')"
            ),
            {"e": marker},
        )
    try:
        with owner_engine.connect() as conn:
            found = conn.execute(
                text("SELECT count(*) FROM public_intel.access_requests WHERE work_email = :e"),
                {"e": marker},
            ).scalar_one()
        assert found == 1
    finally:
        with owner_engine.begin() as conn:
            conn.execute(
                text("DELETE FROM public_intel.access_requests WHERE work_email = :e"),
                {"e": marker},
            )


def test_public_role_reaches_nothing_outside_its_allowlist(owner_engine) -> None:
    """An inventory, not a spot check.

    Codex: a single negative test on one table passes while the role can reach
    anything else that was overlooked. This asks the database what the role can
    ACTUALLY touch, anywhere, and compares the whole set.
    """
    with owner_engine.connect() as conn:
        rows = conn.execute(
            text(
                """
                SELECT n.nspname, c.relname
                  FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
                 WHERE c.relkind IN ('r','v','m','p','f')
                   AND n.nspname NOT IN ('pg_catalog','information_schema')
                   AND (has_table_privilege('evercoat_public', c.oid, 'SELECT')
                     OR has_table_privilege('evercoat_public', c.oid, 'INSERT')
                     OR has_table_privilege('evercoat_public', c.oid, 'UPDATE')
                     OR has_table_privilege('evercoat_public', c.oid, 'DELETE'))
                """
            )
        ).all()
    assert {(r.nspname, r.relname) for r in rows} == ALLOWED


def test_public_role_has_schema_usage_nowhere_else(owner_engine) -> None:
    """Schema USAGE is what makes a granted EXECUTE callable.

    PostgreSQL grants EXECUTE to PUBLIC on new functions by default, so the
    role holds EXECUTE on roughly 230 of them. What keeps `core.current_org_id`
    and every trigger function out of reach is that it has USAGE on neither
    `core` nor any other application schema.
    """
    with owner_engine.connect() as conn:
        rows = conn.execute(
            text(
                """
                SELECT nspname FROM pg_namespace
                 WHERE nspname NOT LIKE 'pg\\_%' ESCAPE '\\'
                   AND nspname <> 'information_schema'
                   AND has_schema_privilege('evercoat_public', nspname, 'USAGE')
                """
            )
        ).all()
    assert {r.nspname for r in rows} == {"public", "public_intel"}


def test_no_security_definer_function_is_reachable(owner_engine) -> None:
    """A SECURITY DEFINER function runs as its OWNER.

    One reachable from the public connection would bypass every grant asserted
    above, which is why this is checked separately from the EXECUTE inventory.
    """
    with owner_engine.connect() as conn:
        rows = conn.execute(
            text(
                """
                SELECT n.nspname, p.proname
                  FROM pg_proc p JOIN pg_namespace n ON n.oid = p.pronamespace
                 WHERE n.nspname NOT IN ('pg_catalog','information_schema')
                   AND p.prosecdef
                   AND has_function_privilege('evercoat_public', p.oid, 'EXECUTE')
                   AND has_schema_privilege('evercoat_public', n.nspname, 'USAGE')
                """
            )
        ).all()
    assert rows == []


def test_public_views_depend_on_nothing_outside_public_intel(owner_engine) -> None:
    """The views run as `evercoat_owner`, so their dependencies ARE the boundary.

    These views deliberately do not set `security_invoker` -- that is what lets
    the public role read them without any base-table privilege. The cost is
    that a later join to a tenant table would read across every tenant and
    serve it anonymously, with nothing else failing. Asked of `pg_depend`
    rather than trusted to a comment.
    """
    with owner_engine.connect() as conn:
        rows = conn.execute(
            text(
                """
                SELECT DISTINCT v.relname AS view_name, tn.nspname AS dep_schema,
                                t.relname AS dep_relation
                  FROM pg_class v
                  JOIN pg_namespace vn ON vn.oid = v.relnamespace
                  JOIN pg_rewrite  r  ON r.ev_class = v.oid
                  JOIN pg_depend   d  ON d.objid = r.oid
                                     AND d.classid = 'pg_rewrite'::regclass
                                     AND d.refclassid = 'pg_class'::regclass
                  JOIN pg_class    t  ON t.oid = d.refobjid
                  JOIN pg_namespace tn ON tn.oid = t.relnamespace
                 WHERE vn.nspname = 'public_intel' AND v.relkind = 'v'
                   AND t.oid <> v.oid AND tn.nspname <> 'public_intel'
                   AND tn.nspname NOT IN ('pg_catalog','information_schema')
                """
            )
        ).all()
    assert rows == [], (
        "a public view joins a relation outside public_intel; because these "
        "views run as the owner, that is an anonymous cross-tenant read"
    )


def test_the_views_do_not_carry_security_invoker(owner_engine) -> None:
    """The inversion is deliberate and must not be 'corrected'.

    Migration 037 makes `security_invoker = true` load-bearing so a view runs
    as the CALLER and RLS applies per tenant. These need the opposite: run as
    the owner so the public role needs no base-table privilege. A reviewer
    applying house convention here would either dissolve the boundary or force
    granting table access, so the intent is asserted rather than commented.
    """
    with owner_engine.connect() as conn:
        rows = conn.execute(
            text(
                """
                SELECT c.relname,
                       coalesce('security_invoker=true' = ANY(c.reloptions), false) AS inv
                  FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
                 WHERE n.nspname = 'public_intel' AND c.relkind = 'v'
                """
            )
        ).all()
    assert rows, "no public_intel views exist"
    assert all(not r.inv for r in rows), (
        "a public view set security_invoker=true; it would then run as "
        "evercoat_public, which holds no privilege on the base tables"
    )


@pytest.mark.parametrize(
    ("origin", "demo", "source_url", "verification", "accepted"),
    [
        # A synthetic row may be published only if it says it is demonstration
        # data. This is the case whose first implementation COULD NOT FAIL:
        # the CHECK evaluated to NULL when the flag was NULL, and PostgreSQL
        # accepts a NULL CHECK.
        ("synthetic", False, None, "unreviewed", False),
        ("synthetic", True, None, "unreviewed", True),
        # Source-derived needs a source and a review.
        ("source_derived", False, None, "unreviewed", False),
        ("source_derived", False, "https://example.test/a", "unreviewed", False),
        ("source_derived", False, "https://example.test/a", "reviewed", True),
        # "verified" is the strongest claim and needs the most.
        ("verified", False, "https://example.test/a", "reviewed", False),
    ],
)
def test_publication_invariant(
    owner_engine,
    origin: str,
    demo: bool,
    source_url: str | None,
    verification: str,
    accepted: bool,
) -> None:
    """Published content must be honest about where it came from.

    🔴 THE DEFAULT MUST NOT BE NULLABLE. `is_demonstration_data` is NOT NULL
    DEFAULT false precisely so the implication below can never evaluate to
    NULL, because a NULL CHECK is a CHECK that admits everything.
    """
    name = f"__inv_{uuid.uuid4()}__"
    statement = text(
        """
        INSERT INTO public_intel.manufacturers
            (name, content_origin, publication_status, is_demonstration_data,
             source_url, verification_status)
        VALUES (:name, cast(:origin AS public_intel.content_origin), 'published',
                :demo, :source_url,
                cast(:verification AS public_intel.verification_status))
        """
    )
    params = {
        "name": name,
        "origin": origin,
        "demo": demo,
        "source_url": source_url,
        "verification": verification,
    }
    if accepted:
        with owner_engine.begin() as conn:
            conn.execute(statement, params)
            conn.execute(
                text("DELETE FROM public_intel.manufacturers WHERE name = :n"), {"n": name}
            )
    else:
        # 🔴 `match=` NAMES THE CONSTRAINT. Without it this passes when the row
        # is refused by a NOT NULL, a bad enum cast, or a unique violation --
        # none of which is the invariant under test.
        with (
            owner_engine.begin() as conn,
            pytest.raises(IntegrityError, match="publication_is_honest"),
        ):
            conn.execute(statement, params)


def test_competitors_products_gained_only_a_nullable_link(owner_engine) -> None:
    """The tenant side gets one nullable column and no reverse projection."""
    with owner_engine.connect() as conn:
        row = conn.execute(
            text(
                """
                SELECT is_nullable, data_type FROM information_schema.columns
                 WHERE table_schema = 'competitors' AND table_name = 'products'
                   AND column_name = 'public_product_id'
                """
            )
        ).one()
    assert row.is_nullable == "YES"
    assert row.data_type == "uuid"
