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


# A SHORT LIST of definer functions is meant to belong to evercoat_owner, each for
# the same reason and each named here with the migration that decided
# it. A definer function runs with ITS OWNER's privileges, so this list
# is a security decision and grows only on purpose.
#
# This test caught the second one being added (migration 015), which is
# exactly what it is for: the entry below is the deliberate
# acknowledgement, not a way of quieting the check.
DEFINER_OWNED_BY_DESIGN = {
    # Migration 013. The audit trigger must read its own chain tail
    # regardless of who is writing, or the chain forks per RLS view.
    "audit.chain_row",
    # Migration 024. Same shape as chain_row: it must answer BEFORE an
    # organization has been chosen, so there is no RLS GUC set and an
    # invoker-rights read would return nothing. `GET /api/me` is the only
    # caller, and it is what tells a freshly signed-in browser which
    # tenant it may ask for -- without it, authentication completes and
    # every subsequent request 400s for want of a header whose value
    # nothing supplies.
    #
    # This test caught the addition, which is exactly what it is for. The
    # entry is the deliberate acknowledgement. Note the limit of what it
    # buys: `evercoat_owner` is exempt from these policies only while RLS
    # is ENABLED and not FORCED. See
    # tests/db/test_024_memberships_for_subject.py, which fails the moment
    # the cutover lands.
    "core.memberships_for_subject",
    # Migration 033. The third instance of the same shape, and the one that
    # showed a tripwire on ONE function is not a tripwire on a PATTERN.
    #
    # 024 reasoned carefully about `memberships_for_subject` because it
    # answers before a tenant is chosen -- and left the tripwire below. But
    # `get_principal` does the same unscoped read for EVERY authenticated
    # request, not just `/api/me`, and nothing named it. Migration 032 closed
    # the permissive escape hatch and **35 route tests across tests/auth/
    # returned 403**: not a leak, a total authentication outage.
    #
    # So this function exists for the same reason, carries the same limit --
    # `evercoat_owner` is exempt only while RLS is ENABLED and not FORCED --
    # and `tests/db/test_033_*` fails the moment that changes.
    "core.principal_for_subject",
    # Migration 044. The FOURTH instance, and this test caught it exactly as
    # designed -- it went red the moment `ALTER FUNCTION ... OWNER TO
    # evercoat_owner` was added, which is the acknowledgement being recorded
    # here rather than a way of quieting the check.
    #
    # 🔴 IT ALSO CAUGHT THE OPPOSITE MISTAKE FIRST, BY NOT FIRING. 044 shipped
    # its `CREATE FUNCTION` with no owner pin, so the function was owned by
    # `postgres` -- a SUPERUSER with BYPASSRLS -- while the migration's own
    # comment claimed `evercoat_owner`. This list only catches definers moved
    # TO `evercoat_owner`, so a superuser-owned one is invisible to it, and
    # nothing in the suite would ever have said so. That is I56's exact shape,
    # created three migrations after 033 wrote the warning.
    #
    # Why it must be a definer at all: 044 makes a user in ANOTHER
    # organization unreadable, and `keycloak_sub` is globally unique, so an
    # administrator could otherwise neither find nor create a human who
    # already has an account elsewhere -- multi-organization membership, which
    # is the reason `core.users` has no `organization_id`, would break.
    #
    # Same limit as the three above: `evercoat_owner` is exempt only while RLS
    # is ENABLED and not FORCED.
    #
    # ⚠️ WHERE THAT IS ASSERTED MOVED, AND THIS COMMENT ONCE POINTED AT
    # NOTHING. It said `test_044_user_directory_is_not_global.py` asserts the
    # owner is not a superuser -- true of the function 049 dropped, and the
    # redirected test then lost the `rolbypassrls` half entirely. Raised by the
    # Supervisor. Both halves now live in
    # `test_044_...::test_the_replacement_runs_as_a_non_superuser_and_only_for_the_app`
    # and in `test_049_atomic_bind.py`.
    # Migration 049 DROPPED `core.user_id_for_subject` -- it was I82's oracle,
    # answering for an exact subject in any organization with a uuid and an
    # existence, on a SELECT that left no row behind. A capability nothing
    # calls is still a capability, so it was removed rather than orphaned.
    #
    # Its replacement is below: same reason for being a definer (044 makes a
    # user in another organization invisible and a human legitimately belongs
    # to several), but it WRITES and returns the identifier only after the
    # membership exists.
    "core.bind_subject_to_organization",
    # Migration 048. The FIFTH instance, and this test caught it as designed.
    #
    # It returns BOTH role codes and permission codes. The first draft
    # returned only permissions, leaving `roles` caller-supplied -- and
    # unclaimed work is matched with `t.assigned_role = ANY(:roles)`, which
    # MSD reaches. Raised by Codex.
    #
    # Why it must be a definer: role and permission rows are tenant-scoped,
    # and the runtime role must not need SELECT on `core.member_roles`,
    # `core.roles`, `core.role_permissions` or `core.permissions` merely to
    # learn what the CALLER may do. Granting those tables to `evercoat_app`
    # to avoid a definer would hand the runtime the whole authorization
    # catalogue, which is a wider change than this one.
    #
    # 🔴 IT DIFFERS FROM THE FOUR ABOVE IN THE WAY THAT MATTERS. Those three
    # `*_for_subject` functions exist because they must answer BEFORE a tenant
    # is chosen, so no GUC is set and an invoker-rights read returns nothing.
    # This one is the opposite: the GUC IS set, and the GUC is its ONLY input.
    # It takes no arguments at all, which is what stops it being the oracle
    # `core.user_id_for_subject` is (I82) — there is no parameter with which
    # to aim it at somebody else.
    #
    # ⚠️ AND ITS BEHAVIOUR UNDER THE I56/I58 FORCE CUTOVER MUST BE MEASURED,
    # NOT ASSUMED — for a different reason from the others. They are exempt
    # only while RLS is ENABLED and not FORCED, and lose their exemption at
    # the cutover. This one runs WITH the caller's GUC set, so under FORCE it
    # degrades to "what that caller can see" rather than to nothing — which
    # for this query may well still be the right answer. *May well* is not a
    # measurement. `tests/db/test_048_session_permissions.py` compares it
    # against the authoritative join and will say plainly which it is.
    "core.authorization_for_current_session",
    # Migration 015. The trigger that freezes the composition of a
    # non-draft formula version looks that version up before deciding.
    # As SECURITY INVOKER, a session whose RLS view of
    # `formula_versions` is empty would find no row -- and a guard that
    # passes when it cannot see its subject is the "check that walks
    # through its own gap" this platform has already been bitten by.
    "formulations.deny_component_mutation",
    # Migration 017. Identical reasoning one slice later: the trigger
    # that freezes an issued weigh-up sheet reads
    # `laboratory.batches.status` before deciding, and must reach that
    # row regardless of the caller.
    #
    # This test has now caught the addition TWICE, which is the argument
    # for keeping it exact rather than loosening it to "any definer
    # function in an application schema". Each entry is a deliberate
    # security decision, made once and written down.
    "laboratory.deny_component_mutation",
    # Migration 027. It answers "who is this project's declared lead?"
    # for a project the caller CANNOT read -- which is the whole point: a
    # Director may convert an opportunity into a RESTRICTED project led
    # by somebody else, and must still be able to enrol that lead. An
    # invoker-rights version returns NULL there and breaks conversion.
    #
    # The disclosure is ONE COLUMN of one row, for a project id the
    # caller already possesses, and ids are gen_random_uuid(). That is
    # the same assumption core.is_project_member rests on.
    #
    # This test has now caught the addition FOUR times, which is the
    # argument for keeping it exact rather than loosening it.
    "core.project_lead",
}


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

    for name in sorted(DEFINER_OWNED_BY_DESIGN):
        assert owner_of.get(name) == "evercoat_owner", (
            f"{name} must be owned by evercoat_owner so it executes with the "
            f"owner's privileges; found {owner_of.get(name)!r}"
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
        if name not in DEFINER_OWNED_BY_DESIGN and owner == "evercoat_owner"
    }
    assert not swept, (
        "these SECURITY DEFINER functions were reassigned to evercoat_owner. A "
        "definer function executes with its owner's privileges, so this changes "
        f"what they are allowed to do: {sorted(swept)}"
    )
