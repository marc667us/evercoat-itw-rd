"""I106 and I108 — an identity has no tenant attributes; a membership does.

🔴 THE TWO DEFECTS ARE ONE DEFECT, AND THE SECOND ONE IS WIDER.

051 closed the channel by which a rolled-back bind handed back an identity
IDENTIFIER, and stated in its own header what it did not close: the same bind
made the foreign identity's stored `email` and `display_name` readable through
the membership it created. That is I106, and it measured exactly as described.

Measuring it turned up I108. `evercoat_app` held table-level INSERT on
`core.organization_members`; `org_member_isolation` constrains only
`organization_id`; `user_id` is a plain FK to a GLOBAL table. So an ORDINARY
member -- no `admin.users`, no EXECUTE on the bind, no `keycloak_sub` -- could
manufacture a membership naming any identity in the system, read it, and roll
back:

    foreign identity visible BEFORE            : 0 rows
    INSERT INTO core.organization_members (organization_id, user_id)
      VALUES (<my org>, <a foreign user id>);
    read AFTER                                  : ('secret...@competitor.example',
                                                   'Confidential B Person')
    ROLLBACK

So the shape is not "the bind leaks". It is **any membership row turns a
global identity into a readable one**, and the bind is one of two ways to make
one.

⚠️ WHICH MEANS THE MEMBERSHIP COLUMNS ARE NOT THE CLOSURE. They are what keeps
the application working once the closure lands. The closure is that
`core.users.email` and `core.users.display_name` stop being readable by the
runtime roles at all -- `test_the_global_attributes_are_not_readable` is the
test that goes red if 052 is reverted, and every behavioural test here rides
on it rather than restating it.

🔴 AND THAT CLOSES THE TABLE, NOT EVERY PATH TO THE VALUE. Codex, reviewing
052, produced one that survives: `core.memberships_for_subject(TEXT)` and
`core.principal_for_subject(TEXT, UUID)` are definers granted to
`evercoat_app` that take a subject as an ARGUMENT and cannot bind it to their
caller. Measured, and it discloses the person's organizations by name as well
as their address. It is filed as I109 and pinned open by
`test_the_sign_in_definers_still_answer_for_any_subject`, because a file whose
title says an identity has no readable attributes must say where that is
false.

Everything runs as `evercoat_app`, the non-superuser runtime role. A privilege
test performed as a superuser proves nothing; the `app_session` fixture
asserts `rolsuper = false` before yielding.
"""

from __future__ import annotations

import uuid
from collections.abc import Iterator
from dataclasses import dataclass

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError, ProgrammingError
from sqlalchemy.orm import Session

pytestmark = [pytest.mark.db]

FOREIGN_NAME = "Confidential B Person"
RUNTIME_ROLES = ("evercoat_app", "evercoat_report", "evercoat_worker")


@dataclass(frozen=True)
class _Tenants:
    """Organization A with an administrator; organization B with a secret."""

    a: uuid.UUID
    b: uuid.UUID
    admin: uuid.UUID
    foreign_sub: str
    foreign_user: uuid.UUID
    foreign_email: str
    suffix: str


