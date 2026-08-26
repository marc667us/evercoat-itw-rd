"""049 — the identifier is returned only after the membership exists (I82).

`core.user_id_for_subject(TEXT)` answered, for an exact Keycloak subject in
ANY organization, with that user's uuid and their existence — on a SELECT,
leaving no row behind. `core.bind_subject_to_organization` replaces it with one
atomic statement, so an identifier and a membership arrive together or not at
all.

🔴 THE MOST IMPORTANT TEST IN THIS FILE IS THE LAST ONE.

ADR-029 rejected this design because a definer that WRITES fires ADR-028's
address guards, which inside a definer owned by the table owner run as that
owner and reopen I83's disclosure. Migration 047 then made both guards scope
themselves by their own predicate, which removed that chain's second step —
and this function is precisely the writing definer ADR-029 warned about. So
the measurement that authorised building it is kept here as a test, and fails
the moment a future migration un-does 047.

⚠️ Everything here runs as `evercoat_app`, the non-superuser runtime role. A
privilege test performed as a superuser proves nothing; the `app_session`
fixture asserts `rolsuper = false` before yielding.
"""

from __future__ import annotations

import uuid
from collections.abc import Iterator
from dataclasses import dataclass

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DatabaseError
from sqlalchemy.orm import Session

pytestmark = [pytest.mark.db]


@dataclass(frozen=True)
class _Tenants:
    """Two real organizations and a subject that exists in neither."""

    a: uuid.UUID
    b: uuid.UUID
    admin: uuid.UUID
    suffix: str


@pytest.fixture
def tenants(owner_session: Session, app_session: Session) -> Iterator[_Tenants]:
    """Two organizations and an administrator scoped to the first.

    Creates its own rows and deletes them: `conftest.py` requires these tests
    to be re-runnable against a developer's database without residue, and a
    fixture that leaks `core.users` rows is I101 — 595 orphans of 782.

    COMMITs, because `evercoat_owner` and `evercoat_app` are different
    connections and the app session must see the rows.

    🔴 IT ROLLS THE APP SESSION BACK BEFORE DELETING, AND THAT IS NOT
    TIDINESS — IT IS WHY THIS FILE STOPPED HANGING.

    Every test here writes through the app session (the bind INSERTs a
    membership). Those rows are uncommitted and LOCKED. Teardown then deletes
    the same rows as the owner, on a different connection, and waits forever:
    the run had to be killed at 90s, twice, before the cause was measured
    rather than guessed at.

    Depending on `app_session` and rolling it back here is the structural fix.
    The alternative — requiring every test to remember a rollback — is a rule
    the next person has to remember, and this file already demonstrates what
    happens to those.
    """
    sfx = uuid.uuid4().hex[:8]
    orgs = [
        owner_session.execute(
            text(
                """
                INSERT INTO core.organizations (code, name)
                VALUES (:c, :n) RETURNING id
                """
            ),
            {"c": f"I82{label}-{sfx}", "n": f"I82 probe {label}"},
        ).scalar_one()
        for label in ("A", "B")
    ]
    admin_id = owner_session.execute(
        text(
            """
            INSERT INTO core.users (keycloak_sub, email, display_name)
            VALUES (:s, :e, 'I82 admin') RETURNING id
            """
        ),
        {"s": f"i82-admin-{sfx}", "e": f"i82-admin-{sfx}@example.test"},
    ).scalar_one()
    member_id = owner_session.execute(
        text(
            """
            INSERT INTO core.organization_members (organization_id, user_id)
            VALUES (:o, :u) RETURNING id
            """
        ),
        {"o": orgs[0], "u": admin_id},
    ).scalar_one()
    # 🔴 A REAL ROLE CARRYING `admin.users`, BECAUSE 050 NOW DEMANDS IT.
    #
    # `bind_subject_to_organization` asks
    # `core.authorization_for_current_session()` whether this session's user
    # may administer this session's organization -- the check that closed the
    # forged-GUC cross-tenant write. A fixture whose actor holds nothing would
    # make every test here fail at that gate, which is the correct behaviour
    # and would prove nothing about the rest of the function.
    role_id = owner_session.execute(
        text(
            """
            SELECT r.id FROM core.roles r
            JOIN core.role_permissions rp ON rp.role_id = r.id
            JOIN core.permissions p       ON p.id = rp.permission_id
            WHERE p.code = 'admin.users' LIMIT 1
            """
        )
    ).scalar_one()
    owner_session.execute(
        text("INSERT INTO core.member_roles (member_id, role_id) VALUES (:m, :r)"),
        {"m": member_id, "r": role_id},
    )
    owner_session.commit()

    try:
        yield _Tenants(a=orgs[0], b=orgs[1], admin=admin_id, suffix=sfx)
    finally:
        # 🔴 THE APP SESSION FIRST. See the docstring: its uncommitted writes
        # hold locks on exactly the rows deleted below.
        app_session.rollback()
        owner_session.rollback()
        owner_session.execute(
            text(
                """
                DELETE FROM core.member_roles WHERE member_id IN (
                    SELECT id FROM core.organization_members
                    WHERE organization_id = ANY(:o)
                )
                """
            ),
            {"o": orgs},
        )
        owner_session.execute(
            text("DELETE FROM core.organization_members WHERE organization_id = ANY(:o)"),
            {"o": orgs},
        )
        owner_session.execute(
            text("DELETE FROM core.users WHERE keycloak_sub LIKE :p"), {"p": f"i82-%-{sfx}"}
        )
        owner_session.execute(
            text("DELETE FROM core.organizations WHERE id = ANY(:o)"), {"o": orgs}
        )
        owner_session.commit()


