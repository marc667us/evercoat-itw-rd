"""Ownership of schema objects is an invariant, not a setup step.

WHY THIS FILE EXISTS
--------------------
The first CI run this repository ever executed failed 37 tests with 50
errors, all of them `permission denied`, against a suite that passed
152/0/0 locally. The two databases were built from the same migrations
and disagreed about who owned the tables, because *no migration decided*
— the local database had been repaired by hand and the CI workflow
repaired a different subset of schemas in YAML.

Migration 014 makes the migration the single decider. This file is what
stops the question re-opening: a future migration that creates a table
without handing it to `evercoat_owner` fails here, in a named test with a
readable message, rather than in fifty `permission denied` tracebacks on
a machine that happens to be configured differently.

WHY OWNERSHIP IS LOAD-BEARING AT ALL
------------------------------------
The tenancy tests connect AS `evercoat_owner` to build fixtures, so the
role must be able to reach the tables. Granting it privileges table by
table would work and would be another hand-maintained list; ownership is
the property the schema declarations in migration 001 already assert
(`CREATE SCHEMA ... AUTHORIZATION evercoat_owner`).

WHAT OWNERSHIP MEANS FOR RLS TODAY — measured, not assumed
----------------------------------------------------------
An earlier version of this docstring said the owner "is still subject to
the policies under FORCE RLS". That is false right now:
`relforcerowsecurity` is `f` on every table, because migration 001 defers
the FORCE cutover on purpose. A table's owner is therefore EXEMPT from its
policies, and `evercoat_owner` bypasses RLS.

That is survivable and deliberate, for the reason `conftest.py` already
states: `app_session` — the runtime role, which owns nothing and is fully
subject to RLS — is what isolation assertions must use. `owner_session`
builds fixtures and plays the attacker with direct database access. If you
are writing a test that asserts one tenant cannot see another's rows and
you reach for `owner_session`, the test will pass whether or not RLS
works. Use `app_session`.
"""

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.orm import Session

# The sixteen application schemas from migration 001. `public` is
# excluded deliberately: it holds `alembic_version`, which belongs to
# whoever runs the migrations.
APP_SCHEMAS = (
    "core",
    "innovation",
    "projects",
    "materials",
    "formulations",
    "laboratory",
    "testing",
    "workflow",
    "quality",
    "products",
    "knowledge",
    "messaging",
    "analytics",
    "modeling",
    "ai",
    "audit",
)


def test_every_table_and_sequence_is_owned_by_the_owner_role(owner_session: Session) -> None:
    """No object in an application schema may belong to anyone else.

    Kinds checked: r ordinary table, p partitioned table, S sequence,
    v view, m materialized view. Indexes follow their table and cannot be
    reassigned independently.
    """
    rows = owner_session.execute(
        text(
            """
            SELECT n.nspname || '.' || c.relname AS object_name,
                   c.relkind                     AS kind,
                   pg_get_userbyid(c.relowner)   AS owner
            FROM pg_class c
            JOIN pg_namespace n ON n.oid = c.relnamespace
            WHERE n.nspname = ANY(:schemas)
              AND c.relkind IN ('r', 'p', 'S', 'v', 'm')
              AND pg_get_userbyid(c.relowner) <> 'evercoat_owner'
            ORDER BY 1
            """
        ),
        {"schemas": list(APP_SCHEMAS)},
    ).all()

    assert not rows, (
        "these objects are not owned by evercoat_owner, so the role the "
        "tenancy suite connects as cannot reach them:\n"
        + "\n".join(f"  {r.object_name} (relkind={r.kind}) owned by {r.owner}" for r in rows)
        + "\nA migration that creates a table must hand it to evercoat_owner; "
        "see migrations/014_object_ownership.sql."
    )


