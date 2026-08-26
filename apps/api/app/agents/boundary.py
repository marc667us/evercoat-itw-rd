"""The permission gate every department conductor applies.

🔴 WHY A CONDUCTOR THAT ONLY FORWARDS WOULD BE DECORATION.

§0.2 requires a conductor per department, and the obvious first draft is a
module that re-exports its domain service. That is a pass-through with no
reason to exist — the same defect as a route nobody calls, wearing a layer's
clothes. If the conductor tier is going to exist it has to OWN something.

It owns this: **§7's rule that the agent tier operates under exactly the
calling user's authorization boundary.**

When a route serves a request, `require_permission(...)` has already run and
RLS scopes the session. But the agent tier is reachable another way — the root
orchestrator, on behalf of MSD or any later agent — and on that path no
FastAPI dependency has fired. `msd_conductor` already does this check inline
and per capability (`"formula.view_cost" in permissions`,
`"knowledge.view" in permissions`); this is the same rule, named once, so the
next department does not have to remember it.

⚠️ THIS IS NOT THE ONLY BOUNDARY AND MUST NOT BE DESCRIBED AS ONE.
Three things refuse an unauthorized read, and they are independent:

  1. the route's `require_permission(...)` — first, on the HTTP path only;
  2. this gate — on every agent-tier path, including the ones with no route;
  3. PostgreSQL RLS — on the session, whatever the Python above it believes.

Removing this one would not by itself open a hole on the HTTP path. It closes
the path that has no route, and it makes the department's requirement a
readable fact instead of a habit.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover - import cycle only matters to the checker
    from app.agents.principal import AgentPrincipal

__all__ = ["DepartmentDeniedError", "require"]


class DepartmentDeniedError(PermissionError):
    """A caller reached a department without the permission it requires.

    A `PermissionError` rather than a bespoke base: callers that already
    handle "not allowed" keep working, and nothing has to import this module
    to catch it correctly.
    """

    def __init__(self, department: str, permission: str) -> None:
        self.department = department
        self.permission = permission
        super().__init__(f"the {department} department requires the {permission!r} permission")


def require(caller: AgentPrincipal, *, department: str, permission: str) -> None:
    """Refuse unless the caller holds `permission`.

    🔴 IT TAKES A VERIFIED PRINCIPAL, NOT A SET OF STRINGS (I104).

    It used to take `permissions: frozenset[str]`, which made this gate exactly
    as true as whatever the caller chose to pass — and the orchestrator above
    it accepted that set as an ordinary keyword argument. A gate consulting a
    set the caller supplied is not a gate; it is a lookup. `AgentPrincipal`
    cannot be built from loose values, so there is no longer a way to reach
    this function with a permission set nobody verified.

    🔴 IT REFUSES, IT DOES NOT FILTER.

    §7 is explicit that retrieval is filtered BEFORE the model sees anything,
    never after — so a department the caller may not reach must raise here,
    at the door, rather than return rows for something downstream to trim.
    A conductor that returned data and trusted its caller to discard it would
    be the "filter after generation" mistake with extra steps.
    """
    if permission not in caller.permissions:
        raise DepartmentDeniedError(department, permission)
