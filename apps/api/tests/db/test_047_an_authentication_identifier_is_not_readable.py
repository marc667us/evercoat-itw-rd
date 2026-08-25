"""I81 — the row carries more than its justification needs.

044's read policy admits a user when the reader shares an organization with
them, with no `status` filter, because eleven INNER joins resolve an actor
through `core.users` and filtering would drop the RECORDS from every list
rather than merely blanking a name. The objection was that those joins need
only the NAME while the policy hands over the whole row.

🔴 THE OBJECTION WAS MEASURED, NOT ACCEPTED. Of the three columns at issue:

    display_name   eleven readers. Attribution. Correct.
    email          TWO production paths deliberately return it --
                   admin.list_members and projects.list_members, the latter
                   documenting that it lists FORMER members on purpose.
                   Messaging also matches on its local part.
    keycloak_sub   NO application query selects it. Anywhere.

So only the last one is over-granted, and RLS -- being row-level -- cannot
take it away. Column privileges can, and migration 047 does.

The catalogue tests here name the cause in one line; the behavioural ones are
the property. Both are present because `has_column_privilege` would keep
answering correctly against a database where some later grant had quietly
re-widened the table.
"""

from __future__ import annotations

import uuid
from collections.abc import Iterator

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DatabaseError, ProgrammingError
from sqlalchemy.orm import Session

RUNTIME_ROLES = ("evercoat_app", "evercoat_report", "evercoat_worker")


def test_the_identifier_is_not_readable_by_any_runtime_role(owner_session: Session) -> None:
    """Catalogue. `keycloak_sub` is gone for the roles that never read it.

    ⚠️ A COLUMN-LEVEL REVOKE AGAINST A TABLE-LEVEL GRANT DOES NOTHING.
    PostgreSQL treats `GRANT SELECT ON core.users` as covering every column,
    so `REVOKE SELECT (keycloak_sub)` on top of it is silently ineffective.
    A migration written that way reads exactly like this one and changes
    nothing, which is why this asserts the privilege rather than the SQL.
    """
    for role in RUNTIME_ROLES:
        readable = owner_session.execute(
            text("SELECT has_column_privilege(:r, 'core.users', 'keycloak_sub', 'SELECT')"),
            {"r": role},
        ).scalar_one()
        assert readable is False, (
            f"{role} can SELECT core.users.keycloak_sub. No application query "
            "reads it, it is the subject a token is verified against, and "
            "044's read policy hands the row to every colleague in your "
            "organization. See migration 047 / I81."
        )


def test_the_columns_the_application_does_read_are_untouched(owner_session: Session) -> None:
    """🔴 THE OTHER DIRECTION, WITHOUT WHICH THE TEST ABOVE IS SATISFIED BY
    REVOKING EVERYTHING.

    `admin.list_members` and `projects.list_members` both return `email`, and
    every actor-resolving join selects `display_name`. Narrowing that far
    would break stated behaviour rather than protect anything.
    """
    for column in ("id", "email", "display_name", "status"):
        readable = owner_session.execute(
            text("SELECT has_column_privilege('evercoat_app', 'core.users', :c, 'SELECT')"),
            {"c": column},
        ).scalar_one()
        assert readable is True, (
            f"evercoat_app can no longer SELECT core.users.{column}. 047 was "
            "supposed to remove one authentication identifier, not the "
            "directory."
        )


def test_the_identifier_may_be_written_once_and_never_rewritten(
    owner_session: Session,
) -> None:
    """INSERT keeps it; UPDATE does not.

    `invite_member` creates identities, so the column has to be writable at
    insert. Rewriting it afterwards would repoint an existing user row at a
    different identity provider subject — an identity swap performed by the
    runtime role, on a row 044 hands to every colleague.
    """
    insertable = owner_session.execute(
        text("SELECT has_column_privilege('evercoat_app','core.users','keycloak_sub','INSERT')")
    ).scalar_one()
    updatable = owner_session.execute(
        text("SELECT has_column_privilege('evercoat_app','core.users','keycloak_sub','UPDATE')")
    ).scalar_one()
    assert insertable is True, (
        "evercoat_app cannot INSERT keycloak_sub, so invite_member cannot "
        "create an identity at all."
    )
    assert updatable is False, (
        "evercoat_app can UPDATE keycloak_sub. That rewrites the subject a "
        "token is verified against."
    )


def test_the_application_role_is_actually_refused(app_session: Session) -> None:
    """The behavioural half. `has_column_privilege` is the catalogue's opinion."""
    with pytest.raises(DatabaseError) as caught:
        app_session.execute(text("SELECT keycloak_sub FROM core.users LIMIT 1"))
    assert "permission denied" in str(caught.value).lower(), (
        f"selecting keycloak_sub failed for some other reason: {caught.value}"
    )
    app_session.rollback()

    # And the query the application actually makes still runs.
    app_session.execute(text("SELECT id, email, display_name FROM core.users LIMIT 1")).all()
    app_session.rollback()