def _scope(session: Session, *, org: uuid.UUID, user: uuid.UUID) -> None:
    session.execute(text("SELECT set_config('app.current_org', :v, true)"), {"v": str(org)})
    session.execute(text("SELECT set_config('app.current_user_id', :v, true)"), {"v": str(user)})


def _bind(session: Session, *, subject: str, email: str, name: str):
    return session.execute(
        text(
            """
            SELECT *
            FROM core.bind_subject_to_organization(:s, :e, :n)
            """
        ),
        {"s": subject, "e": email, "n": name},
    ).one()


def test_the_oracle_is_gone_not_merely_unused(owner_session: Session) -> None:
    """🔴 A CAPABILITY NOTHING CALLS IS STILL A CAPABILITY.

    `core.user_id_for_subject` had one caller and it has been rewired. Leaving
    the function in place with `GRANT EXECUTE ... TO evercoat_app` would leave
    I82 fully reachable and merely unused — this repository's most-repeated
    finding (a route with no caller, a permission with no enforcement point)
    pointed the other way round.
    """
    still_there = owner_session.execute(
        text(
            """
            SELECT count(*) FROM pg_proc p
            JOIN pg_namespace n ON n.oid = p.pronamespace
            WHERE n.nspname = 'core' AND p.proname = 'user_id_for_subject'
            """
        )
    ).scalar_one()
    assert still_there == 0, (
        "core.user_id_for_subject still exists. I82 is reachable by anything "
        "holding EXECUTE, whether or not the application calls it."
    )


def test_a_new_subject_is_created_and_bound_in_one_call(
    app_session: Session, tenants: _Tenants
) -> None:
    """The ordinary path, and the source of the property that closes I82.

    A caller who receives an identifier has, in the same statement, created a
    membership in their OWN organization — after which 044's read policy
    admits that user to them anyway.
    """
    _scope(app_session, org=tenants.a, user=tenants.admin)
    sub = f"i82-new-{tenants.suffix}"
    row = _bind(app_session, subject=sub, email=f"{sub}@example.test", name="Newcomer")

    assert row.member_id is not None

    # 🔴 AND THE MEMBERSHIP MUST POINT AT AN IDENTITY THIS CALL CREATED.
    #
    # This test asserted `row.user_id is not None` until 051 stopped returning
    # it, and my rewrite replaced that line with a copy of the one below it --
    # leaving the test saying nothing at all about the identity, so a function
    # that bound a membership to a PRE-EXISTING or simply wrong `core.users`
    # row would pass. Raised by the Supervisor. The identity is resolved
    # through the membership, which is exactly what the route now does.
    org, bound_user = app_session.execute(
        text("SELECT organization_id, user_id FROM core.organization_members WHERE id = :m"),
        {"m": row.member_id},
    ).one()
    assert org == tenants.a, "the membership was created in the wrong organization"
    # ⚠️ NOT `keycloak_sub` -- 047 REVOKED THAT COLUMN FROM `evercoat_app`,
    # and writing this assertion the obvious way proved it: "permission denied
    # for table users". The identity is checked on the attributes the ROUTE can
    # read, which is the same read `invite_member` performs.
    email, display_name = app_session.execute(
        text("SELECT email::text, display_name FROM core.users WHERE id = :u"),
        {"u": bound_user},
    ).one()
    assert (email, display_name) == (f"{sub}@example.test", "Newcomer"), (
        f"the membership was bound to a different identity: {email!r}, {display_name!r}"
    )