@pytest.fixture
def tenants(owner_session: Session, app_session: Session) -> Iterator[_Tenants]:
    """Two organizations, an administrator of the first, a secret in the second.

    COMMITs, because `evercoat_owner` and `evercoat_app` are different
    connections and the app session must see the rows. Deletes what it
    created: I101 is 595 orphaned `core.users` rows left by a fixture that
    did not.

    🔴 IT ROLLS THE APP SESSION BACK BEFORE DELETING. Every test here writes
    through the app session or tries to; those rows are uncommitted and
    LOCKED, and an owner-side DELETE of the same rows on another connection
    waits forever. `test_049_atomic_bind.py` records the same fixture hanging
    a run twice before the cause was measured rather than guessed at.
    """
    sfx = uuid.uuid4().hex[:8]
    orgs = [
        owner_session.execute(
            text("INSERT INTO core.organizations (code, name) VALUES (:c, :n) RETURNING id"),
            {"c": f"I106{label}-{sfx}", "n": f"I106 probe {label}"},
        ).scalar_one()
        for label in ("A", "B")
    ]

    def identity(sub: str, email: str, name: str) -> uuid.UUID:
        return owner_session.execute(
            text(
                "INSERT INTO core.users (keycloak_sub, email, display_name)"
                " VALUES (:s, :e, :n) RETURNING id"
            ),
            {"s": sub, "e": email, "n": name},
        ).scalar_one()

    def member(org: uuid.UUID, user: uuid.UUID, email: str, name: str) -> uuid.UUID:
        return owner_session.execute(
            text(
                "INSERT INTO core.organization_members"
                " (organization_id, user_id, email, display_name)"
                " VALUES (:o, :u, :e, :n) RETURNING id"
            ),
            {"o": org, "u": user, "e": email, "n": name},
        ).scalar_one()

    admin_email = f"i106-admin-{sfx}@a.example"
    admin_id = identity(f"i106-admin-{sfx}", admin_email, "I106 admin")
    admin_member = member(orgs[0], admin_id, admin_email, "I106 admin")
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
        {"m": admin_member, "r": role_id},
    )

    # The secret. Organization B's business, and nobody else's -- not even
    # whether it exists.
    foreign_sub = f"i106-foreign-{sfx}"
    foreign_email = f"secret.person-{sfx}@competitor.example"
    foreign_user = identity(foreign_sub, foreign_email, FOREIGN_NAME)
    member(orgs[1], foreign_user, foreign_email, FOREIGN_NAME)
    owner_session.commit()

    try:
        yield _Tenants(
            a=orgs[0],
            b=orgs[1],
            admin=admin_id,
            foreign_sub=foreign_sub,
            foreign_user=foreign_user,
            foreign_email=foreign_email,
            suffix=sfx,
        )
    finally:
        # 🔴 THE APP SESSION FIRST. See the docstring.
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
            text("DELETE FROM core.users WHERE keycloak_sub LIKE :p"), {"p": f"i106-%-{sfx}"}
        )
        owner_session.execute(
            text("DELETE FROM core.organizations WHERE id = ANY(:o)"), {"o": orgs}
        )
        owner_session.commit()


def _scope(session: Session, *, org: uuid.UUID, user: uuid.UUID) -> None:
    session.execute(text("SELECT set_config('app.current_org', :v, true)"), {"v": str(org)})
    session.execute(text("SELECT set_config('app.current_user_id', :v, true)"), {"v": str(user)})


# ---------------------------------------------------------------------------
# The closure
# ---------------------------------------------------------------------------


def test_the_global_attributes_are_not_readable(owner_session: Session) -> None:
    """🔴 THE ONE THAT GOES RED IF 052 IS REVERTED.

    Every behavioural test below rides on this rather than restating it: a
    membership makes any global identity readable under 044's policy, and
    a membership can be created and rolled away, so the only closure is that
    the global attributes are not readable in the first place.

    ⚠️ A COLUMN-LEVEL REVOKE AGAINST A TABLE-LEVEL GRANT DOES NOTHING --
    PostgreSQL treats `GRANT SELECT ON core.users` as covering every column.
    047 replaced the table grant with an explicit column list, so the revoke
    in 052 bites; asserting the PRIVILEGE rather than the SQL is what proves
    it did.
    """
    for role in RUNTIME_ROLES:
        for column in ("email", "display_name"):
            readable = owner_session.execute(
                text("SELECT has_column_privilege(:r, 'core.users', :c, 'SELECT')"),
                {"r": role, "c": column},
            ).scalar_one()
            assert readable is False, (
                f"{role} can SELECT core.users.{column}. A membership row -- "
                "which any administrator can create and roll back, and which "
                "before 052 any member could create outright (I108) -- turns "
                "that into another tenant's personal data for free."
            )

    # The control. Without it this test is satisfied by revoking the whole
    # table, which would break every actor join in the application.
    assert (
        owner_session.execute(
            text("SELECT has_column_privilege('evercoat_app', 'core.users', 'id', 'SELECT')")
        ).scalar_one()
        is True
    ), "evercoat_app cannot read core.users.id -- the revoke was too wide"


