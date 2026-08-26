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

⚠️ MIGRATION 052 REPLACED THIS RULE'S MECHANISM, AND THESE TESTS MOVED WITH
IT RATHER THAN BEING DELETED ALONGSIDE IT. 046 enforced "one active member per
address per organization" with two SECURITY INVOKER trigger functions holding
an advisory lock, because the address lived on the GLOBAL `core.users` while
the rule is per-organization and no index spans two tables. 052 puts the
address ON the membership row (I106), at which point the whole rule is one
partial unique index on `(organization_id, email) WHERE status = 'active'` --
insert, rename and reactivation alike.

The properties are unchanged and every one of them is still asserted here:
tenant-scoped, active-only, refuses inside one organization, accepts across
two, holds under concurrency, and names itself the way `app/api/admin.py`
classifies its 409. What changed is that the tenant scope is now the INDEX
KEY rather than a predicate somebody has to keep writing correctly.

⚠️ AND THEY RUN AS THE OWNER NOW. 052 revoked INSERT on
`core.organization_members` from `evercoat_app` (I108), so the runtime role
reaches membership creation only through `core.bind_subject_to_organization`.
A unique index applies to every role identically, so the owner exercises the
same mechanism; that the app role cannot take this path at all is asserted in
`test_052_an_identity_has_no_tenant_attributes.py`.

⚠️ These tests COMMIT. `app_engine` is a separate connection from
`owner_session`, and `evercoat_owner` holds no membership in `evercoat_app`
so `SET ROLE` is refused. Two connections and an RLS-bearing role leave
exactly one option: commit, assert, clean up in a `finally`. The same
reasoning is written out at length in `test_032` and `test_044`.
"""

from __future__ import annotations

import threading
import uuid
from collections.abc import Iterator

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker


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
            text(
                "INSERT INTO core.organization_members (organization_id, user_id, email,"
                " display_name) SELECT :o, :u, u.email, u.display_name FROM core.users u WHERE"
                " u.id = :u"
            ),
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

    046 enforced this rule with two SECURITY INVOKER trigger functions, and
    the choice was load-bearing: as DEFINERs they would have read every tenant
    and refused on what they found there, which is the cross-tenant answer I83
    removed, wearing a different mechanism.

    ⚠️ MIGRATION 052 REPLACED BOTH WITH A PARTIAL UNIQUE INDEX, so the
    question this test asks has to change with the mechanism rather than be
    deleted with it. 046 could not use an index: the address lived on the
    GLOBAL `core.users` while the rule is per-organization, and no index spans
    two tables. 052 puts the address ON the membership row, at which point
    `(organization_id, email) WHERE status = 'active'` says the whole rule in
    one object -- INSERT, rename and reactivation alike, with no advisory lock
    and no window where two writers both pass.

    🔴 THE PROPERTY IS THE KEY, AND IT IS ASSERTED AS THE KEY. `users_email_key`
    was `(email)` platform-wide, so its refusal answered "does this address
    exist ANYWHERE". This index LEADS WITH `organization_id`, so a collision
    necessarily involves a row in the organization the writer named -- a member
    `list_members` already shows them. An index that lost that leading column,
    or its `WHERE status = 'active'`, would be `users_email_key` again.
    """
    trigger_functions = (
        owner_session.execute(
            text(
                """
            SELECT p.proname
              FROM pg_proc p
              JOIN pg_namespace n ON n.oid = p.pronamespace
             WHERE n.nspname = 'core'
               AND p.proname = ANY(:names)
            """
            ),
            {
                "names": [
                    "deny_duplicate_address_in_organization",
                    "deny_address_collision_on_rename",
                ]
            },
        )
        .scalars()
        .all()
    )
    assert trigger_functions == [], (
        f"046's trigger guards are still installed: {trigger_functions}. 052 "
        "replaced them with a unique index, and a rule enforced twice by two "
        "mechanisms is a rule nobody can reason about -- the trigger reads "
        "core.users, which no longer carries the address the index enforces."
    )

    index = owner_session.execute(
        text(
            """
            SELECT i.indisunique,
                   pg_get_expr(i.indpred, i.indrelid) AS predicate,
                   (SELECT a.attname
                      FROM pg_attribute a
                     WHERE a.attrelid = i.indrelid
                       AND a.attnum = i.indkey[0]) AS first_key
              FROM pg_class c
              JOIN pg_namespace n ON n.oid = c.relnamespace
              JOIN pg_index i     ON i.indexrelid = c.oid
             WHERE n.nspname = 'core'
               AND c.relname = 'organization_members_one_address_per_organization'
            """
        )
    ).one_or_none()
    assert index is not None, (
        "there is no organization_members_one_address_per_organization index. "
        "046's guards are gone (above) and nothing replaced them, so one "
        "organization's member list can hold the same address twice -- and "
        "app/api/admin.py classifies its 409 by that exact name."
    )
    assert index.indisunique is True, "the index is not UNIQUE, so it enforces nothing"
    assert index.first_key == "organization_id", (
        f"the index leads with {index.first_key!r}, not organization_id. A key "
        "that does not lead with the tenant is users_email_key wearing a "
        "partial index: its refusal answers whether an address exists in some "
        "organization the writer cannot see, which is I83."
    )
    assert index.predicate is not None, (
        "the index is not PARTIAL. Without a predicate it covers inactive "
        "members too, so deactivating somebody permanently squats their "
        "address inside the organization."
    )
    assert "active" in index.predicate, (
        f"the index predicate is {index.predicate!r}, which does not mention "
        "the active status, so their replacement can never be onboarded at "
        "that address."
    )


