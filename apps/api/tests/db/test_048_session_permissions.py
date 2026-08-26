"""048 — the permission set the agent tier gates on comes from the database.

🔴 WHAT I105 WAS, IN CODEX'S WORDS:

    bind() validates only organization and user; it never validates roles or
    permissions. A forged principal using the real session identity therefore
    passes bind() while claiming arbitrary authorization.

`core.authorization_for_current_session()` answers from the same two GUCs RLS
reads, so the gate and the rows can no longer disagree about who is asking.

⚠️ EVERYTHING HERE RUNS AS `evercoat_app`, the non-superuser runtime role, not
as the owner. A privilege test performed as a superuser proves nothing — the
`app_session` fixture asserts `rolsuper = false` before yielding for exactly
that reason.
"""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session

pytestmark = [pytest.mark.db]


def _authorization(
    session: Session, *, org: uuid.UUID | None, user: uuid.UUID | None
) -> tuple[set[str], set[str]]:
    """Scope the session to (org, user) and ask what it may BE and DO.

    🔴 RETURNS BOTH HALVES, AND THE FIRST VERSION READ ONLY PERMISSIONS.

    Raised by the Supervisor, and it is the sharper version of the defect
    Codex found. The Codex round added `roles` to the SQL *because* MSD feeds
    them into `t.assigned_role = ANY(:roles)` — and then every database test
    kept selecting `a.permissions` alone. The only roles assertion lived in
    `tests/test_conductor_boundary.py` against a Python stub, so it measured
    `authorize()` and never the function.

    Concretely: changing the migration's first aggregate to
    `array_agg(DISTINCT mr.role_id::text)`, or dropping the
    `LEFT JOIN core.roles`, left the whole suite green while the assistant
    matched work on the wrong codes. A fix with no coverage over the half it
    added.
    """
    if org is not None:
        session.execute(text("SELECT set_config('app.current_org', :v, true)"), {"v": str(org)})
    if user is not None:
        session.execute(
            text("SELECT set_config('app.current_user_id', :v, true)"), {"v": str(user)}
        )
    row = session.execute(
        text("SELECT a.roles, a.permissions FROM core.authorization_for_current_session() a")
    ).one()
    return set(row.roles or ()), set(row.permissions or ())


def _perms(session: Session, *, org: uuid.UUID | None, user: uuid.UUID | None) -> set[str]:
    return _authorization(session, org=org, user=user)[1]


def test_the_function_is_a_definer_owned_by_a_non_superuser(owner_session: Session) -> None:
    """🔴 PIN THE OWNER — NOT PINNING IT IS A FOUR-TIME DEFECT IN THIS REPO.

    SECURITY DEFINER means "run as the owner", and the owner is whoever ran
    CREATE FUNCTION unless it is set. Migrations are applied here as
    `postgres` (`rolsuper`, `rolbypassrls`), so an unpinned function runs
    permanently outside RLS — including after the I56/I58 FORCE cutover.
    Migration 044 created the fourth instance of that while its own comment
    claimed it had not, and it was found by reading `pg_proc` rather than by
    either reviewer. So this reads `pg_proc`, not the migration's comment.
    """
    row = owner_session.execute(
        text(
            """
            SELECT pg_get_userbyid(p.proowner) AS owner,
                   p.prosecdef                 AS is_definer,
                   p.provolatile               AS volatility,
                   p.pronargs                  AS nargs,
                   p.proconfig                 AS config,
                   r.rolsuper                  AS owner_is_super
            FROM pg_proc p
            JOIN pg_namespace n ON n.oid = p.pronamespace
            JOIN pg_roles r     ON r.oid = p.proowner
            WHERE n.nspname = 'core'
              AND p.proname = 'authorization_for_current_session'
            """
        )
    ).one_or_none()

    assert row is not None, "core.authorization_for_current_session() does not exist"
    assert row.owner == "evercoat_owner", f"owner is {row.owner!r}, not evercoat_owner"
    assert row.owner_is_super is False, (
        f"the function's owner {row.owner!r} is a SUPERUSER, so it runs outside "
        "RLS permanently — this is I56's shape, for the fifth time"
    )
    assert row.is_definer is True, "not SECURITY DEFINER, so it cannot read the tenant tables"
    # 🔴 THE EXACT SETTING, NOT MERELY THAT ONE EXISTS. Codex: a test that
    # accepts any `search_path=` would pass on `search_path=public`, which is
    # the shadowable configuration the pin exists to prevent.
    assert "search_path=core, pg_temp" in (row.config or []), (
        f"search_path is {row.config!r}, not the pinned 'core, pg_temp'. A "
        "SECURITY DEFINER without an exact pin can be redirected by a "
        "caller-controlled search_path to shadowed objects."
    )


