"""Formulations — the department conductor.

§0.2: department conductors live at
`app/agents/conductors/<dept>_conductor.py`, specialists never call other
agents, and API routes never call specialists directly.

Structural, like `laboratory_conductor`: no tools, no model, no reasoning. It
applies the department's permission gate and dispatches to
`app.domains.formulations.service`, which owns the business rules and its own
tests.

🔴 WHAT IT OWNS, SO THAT IT IS NOT A PASS-THROUGH.

Two permissions, not one, and the second is the interesting one.

`formula.view` reaches the department at all. `formula.view_cost` decides
whether a cost figure is present in what comes back — and the department's rule
is that the figure is **ABSENT rather than null**, so a caller without it
cannot tell a withheld cost from a cost of zero. That decision used to be made
four times inside `app/api/formulations.py`, once per route, as
`include_cost=principal.has("formula.view_cost")`. Four copies of one rule is
this repository's most-repeated defect, and it was one route away from becoming
five: on the agent path there is no route at all, so an agent asking the
formulations department a question had no `include_cost` decision made for it
anywhere.

Now it is decided here, once, from the verified principal — which also means
an agent cannot ask for cost by passing a flag, because there is no flag to
pass.

🔴 THE SESSION IS THE CALLER'S OWN, AND `authorize()` CHECKS IT.
Every function takes the RLS-scoped session the caller already holds and asks
PostgreSQL, through `app.current_org` and `app.current_user_id`, whether the
session really is this principal's. RLS is what makes "this organization's
formulas" true independently of the Python above it.

⚠️ READS ONLY, AND THAT IS §4 RATHER THAN CAUTION. Humans approve. No
write-side service function is reachable from here — not `submit_version`, not
`decide`, not `revise`, not `classify`. A proposal an agent makes reaches a
human through the approval engine, never through this door.

⚠️ `export_version` IS NOT HERE EITHER, AND THAT IS DELIBERATE. It is a read,
and it WRITES an export audit event naming the actor. §4 keeps the audited act
of taking proprietary composition out of a building on the human path, where a
`Principal` with a `user_id` signed for it.
"""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy.orm import Session

from app.agents.boundary import require
from app.agents.principal import AgentPrincipal
from app.domains.formulations import service as formulations

__all__ = [
    "DEPARTMENT",
    "classifications",
    "comparison",
    "evaluation",
    "formulas",
    "version",
]

DEPARTMENT = "formulations"

# The permission a caller needs to read anything in this department. Named
# once, here, rather than repeated at each function — the repeated form is how
# one of them ends up checking a different code from the others.
VIEW = "formula.view"

# 🔴 A SEPARATE GATE, NOT A DEGREE OF THE FIRST. A chemist sees the
# composition; whether they also see what it costs is a different decision,
# held by a different set of roles. Measured on the seeded realm 2026-08-27:
# `formula.view` is held by seven of ten seeded roles and `formula.view_cost` by
# four -- the lead, chemist, engineer and director, and not the technician, QA,
# production engineer, procurement specialist, executive or administrator.
COST = "formula.view_cost"


def _cost_visible(caller: AgentPrincipal) -> bool:
    """Whether this caller's answer may carry cost.

    Derived from the verified principal and from nothing else. There is no
    argument for it on any function in this module, so no caller — route,
    orchestrator or agent — can ask for cost it does not hold.
    """
    return COST in caller.permissions


def formulas(
    session: Session,
    *,
    caller: AgentPrincipal,
    project_id: uuid.UUID | None = None,
    limit: int = 200,
) -> list[dict[str, Any]]:
    """The formulas this caller may see."""
    caller = caller.authorize(session)
    require(caller, department=DEPARTMENT, permission=VIEW)
    return formulations.list_formulas(
        session,
        organization_id=caller.organization_id,
        project_id=project_id,
        limit=limit,
    )


def version(
    session: Session,
    *,
    version_id: uuid.UUID,
    caller: AgentPrincipal,
) -> dict[str, Any]:
    """One formula version, with cost only if this caller may see cost."""
    caller = caller.authorize(session)
    require(caller, department=DEPARTMENT, permission=VIEW)
    return formulations.get_version(
        session,
        version_id=version_id,
        organization_id=caller.organization_id,
        include_cost=_cost_visible(caller),
    )


def evaluation(
    session: Session,
    *,
    version_id: uuid.UUID,
    caller: AgentPrincipal,
) -> dict[str, Any]:
    """The version's computed evaluation — §3's Calculated, never Measured."""
    caller = caller.authorize(session)
    require(caller, department=DEPARTMENT, permission=VIEW)
    return formulations.evaluate_version(
        session,
        version_id=version_id,
        organization_id=caller.organization_id,
        include_cost=_cost_visible(caller),
    )


def comparison(
    session: Session,
    *,
    left_version_id: uuid.UUID,
    right_version_id: uuid.UUID,
    caller: AgentPrincipal,
) -> dict[str, Any]:
    """Two versions against each other — §8's genealogy, made readable."""
    caller = caller.authorize(session)
    require(caller, department=DEPARTMENT, permission=VIEW)
    return formulations.compare_versions(
        session,
        left_version_id=left_version_id,
        right_version_id=right_version_id,
        organization_id=caller.organization_id,
        include_cost=_cost_visible(caller),
    )


def classifications(
    session: Session,
    *,
    caller: AgentPrincipal,
) -> list[dict[str, Any]]:
    """The confidentiality lattice, in rank order.

    ⚠️ THE SERVICE FUNCTION TAKES NO `organization_id`, AND THE GATE STILL
    APPLIES. These are reference rows shared by every tenant, so there is
    nothing here to scope — but "shared" is not "public", and a caller who may
    not read a formula has no business enumerating the levels a formula can
    carry. Gating a global read is the case most easily skipped by reflex,
    which is why it is stated rather than assumed.
    """
    caller = caller.authorize(session)
    require(caller, department=DEPARTMENT, permission=VIEW)
    return formulations.list_classifications(session)
