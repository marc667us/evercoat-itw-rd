"""I109 — the sign-in lookups belong to a role the runtime cannot reach.

`core.principal_for_subject(TEXT, UUID)` and `core.memberships_for_subject(TEXT)`
take a SUBJECT AS AN ARGUMENT and cannot bind it to whoever is asking, because
both exist to answer BEFORE a session has an organization. Granted to
`evercoat_app` they were an identity-enumeration primitive: measured, an
ordinary member of one organization read a foreign subject's address and the
NAME and CODE of every organization that subject belongs to.

🔴 THE FIX COULD NOT BE A CHECK INSIDE THEM, AND THAT IS THE WHOLE DESIGN.

    a GUC naming the verified subject  -- evercoat_app can SET any GUC
    SET ROLE for the lookup            -- evercoat_app can assume the role

Both are misuse barriers rather than boundaries. Privilege had to follow the
CONNECTION, so migration 053 gives EXECUTE to `evercoat_auth` and the
application reaches it on a separate pool.

⚠️ THE EMPTINESS OF THAT ROLE IS LOAD-BEARING. Its connection never sets a
tenant GUC -- it cannot, since it runs before an organization is chosen. A role
that could also read tables there would be a bigger hole than the one being
closed: every tenant's rows, unscoped. So "holds nothing else" is asserted here
over EVERY schema, not argued.
"""

from __future__ import annotations

import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session

pytestmark = [pytest.mark.db]

SIGN_IN_LOOKUPS = (
    "core.principal_for_subject(TEXT, UUID)",
    "core.memberships_for_subject(TEXT)",
)
# Session-scoped and NOT moved: the first takes zero arguments (ADR-030 chose
# that shape so it could not be aimed), the second proves the caller's standing
# before it writes (050). Neither answers about a subject the caller names.
STAYS_WITH_THE_APP = (
    "core.authorization_for_current_session()",
    "core.bind_subject_to_organization(TEXT, TEXT, TEXT)",
)


def test_the_runtime_role_cannot_execute_the_sign_in_lookups(
    owner_session: Session,
) -> None:
    """The revoke, asserted as a PRIVILEGE rather than as a statement.

    ⚠️ `has_function_privilege` answers about EFFECTIVE privilege, so this also
    catches the route Codex constructed while reviewing 053: `GRANT
    evercoat_auth TO evercoat_app` would hand the runtime role EXECUTE by
    inheritance without any direct grant appearing in `proacl`. The migration
    additionally sets the sign-in role `NOINHERIT`, but that protects the auth
    role's own memberships -- this is the assertion that catches the reverse.
    """
    for fn in SIGN_IN_LOOKUPS:
        granted = owner_session.execute(
            text("SELECT has_function_privilege('evercoat_app', :fn, 'EXECUTE')"),
            {"fn": fn},
        ).scalar_one()
        assert granted is False, (
            f"evercoat_app can execute {fn}. It takes a subject as an argument "
            "and cannot check its caller, so on the runtime connection it "
            "enumerates identities and discloses every organization a subject "
            "belongs to (I109)."
        )


def test_public_cannot_execute_them_either(owner_session: Session) -> None:
    """🔴 THE ONE THAT CATCHES A FUTURE `DROP` + `CREATE`.

    PUBLIC EXECUTE is the DEFAULT for a new function. `CREATE OR REPLACE` keeps
    an ACL; `DROP` followed by `CREATE` resets it -- migration 045's header
    records exactly that happening to `memberships_for_subject`. So a later
    migration that rewrites either lookup and forgets its REVOKE hands the
    capability back to every role in the database, with no grant to
    `evercoat_app` anywhere and nothing in the diff that looks like a
    privilege change.

    Raised by Codex, who noted 053 revokes PUBLIC on the two objects that exist
    today and cannot bind what a future migration creates. This is the standing
    assertion that notices.
    """
    for fn in SIGN_IN_LOOKUPS:
        granted = owner_session.execute(
            text("SELECT has_function_privilege('public', :fn, 'EXECUTE')"),
            {"fn": fn},
        ).scalar_one()
        assert granted is False, (
            f"PUBLIC can execute {fn}, so every role in the database can. If a "
            "migration recently dropped and recreated it, add "
            f"`REVOKE ALL ON FUNCTION {fn} FROM PUBLIC` beside the CREATE."
        )


