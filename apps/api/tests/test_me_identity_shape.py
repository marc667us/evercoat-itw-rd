"""🔴 THE ROUTE MUST NOT PUT BACK WHAT MIGRATION 052 TOOK OFF THE IDENTITY.

052 is titled *an identity has no tenant attributes*. It moved ``email`` and
``display_name`` from ``core.users`` onto ``core.organization_members``, and
``core.memberships_for_subject`` returns one row per organization so that each
row can report its own tenant's view of the person. ``test_052`` asserts all of
that against a real database.

``GET /api/me`` then read ``rows[0]`` and reported that pair as *the* identity
-- and the function's own ``ORDER BY o.name`` means row zero is whichever
organization sorts first alphabetically. A member of two organizations working
in the second one saw the first one's name in the top bar, permanently, and
switching organization could not change it because there was nothing per
organization to switch to. Codex found it from the browser end, asking why the
profile does not follow the organization selector.

The database tier was right and the tier above it flattened the answer. These
tests hold the ROUTE to what the migration established, without a database:
what is asserted here is the mapping from rows to response, which is exactly
where the flattening happened.
"""

from __future__ import annotations

import uuid
from contextlib import contextmanager
from typing import Any

import pytest

from app.api import me as me_module
from app.api.me import Me, OrganizationMembership, read_me


class _Result:
    def __init__(self, rows: list[dict[str, Any]]) -> None:
        self._rows = rows

    def mappings(self) -> _Result:
        return self

    def all(self) -> list[dict[str, Any]]:
        return self._rows


class _Session:
    def __init__(self, rows: list[dict[str, Any]]) -> None:
        self._rows = rows

    def execute(self, _statement: Any, _params: Any) -> _Result:
        return _Result(self._rows)


def _rows_for_two_organizations() -> list[dict[str, Any]]:
    """One person, two organizations, two different names — the only shape that
    can tell a per-membership implementation from a flattened one."""
    user_id = uuid.uuid4()
    return [
        {
            "user_id": user_id,
            # Ordered by organization name, as the function orders them: the
            # ALPHABETICALLY FIRST row is the one the old code returned.
            "organization_id": uuid.uuid4(),
            "organization_name": "Acme Coatings",
            "organization_code": "ACME",
            "email": "known.in.acme@acme.example",
            "display_name": "Known In Acme",
            "roles": ["product_development_chemist"],
            "permissions": ["formula.view"],
        },
        {
            "user_id": user_id,
            "organization_id": uuid.uuid4(),
            "organization_name": "Zenith Adhesives",
            "organization_code": "ZEN",
            "email": "different.address@zenith.example",
            "display_name": "Different Name Entirely",
            "roles": ["laboratory_technician"],
            "permissions": ["test.execute"],
        },
    ]


@pytest.fixture
def two_organizations(monkeypatch: pytest.MonkeyPatch) -> list[dict[str, Any]]:
    rows = _rows_for_two_organizations()

    @contextmanager
    def _scope() -> Any:
        yield _Session(rows)

    monkeypatch.setattr(me_module, "auth_session_scope", _scope)
    return rows


def test_the_identity_carries_no_tenant_attributes() -> None:
    """The shape rule from 052, stated where it was broken.

    Asserted on the MODEL rather than on one response, because the defect was
    not a wrong value -- every value was real. It was a field existing at a
    level that cannot answer for it.
    """
    fields = set(Me.model_fields)

    tenant_attributes = fields & {"email", "display_name"}
    assert not tenant_attributes, (
        f"GET /api/me declares a top-level {sorted(tenant_attributes)}. There is "
        "no organization at that level to take it from, so it can only be one "
        "membership's value presented as the identity's -- which is what 052 "
        "removed from the database and what this route re-created above it."
    )
    assert fields == {"user_id", "organizations"}, (
        f"the identity grew a new tenant-independent attribute: {sorted(fields)}"
    )

    membership = set(OrganizationMembership.model_fields)
    assert {"email", "display_name"} <= membership, (
        "the membership does not carry the attributes, so nothing does and the "
        f"browser has no name to show. Fields: {sorted(membership)}"
    )


async def test_each_membership_reports_its_own_organizations_view(
    two_organizations: list[dict[str, Any]],
) -> None:
    """🔴 TWO ORGANIZATIONS, TWO NAMES, AND NEITHER MAY BE THE OTHER'S.

    This is the assertion the old shape could not pass. It returned one pair
    for a caller with two, so the second organization was described by the
    first one's record.
    """
    response = await read_me(subject="a-verified-keycloak-uuid")

    by_code = {org.code: org for org in response.organizations}
    assert set(by_code) == {"ACME", "ZEN"}

    assert (by_code["ACME"].email, by_code["ACME"].display_name) == (
        "known.in.acme@acme.example",
        "Known In Acme",
    )
    assert (by_code["ZEN"].email, by_code["ZEN"].display_name) == (
        "different.address@zenith.example",
        "Different Name Entirely",
    ), (
        "the second organization is describing this person with the first "
        "organization's record. That is `rows[0]` leaking back: the rows are "
        "ordered by organization name, so it is always the alphabetically "
        "first tenant's view that wins."
    )

    # And the one thing that IS the identity is the same in both.
    assert response.user_id == two_organizations[0]["user_id"]
    assert len({org.organization_id for org in response.organizations}) == 2