def test_the_suite_actually_looked_at_something(owner_session: Session) -> None:
    """Guard against the assertion above passing on an empty result set.

    A query that returns nothing satisfies `assert not rows` whether the
    schema is clean or absent — the same shape as a suite reporting green
    because it collected zero tests.

    An aggregate count is not enough on its own: `count >= 17` still passes
    if a schema went missing and the shortfall was made up elsewhere. So
    check both halves — every schema exists, and the specific tables Slices
    1 and 2 built are present by name.
    """
    present_schemas = {
        row[0]
        for row in owner_session.execute(
            text("SELECT nspname FROM pg_namespace WHERE nspname = ANY(:schemas)"),
            {"schemas": list(APP_SCHEMAS)},
        ).all()
    }
    missing = set(APP_SCHEMAS) - present_schemas
    assert not missing, (
        f"application schemas absent from the database: {sorted(missing)}. "
        "The ownership assertion would have inspected nothing for these."
    )

    # Named, not counted. Drift in the schema list cannot mask a table that
    # has actually gone missing.
    expected = {
        "core.organizations",
        "core.users",
        "core.organization_members",
        "innovation.opportunities",
        "projects.projects",
        "projects.requirements",
        "projects.milestones",
        "projects.risks",
        "workflow.tasks",
        "workflow.stage_definitions",
        "workflow.stage_transitions",
        "audit.events",
    }
    found = {
        row[0]
        for row in owner_session.execute(
            text(
                """
                SELECT n.nspname || '.' || c.relname
                FROM pg_class c
                JOIN pg_namespace n ON n.oid = c.relnamespace
                WHERE n.nspname = ANY(:schemas)
                  AND c.relkind = 'r'
                """
            ),
            {"schemas": list(APP_SCHEMAS)},
        ).all()
    }
    assert expected <= found, f"tables missing from the database: {sorted(expected - found)}"


def test_security_definer_functions_were_not_swept_along(owner_session: Session) -> None:
    """`audit.chain_row` owns its privileges; the sweep must not spread that.

    A SECURITY DEFINER function executes with the privileges of its OWNER.
    Migration 013 moved `audit.chain_row` to `evercoat_owner` on purpose —
    that is how the audit trigger reads its own chain tail. Reassigning
    functions wholesale would change what every definer function is
    allowed to do while looking like tidying, so 014 leaves functions
    alone. This test states that intent, so a later "consistency" pass
    cannot quietly widen the sweep.

    Checking only `audit.chain_row` would not do it: that assertion still
    passes if every OTHER definer function was swept along too, which is
    precisely the mistake being guarded against. So assert the whole map.
    """
    owner_of = dict(
        owner_session.execute(
            text(
                """
                SELECT n.nspname || '.' || p.proname,
                       pg_get_userbyid(p.proowner)
                FROM pg_proc p
                JOIN pg_namespace n ON n.oid = p.pronamespace
                WHERE p.prosecdef
                  AND n.nspname = ANY(:schemas)
                """
            ),
            {"schemas": list(APP_SCHEMAS)},
        ).all()
    )

    # Exactly one definer function is meant to belong to evercoat_owner.
    # Migration 013 moved it there deliberately: a definer function runs
    # with ITS OWNER's privileges, which is how the audit trigger reads its
    # own chain tail regardless of the caller.
    assert owner_of.get("audit.chain_row") == "evercoat_owner", (
        "audit.chain_row must be owned by evercoat_owner — migration 013 put it "
        f"there so the chain can read its own tail; found {owner_of.get('audit.chain_row')!r}"
    )

    # Every OTHER definer function must have been left where it was. The
    # assertion is "not evercoat_owner" rather than a named role because
    # the migration role is `postgres` here and in CI but need not be on
    # another deployment — pinning the name would fail somewhere valid,
    # while the invariant that matters is that the sweep did not reach
    # them. `core.is_project_member` is the one that would hurt: it runs
    # inside RLS policies and must not gain the table owner's exemption.
    swept = {
        name: owner
        for name, owner in owner_of.items()
        if name != "audit.chain_row" and owner == "evercoat_owner"
    }
    assert not swept, (
        "these SECURITY DEFINER functions were reassigned to evercoat_owner. A "
        "definer function executes with its owner's privileges, so this changes "
        f"what they are allowed to do: {sorted(swept)}"
    )