def test_a_rolled_back_bind_does_not_disclose_a_foreign_identity(
    app_session: Session, tenants: _Tenants
) -> None:
    """I106, as the exact statement that was measured doing it.

    Run before 052 as a legitimate administrator of organization A, against a
    subject whose identity exists only in organization B::

        submitted  : 'whatever@attacker.example'       / 'Whatever I Typed'
        read back  : 'secret.person@competitor.example'/ 'Confidential B Person'
        memberships left behind: 0

    The bind resolves an existing subject to the global `core.users` row and
    correctly does not touch its attributes -- writing them would be the
    cross-tenant WRITE 049's first design was rejected for. So the membership
    pointed at another tenant's data and 044's policy admitted it for as long
    as the membership existed, which the caller controls entirely.
    """
    _scope(app_session, org=tenants.a, user=tenants.admin)
    submitted_email = f"whatever-{tenants.suffix}@attacker.example"
    member_id = app_session.execute(
        text("SELECT member_id FROM core.bind_subject_to_organization(:s, :e, :n)"),
        {"s": tenants.foreign_sub, "e": submitted_email, "n": "Whatever I Typed"},
    ).scalar_one()

    with pytest.raises(ProgrammingError) as caught:
        app_session.execute(
            text(
                """
                SELECT u.email::text, u.display_name
                  FROM core.organization_members om
                  JOIN core.users u ON u.id = om.user_id
                 WHERE om.id = :m
                """
            ),
            {"m": member_id},
        )
    # Named as a PRIVILEGE refusal ON THIS TABLE, not accepted as "an error":
    # a lost schema USAGE or a missing SELECT on the membership table would
    # otherwise satisfy this while the channel stayed open.
    refusal = str(caught.value).lower()
    assert "permission denied" in refusal, f"the read failed for another reason: {caught.value}"
    assert "users" in refusal, f"something other than core.users refused the read: {caught.value}"
    app_session.rollback()


def test_the_membership_records_what_the_caller_submitted(
    app_session: Session, tenants: _Tenants
) -> None:
    """🔴 THE CONTROL, AND WITHOUT IT THE TEST ABOVE IS SATISFIED BY A DEAD BIND.

    A function that refused everything, or a schema where nothing is readable,
    would pass the disclosure test and be useless. This asserts the positive
    half: organization A binds a subject that already exists in organization B
    and gets back ITS OWN submission, which answers nothing about B.

    It is also the correctness claim 052 makes in its own right. A person who
    belongs to two tenants used to be described everywhere by whichever tenant
    onboarded them first.
    """
    _scope(app_session, org=tenants.a, user=tenants.admin)
    submitted_email = f"ours-{tenants.suffix}@a.example"
    submitted_name = "The Name We Use"
    member_id = app_session.execute(
        text("SELECT member_id FROM core.bind_subject_to_organization(:s, :e, :n)"),
        {"s": tenants.foreign_sub, "e": submitted_email, "n": submitted_name},
    ).scalar_one()

    stored = app_session.execute(
        text("SELECT email::text, display_name FROM core.organization_members WHERE id = :m"),
        {"m": member_id},
    ).one()
    assert tuple(stored) == (submitted_email, submitted_name), (
        f"the membership records {tuple(stored)!r}, not what this organization "
        "submitted. If those are the other tenant's values the bind is reading "
        "the global identity again and I106 is open."
    )
    assert tuple(stored) != (tenants.foreign_email, FOREIGN_NAME)
    app_session.rollback()


def test_the_bind_does_not_overwrite_the_global_identity(
    app_session: Session, owner_session: Session, tenants: _Tenants
) -> None:
    """The other direction, which is the mistake 049 actually made.

    Recording the submitted attributes on the membership must not also write
    them onto `core.users`. That would let organization A rename a person
    inside organization B -- a cross-tenant WRITE introduced by the change
    that removes a cross-tenant READ, which is the reflex ADR-029 caught in
    its own first draft and 049 then shipped anyway.

    Asked of `owner_session`, which RLS does not apply to, so a write that
    happened would be COUNTED rather than hidden from the session that made
    it. That is the fifth-instance lesson from 049: a postcondition read
    through the attacking session can pass because it cannot see.
    """
    _scope(app_session, org=tenants.a, user=tenants.admin)
    app_session.execute(
        text("SELECT member_id FROM core.bind_subject_to_organization(:s, :e, :n)"),
        {"s": tenants.foreign_sub, "e": f"ours-{tenants.suffix}@a.example", "n": "Ours"},
    )
    app_session.commit()

    try:
        stored = owner_session.execute(
            text("SELECT email::text, display_name FROM core.users WHERE id = :u"),
            {"u": tenants.foreign_user},
        ).one()
        assert tuple(stored) == (tenants.foreign_email, FOREIGN_NAME), (
            f"organization B's identity now reads {tuple(stored)!r}. Organization "
            "A's bind rewrote the global row -- a cross-tenant write inside the "
            "migration that removes a cross-tenant read."
        )
        # And organization B still sees its own member as it always did.
        b_view = owner_session.execute(
            text(
                """
                SELECT email::text, display_name FROM core.organization_members
                 WHERE organization_id = :o AND user_id = :u
                """
            ),
            {"o": tenants.b, "u": tenants.foreign_user},
        ).one()
        assert tuple(b_view) == (tenants.foreign_email, FOREIGN_NAME)
    finally:
        app_session.rollback()
        owner_session.rollback()