def test_no_identifier_is_returned_when_the_bind_fails(
    app_session: Session, tenants: _Tenants
) -> None:
    """🔴 THIS IS I82's ACTUAL CLOSURE, AND IT IS THE WHOLE POINT.

    Binding the same subject twice must refuse — and refuse *without* handing
    back the uuid it resolved on the way. The old `user_id_for_subject` would
    have answered happily: that is exactly the silent, traceless disclosure.

    ⚠️ A SAVEPOINT, NOT A COMMIT, AND THE FIRST VERSION HUNG THE SUITE.
    It committed the first bind so the second would collide. That left rows
    the fixture then had to delete while the app session still held locks, and
    the run had to be killed at 90s — the "fixture that deadlocks the suite"
    shape this project has a standing lesson about, hit twice today.

    Both binds run in ONE transaction: the first is visible to the second, so
    the collision happens without anything being committed. `begin_nested()`
    puts the failing call in a SAVEPOINT so its exception refuses the
    statement instead of poisoning the transaction (I30's lesson).
    """
    _scope(app_session, org=tenants.a, user=tenants.admin)
    sub = f"i82-twice-{tenants.suffix}"

    first = _bind(app_session, subject=sub, email=f"{sub}@example.test", name="Twice")
    assert first.member_id is not None, "the first bind produced no membership"

    with pytest.raises(DatabaseError) as caught, app_session.begin_nested():
        _bind(app_session, subject=sub, email=f"{sub}@example.test", name="Twice")

    # The refusal is a constraint, not a hand-rolled check two callers could
    # walk past together.
    assert "organization_members" in str(caught.value).lower()
    app_session.rollback()


def test_the_organization_comes_from_the_guc_not_from_an_argument(
    owner_session: Session,
) -> None:
    """🔴 A DEFINER THAT TOOK AN ORGANIZATION WOULD BE A CROSS-TENANT WRITE.

    The obvious signature mirrors the route's `principal.organization_id`. That
    would let an `admin.users` holder in one tenant create a membership in any
    tenant they could name — granted by accident, inside the change that
    removes a cross-tenant READ. ADR-029 caught the same reflex in its own
    first draft (`UPDATE status` on a GLOBAL row).

    Asserted on the signature, from `pg_proc`, because the absence of a
    parameter is the mechanism.
    """
    args = owner_session.execute(
        text(
            """
            SELECT pg_get_function_identity_arguments(p.oid)
            FROM pg_proc p
            JOIN pg_namespace n ON n.oid = p.pronamespace
            WHERE n.nspname = 'core' AND p.proname = 'bind_subject_to_organization'
            """
        )
    ).scalar_one()
    assert "uuid" not in args.lower(), (
        f"the signature is ({args}) — a uuid argument is almost certainly an "
        "organization, which would make this a cross-tenant write"
    )


