"""I83 — an email address is an attribute, not a global key.

`core.users.email` carried `users_email_key`, a GLOBALLY unique constraint,
and unique constraints are enforced OUTSIDE row-level security. Measured
2026-08-25 as `evercoat_app` scoped to organization A:

    INSERT INTO core.users (keycloak_sub, email, display_name)
    VALUES ('throwaway', <an address held in organization B>, 'throwaway');
      -->  REFUSED by "users_email_key"          --> the route answers 409

    ... the same statement with an address nobody holds:
      -->  ACCEPTED                              --> the route answers 201

So a holder of `admin.users` in ANY tenant read platform-wide existence from
a status code, with a throwaway subject and no row left behind.

🔴 THE TEST THAT MATTERS IS THE BEHAVIOURAL ONE, NOT THE CATALOGUE ONE.
`test_the_global_constraint_is_gone` reads `pg_constraint` and would pass
against a schema where the oracle had been rebuilt some other way -- a
trigger, a definer, a check. It is here so a failure names its cause in one
line. `test_the_oracle_is_closed` is the security property.

⚠️ These tests COMMIT. `app_engine` is a separate connection from
`owner_session`, and `evercoat_owner` holds no membership in `evercoat_app`
so `SET ROLE` is refused. Two connections and an RLS-bearing role leave
exactly one option: commit, assert, clean up in a `finally`. The same
reasoning is written out at length in `test_032` and `test_044`.
"""

from __future__ import annotations

import uuid
from collections.abc import Iterator

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session


@pytest.fixture
def two_orgs_one_address(
    owner_session: Session, app_session: Session
) -> Iterator[dict[str, object]]:
    """Organization A with an admin, organization B with one member.

    B's member holds an address that A will try to probe for. Committed,
    because the assertions run on a different connection as a role RLS
    applies to. Removed in the `finally` regardless of outcome.

    🔴 THE FIXTURE ROLLS BACK `app_session` ITSELF, AND THAT IS NOT
    BELT-AND-BRACES.

    Every test below ends with `app_session.rollback()`, and a test that
    FAILS never reaches its last line. Its transaction then stays open
    holding row locks on `core.organization_members`, and this cleanup's
    `DELETE FROM core.organizations` blocks on them **forever** — the
    session never times out because pytest is not doing anything else.

    Measured while falsifying these tests by dropping the 046 guard: the
    run wedged with `DELETE ... FROM core.organizations` in `wait_event_type
    = Lock` behind an `idle in transaction` INSERT, and had to be killed.
    A suite that HANGS on a failure is worse than one that reports it,
    because the failure never gets reported at all.
    """
    suffix = uuid.uuid4().hex[:8]
    orgs: list[uuid.UUID] = []
    users: list[uuid.UUID] = []

    for label in ("A", "B"):
        orgs.append(
            owner_session.execute(
                text("INSERT INTO core.organizations (code, name) VALUES (:c,:n) RETURNING id"),
                {"c": f"I83-{label}-{suffix}", "n": f"I83 probe {label}"},
            ).scalar_one()
        )

    def make_user(sub: str, email: str, name: str, org: uuid.UUID) -> uuid.UUID:
        uid: uuid.UUID = owner_session.execute(
            text(
                "INSERT INTO core.users (keycloak_sub, email, display_name)"
                " VALUES (:s,:e,:n) RETURNING id"
            ),
            {"s": sub, "e": email, "n": name},
        ).scalar_one()
        users.append(uid)
        owner_session.execute(
            text("INSERT INTO core.organization_members (organization_id, user_id) VALUES (:o,:u)"),
            {"o": org, "u": uid},
        )
        return uid

    victim_email = f"victim-{suffix}@competitor.example"
    admin_a = make_user(f"i83-admin-{suffix}", f"admin-{suffix}@a.example", "I83 admin A", orgs[0])
    make_user(f"i83-victim-{suffix}", victim_email, "I83 victim B", orgs[1])
    owner_session.commit()

    try:
        yield {
            "org_a": orgs[0],
            "org_b": orgs[1],
            "admin_a": admin_a,
            "victim_email": victim_email,
            "suffix": suffix,
        }
    finally:
        # FIRST, before anything tries to take a lock the probing connection
        # may still be holding. See the docstring.
        app_session.rollback()
        owner_session.rollback()
        owner_session.execute(
            text("DELETE FROM core.organization_members WHERE organization_id = ANY(:o)"),
            {"o": orgs},
        )
        owner_session.execute(
            text("DELETE FROM core.users WHERE keycloak_sub LIKE :p"), {"p": f"i83-%-{suffix}"}
        )
        owner_session.execute(
            text("DELETE FROM core.organizations WHERE id = ANY(:o)"), {"o": orgs}
        )
        owner_session.commit()