def test_the_runtime_role_cannot_manufacture_a_membership(
    app_session: Session, tenants: _Tenants
) -> None:
    """I108 — the path that needs no bind, no permission and no subject.

    Measured before 052 as an ordinary member of organization A: a plain
    INSERT naming a foreign `user_id` was ACCEPTED, the identity became
    readable, and the rollback left nothing behind. It needed neither
    `admin.users` nor EXECUTE on the bind.

    Nothing in `app/` inserts this table -- the only writer is the SECURITY
    DEFINER bind, which runs as the owner -- so the grant was a capability
    nothing called and a disclosure primitive at the same time.

    ⚠️ THIS TEST IS NOT THE CLOSURE EITHER. Revoking INSERT removes one way to
    make a membership; `test_the_global_attributes_are_not_readable` is what
    makes any membership harmless. Both are asserted because 052 does both,
    and because a later migration re-granting INSERT should redden something.
    """
    _scope(app_session, org=tenants.a, user=tenants.admin)
    with pytest.raises(ProgrammingError) as caught:
        app_session.execute(
            text(
                """
                INSERT INTO core.organization_members
                    (organization_id, user_id, email, display_name)
                VALUES (:o, :u, 'anything@example.test', 'anything')
                """
            ),
            {"o": tenants.a, "u": tenants.foreign_user},
        )
    refusal = str(caught.value).lower()
    assert "permission denied" in refusal, f"the INSERT failed for another reason: {caught.value}"
    assert "organization_members" in refusal, (
        f"something other than the membership table refused it: {caught.value}"
    )
    app_session.rollback()

    # The control: what the role legitimately does with this table still
    # works. Without it the assertion above is satisfied by revoking
    # everything, which would break `list_members` and `set_member_status`.
    app_session.execute(text("SELECT count(*) FROM core.organization_members")).scalar_one()
    app_session.execute(
        text(
            """
            UPDATE core.organization_members SET display_name = display_name
             WHERE organization_id = :o
            """
        ),
        {"o": tenants.a},
    )
    app_session.rollback()


def test_the_bind_remains_the_one_path_that_works(app_session: Session, tenants: _Tenants) -> None:
    """Revoking INSERT must not have broken the only writer there is.

    `invite_member` calls a SECURITY DEFINER, which runs as `evercoat_owner`
    and is unaffected by the runtime role's privileges. Stated as a test
    rather than as an argument, because "the definer is not affected" is
    exactly the kind of claim this repository has found to be false before --
    a trigger inside a definer, a column revoke against a table grant.
    """
    _scope(app_session, org=tenants.a, user=tenants.admin)
    sub = f"i106-new-{tenants.suffix}"
    member_id = app_session.execute(
        text("SELECT member_id FROM core.bind_subject_to_organization(:s, :e, :n)"),
        {"s": sub, "e": f"{sub}@a.example", "n": "Newcomer"},
    ).scalar_one()
    assert member_id is not None
    app_session.rollback()


# ---------------------------------------------------------------------------
# The schema the closure rests on
# ---------------------------------------------------------------------------