def test_it_is_declared_stable_and_its_body_contains_no_write(
    owner_session: Session,
) -> None:
    """🔴 THE ANSWER TO ADR-029's REJECTION — AND THIS TEST USED TO OVERCLAIM.

    ADR-029 rejected a SECURITY DEFINER for I82 because a definer that WRITES
    fires ADR-028's address guards, which inside a definer owned by the table
    owner run as that owner — bypassing RLS while FORCE is off, so the guard
    refuses on another tenant's row and the refusal discloses that the address
    exists. Every step of that chain begins with a write.

    ⚠️ THIS TEST WAS NAMED `test_it_writes_nothing` AND CHECKED ONLY
    `provolatile = 's'`. Codex was right that this proves less than the name
    claimed: PostgreSQL TRUSTS a volatility declaration, and while it refuses
    a data-modifying statement written directly in a STABLE body, `STABLE` is
    not transitive — a SELECT could call a VOLATILE function that writes.

    So the test now asserts the two things it can actually establish: the
    declared contract, AND that the body itself contains no write and calls
    only the two schema-qualified GUC readers. That second half is what makes
    the first half meaningful here, and it is read from `pg_get_functiondef`
    rather than from the migration file, so editing the migration without
    re-applying it cannot satisfy it.
    """
    volatility = owner_session.execute(
        text(
            """
            SELECT p.provolatile FROM pg_proc p
            JOIN pg_namespace n ON n.oid = p.pronamespace
            WHERE n.nspname = 'core' AND p.proname = 'authorization_for_current_session'
            """
        )
    ).scalar_one()
    assert volatility == "s", (
        f"provolatile is {volatility!r}, not 's' (STABLE). A VOLATILE definer may "
        "write, and a write fires ADR-028's guards inside the definer — which is "
        "precisely the chain ADR-029 measured and rejected."
    )

    body = owner_session.execute(
        text(
            """
            SELECT pg_get_functiondef(p.oid) FROM pg_proc p
            JOIN pg_namespace n ON n.oid = p.pronamespace
            WHERE n.nspname = 'core' AND p.proname = 'authorization_for_current_session'
            """
        )
    ).scalar_one()

    # The executable half only — the migration's own prose discusses INSERT
    # and UPDATE at length, and a test its documentation can redden (or
    # satisfy) is worth nothing. This file has already been bitten by exactly
    # that, in both directions.
    code = " ".join(line for line in body.splitlines() if not line.strip().startswith("--"))
    for verb in ("INSERT", "UPDATE", "DELETE", "MERGE", "TRUNCATE", "COPY"):
        assert verb not in code.upper(), (
            f"the function body contains {verb}. STABLE is a declaration "
            "PostgreSQL trusts, not a proof — the body must be a read."
        )

    # Only the two GUC readers are called, and both are schema-qualified, so
    # nothing here is reachable through a caller-controlled search_path.
    called = {
        "core.current_user_id" in code,
        "core.current_org_id" in code,
    }
    assert called == {True}, "the function no longer keys on the session's own GUCs"


def test_it_takes_no_arguments_so_it_cannot_be_aimed_at_anybody(
    owner_session: Session,
) -> None:
    """🔴 THE DIFFERENCE BETWEEN A LOOKUP AND AN ORACLE.

    `core.user_id_for_subject(TEXT)` answers a question about somebody the
    caller names — that is I82, still open. This function can only ever answer
    about the session it is called on, because there is no input with which to
    ask about a victim.

    A caller who could set the GUC to another user could already read that
    user's rows through RLS, which is a strictly larger hole and not one this
    creates.
    """
    nargs = owner_session.execute(
        text(
            """
            SELECT p.pronargs FROM pg_proc p
            JOIN pg_namespace n ON n.oid = p.pronamespace
            WHERE n.nspname = 'core' AND p.proname = 'authorization_for_current_session'
            """
        )
    ).scalar_one()
    assert nargs == 0, (
        f"the function takes {nargs} argument(s). A permission lookup a caller "
        "can aim at somebody else is an oracle — see I82."
    )


