"""Who the caller is, before they have chosen a tenant.

🔴 WHY THIS ROUTE HAD TO EXIST BEFORE SIGN-IN COULD WORK

``get_principal`` requires the ``X-Organization-Id`` header and refuses
without it -- correctly, because defaulting to "the user's only
organization" silently picks one for a user who belongs to several and
writes records into whichever tenant happened to sort first. Every
authenticated route in this application depends on ``get_principal``,
directly or through ``require_permission``.

So a browser that had just signed in held a perfectly valid token and
**no way to discover a tenant to ask for**. Every request it could make
returned 400 telling it to supply a header whose value nothing would
tell it. Authentication was complete and the application was still
unusable.

This is the project's own most-repeated lesson wearing a new face. It has
been asked six times of roles -- *which production path WRITES this?* --
and the same question had never been asked of the organization id:
**which production path TELLS THE BROWSER its organization?** None did.

The CI auth suite could not catch it, because the workflow computes
``TEST_ORGANIZATION_ID`` from the seeder and injects it as an environment
variable. The tests were handed the answer that a real browser has no way
to obtain.

WHAT THIS ROUTE DOES NOT DO
---------------------------
It grants nothing and it is not a way around the header rule. It reports
memberships that ``core.organization_members`` already asserts for the
*signature-verified subject making the request*. Choosing among them is
still the client's act, and the choice is still re-validated by
``get_principal`` against the same table on every subsequent request. A
client that names an organization it is not a member of is refused
exactly as before -- ``test_a_foreign_organization_is_refused`` asserts
it.

See migration 024 for why the lookup is a ``SECURITY DEFINER`` function
rather than an ordinary query, and ADR-025 for the sign-in flow it
serves.
"""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import text

from app.core.db import unscoped_session_scope
from app.core.security import get_verified_subject

router = APIRouter()


class OrganizationMembership(BaseModel):
    """One organization this user may act in."""

    organization_id: uuid.UUID
    name: str
    code: str
    #: Role codes held IN THIS ORGANIZATION. Membership is per-tenant, so
    #: a user can be a chemist in one and a viewer in another. A single
    #: flat role list would be wrong in a way nobody would notice until a
    #: server-side permission check disagreed with the sidebar.
    roles: list[str] = Field(default_factory=list)


class Me(BaseModel):
    """The caller's identity, and the tenants they may choose from."""

    user_id: uuid.UUID
    email: str
    display_name: str
    organizations: list[OrganizationMembership] = Field(default_factory=list)


# The whole query is the function call. The predicate lives in the
# database (migration 024) rather than here, so there is exactly one
# definition of "which organizations may this subject act in" and no
# second spelling of it to drift.
_ME_SQL = text("SELECT * FROM core.memberships_for_subject(:sub)")


@router.get("", response_model=Me, tags=["identity"])
async def read_me(subject: Annotated[str, Depends(get_verified_subject)]) -> Me:
    """The signed-in user and every organization they may act in.

    🔴 A VALID TOKEN WITH NO MEMBERSHIPS IS **404, NOT 200 WITH AN EMPTY
    LIST.**

    An empty list would render as a successful sign-in leading to an
    application with nothing in it -- the exact failure this codebase has
    already shipped once, where *an empty requirement set rendered "ALL
    REQUIREMENTS PASSED"*. Absence must never present as success.

    It is also the precise symptom of a real, previously-recorded defect:
    ``seed.py`` writing ``keycloak_sub = 'demo-chem.demo'`` while a
    genuine token carries a UUID. The subject then resolves to no row,
    and saying so plainly is the fastest diagnostic in the whole auth
    path -- it distinguishes "you are not signed in" from "you are signed
    in as somebody this database has never heard of", which otherwise
    present identically.
    """
    # unscoped_session_scope() rather than get_db(), and named ugly on
    # purpose so a reviewer stops here. get_db depends on get_principal,
    # so it cannot be used before an organization exists -- that is the
    # circularity this route breaks. Safety does not come from the
    # session: it comes from the SECURITY DEFINER function, which is
    # scoped strictly to the verified subject and accepts no organization
    # argument. Do NOT add another query to this session.
    with unscoped_session_scope() as session:
        rows = session.execute(_ME_SQL, {"sub": subject}).mappings().all()

    if not rows:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=(
                "this token is valid, but its subject matches no active user with "
                "an active organization membership"
            ),
        )

    first = rows[0]
    return Me(
        user_id=first["user_id"],
        email=first["email"],
        display_name=first["display_name"],
        organizations=[
            OrganizationMembership(
                organization_id=row["organization_id"],
                name=row["organization_name"],
                code=row["organization_code"],
                roles=sorted(row["roles"]),
            )
            for row in rows
        ],
    )