def test_a_membership_cannot_exist_without_its_own_attributes(
    owner_session: Session,
) -> None:
    """NOT NULL, asserted as the constraint rather than as a convention.

    Every read that used to go to `core.users` now goes here, so a membership
    with no address and no name is a member the Administration list cannot
    describe and `@mentions` cannot resolve. The runtime role reaches this
    table only through the bind, which always supplies both -- but "the only
    writer supplies them" is an argument, and NOT NULL is the mechanism.

    🔴 IT ASSERTS THE COLUMNS EXIST BEFORE IT ASSERTS THEY ARE NOT NULL.

    The first version selected the nullable ones among the two and required an
    empty result. Run against the database rolled back to `j1000`, where
    neither column exists, that query returns nothing and the test PASSED --
    reporting the constraint intact on a schema that has no such column. Found
    by falsifying against the DATABASE rather than by reading the test, and it
    is another instance of a guard that passes because it cannot see. Both
    directions, always.
    """
    found = dict(
        owner_session.execute(
            text(
                """
                SELECT a.attname, a.attnotnull
                  FROM pg_attribute a
                  JOIN pg_class c     ON c.oid = a.attrelid
                  JOIN pg_namespace n ON n.oid = c.relnamespace
                 WHERE n.nspname = 'core'
                   AND c.relname = 'organization_members'
                   AND a.attname IN ('email', 'display_name')
                   AND a.attnum > 0
                   AND NOT a.attisdropped
                """
            )
        ).all()
    )
    assert set(found) == {"email", "display_name"}, (
        f"core.organization_members carries {sorted(found)} of the two "
        "attributes 052 added. Every actor join in the application resolves "
        "through them, so a missing one is not a relaxed constraint -- it is a "
        "schema the code cannot run against."
    )
    nullable = sorted(name for name, notnull in found.items() if not notnull)
    assert nullable == [], (
        f"these membership attributes are nullable: {nullable}. A membership "
        "with no address and no name is a member the Administration list "
        "cannot describe and @mentions cannot resolve."
    )


def test_the_address_rule_still_refuses_inside_one_organization(
    owner_session: Session,
) -> None:
    """046's rule survived being re-homed, and names itself the same way.

    `app/api/admin.py` turns this exact constraint name into a 409 that says
    the address is taken; anything it cannot name becomes a 500. 052 replaced
    046's trigger with an index and deliberately kept the name, so this is the
    assertion that notices a rename -- which would silently downgrade a
    correct 409 into a server error.

    The behavioural coverage lives in `test_046_email_is_an_attribute.py`;
    this is the piece 052 could have broken.
    """
    sfx = uuid.uuid4().hex[:8]
    addr = f"i106-dup-{sfx}@example.test"
    org = owner_session.execute(
        text("INSERT INTO core.organizations (code, name) VALUES (:c, :n) RETURNING id"),
        {"c": f"I106D-{sfx}", "n": "I106 duplicate probe"},
    ).scalar_one()
    users = [
        owner_session.execute(
            text(
                "INSERT INTO core.users (keycloak_sub, email, display_name)"
                " VALUES (:s, :e, :n) RETURNING id"
            ),
            {"s": f"i106-dup{n}-{sfx}", "e": addr, "n": f"Dup {n}"},
        ).scalar_one()
        for n in (1, 2)
    ]
    insert = text(
        "INSERT INTO core.organization_members"
        " (organization_id, user_id, email, display_name) VALUES (:o, :u, :e, :n)"
    )
    owner_session.execute(insert, {"o": org, "u": users[0], "e": addr, "n": "Dup 1"})
    with pytest.raises(IntegrityError) as caught:
        owner_session.execute(insert, {"o": org, "u": users[1], "e": addr, "n": "Dup 2"})
    diag = getattr(caught.value.orig, "diag", None)
    assert getattr(diag, "constraint_name", None) == (
        "organization_members_one_address_per_organization"
    ), (
        "the address rule did not name itself the way app/api/admin.py expects, "
        f"so a taken address answers 500 instead of 409. Got "
        f"{getattr(diag, 'constraint_name', None)!r}"
    )
    owner_session.rollback()