def test_an_unscoped_session_is_granted_nothing(app_session: Session) -> None:
    """🔴 A GUARD THAT PASSES WHEN IT CANNOT SEE IS NOT A GUARD.

    `current_setting(..., true)` returns NULL rather than raising when a GUC
    was never set. An implementation that read that as "no restriction" would
    hand every permission to the one session that sees across tenants — the
    one `unscoped_session_scope()` opens.
    """
    assert _perms(app_session, org=None, user=None) == set()


def test_a_scoped_session_gets_exactly_its_own_grants(
    app_session: Session, owner_session: Session
) -> None:
    """The other direction — otherwise the function could be `SELECT '{}'`.

    Compared against the authoritative join computed as the owner, so this
    fails if the function silently narrows as well as if it widens.
    """
    member = owner_session.execute(
        text(
            """
            SELECT om.user_id, om.organization_id
            FROM core.organization_members om
            JOIN core.users u             ON u.id = om.user_id
            JOIN core.member_roles mr     ON mr.member_id = om.id
            WHERE om.status = 'active' AND u.status = 'active'
            LIMIT 1
            """
        )
    ).one_or_none()
    if member is None:
        pytest.skip("no seeded active membership with a role to measure")

    expected = {
        r[0]
        for r in owner_session.execute(
            text(
                """
                SELECT DISTINCT p.code
                FROM core.organization_members om
                JOIN core.member_roles mr     ON mr.member_id = om.id
                JOIN core.roles r             ON r.id = mr.role_id
                JOIN core.role_permissions rp ON rp.role_id = r.id
                JOIN core.permissions p       ON p.id = rp.permission_id
                WHERE om.user_id = :u AND om.organization_id = :o
                  AND om.status = 'active'
                """
            ),
            {"u": member.user_id, "o": member.organization_id},
        ).all()
    }

    got = _perms(app_session, org=member.organization_id, user=member.user_id)
    assert got, "a member with a role was granted nothing at all"
    assert got == expected, f"derived {sorted(got)}, authoritative join says {sorted(expected)}"


def test_a_user_gets_nothing_in_an_organization_they_do_not_belong_to(
    app_session: Session, owner_session: Session
) -> None:
    """Membership is per organization, and so is the answer.

    This is the cross-tenant case: the same real person, the same real
    organization, and no membership joining them. A function keyed on the user
    alone would hand over their permissions from elsewhere.
    """
    pair = owner_session.execute(
        text(
            """
            SELECT om.user_id AS uid, o.id AS other_org
            FROM core.organization_members om
            CROSS JOIN core.organizations o
            WHERE om.status = 'active'
              AND o.id <> om.organization_id
              AND NOT EXISTS (
                  SELECT 1 FROM core.organization_members x
                  WHERE x.user_id = om.user_id AND x.organization_id = o.id
              )
            LIMIT 1
            """
        )
    ).one_or_none()
    if pair is None:
        pytest.skip("needs two organizations with a user in only one of them")

    assert _perms(app_session, org=pair.other_org, user=pair.uid) == set()


def _looks_like_a_uuid(value: str) -> bool:
    try:
        uuid.UUID(value)
    except ValueError:
        return False
    return True


def test_the_roles_half_matches_the_authoritative_join(
    app_session: Session, owner_session: Session
) -> None:
    """🔴 THE HALF THE CODEX ROUND ADDED AND NOTHING MEASURED IN SQL.

    Raised by the Supervisor. `authorize()` derives roles because
    `app/domains/tasks/service.py` matches unclaimed work with
    `t.assigned_role = ANY(:roles)` -- so the CODES must be right, not merely
    present. A `role_id` where a `code` belongs, or a dropped
    `LEFT JOIN core.roles`, would leave every other test green and make the
    assistant match on values `workflow.tasks.assigned_role` never holds.
    """
    member = owner_session.execute(
        text(
            """
            SELECT om.user_id, om.organization_id
            FROM core.organization_members om
            JOIN core.users u         ON u.id = om.user_id
            JOIN core.member_roles mr ON mr.member_id = om.id
            WHERE om.status = 'active' AND u.status = 'active'
            LIMIT 1
            """
        )
    ).one_or_none()
    if member is None:
        pytest.skip("no seeded active membership with a role to measure")

    expected = {
        r[0]
        for r in owner_session.execute(
            text(
                """
                SELECT DISTINCT r.code
                FROM core.organization_members om
                JOIN core.member_roles mr ON mr.member_id = om.id
                JOIN core.roles r         ON r.id = mr.role_id
                WHERE om.user_id = :u AND om.organization_id = :o
                  AND om.status = 'active'
                """
            ),
            {"u": member.user_id, "o": member.organization_id},
        ).all()
    }

    roles, _ = _authorization(app_session, org=member.organization_id, user=member.user_id)
    assert roles, "a member with a role was given no role codes at all"
    assert roles == expected, f"derived roles {sorted(roles)}, join says {sorted(expected)}"

    # 🔴 CODES, NOT IDS. The cheapest way to break this silently is to
    # aggregate `mr.role_id` instead of `r.code` -- both are non-empty sets of
    # strings, and only one of them matches `workflow.tasks.assigned_role`.
    assert all(not _looks_like_a_uuid(code) for code in roles), (
        f"the roles half returned identifiers rather than codes: {sorted(roles)}"
    )


