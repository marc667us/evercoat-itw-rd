"""Quality — the department conductor.

§0.2: department conductors live at
`app/agents/conductors/<dept>_conductor.py`, specialists never call other
agents, and API routes never call specialists directly.

Structural, like `laboratory_conductor`: no tools, no model, no reasoning.

🔴 WHAT IT OWNS, AND WHY THIS DEPARTMENT IS THE ONE THE AGENT TIER MUST NOT
REACH AROUND.

`failure.view`. A failure investigation is where §7's most consequential rule
lands: *an AI hypothesis is never an accepted root cause*. `failure_hypotheses`
carries `proposed → under_review → accepted → rejected` and **only a human**
moves anything to `accepted`. So the department is readable from the agent tier
and its state machine is not touchable from it — a distinction that only exists
if the door is here rather than in a route the agent path never traverses.

Measured on the seeded realm 2026-08-27: five of ten roles hold `failure.view`
(lead, chemist, QA, engineer, director). The technician who ran the failing
batch is not one of them.

⚠️ APPROVALS ARE NOT IN THIS DEPARTMENT, ALTHOUGH THEY SHARE A ROUTER FILE.
`app/api/failures.py` also mounts `/api/approvals`, whose routes declare
`test.view` rather than `failure.view` — a different department's permission on
a shared module. That is a fact about the file, not about the domain, and
mapping it into this conductor because the two are adjacent would put the
approval queue behind a gate no route uses. The approval engine is §9's shared
infrastructure and belongs to whichever department raises the route; it stays
on the HTTP path until a department claims it deliberately.

🔴 THE SESSION IS THE CALLER'S OWN, AND `authorize()` CHECKS IT.

⚠️ READS ONLY (§4). Not `open_investigation`, not `accept_root_cause`, not
`close`. §7 is explicit and this is where it is enforced structurally.
"""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy.orm import Session

from app.agents.boundary import require
from app.agents.principal import AgentPrincipal
from app.domains.failures import service as quality

__all__ = ["DEPARTMENT", "failure", "failures"]

DEPARTMENT = "quality"

# Named once rather than repeated per function.
VIEW = "failure.view"


def failures(
    session: Session,
    *,
    caller: AgentPrincipal,
    project_id: uuid.UUID | None = None,
    status: str | None = None,
    limit: int = 200,
) -> list[dict[str, Any]]:
    """Failure investigations this caller may see."""
    caller = caller.authorize(session)
    require(caller, department=DEPARTMENT, permission=VIEW)
    return quality.list_failures(
        session,
        organization_id=caller.organization_id,
        project_id=project_id,
        status=status,
        limit=limit,
    )


def failure(
    session: Session,
    *,
    failure_id: uuid.UUID,
    caller: AgentPrincipal,
) -> dict[str, Any]:
    """One investigation, with its hypotheses and their STATUS.

    🔴 THE STATUS TRAVELS WITH THE HYPOTHESIS AND IS NOT COSMETIC. §7: an AI
    hypothesis is not an accepted root cause. An agent reading this receives
    `proposed`/`under_review`/`accepted`/`rejected` as the domain recorded them,
    and has no way to change one — the transition is a human act with no
    entry point on this door.
    """
    caller = caller.authorize(session)
    require(caller, department=DEPARTMENT, permission=VIEW)
    return quality.get_failure(
        session,
        failure_id=failure_id,
        organization_id=caller.organization_id,
    )