def test_it_is_a_definer_owned_by_a_non_superuser(owner_session: Session) -> None:
    """Unpinned, a definer created by a migration run as `postgres` is a
    SUPERUSER with BYPASSRLS — permanently outside RLS, including after the
    I56/I58 cutover. 044 did exactly that while claiming otherwise, and it was
    found by reading `pg_proc`. So this reads `pg_proc`.
    """
    row = owner_session.execute(
        text(
            """
            SELECT pg_get_userbyid(p.proowner) AS owner, p.prosecdef, p.proconfig,
                   r.rolsuper, r.rolbypassrls
            FROM pg_proc p
            JOIN pg_namespace n ON n.oid = p.pronamespace
            JOIN pg_roles r     ON r.oid = p.proowner
            WHERE n.nspname = 'core' AND p.proname = 'bind_subject_to_organization'
            """
        )
    ).one()
    assert row.owner == "evercoat_owner", f"owner is {row.owner!r}"
    assert row.rolsuper is False, f"the owner {row.owner!r} is a SUPERUSER"
    # BOTH halves: `rolbypassrls` is not implied by `NOT rolsuper`, and a grep
    # across the test tree found ZERO assertions on it after 049's rewrite.
    assert row.rolbypassrls is False, (
        f"the owner {row.owner!r} has BYPASSRLS -- outside RLS permanently, "
        "including after the I56/I58 cutover"
    )
    assert row.prosecdef is True, "not SECURITY DEFINER"
    assert "search_path=core, pg_temp" in (row.proconfig or []), (
        f"search_path is {row.proconfig!r}, not the pinned 'core, pg_temp'"
    )


def test_public_cannot_execute_it(owner_session: Session) -> None:
    """Assert the PRIVILEGE, not the SQL (I81's lesson).

    EXECUTE to PUBLIC is the DEFAULT for a new function, so the REVOKE is
    load-bearing. Calling it successfully as `evercoat_app` proves the GRANT
    and says nothing about the REVOKE.
    """
    acl = owner_session.execute(
        text(
            """
            SELECT COALESCE(p.proacl::text[], ARRAY[]::text[])
            FROM pg_proc p
            JOIN pg_namespace n ON n.oid = p.pronamespace
            WHERE n.nspname = 'core' AND p.proname = 'bind_subject_to_organization'
            """
        )
    ).scalar_one()
    assert acl, "proacl is empty, which means the default applies: EXECUTE to PUBLIC"
    assert not [e for e in acl if e.startswith("=")], f"PUBLIC can execute it: {acl}"
    assert any(e.startswith("evercoat_app=X") for e in acl), f"evercoat_app cannot execute: {acl}"


def test_a_definer_write_does_not_widen_the_address_guards(
    app_session: Session, owner_session: Session, tenants: _Tenants
) -> None:
    """🔴 THE MEASUREMENT THAT AUTHORISED THIS MIGRATION, KEPT AS A TEST.

    ADR-029 rejected the atomic-bind design on measured evidence: a definer
    WRITES, the write fires ADR-028's address guards, and a trigger inside a
    definer owned by the table owner runs as that owner — bypassing RLS while
    FORCE is off. The guard then refused on a row in an organization the
    caller cannot see, and *the refusal itself disclosed that the address
    exists somewhere*. That is I83, rebuilt inside the guard that replaced it.

    ADR-029's own hardening (047) made both guards scope themselves by their
    own predicate, which removed the chain's second step. Re-measured with
    ADR-029's probes before writing this migration: the DEFINER path is
    ACCEPTED where it was REFUSED.

    ⚠️ THIS FUNCTION IS THAT WRITING DEFINER. So the measurement is kept here.
    An address held ONLY by a member of organization B must not cause a
    refusal for a caller scoped to organization A — the caller cannot see B,
    and a refusal would tell them the address exists.
    """
    only_in_b = f"i82-onlyb-{tenants.suffix}@example.test"

    # A member of organization B holds that address. Invisible to A.
    b_user = owner_session.execute(
        text(
            """
            INSERT INTO core.users (keycloak_sub, email, display_name)
            VALUES (:s, :e, 'B member') RETURNING id
            """
        ),
        {"s": f"i82-bmem-{tenants.suffix}", "e": only_in_b},
    ).scalar_one()
    owner_session.execute(
        text(
            """
            INSERT INTO core.organization_members (organization_id, user_id)
            VALUES (:o, :u)
            """
        ),
        {"o": tenants.b, "u": b_user},
    )
    owner_session.commit()

    # Organization A binds a DIFFERENT subject that submits the same address.
    _scope(app_session, org=tenants.a, user=tenants.admin)
    try:
        row = _bind(
            app_session,
            subject=f"i82-collide-{tenants.suffix}",
            email=only_in_b,
            name="Same address, different tenant",
        )
    except DatabaseError as exc:  # pragma: no cover - the regression being watched
        app_session.rollback()
        pytest.fail(
            "the address guard REFUSED inside the writing definer, on a row in "
            "an organization this caller cannot see. The refusal discloses that "
            "the address exists somewhere — I83, through the guard that replaced "
            "it. ADR-029 measured exactly this before migration 047 made both "
            "guards scope themselves explicitly; something has un-done that. "
            f"Driver said: {str(exc.orig).splitlines()[0]}"
        )

    assert row.member_id is not None, "the bind produced no membership"
    app_session.rollback()


