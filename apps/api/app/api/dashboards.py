"""Role dashboard routes. TODO I4.

🔴 THE ROLE IS A VIEW, NOT A PRIVILEGE.

`/api/dashboards/{role}` selects WHICH QUESTIONS to answer, not what the
caller is allowed to see. Every query behind it filters `organization_id`
explicitly and runs under RLS and the project-confidentiality predicate, so
asking for the director view does not show a chemist the portfolio — it shows
them the portfolio *they can already reach*, which for somebody on two
projects is two projects.

That is deliberate and it matters. §6 says authorization is on PERMISSIONS and
never on role names, and the frontend's checks are cosmetic. A dashboard that
gated on `role == "director"` would be inventing a second authorization model
beside the real one, in the layer §6 explicitly says must not hold one.

It also makes the product usable: a Lead who wants to see what their chemists
see can open the chemist view, and gets their own data through it.

**The permission floor is `project.view`** — someone with no read access at
all has no business on any of these — and everything past that floor is
decided by the same RLS every other read goes through.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.security import Principal, get_db, require_permission
from app.domains.dashboards.service import ROLE_DASHBOARDS

router = APIRouter()

__all__ = ["router"]


@router.get("/{role}", tags=["dashboards"])
def get_role_dashboard(
    role: str,
    principal: Principal = Depends(require_permission("project.view")),
    session: Session = Depends(get_db),
) -> dict[str, Any]:
    """One role's dashboard, answered from source records.

    Every panel returns `{available, reason, rows, count}`. A panel whose
    engine does not exist yet comes back `available: false` with the slice
    that will build it — NOT an empty list, because a screen cannot tell
    "nothing to report" from "not built yet" and a reader certainly cannot.

    Every row carries the id of the record it came from, so §2's requirement
    that dashboards "drill down to real source records" is satisfiable by the
    client without a second round trip to work out what it is looking at.
    """
    builder = ROLE_DASHBOARDS.get(role)
    if builder is None:
        # 404 names the four rather than echoing the input back: a message
        # that repeats an arbitrary path segment is a reflected-content
        # smell, and naming the valid set is more useful anyway.
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=(f"no such dashboard; the roles with a dashboard are {sorted(ROLE_DASHBOARDS)}"),
        )

    return builder(
        session,
        user_id=principal.user_id,
        organization_id=principal.organization_id,
    )
