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
    owner_session.execute(
        text(
            """
            INSERT INTO core.organization_members (organization_id, user_id)
            VALUES (:o, :u)
            """
        ),
        {"o": orgs[0], "u": admin_id},
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
            SELECT user_id, member_id, identity_created
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

    assert row.identity_created is True
    assert row.user_id is not None
    assert row.member_id is not None

    org = app_session.execute(
        text("SELECT organization_id FROM core.organization_members WHERE id = :m"),
        {"m": row.member_id},
    ).scalar_one()
    assert org == tenants.a, "the membership was created in the wrong organization"


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
    assert first.user_id is not None, "the first bind produced no identity"

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
                   r.rolsuper
            FROM pg_proc p
            JOIN pg_namespace n ON n.oid = p.pronamespace
            JOIN pg_roles r     ON r.oid = p.proowner
            WHERE n.nspname = 'core' AND p.proname = 'bind_subject_to_organization'
            """
        )
    ).one()
    assert row.owner == "evercoat_owner", f"owner is {row.owner!r}"
    assert row.rolsuper is False, f"the owner {row.owner!r} is a SUPERUSER"
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

    assert row.user_id is not None, "the bind produced no identity"
    app_session.rollback()