def test_a_forged_organization_guc_cannot_drive_a_cross_tenant_write(
    app_session: Session, owner_session: Session, tenants: _Tenants
) -> None:
    """🔴 049 GRANTED A CROSS-TENANT WRITE. THIS IS THE REGRESSION TEST IT LACKED.

    The bind is SECURITY DEFINER, so its INSERT runs as `evercoat_owner` and
    RLS does not apply. 049 took the organization from `app.current_org` and
    stopped there — and a GUC is caller-settable by `evercoat_app`. Measured
    before 050: an actor who is an active member of organization A ONLY, with
    the GUC pointed at organization B, **successfully created a membership in
    B**. Before 049 the route did that INSERT itself, where
    `org_member_isolation` refused it. So 049 moved a write out from under RLS.

    Raised by Codex. *A cross-tenant WRITE, granted by accident, inside the
    change that removes a cross-tenant READ* — which 049's own header quotes
    from ADR-029 and then reproduced.

    050 makes the function PROVE the caller's standing:
    `core.authorization_for_current_session()` returns nothing for a user who
    is not an active member of the session's organization, so the forgery
    fails on itself.

    ⚠️ AND IT HAD NO TEST UNTIL NOW. The fix was verified by a throwaway probe
    and the suite would not have noticed it being reverted — which is the
    shape this file is otherwise full of warnings about.
    """
    # The fixture's actor administers organization A. Point the GUC at B,
    # where they are not a member at all.
    _scope(app_session, org=tenants.b, user=tenants.admin)

    with pytest.raises(DatabaseError) as caught:
        _bind(
            app_session,
            subject=f"i82-cross-{tenants.suffix}",
            email=f"i82-cross-{tenants.suffix}@example.test",
            name="cross-tenant attempt",
        )
    app_session.rollback()

    assert "not permitted" in str(caught.value).lower(), (
        f"the bind refused for the wrong reason: {caught.value}. It must be "
        "the standing check, not an incidental constraint — otherwise this "
        "test would keep passing after the check was removed."
    )

    # 🔴 AND THE POSTCONDITION IS ASKED OF `owner_session`, NOT `app_session`.
    #
    # This counted through the SAME session the attack ran in -- scoped to
    # organization B with an actor who is not a member of B. `org_member_isolation`
    # returns nothing to that session whether or not the row exists, so the
    # count was zero by construction: a check that passes because it cannot
    # see. Raised by Codex, and it is the fifth instance of that shape.
    #
    # `owner_session` is not subject to the policy, so a leaked row would be
    # counted. The identity is checked too: the exception must have rolled the
    # whole statement back, not merely the membership half of it.
    leaked = owner_session.execute(
        text("SELECT count(*) FROM core.organization_members WHERE organization_id = :o"),
        {"o": tenants.b},
    ).scalar_one()
    stranded = owner_session.execute(
        text("SELECT count(*) FROM core.users WHERE keycloak_sub = :s"),
        {"s": f"i82-cross-{tenants.suffix}"},
    ).scalar_one()
    app_session.rollback()
    assert leaked == 0, f"{leaked} membership(s) exist in the foreign organization"
    assert stranded == 0, "the refused bind left an identity behind"