def test_the_oracle_is_closed(app_session: Session, two_orgs_one_address: dict) -> None:
    """🔴 THE SECURITY PROPERTY.

    Organization A, holding `admin.users`, submits a throwaway subject with
    an address belonging to a member of organization B. Before 046 this was
    refused by `users_email_key` and the route turned it into 409, while an
    unused address returned 201 -- the difference IS the oracle.

    Both must now be accepted, and accepted IDENTICALLY. Asserting only that
    the known address works would pass against a database with no users at
    all, so the control case is measured beside it.

    🔴 THE OUTCOMES ARE CAPTURED AND COMPARED, NOT LEFT TO AN EXCEPTION.
    The first version ended each iteration with `assert True, label`, which
    Codex correctly called an assertion incapable of failing. The test still
    failed when the fix was reverted -- the insert raised -- but nothing in it
    stated the property, and "it happens to raise before reaching a no-op
    assert" is not a test of indistinguishability. Both outcomes are now
    recorded and required to be the same.
    """
    fx = two_orgs_one_address
    _scope(app_session, fx["org_a"], fx["admin_a"])
    suffix = fx["suffix"]

    outcomes: dict[str, str] = {}
    for label, email in (
        ("an address held in ANOTHER organization", fx["victim_email"]),
        ("an address nobody holds", f"nobody-{suffix}@competitor.example"),
    ):
        try:
            app_session.execute(
                text(
                    "INSERT INTO core.users (keycloak_sub, email, display_name) VALUES (:s,:e,:n)"
                ),
                {
                    "s": f"i83-probe-{uuid.uuid4().hex[:8]}-{suffix}",
                    "e": email,
                    "n": "throwaway",
                },
            )
            outcomes[label] = "accepted"
        except IntegrityError as exc:
            app_session.rollback()
            _scope(app_session, fx["org_a"], fx["admin_a"])
            constraint = getattr(getattr(exc.orig, "diag", None), "constraint_name", None)
            outcomes[label] = f"refused by {constraint}"

    assert len(set(outcomes.values())) == 1, (
        "the two cases are DISTINGUISHABLE, which is the oracle: an "
        "admin.users holder submits a throwaway subject with a guessed "
        f"address and reads existence from the difference. {outcomes}"
    )
    assert set(outcomes.values()) == {"accepted"}, (
        "both cases were refused. The oracle is closed, but creating an "
        f"identity no longer works at all: {outcomes}"
    )
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