def _scope(session: Session, org: uuid.UUID, user: uuid.UUID) -> None:
    session.execute(text("SELECT set_config('app.current_org', :o, true)"), {"o": str(org)})
    session.execute(text("SELECT set_config('app.current_user_id', :u, true)"), {"u": str(user)})


def _new_identity(session: Session, sub: str, email: str, name: str) -> uuid.UUID:
    """Insert an identity and return its id WITHOUT `RETURNING`.

    🔴 `INSERT ... RETURNING id` FAILS HERE, AND THE REASON IS 044'S READ
    POLICY, NOT THIS MIGRATION.

    `RETURNING` makes PostgreSQL apply the SELECT policy to the new row, and
    that policy admits a user only when the reader shares an organization
    with them. A freshly created identity has no membership yet, so it is
    invisible to the connection that just created it and the statement is
    refused. `app/api/admin.py` records the same fact from the other side:
    it reads the stored attributes AFTER the membership exists, because
    before that the lookup returns nothing.

    So the id is chosen here and inserted explicitly. That keeps these tests
    about migration 046 rather than about 044's visibility rule.
    """
    uid = uuid.uuid4()
    session.execute(
        text("INSERT INTO core.users (id, keycloak_sub, email, display_name) VALUES (:i,:s,:e,:n)"),
        {"i": uid, "s": sub, "e": email, "n": name},
    )
    return uid


def test_the_global_constraint_is_gone_and_identity_is_not(owner_session: Session) -> None:
    """Catalogue check. Names the cause when the behavioural tests fail.

    Both halves matter. Dropping `users_email_key` closes the oracle;
    dropping `users_keycloak_sub_key` with it would mean the same human
    could be created twice and the migration broke more than it fixed.
    """
    names = {
        row[0]
        for row in owner_session.execute(
            text(
                "SELECT conname FROM pg_constraint"
                " WHERE conrelid = 'core.users'::regclass AND contype = 'u'"
            )
        ).all()
    }
    assert "users_email_key" not in names, (
        "core.users still carries a GLOBAL unique constraint on email. Unique "
        "constraints are enforced outside RLS, so 201-vs-409 on "
        "POST /api/admin/members discloses platform-wide existence to any "
        "admin.users holder in any tenant. See migration 046 / I83."
    )
    assert "users_keycloak_sub_key" in names, (
        "core.users has lost its unique constraint on keycloak_sub. Identity "
        "is no longer unique and 046 removed more than the oracle."
    )


def test_the_replacement_guard_is_not_a_security_definer(owner_session: Session) -> None:
    """🔴 A DEFINER HERE WOULD REBUILD THE ORACLE INSIDE A TRIGGER.

    `core.deny_duplicate_address_in_organization` refuses a write based on
    rows it can read. As SECURITY INVOKER it reads only what the writing
    role may see, which within one organization is every member. As
    SECURITY DEFINER it would read every tenant and refuse on what it found
    there -- which is precisely the cross-tenant answer I83 removed, wearing
    a different mechanism.

    The catalogue is asked because a comment claiming INVOKER proves
    nothing; `pg_proc.prosecdef` is the fact.
    """
    row = owner_session.execute(
        text(
            """
            SELECT p.prosecdef, r.rolname
              FROM pg_proc p
              JOIN pg_namespace n ON n.oid = p.pronamespace
              JOIN pg_roles r     ON r.oid = p.proowner
             WHERE n.nspname = 'core'
               AND p.proname = 'deny_duplicate_address_in_organization'
            """
        )
    ).one_or_none()
    assert row is not None, (
        "core.deny_duplicate_address_in_organization does not exist. Migration "
        "046 dropped users_email_key and this is what replaced it; without it "
        "one organization's member list can hold the same address twice."
    )
    prosecdef, owner = row
    assert prosecdef is False, (
        "the per-organization address guard is SECURITY DEFINER. It reads "
        "core.users and core.organization_members and refuses on what it "
        "finds, so as a definer it answers questions about EVERY tenant -- "
        "rebuilding I83's oracle inside a trigger."
    )
    assert owner == "evercoat_owner", (
        f"the guard is owned by {owner!r}, not evercoat_owner. 046 states the "
        "owner explicitly; an unstated owner is how a function ends up owned "
        "by whoever ran the migration."
    )