def test_the_standing_check_needs_admin_users_not_merely_membership(
    app_session: Session, owner_session: Session, tenants: _Tenants
) -> None:
    """Membership alone is not authority.

    A user who genuinely belongs to the organization but holds no
    `admin.users` must still be refused — otherwise the check would be
    "are you here", which every member passes, rather than "may you do this".

    That distinction is the whole reason 050 asks
    `core.authorization_for_current_session()` for the PERMISSION rather than
    just confirming a membership row exists.
    """
    plain = owner_session.execute(
        text(
            """
            INSERT INTO core.users (keycloak_sub, email, display_name)
            VALUES (:s, :e, 'ordinary member') RETURNING id
            """
        ),
        {
            "s": f"i82-plain-{tenants.suffix}",
            "e": f"i82-plain-{tenants.suffix}@example.test",
        },
    ).scalar_one()
    owner_session.execute(
        text(
            """
            INSERT INTO core.organization_members (organization_id, user_id)
            VALUES (:o, :u)
            """
        ),
        {"o": tenants.a, "u": plain},
    )
    owner_session.commit()

    _scope(app_session, org=tenants.a, user=plain)
    with pytest.raises(DatabaseError) as caught:
        _bind(
            app_session,
            subject=f"i82-byplain-{tenants.suffix}",
            email=f"i82-byplain-{tenants.suffix}@example.test",
            name="invited by a non-admin",
        )
    app_session.rollback()
    assert "not permitted" in str(caught.value).lower()


def test_admin_users_in_one_organization_does_not_carry_into_another(
    app_session: Session, owner_session: Session, tenants: _Tenants
) -> None:
    """🔴 THE SHARPEST CASE, AND THE ONE A WEAKER CHECK WOULD PASS.

    A person who is an active member of BOTH organizations, holding
    `admin.users` in A and an ordinary role in B, must NOT be able to bind
    members into B.

    A check that confirmed *membership* would admit them: they really are a
    member of B. A check that asked "does this user hold admin.users
    anywhere" would admit them too. Only a check that asks what they hold **in
    the session's organization** refuses — which is what
    `core.authorization_for_current_session()` answers, because it joins
    through `core.organization_members` on the GUC's organization.

    Neither of the other two standing tests covers this: one uses a
    non-member, the other a member with no role at all. Both would keep
    passing against a weaker check. This one would not.
    """
    admin_role = owner_session.execute(
        text(
            """
            SELECT r.id FROM core.roles r
            JOIN core.role_permissions rp ON rp.role_id = r.id
            JOIN core.permissions p       ON p.id = rp.permission_id
            WHERE p.code = 'admin.users' LIMIT 1
            """
        )
    ).scalar_one()
    plain_role = owner_session.execute(
        text(
            """
            SELECT r.id FROM core.roles r
            WHERE r.id <> :admin
              AND NOT EXISTS (
                  SELECT 1 FROM core.role_permissions rp
                  JOIN core.permissions p ON p.id = rp.permission_id
                  WHERE rp.role_id = r.id AND p.code = 'admin.users'
              )
            LIMIT 1
            """
        ),
        {"admin": admin_role},
    ).scalar_one()

    dual = owner_session.execute(
        text(
            """
            INSERT INTO core.users (keycloak_sub, email, display_name)
            VALUES (:s, :e, 'member of both') RETURNING id
            """
        ),
        {"s": f"i82-dual-{tenants.suffix}", "e": f"i82-dual-{tenants.suffix}@example.test"},
    ).scalar_one()
    for org, role in ((tenants.a, admin_role), (tenants.b, plain_role)):
        member = owner_session.execute(
            text(
                """
                INSERT INTO core.organization_members (organization_id, user_id)
                VALUES (:o, :u) RETURNING id
                """
            ),
            {"o": org, "u": dual},
        ).scalar_one()
        owner_session.execute(
            text("INSERT INTO core.member_roles (member_id, role_id) VALUES (:m, :r)"),
            {"m": member, "r": role},
        )
    owner_session.commit()

    # Acting in B, where they are a member and NOT an administrator.
    _scope(app_session, org=tenants.b, user=dual)
    with pytest.raises(DatabaseError) as caught:
        _bind(
            app_session,
            subject=f"i82-carry-{tenants.suffix}",
            email=f"i82-carry-{tenants.suffix}@example.test",
            name="should not be bindable by them",
        )
    app_session.rollback()
    assert "not permitted" in str(caught.value).lower()

    # ...and the same person IS accepted in A, so the refusal above is about
    # the organization and not about them. Without this half the test would
    # pass against a gate that refuses everyone.
    _scope(app_session, org=tenants.a, user=dual)
    row = _bind(
        app_session,
        subject=f"i82-ok-{tenants.suffix}",
        email=f"i82-ok-{tenants.suffix}@example.test",
        name="bound where they administer",
    )
    assert row.member_id is not None
    app_session.rollback()