def test_a_deactivated_membership_stops_granting(
    app_session: Session, owner_session: Session
) -> None:
    """🔴 REVOCATION TAKES EFFECT, WHICH IS WHY THE SET IS DERIVED.

    `get_principal` already says a JWT "is not a current statement about
    authorization". The same is true of a role or permission set computed at
    the start of a request. Because `authorize()` re-reads rather than
    compares, a membership deactivated mid-request stops granting on the next
    agent-tier call instead of being read as a mismatch and reported as an
    attack.

    WARNING: IT BUILDS ITS OWN MEMBERSHIP AND DELETES IT. The first version
    flipped a REAL seeded membership to `inactive` and restored it with a
    second COMMIT in `finally` -- against `conftest.py`'s stated contract that
    *"every fixture rolls back; these tests must be runnable against a
    developer's local database repeatedly without leaving residue"*. Raised by
    the Supervisor, and the failure mode is specific: interrupt the run
    between the two commits and the demo organization's membership stays
    inactive, so sign-in breaks afterwards with no failing test pointing at
    the cause. On this host the local API and an e2e run read that table
    concurrently.

    WARNING: `inactive`, not `suspended` -- `organization_members_status_check`
    admits exactly `active` and `inactive`, and an earlier draft invented a
    third value and was refused by the constraint. Read the vocabulary from
    the database.
    """
    org = owner_session.execute(
        text("SELECT id FROM core.organizations LIMIT 1")
    ).scalar_one_or_none()
    role_id = owner_session.execute(text("SELECT id FROM core.roles LIMIT 1")).scalar_one_or_none()
    if org is None or role_id is None:
        pytest.skip("needs at least one organization and one role")

    sub = f"i105-revocation-{uuid.uuid4()}"
    user_id = owner_session.execute(
        text(
            """
            INSERT INTO core.users (keycloak_sub, email, display_name)
            VALUES (:sub, :email, 'I105 revocation probe')
            RETURNING id
            """
        ),
        {"sub": sub, "email": f"{sub}@example.test"},
    ).scalar_one()
    member_id = owner_session.execute(
        text(
            """
            INSERT INTO core.organization_members (organization_id, user_id, status)
            VALUES (:org, :uid, 'active')
            RETURNING id
            """
        ),
        {"org": org, "uid": user_id},
    ).scalar_one()
    owner_session.execute(
        text("INSERT INTO core.member_roles (member_id, role_id) VALUES (:m, :r)"),
        {"m": member_id, "r": role_id},
    )
    # Committed because `evercoat_owner` and `evercoat_app` are separate
    # connections and the app session must SEE these rows. Deleted in
    # `finally` -- see the docstring, and I101 on leaked `core.users` rows.
    owner_session.commit()

    try:
        before_roles, _ = _authorization(app_session, org=org, user=user_id)
        assert before_roles, "the purpose-built membership granted no roles; nothing to prove"

        owner_session.execute(
            text("UPDATE core.organization_members SET status = 'inactive' WHERE id = :i"),
            {"i": member_id},
        )
        owner_session.commit()
        app_session.rollback()

        after_roles, after_perms = _authorization(app_session, org=org, user=user_id)
        assert after_roles == set(), f"an inactive membership still granted roles {after_roles}"
        assert after_perms == set(), f"an inactive membership still granted {after_perms}"
    finally:
        app_session.rollback()
        owner_session.rollback()
        owner_session.execute(
            text("DELETE FROM core.member_roles WHERE member_id = :m"), {"m": member_id}
        )
        owner_session.execute(
            text("DELETE FROM core.organization_members WHERE id = :i"), {"i": member_id}
        )
        owner_session.execute(text("DELETE FROM core.users WHERE id = :u"), {"u": user_id})
        owner_session.commit()