def _add_member(
    session: Session,
    org: uuid.UUID,
    user: uuid.UUID,
    email: str,
    name: str,
    status: str = "active",
) -> None:
    """Create a membership carrying the address THIS organization uses.

    🔴 AS THE OWNER, AND THAT IS THE POINT OF 052's OTHER HALF.

    These tests used to insert memberships through `app_session`. Migration
    052 revoked INSERT on `core.organization_members` from `evercoat_app`
    (I108): a membership row makes any global identity readable under 044's
    policy, so an ordinary member could manufacture one naming an arbitrary
    `user_id`, read the identity and roll back. The runtime role now reaches
    membership creation only through `core.bind_subject_to_organization`,
    which takes the organization from the session and proves the caller
    administers it -- covered by `test_049_atomic_bind.py`.

    The rule under test here is a unique INDEX, which applies to every role
    identically, so exercising it as the owner tests the same mechanism. That
    `evercoat_app` cannot take this path at all is asserted in
    `test_052_an_identity_has_no_tenant_attributes.py`.
    """
    session.execute(
        text(
            "INSERT INTO core.organization_members"
            " (organization_id, user_id, status, email, display_name)"
            " VALUES (:o, :u, :st, :e, :n)"
        ),
        {"o": org, "u": user, "st": status, "e": email, "n": name},
    )


def test_one_active_address_per_organization(
    owner_session: Session, two_orgs_one_address: dict
) -> None:
    """The tenant-scoped rule that replaced the global one.

    Two identities may share an address -- that is what closes the oracle --
    but not as two ACTIVE members of the same organization, where a duplicate
    would make the member list ambiguous. The refusal discloses only what
    `list_members` already shows this caller.
    """
    fx = two_orgs_one_address
    suffix = fx["suffix"]
    shared = f"shared-{suffix}@example.test"

    first = _new_identity(owner_session, f"i83-one-{suffix}", shared, "One")
    second = _new_identity(owner_session, f"i83-two-{suffix}", shared, "Two")

    _add_member(owner_session, fx["org_a"], first, shared, "One")
    with pytest.raises(IntegrityError) as caught:
        _add_member(owner_session, fx["org_a"], second, shared, "Two")

    # 🔴 ASSERT THE FIELD THE ROUTE ACTUALLY BRANCHES ON.
    #
    # `app/api/admin.py` distinguishes this refusal from the
    # `organization_members_unique` race by reading
    # `exc.orig.diag.constraint_name`, because the two mean different things
    # to the caller and one message would describe the other wrongly. It is
    # also why 052 gave the INDEX the name 046's TRIGGER had: renaming it
    # would silently turn a correct 409 into "the membership could not be
    # created" -- a 500 -- and nothing else in the suite reads the name.
    diag = getattr(caught.value.orig, "diag", None)
    assert getattr(diag, "constraint_name", None) == (
        "organization_members_one_address_per_organization"
    ), (
        "the address guard did not name itself in diag.constraint_name, so "
        "app/api/admin.py cannot tell an address collision from an "
        "already-a-member race and will answer the wrong 409. Got: "
        f"{getattr(diag, 'constraint_name', None)!r} / {caught.value}"
    )
    owner_session.rollback()


def test_the_guard_is_scoped_to_one_organization(
    owner_session: Session, two_orgs_one_address: dict
) -> None:
    """🔴 OTHERWISE IT IS users_email_key WEARING A PARTIAL INDEX.

    The same address in a DIFFERENT organization must be accepted. Without
    this assertion the previous test passes just as well against a rule that
    refuses globally -- which would leave I83 wide open while the suite went
    green. Falsified by dropping `organization_id` from the index key: this
    test fails and the other does not.
    """
    fx = two_orgs_one_address
    suffix = fx["suffix"]
    shared = f"cross-{suffix}@example.test"

    ids = [_new_identity(owner_session, f"i83-x{n}-{suffix}", shared, f"Cross {n}") for n in (1, 2)]

    _add_member(owner_session, fx["org_a"], ids[0], shared, "Cross 1")
    _add_member(owner_session, fx["org_b"], ids[1], shared, "Cross 2")
    owner_session.rollback()


