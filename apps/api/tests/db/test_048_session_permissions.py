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


def _perms(session: Session, *, org: uuid.UUID | None, user: uuid.UUID | None) -> set[str]:
    """Scope the session to (org, user) and ask what it may do."""
    if org is not None:
        session.execute(text("SELECT set_config('app.current_org', :v, true)"), {"v": str(org)})
    if user is not None:
        session.execute(
            text("SELECT set_config('app.current_user_id', :v, true)"), {"v": str(user)}
        )
    row = session.execute(
        text("SELECT a.permissions FROM core.authorization_for_current_session() a")
    ).scalar_one()
    return set(row or ())


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


def test_a_deactivated_membership_stops_granting(
    app_session: Session, owner_session: Session
) -> None:
    """🔴 REVOCATION TAKES EFFECT, WHICH IS WHY THE SET IS DERIVED NOT COMPARED.

    `get_principal` already says a JWT "is not a current statement about
    authorization". The same is true of a permission set computed at the start
    of a request. Because `authorize()` re-reads rather than compares, a
    membership deactivated mid-request stops granting on the next agent-tier
    call instead of being read as a mismatch and reported as an attack.

    ⚠️ `inactive`, not `suspended` — `organization_members_status_check`
    admits exactly `active` and `inactive`, and the first draft of this test
    invented a third value and was refused by the constraint. Read the
    vocabulary from the database.
    """
    member = owner_session.execute(
        text(
            """
            SELECT om.id, om.user_id, om.organization_id
            FROM core.organization_members om
            JOIN core.member_roles mr ON mr.member_id = om.id
            WHERE om.status = 'active'
            LIMIT 1
            """
        )
    ).one_or_none()
    if member is None:
        pytest.skip("no seeded active membership with a role to suspend")

    before = _perms(app_session, org=member.organization_id, user=member.user_id)
    assert before, "the membership granted nothing to begin with; nothing to prove"

    owner_session.execute(
        text("UPDATE core.organization_members SET status = 'inactive' WHERE id = :i"),
        {"i": member.id},
    )
    owner_session.commit()
    try:
        # A fresh statement on the app session; the GUCs are still set.
        after = _perms(app_session, org=member.organization_id, user=member.user_id)
        assert after == set(), f"an inactive membership still granted {sorted(after)}"
    finally:
        owner_session.execute(
            text("UPDATE core.organization_members SET status = 'active' WHERE id = :i"),
            {"i": member.id},
        )
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
