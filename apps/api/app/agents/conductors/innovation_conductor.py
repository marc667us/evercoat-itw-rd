"""Innovation — the department conductor.

§0.2: department conductors live at
`app/agents/conductors/<dept>_conductor.py`, specialists never call other
agents, and API routes never call specialists directly.

Structural, like `laboratory_conductor`: no tools, no model, no reasoning.

🔴 WHAT IT OWNS.

`opportunity.view`, on every agent-tier entry into the innovation department.
It is the NARROWEST department gate in the product — measured on the seeded
realm 2026-08-27, three of ten roles hold it (lead, chemist, director) against
nine for `project.view` and ten for `knowledge.view`. That matters because an
opportunity is the first link of §2's digital thread and carries commercial
intent before any project exists to attach it to; a technician who may read
every project in the organization may not read what is being considered.

That narrowness is exactly why the gate belongs on the agent path too. A
question put to MSD about "what are we considering next" reaches this
department with no route in front of it, and the department's own answer is
that most of the organization may not have one.

🔴 THE SESSION IS THE CALLER'S OWN, AND `authorize()` CHECKS IT.

⚠️ READS ONLY (§4). Creating an opportunity, deciding one, and converting one
into a project are all human acts and none is reachable from here.
"""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy.orm import Session

from app.agents.boundary import require
from app.agents.principal import AgentPrincipal
from app.domains.opportunities import service as innovation

__all__ = ["DEPARTMENT", "opportunities", "opportunity"]

DEPARTMENT = "innovation"

# Named once rather than repeated per function.
VIEW = "opportunity.view"


def opportunities(
    session: Session,
    *,
    caller: AgentPrincipal,
    status: str | None = None,
    limit: int = 200,
) -> list[dict[str, Any]]:
    """The opportunity pipeline this caller may see."""
    caller = caller.authorize(session)
    require(caller, department=DEPARTMENT, permission=VIEW)
    return innovation.list_opportunities(
        session,
        organization_id=caller.organization_id,
        status=status,
        limit=limit,
    )


def opportunity(
    session: Session,
    *,
    opportunity_id: uuid.UUID,
    caller: AgentPrincipal,
) -> dict[str, Any]:
    """One opportunity and its detail."""
    caller = caller.authorize(session)
    require(caller, department=DEPARTMENT, permission=VIEW)
    return innovation.opportunity_detail(
        session,
        opportunity_id=opportunity_id,
        organization_id=caller.organization_id,
    )
