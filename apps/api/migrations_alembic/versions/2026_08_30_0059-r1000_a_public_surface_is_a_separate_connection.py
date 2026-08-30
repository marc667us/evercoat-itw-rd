"""a public surface is a separate connection, not a flag

Revision ID: r1000
Revises: q1000
Created: 2026-08-30

The public landing page, the Global Competitor Product Marketplace and the
Global Competitor Industry News Feed: a new non-tenanted `public_intel`
schema, read by a new `evercoat_public` role that holds no table privilege
anywhere and cannot reach a tenant row.

🔴 EVERY ASSERTION BELOW EXISTS BECAUSE A REVIEW FOUND THE GAP IT COVERS.

- The privilege probe is an INVENTORY, not a spot check. Codex: "the
  privilege test is radically too narrow for a role that inherits
  database-wide PUBLIC privileges" -- PostgreSQL grants EXECUTE on new
  functions to PUBLIC by default, and this repository has twice treated
  that as a live vulnerability (027, 053). One negative test on one table
  would have passed while the role could call anything.

- The `pg_depend` probe exists because an owner-owned view runs with the
  OWNER's privileges. Today these views touch only `public_intel`. A later
  join to a tenant table would read across every tenant, anonymously, and
  nothing else would fail. A comment asking the next person not to do that
  is not a control.

- The CHECK is falsified here, in the migration, by attempting a write that
  must fail. The first draft's constraint could not fail at all: it
  evaluated to NULL when the flag was NULL, and PostgreSQL accepts a NULL
  CHECK. Asserting the constraint EXISTS would not have caught that. This
  asserts it REFUSES.
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op
from sqlalchemy import text

from migrations_alembic._sql import apply_sql

revision: str = "r1000"
down_revision: str | None = "q1000"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


# The complete set of objects `evercoat_public` may touch. Anything else it
# can reach is a defect, and the inventory below says which.
ALLOWED_RELATIONS = {
    ("public_intel", "v_manufacturers"),
    ("public_intel", "v_products"),
    ("public_intel", "v_product_documents"),
    ("public_intel", "v_news_categories"),
    ("public_intel", "v_news_items"),
    ("public_intel", "access_requests"),  # INSERT only; asserted below
}


def upgrade() -> None:
    apply_sql("059_a_public_surface_is_a_separate_connection.sql")

    bind = op.get_bind()

    # -----------------------------------------------------------------
    # 1. The role is what this migration assumes it is.
    #
    # `CREATE ROLE IF NOT EXISTS` is idempotent about EXISTENCE and silent
    # about CAPABILITY. A role somebody else created, or one left by a
    # downgrade, keeps whatever it had. NOINHERIT is the load-bearing one:
    # without it a group membership hands this role that group's
    # privileges on a connection that has no tenant.
    # -----------------------------------------------------------------
    attrs = bind.execute(
        text(
            """
            SELECT rolsuper, rolcreatedb, rolcreaterole, rolbypassrls,
                   rolreplication, rolinherit, rolcanlogin
              FROM pg_roles WHERE rolname = 'evercoat_public'
            """
        )
    ).one_or_none()
    if attrs is None:
        raise RuntimeError("evercoat_public was not created")
    wrong = [
        name
        for name, value, want in (
            ("rolsuper", attrs.rolsuper, False),
            ("rolcreatedb", attrs.rolcreatedb, False),
            ("rolcreaterole", attrs.rolcreaterole, False),
            ("rolbypassrls", attrs.rolbypassrls, False),
            ("rolreplication", attrs.rolreplication, False),
            ("rolinherit", attrs.rolinherit, False),
            # NOLOGIN: granting LOGIN and a password is the deployment's
            # job. A migration that baked one in would put a credential in
            # the repository.
            ("rolcanlogin", attrs.rolcanlogin, False),
        )
        if value != want
    ]
    if wrong:
        raise RuntimeError(
            f"evercoat_public has the wrong attributes: {', '.join(wrong)}. "
            "NOINHERIT and NOBYPASSRLS are load-bearing -- without them this "
            "role can reach tenant rows on a connection that has no tenant."
        )

    # -----------------------------------------------------------------
    # 2. THE INVENTORY. Not "can it read competitors.products" -- what CAN
    #    it reach, anywhere in the database, and is that exactly the
    #    allowlist?
    # -----------------------------------------------------------------
    reachable = bind.execute(
        text(
            """
            SELECT n.nspname, c.relname
              FROM pg_class c
              JOIN pg_namespace n ON n.oid = c.relnamespace
             WHERE c.relkind IN ('r', 'v', 'm', 'p', 'f')
               AND n.nspname NOT IN ('pg_catalog', 'information_schema')
               AND (
                    has_table_privilege('evercoat_public', c.oid, 'SELECT')
                 OR has_table_privilege('evercoat_public', c.oid, 'INSERT')
                 OR has_table_privilege('evercoat_public', c.oid, 'UPDATE')
                 OR has_table_privilege('evercoat_public', c.oid, 'DELETE')
               )
            """
        )
    ).all()
    actual = {(r.nspname, r.relname) for r in reachable}
    unexpected = actual - ALLOWED_RELATIONS
    if unexpected:
        raise RuntimeError(
            "evercoat_public can reach relations outside its allowlist: "
            f"{sorted(unexpected)}. A public connection that can read a "
            "tenant table is an anonymous cross-tenant disclosure."
        )
    missing = ALLOWED_RELATIONS - actual
    if missing:
        raise RuntimeError(
            f"evercoat_public cannot reach {sorted(missing)} -- the public "
            "surface would return nothing and look like an empty catalogue."
        )

    # The write is INSERT-only. If it could SELECT, an anonymous caller
    # could enumerate everyone who has requested access.
    for privilege, want in (("SELECT", False), ("UPDATE", False), ("DELETE", False), ("INSERT", True)):
        got = bind.execute(
            text(
                "SELECT has_table_privilege('evercoat_public', "
                "'public_intel.access_requests', :p)"
            ),
            {"p": privilege},
        ).scalar_one()
        if got != want:
            raise RuntimeError(
                f"evercoat_public has {privilege}={got} on access_requests, "
                f"expected {want}. INSERT-only is what stops an anonymous "
                "caller enumerating who has applied."
            )

    # -----------------------------------------------------------------
    # 3. Functions.
    #
    # 🔴 THE FIRST VERSION OF THIS PROBE WAS WRONG, AND FAILED THE
    #    MIGRATION ON ITS FIRST RUN -- CORRECTLY, BUT FOR A REASON THAT
    #    WOULD NEVER HAVE GONE GREEN.
    #
    # It asked `has_function_privilege` alone and found ~230 functions,
    # because PostgreSQL grants EXECUTE to PUBLIC by default. But EXECUTE
    # is not reachability: calling a function ALSO needs USAGE on its
    # schema. Measured, `evercoat_public` holds USAGE on `public` only --
    # so `core.current_org_id` and every trigger function are already
    # unreachable, and a probe demanding zero EXECUTE could never pass
    # without revoking PUBLIC's grant across the whole database.
    #
    # The invariant that actually matters, and that a future change could
    # really break, is: NOTHING IN AN APPLICATION SCHEMA IS REACHABLE, AND
    # NO `SECURITY DEFINER` FUNCTION IS REACHABLE ANYWHERE. The 201
    # reachable functions in `public` are pgvector/pgcrypto/citext, none of
    # them SECURITY DEFINER -- and `gen_random_uuid()` among them is
    # REQUIRED, because it is the default on `access_requests.id` and runs
    # as the inserting role.
    #
    # This fails if anyone grants `evercoat_public` USAGE on an application
    # schema, or adds a SECURITY DEFINER function to `public`.
    # -----------------------------------------------------------------
    reachable_fns = bind.execute(
        text(
            """
            SELECT n.nspname, p.proname, p.prosecdef
              FROM pg_proc p
              JOIN pg_namespace n ON n.oid = p.pronamespace
             WHERE n.nspname NOT IN ('pg_catalog', 'information_schema')
               AND has_function_privilege('evercoat_public', p.oid, 'EXECUTE')
               AND has_schema_privilege('evercoat_public', n.nspname, 'USAGE')
             ORDER BY 1, 2
            """
        )
    ).all()

    # `public` holds the extensions and nothing of ours. Every other schema
    # in this database is an application schema.
    in_app_schema = [
        (r.nspname, r.proname) for r in reachable_fns
        if r.nspname not in ("public", "public_intel")
    ]
    if in_app_schema:
        raise RuntimeError(
            "evercoat_public can reach application functions "
            f"{in_app_schema}. The public connection has no tenant, so a "
            "function that reads one answers a question it was never asked."
        )

    definers = [(r.nspname, r.proname) for r in reachable_fns if r.prosecdef]
    if definers:
        raise RuntimeError(
            f"evercoat_public can EXECUTE SECURITY DEFINER functions {definers}. "
            "Such a function runs as its OWNER, which bypasses every grant "
            "asserted above."
        )

    # And the boundary it depends on: USAGE nowhere but `public` and
    # `public_intel`. This is the assertion that makes the two above mean
    # something -- without it they pass by accident.
    usable_schemas = {
        r.nspname
        for r in bind.execute(
            text(
                """
                SELECT nspname FROM pg_namespace
                 WHERE nspname NOT LIKE 'pg\\_%' ESCAPE '\\'
                   AND nspname <> 'information_schema'
                   AND has_schema_privilege('evercoat_public', nspname, 'USAGE')
                """
            )
        ).all()
    }
    if usable_schemas != {"public", "public_intel"}:
        raise RuntimeError(
            f"evercoat_public has schema USAGE on {sorted(usable_schemas)}; "
            "expected exactly {'public', 'public_intel'}. Schema USAGE is what "
            "makes a granted EXECUTE actually callable."
        )

    # -----------------------------------------------------------------
    # 4. THE VIEWS TOUCH NOTHING TENANTED.
    #
    # These views deliberately do NOT set `security_invoker`, so they run
    # as `evercoat_owner`. That is safe only while every relation they read
    # is itself public. Asked of `pg_depend`, so a later join to a tenant
    # table fails this migration instead of leaking silently.
    # -----------------------------------------------------------------
    foreign = bind.execute(
        text(
            """
            SELECT DISTINCT v.relname AS view_name,
                            tn.nspname AS dep_schema,
                            t.relname  AS dep_relation
              FROM pg_class v
              JOIN pg_namespace vn ON vn.oid = v.relnamespace
              JOIN pg_rewrite  r  ON r.ev_class = v.oid
              JOIN pg_depend   d  ON d.objid = r.oid
                                 AND d.classid = 'pg_rewrite'::regclass
                                 AND d.refclassid = 'pg_class'::regclass
              JOIN pg_class    t  ON t.oid = d.refobjid
              JOIN pg_namespace tn ON tn.oid = t.relnamespace
             WHERE vn.nspname = 'public_intel'
               AND v.relkind = 'v'
               AND t.oid <> v.oid
               AND tn.nspname <> 'public_intel'
               AND tn.nspname NOT IN ('pg_catalog', 'information_schema')
            """
        )
    ).all()
    if foreign:
        raise RuntimeError(
            "a public_intel view depends on a relation outside public_intel: "
            f"{[(r.view_name, r.dep_schema, r.dep_relation) for r in foreign]}. "
            "These views run as evercoat_owner, so such a join reads across "
            "every tenant and serves it anonymously."
        )

    # -----------------------------------------------------------------
    # 5. THE PUBLICATION INVARIANT REFUSES, rather than merely existing.
    #
    # The first draft could not fail: `NOT (a AND b) OR c` is NULL when `c`
    # is NULL, and PostgreSQL accepts a NULL CHECK. Asserting the
    # constraint was present would have passed over that. This attempts the
    # write the constraint is supposed to stop.
    # -----------------------------------------------------------------
    refused = False
    try:
        with bind.begin_nested():
            bind.execute(
                text(
                    """
                    INSERT INTO public_intel.manufacturers
                        (name, content_origin, publication_status,
                         is_demonstration_data)
                    VALUES ('__probe_must_be_refused__', 'synthetic',
                            'published', false)
                    """
                )
            )
    except Exception:
        refused = True
    if not refused:
        raise RuntimeError(
            "a SYNTHETIC row was PUBLISHED without is_demonstration_data. "
            "The publication invariant does not hold, which means invented "
            "content can be served to the public as fact."
        )

    # And the honest form is accepted -- a constraint that refuses
    # everything would also pass the probe above.
    with bind.begin_nested() as accepted:
        bind.execute(
            text(
                """
                INSERT INTO public_intel.manufacturers
                    (name, content_origin, publication_status,
                     is_demonstration_data)
                VALUES ('__probe_must_be_accepted__', 'synthetic',
                        'published', true)
                """
            )
        )
        accepted.rollback()


def downgrade() -> None:
    raise NotImplementedError(
        "059 is not reversible: dropping public_intel would drop the "
        "competitors.products.public_product_id references with it."
    )