def test_sign_in_reports_each_organizations_own_view(
    owner_session: Session,
    tenants: _Tenants,
) -> None:
    """🔴 THE DEFINERS MOVED WITH THE ATTRIBUTES, AND THAT IS A FIX.

    `core.memberships_for_subject` returns ONE ROW PER ORGANIZATION and used
    to read `core.users`, so every tenant in the list described the person by
    a single shared address -- whichever one was registered first. Reading the
    membership makes each row report its own organization's view.

    Asserted on a person who really is in two organizations under two
    addresses, because a single-tenant subject cannot tell the two
    implementations apart.
    """
    owner_session.execute(
        text(
            "INSERT INTO core.organization_members"
            " (organization_id, user_id, email, display_name) VALUES (:o, :u, :e, :n)"
        ),
        {
            "o": tenants.a,
            "u": tenants.foreign_user,
            "e": f"known-in-a-{tenants.suffix}@a.example",
            "n": "Known In A",
        },
    )
    owner_session.commit()

    try:
        rows = {
            r.organization_id: (r.email, r.display_name)
            for r in owner_session.execute(
                text(
                    "SELECT organization_id, email, display_name"
                    " FROM core.memberships_for_subject(:s)"
                ),
                {"s": tenants.foreign_sub},
            ).all()
        }
        assert rows[tenants.a] == (f"known-in-a-{tenants.suffix}@a.example", "Known In A"), (
            f"organization A sees {rows.get(tenants.a)!r} for this person. If "
            "that is organization B's address the definer is still reading the "
            "global identity."
        )
        assert rows[tenants.b] == (tenants.foreign_email, FOREIGN_NAME), (
            f"organization B sees {rows.get(tenants.b)!r}, not its own record."
        )

        # And the single-organization lookup agrees with the list. Two
        # functions answering the same question differently is how the browser
        # and the API drifted in I79.
        one = owner_session.execute(
            text("SELECT email, display_name FROM core.principal_for_subject(:s, :o)"),
            {"s": tenants.foreign_sub, "o": tenants.a},
        ).one()
        assert tuple(one) == rows[tenants.a], (
            f"principal_for_subject says {tuple(one)!r} and "
            f"memberships_for_subject says {rows[tenants.a]!r} for the same "
            "(subject, organization)."
        )
    finally:
        owner_session.rollback()


def test_no_view_hands_the_attributes_back(owner_session: Session) -> None:
    """A column revoke on a base table is not a revoke on every projection.

    The same future-object risk 047 recorded for `keycloak_sub`, which now
    applies to two more columns: `ALTER DEFAULT PRIVILEGES` in 001 grants the
    runtime roles SELECT on tables and views `evercoat_owner` creates in
    `core`, and a view runs against its OWNER's privileges. So a view
    projecting `core.users.email` would be readable the moment it exists and
    would hand back exactly what 052 took away -- with no migration appearing
    to change any grant.

    🔴 IT ASKS `pg_depend` WHAT THE VIEW READS, NOT WHAT ITS COLUMNS ARE CALLED.

    The first version listed views with a column named `email` or
    `display_name` and then guessed the source table from whether the VIEW's
    name contained "user". Raised by Codex with a counterexample that defeats
    it in one line::

        CREATE VIEW core.identity_directory AS
            SELECT email, display_name FROM core.users;

    Neither "user" nor "member" appears in `identity_directory`, so the guess
    excluded it and the test passed over a view handing back the whole
    channel. It could also be beaten by `SELECT email AS contact`. **A test
    that infers a data source from a NAME is a test that can be renamed
    around.** `pg_depend` records the actual column-level dependency a view's
    rewrite rule has on its base tables, so this asks the catalogue the
    question instead of pattern-matching an identifier.

    Nothing exposes them today. This is the test that notices when something
    does: default privileges cannot be made column-aware.
    """
    leaks = owner_session.execute(
        text(
            """
            SELECT DISTINCT vn.nspname AS view_schema,
                            v.relname   AS view_name,
                            a.attname   AS source_column
              FROM pg_depend d
              JOIN pg_rewrite rw   ON rw.oid = d.objid
              JOIN pg_class v      ON v.oid = rw.ev_class
              JOIN pg_namespace vn ON vn.oid = v.relnamespace
              JOIN pg_class src    ON src.oid = d.refobjid
              JOIN pg_namespace sn ON sn.oid = src.relnamespace
              JOIN pg_attribute a  ON a.attrelid = src.oid
                                  AND a.attnum   = d.refobjsubid
             WHERE d.classid    = 'pg_rewrite'::regclass
               AND d.refclassid = 'pg_class'::regclass
               AND sn.nspname = 'core'
               AND src.relname = 'users'
               AND a.attname IN ('email', 'display_name')
               AND v.relkind IN ('v', 'm')
               AND has_table_privilege('evercoat_app', v.oid, 'SELECT')
            """
        )
    ).all()
    assert leaks == [], (
        "these views read core.users.email or core.users.display_name and "
        f"evercoat_app may SELECT them: {leaks}. A view runs with its owner's "
        "privileges, so this returns exactly what migration 052 revoked on the "
        "base table -- without any migration appearing to change a grant."
    )