def test_an_inactive_member_does_not_block_the_address(
    owner_session: Session, two_orgs_one_address: dict
) -> None:
    """Deactivating somebody must not lock their address out of the tenant.

    Otherwise offboarding a person and onboarding their replacement at the
    same address becomes impossible, and the rule has turned a data-quality
    guarantee into a permanent squat inside one organization. This is what
    the index's `WHERE status = 'active'` predicate buys.
    """
    fx = two_orgs_one_address
    suffix = fx["suffix"]
    shared = f"leaver-{suffix}@example.test"

    leaver = _new_identity(owner_session, f"i83-leaver-{suffix}", shared, "Leaver")
    joiner = _new_identity(owner_session, f"i83-joiner-{suffix}", shared, "Joiner")

    _add_member(owner_session, fx["org_a"], leaver, shared, "Leaver", status="inactive")
    _add_member(owner_session, fx["org_a"], joiner, shared, "Joiner")
    owner_session.rollback()


def test_an_address_cannot_be_taken_by_renaming(
    owner_session: Session, two_orgs_one_address: dict
) -> None:
    """🔴 A RULE ENFORCED ON INSERT AND NOT ON UPDATE IS BYPASSED IN PLACE.

    Raised by Codex against 046 and measured before its second trigger
    existed: changing the address on the row directly moved no membership, so
    the INSERT-side trigger never fired and two active members of one
    organization ended up holding one address. 046 needed a SECOND trigger,
    on a SECOND table, to cover it.

    052 needs neither. A unique index is consulted on every write to the
    indexed columns, so the rename path is the same mechanism as the insert
    path -- and there is no longer a second table to bypass it through, since
    the address the rule is about now lives on the membership itself.
    """
    fx = two_orgs_one_address
    suffix = fx["suffix"]
    taken = f"taken-{suffix}@example.test"

    holder = _new_identity(owner_session, f"i83-holder-{suffix}", taken, "Holder")
    renamer = _new_identity(
        owner_session, f"i83-renamer-{suffix}", f"renamer-{suffix}@example.test", "Renamer"
    )
    _add_member(owner_session, fx["org_a"], holder, taken, "Holder")
    _add_member(owner_session, fx["org_a"], renamer, f"renamer-{suffix}@example.test", "Renamer")

    with pytest.raises(IntegrityError) as caught:
        owner_session.execute(
            text(
                """
                UPDATE core.organization_members SET email = :e
                 WHERE organization_id = :o AND user_id = :u
                """
            ),
            {"e": taken, "o": fx["org_a"], "u": renamer},
        )
    diag = getattr(caught.value.orig, "diag", None)
    assert getattr(diag, "constraint_name", None) == (
        "organization_members_one_address_per_organization"
    ), (
        "renaming a member onto a colleague's address was refused by something "
        f"other than the address index: {getattr(diag, 'constraint_name', None)!r}"
    )
    owner_session.rollback()


def test_reactivating_onto_a_taken_address_is_refused(
    owner_session: Session, two_orgs_one_address: dict
) -> None:
    """The third write path, which the INSERT and UPDATE tests do not cover.

    An inactive member is allowed to hold an address somebody else now uses --
    the test above depends on it. Flipping them back to `active` must then be
    refused, or that exemption IS the bypass. 046's trigger reached this only
    because somebody remembered a `WHEN (NEW.status = 'active')` clause on an
    `UPDATE OF ... status` trigger; the index reaches it because `status` is
    in its predicate, which is one fewer thing to remember.
    """
    fx = two_orgs_one_address
    suffix = fx["suffix"]
    shared = f"revive-{suffix}@example.test"

    leaver = _new_identity(owner_session, f"i83-rev1-{suffix}", shared, "Leaver")
    joiner = _new_identity(owner_session, f"i83-rev2-{suffix}", shared, "Joiner")
    _add_member(owner_session, fx["org_a"], leaver, shared, "Leaver", status="inactive")
    _add_member(owner_session, fx["org_a"], joiner, shared, "Joiner")

    with pytest.raises(IntegrityError):
        owner_session.execute(
            text(
                """
                UPDATE core.organization_members SET status = 'active'
                 WHERE organization_id = :o AND user_id = :u
                """
            ),
            {"o": fx["org_a"], "u": leaver},
        )
    owner_session.rollback()