def test_no_returned_value_repeats_across_rolled_back_binds(
    app_session: Session, owner_session: Session, tenants: _Tenants
) -> None:
    """🔴 THE IDENTIFIER *WAS* THE EXISTENCE ANSWER (051).

    050 removed `identity_created` because it told a caller, for free, whether
    a Keycloak subject already existed somewhere on this platform. Codex,
    reviewing 050, pointed out that removing the flag did not remove the
    answer -- `user_id` carries it. Measured before it was believed:

        BEGIN; SELECT user_id FROM core.bind_subject_to_organization(S,...);
        ROLLBACK;                                                    -- twice

        subject that exists in another tenant : e55fea29  e55fea29   SAME
        subject that exists nowhere           : 6e0e24e8  22231d7c   DIFFER

    An existing identity is SELECTed, so its uuid repeats; a new one is minted
    per attempt, so it does not. Nothing is left behind either way. That is
    I83's oracle with a different column name, inside the migration that
    claimed to have removed it.

    ⚠️ THIS TESTS THE PROPERTY, NOT THE SHAPE. `test_044...returns_only_ids`
    names the permitted column and would catch `user_id` coming back under its
    own name. It would not catch a differently named column carrying the same
    bit, nor a `member_id` made deterministic from the subject. The property
    is what actually matters: **no value this function returns may repeat
    across rolled-back attempts**, because any value that does is the answer.
    """

    def bind_twice(subject: str) -> list[dict[str, object]]:
        seen = []
        for _ in range(2):
            _scope(app_session, org=tenants.a, user=tenants.admin)
            row = _bind(
                app_session,
                subject=subject,
                email=f"{uuid.uuid4().hex[:8]}@example.test",
                name="probe",
            )
            seen.append(dict(row._mapping))
            app_session.rollback()
        return seen

    # A subject that exists ONLY in the other tenant. Nothing about it is this
    # administrator's business -- not even whether it exists.
    foreign_sub = f"i82-foreign-{tenants.suffix}"
    foreign_user = owner_session.execute(
        text(
            "INSERT INTO core.users (keycloak_sub, email, display_name)"
            " VALUES (:s, :e, 'exists only in B') RETURNING id"
        ),
        {"s": foreign_sub, "e": f"{foreign_sub}@example.test"},
    ).scalar_one()
    owner_session.execute(
        text("INSERT INTO core.organization_members (organization_id, user_id) VALUES (:o, :u)"),
        {"o": tenants.b, "u": foreign_user},
    )
    owner_session.commit()

    existing = bind_twice(foreign_sub)
    absent = bind_twice(f"i82-nobody-{tenants.suffix}")

    for column in existing[0]:
        assert existing[0][column] != existing[1][column], (
            f"core.bind_subject_to_organization returned the same {column!r} "
            "from two rolled-back binds of a subject that exists in ANOTHER "
            "tenant. A value that repeats is the answer to 'does this subject "
            "already exist', it costs nothing, and it leaves no trace -- which "
            "is the oracle I83 was closed by DROPPING rather than renaming."
        )
    # The control half. Without it a function that returned a constant, or
    # nothing at all, would satisfy the loop above while being useless.
    for column in absent[0]:
        assert absent[0][column] != absent[1][column], (
            f"two binds of a brand-new subject returned the same {column!r}"
        )
    assert set(existing[0]) == {"member_id"}, (
        f"the bind returned {sorted(existing[0])}; only the membership it created may come back"
    )

    # And nothing survived the probing -- the reason the oracle was free.
    assert (
        owner_session.execute(
            text("SELECT count(*) FROM core.users WHERE keycloak_sub = :s"),
            {"s": f"i82-nobody-{tenants.suffix}"},
        ).scalar_one()
        == 0
    )