def test_the_oracle_is_closed(app_session: Session, two_orgs_one_address: dict) -> None:
    """🔴 THE SECURITY PROPERTY.

    Organization A, holding `admin.users`, submits a throwaway subject with
    an address belonging to a member of organization B. Before 046 this was
    refused by `users_email_key` and the route turned it into 409, while an
    unused address returned 201 -- the difference IS the oracle.

    Both must now be accepted, and accepted identically. Asserting only that
    the known address works would pass against a database with no users at
    all, so the control case is asserted beside it.
    """
    fx = two_orgs_one_address
    _scope(app_session, fx["org_a"], fx["admin_a"])
    suffix = fx["suffix"]

    for label, email in (
        ("an address held in ANOTHER organization", fx["victim_email"]),
        ("an address nobody holds", f"nobody-{suffix}@competitor.example"),
    ):
        app_session.execute(
            text("INSERT INTO core.users (keycloak_sub, email, display_name) VALUES (:s,:e,:n)"),
            {"s": f"i83-probe-{uuid.uuid4().hex[:8]}-{suffix}", "e": email, "n": "throwaway"},
        )
        # Reached without an IntegrityError: the two cases are indistinguishable
        # to the caller, which is the whole point. A failure here surfaces as
        # the exception itself, naming the constraint that answered.
        assert True, label

    app_session.rollback()


def test_identity_is_still_unique(app_session: Session, two_orgs_one_address: dict) -> None:
    """Dropping the email key must not have made a subject creatable twice."""
    fx = two_orgs_one_address
    _scope(app_session, fx["org_a"], fx["admin_a"])
    sub = f"i83-dup-{fx['suffix']}"

    app_session.execute(
        text("INSERT INTO core.users (keycloak_sub, email, display_name) VALUES (:s,:e,:n)"),
        {"s": sub, "e": f"one-{fx['suffix']}@example.test", "n": "first"},
    )
    with pytest.raises(IntegrityError) as caught:
        app_session.execute(
            text("INSERT INTO core.users (keycloak_sub, email, display_name) VALUES (:s,:e,:n)"),
            {"s": sub, "e": f"two-{fx['suffix']}@example.test", "n": "second"},
        )
    assert "users_keycloak_sub_key" in str(caught.value), (
        "the second insert of the same keycloak_sub failed for some reason "
        f"other than the identity constraint: {caught.value}"
    )
    app_session.rollback()