def test_the_guard_holds_under_concurrency(
    owner_engine, owner_session: Session, two_orgs_one_address: dict
) -> None:
    """🔴 A CHECK THAT DECIDES BY SELECT IS NOT A UNIQUE INDEX.

    Measured against 046's first draft, before its advisory lock existed, on
    two real connections:

        session 1 inserted (uncommitted)
        session 2 inserted (uncommitted) -- the trigger did NOT see session 1
        session 1 committed
        session 2 committed
        ACTIVE members of one organization holding the address: 2

    Under READ COMMITTED neither transaction sees the other's uncommitted row,
    so both `EXISTS` came back empty and both committed. ADR-028 said the rule
    was "enforced"; that was true serially and false under concurrency -- a
    comment asserting a rule the code did not implement.

    046 fixed it with `pg_advisory_xact_lock`. 052 does not need one: this is
    now a real unique index, and PostgreSQL blocks the second inserter on the
    first's uncommitted key until that transaction ends. **The property is
    unchanged and the mechanism is smaller**, which is why this test is kept
    rather than deleted with the lock -- it asserts BOTH halves, that the
    second writer is made to WAIT and that it is then REFUSED. Without the
    wait there is nothing to refuse.

    Two fresh connections, because the two sessions must be in flight at the
    same time -- a single session cannot race itself. As the OWNER since 052:
    `evercoat_app` no longer holds INSERT on this table (I108). The index is
    role-independent, so the race is the same race.
    """
    fx = two_orgs_one_address
    suffix = fx["suffix"]
    shared = f"race-{suffix}@example.test"

    first = uuid.uuid4()
    second = uuid.uuid4()
    for uid, sub in ((first, "r1"), (second, "r2")):
        owner_session.execute(
            text(
                "INSERT INTO core.users (id, keycloak_sub, email, display_name)"
                " VALUES (:i,:s,:e,:n)"
            ),
            {"i": uid, "s": f"i83-{sub}-{suffix}", "e": shared, "n": f"Racer {sub}"},
        )
    owner_session.commit()

    maker = sessionmaker(bind=owner_engine)
    s1, s2 = maker(), maker()

    insert = text(
        "INSERT INTO core.organization_members"
        " (organization_id, user_id, email, display_name)"
        " VALUES (:o, :u, :e, :n)"
    )
    outcome: dict[str, str] = {}

    def second_writer() -> None:
        try:
            s2.execute(insert, {"o": fx["org_a"], "u": second, "e": shared, "n": "Racer r2"})
            s2.commit()
            outcome["result"] = "committed"
        except IntegrityError:
            outcome["result"] = "refused"
        except Exception as exc:  # noqa: BLE001
            outcome["result"] = f"error: {exc}"

    try:
        s1.execute(insert, {"o": fx["org_a"], "u": first, "e": shared, "n": "Racer r1"})

        worker = threading.Thread(target=second_writer, daemon=True)
        worker.start()
        worker.join(timeout=3)
        assert worker.is_alive(), (
            "the second writer finished while the first still held its transaction "
            f"open ({outcome.get('result')}). Nothing serialised the two, so the "
            "rule is a best-effort check and not a constraint."
        )

        s1.commit()
        worker.join(timeout=20)
        assert outcome.get("result") == "refused", (
            f"the second writer was not refused after the first committed: {outcome.get('result')}"
        )

        survivors = owner_session.execute(
            text(
                """
                SELECT count(*) FROM core.organization_members m
                WHERE m.organization_id = :o AND m.status = 'active' AND m.email = :e
                """
            ),
            {"o": fx["org_a"], "e": shared},
        ).scalar_one()
        assert survivors == 1, (
            f"{survivors} active members of one organization hold {shared}. Both "
            "concurrent writers got through, so the rule is not enforced."
        )
    finally:
        for s in (s1, s2):
            try:
                s.rollback()
                s.close()
            except Exception:  # noqa: BLE001, S110
                # Best effort. These two connections exist only for this test
                # and the owner-side cleanup below is what must not be skipped.
                pass
        owner_session.rollback()
        owner_session.execute(
            text("DELETE FROM core.organization_members WHERE user_id = ANY(:u)"),
            {"u": [first, second]},
        )
        owner_session.execute(
            text("DELETE FROM core.users WHERE id = ANY(:u)"), {"u": [first, second]}
        )
        owner_session.commit()