def test_the_sign_in_definers_still_answer_for_any_subject(
    app_session: Session, tenants: _Tenants
) -> None:
    """🔴 A CHANNEL THAT IS STILL OPEN, PINNED OPEN ON PURPOSE. FILED AS I109.

    Raised by Codex reviewing 052 and MEASURED before it was accepted, as an
    ordinary member of organization A holding nothing::

        direct read of B's memberships          : 0 rows
        core.memberships_for_subject(<B's sub>) : org='...B' code='...'
                                                  email='secret.person@competitor.example'
                                                  name='Confidential B Person'

    Both sign-in lookups are SECURITY DEFINER, take a subject as an ARGUMENT,
    and are granted EXECUTE to `evercoat_app`. Neither can bind that argument
    to the caller, because both exist precisely to answer BEFORE a session has
    an organization -- there is nothing yet to compare against. So the runtime
    role can ask about any subject it can name.

    ⚠️ AND IT DISCLOSES MORE THAN THE ADDRESS. `memberships_for_subject`
    returns the NAME and CODE of every organization that subject belongs to,
    which is a larger fact than the email 052 is about.

    **This is not something 052 introduced** -- the functions date from 024,
    033 and 045, and before 052 they read `core.users` directly. What 052 does
    is make the claim above it false if it goes unstated: this file asserts
    the global attributes are unreadable, and that is true of the TABLE and not
    of every path. A test that pins a known-open channel open is the only
    honest way to hold both.

    The bound is real and it comes from 047: `keycloak_sub` is not readable by
    any runtime role, so an `evercoat_app` session cannot enumerate subjects
    from the database at all and must already know an opaque Keycloak uuid.
    **A bound is not a closure.** The fix is a separate database role holding
    EXECUTE on these two functions and used only by the authentication path,
    which is a change to `app/core/db.py` with its own measurement -- I109.

    THIS TEST MUST GO RED WHEN I109 IS CLOSED. That is what it is for.
    """
    _scope(app_session, org=tenants.a, user=tenants.admin)
    rows = app_session.execute(
        text(
            "SELECT organization_id, organization_name, email, display_name"
            " FROM core.memberships_for_subject(:s)"
        ),
        {"s": tenants.foreign_sub},
    ).all()
    assert [r.organization_id for r in rows] == [tenants.b], (
        f"memberships_for_subject returned {[r.organization_id for r in rows]} "
        "for a subject belonging only to organization B. If it returned "
        "NOTHING, I109 has been closed and this test should be deleted along "
        "with the note in ADR-031; if it returned MORE, something else changed."
    )
    assert rows[0].email == tenants.foreign_email, (
        "the definer no longer discloses the foreign address. If that is "
        "deliberate, I109 is closed -- delete this test."
    )
    app_session.rollback()


def test_the_bind_is_still_the_only_thing_that_creates_identities(
    app_session: Session, tenants: _Tenants
) -> None:
    """⚠️ A CAPABILITY NOTHING CALLS IS STILL A CAPABILITY, AND THIS ONE STAYS.

    `evercoat_app` keeps INSERT on `core.users`, and no query in `app/` uses
    it -- the bind is a definer and inserts as the owner. Recorded here as a
    deliberately OPEN finding rather than left silent, because 052 revoked the
    membership-table grant for exactly this reasoning and stopping halfway
    without saying so is how a gap becomes invisible.

    It is not a disclosure channel: creating an identity tells the caller
    nothing about anyone else, and `users_keycloak_sub_key` refusing a
    duplicate subject is the oracle I82 closed at the resolver instead. Ask of
    it what I108 asked: which production path writes it? None. It should go,
    and it needs its own measurement of what breaks.
    """
    still_granted = app_session.execute(
        text("SELECT has_table_privilege('evercoat_app', 'core.users', 'INSERT')")
    ).scalar_one()
    assert still_granted is True, (
        "evercoat_app no longer holds INSERT on core.users. That may well be "
        "correct -- see this test's docstring -- but it was not measured, and "
        "the bind creating identities as the owner is the only reason it can "
        "be removed safely. Measure it, then delete this test."
    )
    _ = tenants