def test_sign_in_still_resolves_a_subject(app_session: Session, owner_session: Session) -> None:
    """🔴 THE REVOKE MUST NOT HAVE KILLED SIGN-IN.

    `principal_for_subject`, `memberships_for_subject` and
    `user_id_for_subject` all read `keycloak_sub`. They are SECURITY DEFINER
    owned by `evercoat_owner`, so they keep working — but that is an
    argument, and this is the measurement. If it is wrong, nobody can log in
    and the catalogue tests above still pass.
    """
    subject = owner_session.execute(
        text("SELECT keycloak_sub FROM core.users LIMIT 1")
    ).scalar_one_or_none()
    if subject is None:
        pytest.skip("no users in this database to resolve")

    resolved = app_session.execute(
        text("SELECT core.user_id_for_subject(:s)"), {"s": subject}
    ).scalar_one_or_none()
    assert resolved is not None, (
        "core.user_id_for_subject returned nothing for a subject that exists. "
        "The definer can no longer read keycloak_sub and sign-in is dead."
    )
    app_session.rollback()


@pytest.fixture
def two_orgs_and_a_shared_member(owner_session: Session) -> Iterator[dict[str, object]]:
    """A user who is an active member of BOTH organizations, plus an address
    held only in the second one."""
    suffix = uuid.uuid4().hex[:8]
    orgs = [
        owner_session.execute(
            text("INSERT INTO core.organizations (code, name) VALUES (:c,:n) RETURNING id"),
            {"c": f"I81-{label}-{suffix}", "n": f"I81 probe {label}"},
        ).scalar_one()
        for label in ("A", "B")
    ]
    only_in_b = f"onlyb-{suffix}@example.test"
    both = uuid.uuid4()
    b_member = uuid.uuid4()
    for uid, sub, email in (
        (both, "both", f"both-{suffix}@example.test"),
        (b_member, "bonly", only_in_b),
    ):
        owner_session.execute(
            text(
                "INSERT INTO core.users (id, keycloak_sub, email, display_name)"
                " VALUES (:i,:s,:e,:n)"
            ),
            {"i": uid, "s": f"i81-{sub}-{suffix}", "e": email, "n": sub},
        )
    for uid, org in ((both, orgs[0]), (both, orgs[1]), (b_member, orgs[1])):
        owner_session.execute(
            text("INSERT INTO core.organization_members (organization_id, user_id) VALUES (:o,:u)"),
            {"o": org, "u": uid},
        )
    owner_session.commit()
    try:
        yield {"org_a": orgs[0], "org_b": orgs[1], "both": both, "only_in_b": only_in_b}
    finally:
        owner_session.rollback()
        owner_session.execute(
            text("DELETE FROM core.organization_members WHERE organization_id = ANY(:o)"),
            {"o": orgs},
        )
        owner_session.execute(
            text("DELETE FROM core.users WHERE keycloak_sub LIKE :p"), {"p": f"i81-%-{suffix}"}
        )
        owner_session.execute(
            text("DELETE FROM core.organizations WHERE id = ANY(:o)"), {"o": orgs}
        )
        owner_session.commit()


def test_the_rename_guard_is_scoped_by_its_own_predicate_not_by_rls(
    owner_session: Session, two_orgs_and_a_shared_member: dict
) -> None:
    """🔴 A GUARD SCOPED BY THE CALLER'S RLS WIDENS WHEN THE CALLER CHANGES.

    046's rename guard restricted its `mine` side with nothing but the RLS
    policy on `core.organization_members`. A trigger runs as whatever the
    current user is, and `evercoat_owner` OWNS that table and bypasses RLS
    while FORCE is off — so inside a SECURITY DEFINER, or in any owner-side
    script, the guard saw EVERY tenant and refused on their rows. Its
    refusal then discloses that the address exists somewhere, which is
    I83's oracle rebuilt inside the guard that replaced it.

    Measured before 047, same data, both paths:

        INVOKER path  : ACCEPTED  <- tenant-scoped, correct
        DEFINER path  : REFUSED   <- refused on organization B's row

    This test runs as `owner_session`, which bypasses RLS exactly as a
    definer does, with the GUC naming organization A. The rename must be
    ACCEPTED: organization B's collision is none of A's business, and
    missing it beats answering for it.

    Falsified by reverting the function to 046's text — dropping
    `mine.organization_id = core.current_org_id()` makes this fail.
    """
    fx = two_orgs_and_a_shared_member
    owner_session.execute(
        text("SELECT set_config('app.current_org', :v, true)"), {"v": str(fx["org_a"])}
    )
    try:
        owner_session.execute(
            text("UPDATE core.users SET email = :e WHERE id = :u"),
            {"e": fx["only_in_b"], "u": fx["both"]},
        )
    except ProgrammingError:
        raise
    except DatabaseError as exc:
        owner_session.rollback()
        constraint = getattr(getattr(exc.orig, "diag", None), "constraint_name", None)
        pytest.fail(
            "the rename was REFUSED on a collision that exists only in an "
            "organization this caller is not scoped to "
            f"(constraint {constraint!r}). The guard is scoped by the "
            "caller's RLS rather than by its own predicate, so it widens the "
            "moment it runs as a role that bypasses RLS — a SECURITY DEFINER, "
            "or an owner-side script, or the FORCE RLS cutover of I56/I58."
        )
    owner_session.rollback()