def test_the_rule_does_not_answer_for_another_tenant(
    owner_session: Session, two_orgs_one_address: dict
) -> None:
    """🔴 A RULE THAT REFUSES ON A ROW YOU CANNOT SEE IS AN ORACLE AGAIN.

    046's rename guard refused when the new address already belonged to an
    active member of an organization the writer shares with the person being
    renamed. As a SECURITY DEFINER -- or with a join that reached past RLS --
    it would have refused on an address held only in a tenant the caller
    cannot see, and that refusal would tell them the address exists somewhere
    on the platform. I83, rebuilt inside its own replacement, and 047 had to
    make the guard scope itself by its own predicate to stop it.

    ⚠️ 052 MAKES THE QUESTION STRUCTURAL RATHER THAN BEHAVIOURAL, and the
    test moves with it. The rule is a unique index keyed
    `(organization_id, email)`. A key that leads with the tenant CANNOT
    collide across tenants -- there is no predicate to get wrong, no security
    context to get wrong, and nothing a later migration can quietly widen
    except the key itself, which
    `test_the_replacement_guard_is_not_a_security_definer` asserts directly.

    The shape that made the question live is still exercised: a person who is
    an active member of BOTH organizations, given in organization A an address
    held only in organization B. It must be ACCEPTED.

    ⚠️ Accepting it is a MISS, not a win -- organization B is unaffected but
    the platform now has that address twice. That is the trade ADR-028 states
    plainly: missing inside a tenant you can see beats answering about one you
    cannot.
    """
    fx = two_orgs_one_address
    suffix = fx["suffix"]
    only_in_b = f"only-in-b-{suffix}@example.test"

    both = _new_identity(owner_session, f"i83-both-{suffix}", f"both-{suffix}@example.test", "Both")
    b_member = _new_identity(owner_session, f"i83-bonly-{suffix}", only_in_b, "B only")

    _add_member(owner_session, fx["org_b"], b_member, only_in_b, "B only")
    _add_member(owner_session, fx["org_b"], both, f"both-{suffix}@example.test", "Both")
    _add_member(owner_session, fx["org_a"], both, f"both-{suffix}@example.test", "Both")

    try:
        owner_session.execute(
            text(
                """
                UPDATE core.organization_members SET email = :e
                 WHERE organization_id = :o AND user_id = :u
                """
            ),
            {"e": only_in_b, "o": fx["org_a"], "u": both},
        )
    except IntegrityError as exc:
        constraint = getattr(getattr(exc.orig, "diag", None), "constraint_name", None)
        owner_session.rollback()
        pytest.fail(
            "giving a member of organization A an address held only in "
            f"organization B was REFUSED (constraint {constraint!r}). That "
            "refusal discloses the address exists somewhere on the platform, "
            "which re-opens I83 inside the rule that replaced it. The index "
            "key must lead with organization_id."
        )
    owner_session.rollback()