# ---------------------------------------------------------------------------
# 🔴 THE I56/I58 MEASUREMENT IS STILL OWED, AND I TRIED AND WITHDREW IT
# ---------------------------------------------------------------------------
#
# Codex asked, reasonably, that the FORCE RLS cutover be PRE-EMPTED here
# rather than warned about: force RLS on precisely the tables this function
# reads, call it as `evercoat_app` with valid GUCs, and compare the answer.
# Four previous SECURITY DEFINER functions shipped with a note saying their
# behaviour would change at the cutover and nothing that would fail.
#
# I wrote it. It HANGS, and it is withdrawn rather than left in.
#
#   `ALTER TABLE ... FORCE ROW LEVEL SECURITY` takes an ACCESS EXCLUSIVE lock
#   on all six of `core.users`, `organization_members`, `member_roles`,
#   `roles`, `role_permissions` and `permissions`. Any other connection
#   holding those tables blocks it -- and on a development host the demo API
#   is running with a live pool, measured `1 idle in transaction`. Rolling
#   back the fixtures first and setting `lock_timeout` were BOTH insufficient:
#   the run still had to be killed at 120s.
#
# A test that can hang the suite is worse than a documented gap, and this
# project has a recorded lesson about exactly that shape -- "a fixture that
# deadlocks the suite: a failing test never reaches its rollback and its locks
# block cleanup forever". The `finally` restore did work (FORCE was `f` on all
# six afterwards, checked), so the withdrawal is about the hang, not damage.
#
# ⚠️ SO THIS REMAINS UNMEASURED, AND SAYING SO IS THE POINT. The honest place
# for it is the I56/I58 cutover itself, where those tables are being altered
# anyway and the suite is expected to be the only thing talking to the
# database. `tests/db/test_object_ownership.py` names what must be checked.
#
# What is NOT guesswork: this function reads its scope from the same two GUCs
# the policies read, which is why the expectation is that it degrades to "what
# the caller can see" rather than to nothing. An expectation is not a
# measurement and is not recorded as one.


def test_public_cannot_execute_it(owner_session: Session) -> None:
    """🔴 ASSERT THE PRIVILEGE, NOT THE SQL. Raised by the Supervisor.

    A new function is granted EXECUTE to PUBLIC by default, so
    `REVOKE ALL ... FROM PUBLIC` in migration 048 is load-bearing rather than
    tidy. Nothing measured it: every other test here calls the function as
    `evercoat_app`, which proves the GRANT and says nothing about the REVOKE.

    That is I81's own lesson from 2026-08-25 — *a column-level REVOKE against
    a table-level GRANT does nothing, so assert the PRIVILEGE, not the SQL* —
    applied one object type over. A later `CREATE OR REPLACE` that reset the
    ACL would be invisible to the suite otherwise.

    Read from `proacl`, which is what PostgreSQL actually enforces.
    """
    acl = owner_session.execute(
        text(
            """
            SELECT COALESCE(p.proacl::text[], ARRAY[]::text[])
            FROM pg_proc p
            JOIN pg_namespace n ON n.oid = p.pronamespace
            WHERE n.nspname = 'core'
              AND p.proname = 'authorization_for_current_session'
            """
        )
    ).scalar_one()

    assert acl, (
        "proacl is empty, which in PostgreSQL means the DEFAULT applies — and "
        "the default for a function is EXECUTE to PUBLIC. The REVOKE did not "
        "take, or a later CREATE OR REPLACE reset it."
    )
    # An entry whose grantee is empty ("=X/owner") IS the PUBLIC grant.
    public_grants = [entry for entry in acl if entry.startswith("=")]
    assert not public_grants, (
        f"PUBLIC can execute core.authorization_for_current_session(): {public_grants}. "
        "Any database role could then read the authorization catalogue for "
        "whatever session it can scope."
    )
    assert any(entry.startswith("evercoat_app=X") for entry in acl), (
        f"evercoat_app cannot execute it: {acl}. The runtime role needs it on "
        "every agent-tier call."
    )
