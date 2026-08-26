"""How `POST /api/admin/members` reports what the database refused.

🔴 THE ROUTE HAD NO TEST OF ANY KIND, AND THE GAP HID A REAL DEFECT.

The Supervisor's finding: migration 050's standing check raises SQLSTATE
42501, psycopg surfaces that as `ProgrammingError` -- a SIBLING of
`IntegrityError`, not a subclass -- and `invite_member` caught only
`IntegrityError`. No exception handler is registered on the app, so the
database refusing a privileged write left the route as a **500 carrying a
driver message** instead of a 403. Measured before it was believed.

⚠️ THESE ARE UNIT TESTS OVER THE CLASSIFIERS, NOT A ROUTE TEST, AND THE
DIFFERENCE MATTERS. They prove each translation is correct; they do NOT prove
the route reaches them, because nothing in this suite posts to
`/api/admin/members`. That gap is real and is filed as **I107** -- `_bind_conflict`,
the nested retry, and the membership-resolution read added by 051 all still
have zero end-to-end coverage. A test that cannot see the wiring is not a test
of the wiring, and saying so here is cheaper than discovering it later.
"""

from __future__ import annotations

import pytest
from fastapi import status
from sqlalchemy.exc import IntegrityError, ProgrammingError

from app.api.admin import _bind_conflict, _standing_refusal


class _Diag:
    def __init__(self, constraint_name: str | None) -> None:
        self.constraint_name = constraint_name


class _OrigError(Exception):
    def __init__(self, sqlstate: str | None = None, constraint: str | None = None) -> None:
        super().__init__("simulated")
        self.sqlstate = sqlstate
        self.diag = _Diag(constraint)


def _programming(sqlstate: str) -> ProgrammingError:
    return ProgrammingError("SELECT 1", {}, _OrigError(sqlstate=sqlstate))


def _integrity(constraint: str | None) -> IntegrityError:
    return IntegrityError("INSERT", {}, _OrigError(constraint=constraint))


def test_the_standing_check_becomes_a_403_and_not_a_500() -> None:
    """050's refusal is the immediate-revocation window, answered honestly."""
    refusal = _standing_refusal(_programming("42501"))
    assert refusal is not None, (
        "SQLSTATE 42501 was not recognised as the standing check's refusal, so "
        "it leaves the route as a 500 with a driver message -- which is exactly "
        "the defect this test exists for."
    )
    assert refusal.status_code == status.HTTP_403_FORBIDDEN
    # And it must not repeat the database's wording: which of membership or
    # permission is missing is not the caller's business (050).
    assert "member" not in refusal.detail.lower() or "not permitted" in refusal.detail.lower()


@pytest.mark.parametrize("sqlstate", ["23505", "23502", "42P01", None])
def test_an_unrelated_database_fault_is_not_relabelled_a_permission_problem(
    sqlstate: str | None,
) -> None:
    """The other direction, which is the half a one-sided guard leaves out.

    A classifier that answered 403 for everything would satisfy the test above
    and would be worse than what it replaced.
    """
    assert _standing_refusal(_programming(sqlstate)) is None  # type: ignore[arg-type]


def test_a_membership_conflict_is_a_409_and_names_only_visible_facts() -> None:
    assert _bind_conflict(_integrity("organization_members_unique")).status_code == (
        status.HTTP_409_CONFLICT
    )
    assert (
        _bind_conflict(_integrity("organization_members_one_address_per_organization")).status_code
        == status.HTTP_409_CONFLICT
    )


@pytest.mark.parametrize("constraint", [None, "users_pkey", "something_a_later_migration_adds"])
def test_an_unknown_constraint_is_a_500_because_unknown_is_not_a_conflict(
    constraint: str | None,
) -> None:
    """🔴 THIS RETURNED 409 FOR ANYTHING IT COULD NOT NAME.

    A 409 tells the client its request conflicts with existing state and that
    changing the request will help. A NOT NULL, CHECK or FK violation raised
    inside the definer is a server-side fault the client can do nothing about.
    Raised by the Supervisor against this function's own rule -- report the
    RESULT, not a guess -- which had been applied to the message and not to
    the status code.
    """
    assert _bind_conflict(_integrity(constraint)).status_code == (
        status.HTTP_500_INTERNAL_SERVER_ERROR
    )