def test_one_active_address_per_organization(
    app_session: Session, two_orgs_one_address: dict
) -> None:
    """The tenant-scoped rule that replaced the global one.

    Two identities may share an address -- that is what closes the oracle --
    but not as two ACTIVE members of the same organization, where a duplicate
    would make the member list ambiguous. The refusal discloses only what
    `list_members` already shows this caller.
    """
    fx = two_orgs_one_address
    _scope(app_session, fx["org_a"], fx["admin_a"])
    suffix = fx["suffix"]
    shared = f"shared-{suffix}@example.test"

    first = _new_identity(app_session, f"i83-one-{suffix}", shared, "One")
    second = _new_identity(app_session, f"i83-two-{suffix}", shared, "Two")

    app_session.execute(
        text("INSERT INTO core.organization_members (organization_id, user_id) VALUES (:o,:u)"),
        {"o": fx["org_a"], "u": first},
    )
    with pytest.raises(IntegrityError) as caught:
        app_session.execute(
            text("INSERT INTO core.organization_members (organization_id, user_id) VALUES (:o,:u)"),
            {"o": fx["org_a"], "u": second},
        )
    # 🔴 ASSERT THE FIELD THE ROUTE ACTUALLY BRANCHES ON.
    #
    # `app/api/admin.py` distinguishes this refusal from the
    # `organization_members_unique` race by reading
    # `exc.orig.diag.constraint_name`, because the two mean different things
    # to the caller and one message would describe the other wrongly. A
    # trigger's `RAISE ... USING CONSTRAINT = ...` does NOT put the name into
    # the exception's string form -- asserting on `str(exc)` passes for the
    # wrong reason or fails for one, and either way says nothing about
    # whether the route can tell them apart. Measured: `diag.constraint_name`
    # is populated and `diag.table_name` is None, so this is the field.
    diag = getattr(caught.value.orig, "diag", None)
    assert getattr(diag, "constraint_name", None) == (
        "organization_members_one_address_per_organization"
    ), (
        "the 046 guard did not name itself in diag.constraint_name, so "
        "app/api/admin.py cannot tell an address collision from an "
        "already-a-member race and will answer the wrong 409. Got: "
        f"{getattr(diag, 'constraint_name', None)!r} / {caught.value}"
    )
    app_session.rollback()


def test_the_guard_is_scoped_to_one_organization(
    app_session: Session, two_orgs_one_address: dict
) -> None:
    """🔴 OTHERWISE IT IS users_email_key WEARING A TRIGGER.

    The same address in a DIFFERENT organization must be accepted. Without
    this assertion the previous test passes just as well against a guard that
    refuses globally -- which would leave I83 wide open while the suite went
    green. Falsified by deleting `om.organization_id = NEW.organization_id`
    from the function: this test fails and the other does not.
    """
    fx = two_orgs_one_address
    _scope(app_session, fx["org_a"], fx["admin_a"])
    suffix = fx["suffix"]
    shared = f"cross-{suffix}@example.test"

    ids = [_new_identity(app_session, f"i83-x{n}-{suffix}", shared, f"Cross {n}") for n in (1, 2)]

    app_session.execute(
        text("INSERT INTO core.organization_members (organization_id, user_id) VALUES (:o,:u)"),
        {"o": fx["org_a"], "u": ids[0]},
    )
    # The GUC still names organization A; the row names organization B. The
    # INSERT policy on core.organization_members decides whether that is
    # allowed at all -- what is under test here is that the 046 guard does not
    # refuse it on ADDRESS grounds.
    # `SET LOCAL app.current_org = :o` is a SYNTAX ERROR -- SET takes no bind
    # parameter, which is why `app/core/db.py` uses set_config() and says so.
    app_session.execute(
        text("SELECT set_config('app.current_org', :o, true)"), {"o": str(fx["org_b"])}
    )
    app_session.execute(
        text("INSERT INTO core.organization_members (organization_id, user_id) VALUES (:o,:u)"),
        {"o": fx["org_b"], "u": ids[1]},
    )
    app_session.rollback()


def test_an_inactive_member_does_not_block_the_address(
    app_session: Session, two_orgs_one_address: dict
) -> None:
    """Deactivating somebody must not lock their address out of the tenant.

    Otherwise offboarding a person and onboarding their replacement at the
    same address becomes impossible, and the guard has turned a data-quality
    rule into a permanent squat inside one organization.
    """
    fx = two_orgs_one_address
    _scope(app_session, fx["org_a"], fx["admin_a"])
    suffix = fx["suffix"]
    shared = f"leaver-{suffix}@example.test"

    leaver = _new_identity(app_session, f"i83-leaver-{suffix}", shared, "Leaver")
    joiner = _new_identity(app_session, f"i83-joiner-{suffix}", shared, "Joiner")

    app_session.execute(
        text(
            "INSERT INTO core.organization_members (organization_id, user_id, status)"
            " VALUES (:o,:u,'inactive')"
        ),
        {"o": fx["org_a"], "u": leaver},
    )
    app_session.execute(
        text("INSERT INTO core.organization_members (organization_id, user_id) VALUES (:o,:u)"),
        {"o": fx["org_a"], "u": joiner},
    )
    app_session.rollback()