def test_the_sign_in_role_can_execute_both(owner_session: Session) -> None:
    """🔴 THE CONTROL. Without it, a database nobody can sign in to passes.

    Every assertion above is satisfied by a schema where the functions were
    dropped or where no role holds EXECUTE. Both of those are outages, and both
    would report as a successful closure.
    """
    for fn in SIGN_IN_LOOKUPS:
        granted = owner_session.execute(
            text("SELECT has_function_privilege('evercoat_auth', :fn, 'EXECUTE')"),
            {"fn": fn},
        ).scalar_one()
        assert granted is True, (
            f"evercoat_auth cannot execute {fn}, so the capability was removed "
            "rather than moved and nobody can authenticate."
        )


def test_the_session_scoped_functions_did_not_move(owner_session: Session) -> None:
    """The second control, and the one a too-wide revoke would trip.

    If these went with the other two, every permission check and every member
    invitation would break -- and the tests above would still pass.
    """
    for fn in STAYS_WITH_THE_APP:
        granted = owner_session.execute(
            text("SELECT has_function_privilege('evercoat_app', :fn, 'EXECUTE')"),
            {"fn": fn},
        ).scalar_one()
        assert granted is True, (
            f"evercoat_app lost EXECUTE on {fn}. That function is scoped by the "
            "session rather than by an argument, so it was never part of I109."
        )


def test_the_sign_in_role_holds_nothing_else_anywhere(owner_session: Session) -> None:
    """🔴 EVERY SCHEMA, NOT JUST `core`.

    The migration's own probe checked `core` only, and Codex supplied the hole:
    a pre-existing `evercoat_auth` that was a member of a group with SELECT on
    `projects` or `materials` would pass a core-only check and still read those
    tables on a connection that never sets a tenant GUC. 053 now sets the role
    `NOINHERIT` and probes every schema; this is the standing version, because a
    migration's probe runs once and a grant can be added afterwards.
    """
    reachable = owner_session.execute(
        text(
            """
            SELECT format('%I.%I', n.nspname, c.relname) AS relation, priv
              FROM pg_class c
              JOIN pg_namespace n ON n.oid = c.relnamespace
              CROSS JOIN unnest(ARRAY['SELECT', 'INSERT', 'UPDATE', 'DELETE']) AS priv
             WHERE n.nspname NOT IN ('pg_catalog', 'information_schema')
               AND n.nspname NOT LIKE 'pg_toast%'
               AND c.relkind IN ('r', 'v', 'm', 'p')
               AND has_table_privilege('evercoat_auth', c.oid, priv)
             ORDER BY 1, 2
            """
        )
    ).all()
    assert reachable == [], (
        "evercoat_auth can reach tables: "
        f"{[(r.relation, r.priv) for r in reachable]}. Its connection never "
        "sets a tenant GUC, so any table it can read it reads across every "
        "tenant. It needs EXECUTE on two SECURITY DEFINER functions and "
        "nothing else."
    )


def test_the_sign_in_role_is_not_powerful(owner_session: Session) -> None:
    """Attributes, normalised by 053 rather than assumed from `CREATE ROLE`.

    `CREATE ROLE ... IF NOT EXISTS` is idempotent about EXISTENCE and says
    nothing about CAPABILITY, so a role left by an earlier downgrade -- or
    created by hand -- kept whatever it had. Raised by Codex.

    `NOINHERIT` is the load-bearing one: with it, a membership in some group
    does not silently grant this role that group's privileges.
    """
    row = owner_session.execute(
        text(
            """
            SELECT rolsuper, rolbypassrls, rolinherit, rolcreatedb, rolcreaterole
              FROM pg_roles WHERE rolname = 'evercoat_auth'
            """
        )
    ).one()
    assert row.rolsuper is False, "the sign-in role is a SUPERUSER"
    assert row.rolbypassrls is False, "the sign-in role has BYPASSRLS"
    assert row.rolinherit is False, (
        "the sign-in role INHERITS. A membership in any group would hand it "
        "that group's privileges on a connection with no tenant context."
    )
    assert row.rolcreatedb is False
    assert row.rolcreaterole is False


def test_it_really_is_refused_over_a_connection(auth_session: Session) -> None:
    """The catalogue's opinion is not the same claim as a refusal.

    047 is the reason this project asserts both: `has_function_privilege` and
    the error a real statement gets are different facts, and only the second is
    what a caller experiences.

    Here the direction is inverted -- the sign-in role must SUCCEED at its two
    functions and FAIL at everything else -- so this reaches for a table and
    requires the refusal.
    """
    from sqlalchemy.exc import ProgrammingError

    with pytest.raises(ProgrammingError) as caught:
        auth_session.execute(text("SELECT 1 FROM core.organizations LIMIT 1"))
    assert "permission denied" in str(caught.value).lower(), (
        f"reading a table as the sign-in role failed for another reason: {caught.value}"
    )
    auth_session.rollback()
