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
               AND p.proname = ANY(:names)
            """
        ),
        {
            "names": [
                "deny_duplicate_address_in_organization",
                "deny_address_collision_on_rename",
            ]
        },
    ).all()
    assert len(row) == 2, (
        "046 installs TWO guards -- one on core.organization_members for the "
        "INSERT path and one on core.users for the rename path -- and this "
        f"database has {len(row)}. A rule enforced on INSERT and not on UPDATE "
        "is bypassed by changing the address in place."
    )
    for prosecdef, owner in row:
        assert prosecdef is False, (
            "an address guard is SECURITY DEFINER. Both read core.users and "
            "core.organization_members and refuse on what they find, so as "
            "definers they answer questions about EVERY tenant -- rebuilding "
            "I83's oracle inside a trigger."
        )
        assert owner == "evercoat_owner", (
            f"a guard is owned by {owner!r}, not evercoat_owner. 046 states the "
            "owner explicitly; an unstated owner is how a function ends up "
            "owned by whoever ran the migration."
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


def test_an_address_cannot_be_taken_by_renaming(
    app_session: Session, two_orgs_one_address: dict
) -> None:
    """🔴 THE MEMBERSHIP TRIGGER IS BYPASSED BY CHANGING THE ADDRESS IN PLACE.

    Raised by Codex and measured before the second trigger existed:
    `evercoat_app` holds UPDATE on `core.users` and 044's UPDATE policy admits
    a user who shares an organization with the writer, so

        UPDATE core.users SET email = <a colleague's address> WHERE id = ...

    was ACCEPTED and left two active members of one organization holding it.
    No membership row moved, so the trigger on `core.organization_members`
    never fired.

    That path also made the schema WEAKER than before 046, because
    `users_email_key` covered updates as well as inserts. A rule enforced on
    INSERT and not on UPDATE is a shape this repository has shipped before.
    """
    fx = two_orgs_one_address
    _scope(app_session, fx["org_a"], fx["admin_a"])
    suffix = fx["suffix"]
    taken = f"taken-{suffix}@example.test"

    holder = _new_identity(app_session, f"i83-holder-{suffix}", taken, "Holder")
    renamer = _new_identity(
        app_session, f"i83-renamer-{suffix}", f"renamer-{suffix}@example.test", "Renamer"
    )
    for uid in (holder, renamer):
        app_session.execute(
            text("INSERT INTO core.organization_members (organization_id, user_id) VALUES (:o,:u)"),
            {"o": fx["org_a"], "u": uid},
        )

    with pytest.raises(IntegrityError) as caught:
        app_session.execute(
            text("UPDATE core.users SET email = :e WHERE id = :u"),
            {"e": taken, "u": renamer},
        )
    diag = getattr(caught.value.orig, "diag", None)
    assert getattr(diag, "constraint_name", None) == (
        "users_address_stays_unique_in_organization"
    ), (
        "renaming a member onto a colleague's address was refused by something "
        f"other than the 046 rename guard: {getattr(diag, 'constraint_name', None)!r}"
    )
    app_session.rollback()


def test_the_guard_holds_under_concurrency(
    app_engine, owner_session: Session, two_orgs_one_address: dict
) -> None:
    """🔴 A TRIGGER THAT DECIDES BY SELECT IS NOT A UNIQUE INDEX.

    Measured before the advisory lock existed, on two real connections:

        session 1 inserted (uncommitted)
        session 2 inserted (uncommitted) -- the trigger did NOT see session 1
        session 1 committed
        session 2 committed
        ACTIVE members of one organization holding the address: 2

    Under READ COMMITTED neither transaction sees the other's uncommitted
    row, so both `EXISTS` come back empty and both commit. The comments and
    ADR-028 said the rule was "enforced"; that was true serially and false
    under concurrency — a comment asserting a rule the code did not
    implement.

    `pg_advisory_xact_lock` on (organization, address) is the mechanism that
    makes the claim true, the same one `audit.chain_row()` uses. This test
    asserts BOTH halves: that the second writer is made to WAIT, and that it
    is then REFUSED. Without the wait there is nothing to refuse.

    Two fresh connections, because the two sessions must be in flight at the
    same time — a single session cannot race itself.
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

    maker = sessionmaker(bind=app_engine)
    s1, s2 = maker(), maker()
    for s in (s1, s2):
        s.execute(text("SELECT set_config('app.current_org', :v, true)"), {"v": str(fx["org_a"])})
        s.execute(
            text("SELECT set_config('app.current_user_id', :v, true)"),
            {"v": str(fx["admin_a"])},
        )

    outcome: dict[str, str] = {}

    def second_writer() -> None:
        try:
            s2.execute(
                text(
                    "INSERT INTO core.organization_members (organization_id, user_id)"
                    " VALUES (:o,:u)"
                ),
                {"o": fx["org_a"], "u": second},
            )
            s2.commit()
            outcome["result"] = "committed"
        except IntegrityError:
            outcome["result"] = "refused"
        except Exception as exc:  # noqa: BLE001
            outcome["result"] = f"error: {exc}"

    try:
        s1.execute(
            text("INSERT INTO core.organization_members (organization_id, user_id) VALUES (:o,:u)"),
            {"o": fx["org_a"], "u": first},
        )

        worker = threading.Thread(target=second_writer, daemon=True)
        worker.start()
        worker.join(timeout=3)
        assert worker.is_alive(), (
            "the second writer finished while the first still held its transaction "
            f"open ({outcome.get('result')}). Nothing serialised the two, so the "
            "guard is a best-effort check and not a constraint."
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
                JOIN core.users u ON u.id = m.user_id
                WHERE m.organization_id = :o AND m.status = 'active' AND u.email = :e
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


def test_the_rename_guard_does_not_answer_for_another_tenant(
    app_session: Session, owner_session: Session, two_orgs_one_address: dict
) -> None:
    """🔴 A GUARD THAT REFUSES ON A ROW YOU CANNOT SEE IS AN ORACLE AGAIN.

    The rename guard added after review refuses when the new address already
    belongs to an active member of an organization the writer shares with the
    user being renamed. If it were a SECURITY DEFINER — or if its join
    reached past RLS — it would refuse on an address held only in a tenant the
    caller cannot see, and that refusal would tell them the address exists
    somewhere on the platform. That is exactly the channel migration 046
    removed, rebuilt inside its own replacement.

    So the shape that makes the question live is asserted directly: a user who
    is an active member of BOTH organizations, renamed onto an address held
    only in the one the caller is NOT scoped to. It must be ACCEPTED.

    ⚠️ Accepting it is a MISS, not a win — organization B now has two active
    members at one address. That is the trade ADR-028 states plainly: missing
    inside a tenant you can see beats answering about one you cannot.

    Falsified by making `core.deny_address_collision_on_rename` SECURITY
    DEFINER: the rename is then refused and this test fails.
    """
    fx = two_orgs_one_address
    suffix = fx["suffix"]
    only_in_b = f"only-in-b-{suffix}@example.test"

    both = uuid.uuid4()
    b_member = uuid.uuid4()
    owner_session.execute(
        text("INSERT INTO core.users (id, keycloak_sub, email, display_name) VALUES (:i,:s,:e,:n)"),
        {"i": both, "s": f"i83-both-{suffix}", "e": f"both-{suffix}@example.test", "n": "Both"},
    )
    owner_session.execute(
        text("INSERT INTO core.users (id, keycloak_sub, email, display_name) VALUES (:i,:s,:e,:n)"),
        {"i": b_member, "s": f"i83-bonly-{suffix}", "e": only_in_b, "n": "B only"},
    )
    for uid, org in ((both, fx["org_a"]), (both, fx["org_b"]), (b_member, fx["org_b"])):
        owner_session.execute(
            text("INSERT INTO core.organization_members (organization_id, user_id) VALUES (:o,:u)"),
            {"o": org, "u": uid},
        )
    owner_session.commit()

    try:
        _scope(app_session, fx["org_a"], fx["admin_a"])
        app_session.execute(
            text("UPDATE core.users SET email = :e WHERE id = :u"),
            {"e": only_in_b, "u": both},
        )
        app_session.rollback()
    except IntegrityError as exc:
        app_session.rollback()
        constraint = getattr(getattr(exc.orig, "diag", None), "constraint_name", None)
        pytest.fail(
            "the rename was REFUSED because the address is held in an "
            "organization the caller cannot see "
            f"(constraint {constraint!r}). That refusal discloses the address "
            "exists somewhere on the platform, which re-opens I83 inside the "
            "guard that replaced it. The guard must be SECURITY INVOKER and "
            "must not reach past RLS."
        )
    finally:
        owner_session.rollback()
        owner_session.execute(
            text("DELETE FROM core.organization_members WHERE user_id = ANY(:u)"),
            {"u": [both, b_member]},
        )
        owner_session.execute(
            text("DELETE FROM core.users WHERE id = ANY(:u)"), {"u": [both, b_member]}
        )
        owner_session.commit()
