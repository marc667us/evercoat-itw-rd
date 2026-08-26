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

from app.agents.orchestrators.root_orchestrator import (
    AgentPrincipal,
    UnknownDashboardError,
    analysis_dashboard,
)
from app.core.security import Principal, get_db, require_permission

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
    # 🔴 THROUGH THE ORCHESTRATOR, NOT STRAIGHT INTO THE SERVICE (§0.2, I103).
    #
    # This route imported `app.domains.dashboards.service` and called the
    # builder itself. The analysis conductor existed and NOTHING CALLED IT --
    # a layer with no caller, which is the same defect as a route with no
    # caller, and it meant the "analysis department" was a Python module you
    # could not reach from anywhere in the running product.
    #
    # §0.2 says API routes never call specialists directly. This is the second
    # route to obey it (msd.py was the first), and `tests/test_agent_topology`
    # already forbids importing a conductor here -- so the import is the
    # ORCHESTRATOR, which owns the department gate.
    #
    # ⚠️ `require_permission("project.view")` ABOVE STAYS. The conductor
    # asserts the same permission, and that is deliberate defence in depth,
    # not duplication: this dependency is what refuses an unauthenticated
    # caller before any handler runs, and the conductor is what refuses on the
    # paths that have no route at all. `analysis_conductor.VIEW` is pinned to
    # this literal by a test that reads this file's source, so they cannot
    # drift apart.
    try:
        return analysis_dashboard(
            session,
            name=role,
            # 🔴 ONE ARGUMENT, AND IT CANNOT BE ASSEMBLED FROM VALUES (I104).
            #
            # This used to pass `user_id`, `organization_id` and `permissions`
            # separately, with a comment explaining that the permissions were
            # load-bearing: §11's counts are of ACTIONABLE items, RLS says
            # what may be SEEN and a permission says what may be DONE, and
            # dropping them left the approvals panel offering steps the engine
            # would refuse. All three still reach the builders — they are
            # carried by the principal now, so a caller cannot pass two of the
            # three, and cannot pass a set nobody verified.
            caller=AgentPrincipal.of(principal),
        )
    except UnknownDashboardError as exc:
        # 404 names the four rather than echoing the input back: a message
        # that repeats an arbitrary path segment is a reflected-content
        # smell, and naming the valid set is more useful anyway.
        #
        # Translated HERE rather than left to escape, because the department's
        # error type is not this endpoint's public contract.
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
