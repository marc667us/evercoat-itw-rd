"""Laboratory — the department conductor.

§0.2: department conductors live at
`app/agents/conductors/<dept>_conductor.py`, specialists never call other
agents, and API routes never call specialists directly.

This is a STRUCTURAL conductor. It has no tools, no model and no reasoning:
it applies the department's permission gate and dispatches to
`app.domains.laboratory.service`, which owns the business rules and is
already covered by its own tests. Reasoning, if the laboratory ever needs
any, is added behind this same door rather than beside it.

🔴 WHAT IT OWNS, SO THAT IT IS NOT A PASS-THROUGH.

`batch.view` is asserted here, on every agent-tier entry into the laboratory.
On the HTTP path `require_permission("batch.view")` has already run; on the
orchestrator path — MSD asking the laboratory a question, or any later agent
— no FastAPI dependency has fired, and this is the check that stands in its
place. See `app/agents/boundary.py` for why that is the conductor tier's job
and why it is deliberately not described as the only boundary.

🔴 THE SESSION IS THE CALLER'S OWN, AND SINCE I104 SOMETHING CHECKS IT.
Every function here takes the RLS-scoped session the caller already holds. It
must never open its own connection or borrow a privileged one: RLS is what
makes "this organization's batches" true independently of the Python above
it, and a conductor that reached around it would return another tenant's
work to an agent that then reasoned over it.

That used to be this paragraph and nothing else — a comment asserting a rule
the code did not have. `caller.authorize(session)` now asks PostgreSQL,
through `app.current_org` and `app.current_user_id`, whether the session
really is this principal's, and refuses if it is not.

🔴 AND SINCE I105 IT ALSO TAKES THE PERMISSIONS FROM THE DATABASE, which is
why it runs BEFORE the gate rather than beside it. The gate is only as true as
the set it consults, and until 048 that set had never left Python.

⚠️ FORGETTING THE LINE IS LOUD, NOT SILENT. `require()` refuses a principal
that has not been authorized (`UnverifiedPrincipalError`) — because for a
legitimate caller the claimed and derived sets are identical, so a conductor
that skipped this would pass every ordinary test and be wrong only for a
forgery.
"""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy.orm import Session

from app.agents.boundary import require
from app.agents.principal import AgentPrincipal
from app.domains.laboratory import service as laboratory

__all__ = ["DEPARTMENT", "batch", "batches"]

DEPARTMENT = "laboratory"

# The permission a caller needs to read anything in this department. Named
# once, here, rather than repeated at each function — the repeated form is
# how one of them ends up checking a different code from the others.
VIEW = "batch.view"


def batches(
    session: Session,
    *,
    caller: AgentPrincipal,
    project_id: uuid.UUID | None = None,
    status: str | None = None,
    limit: int = 200,
) -> list[dict[str, Any]]:
    """Lab batches this caller may see."""
    caller = caller.authorize(session)
    require(caller, department=DEPARTMENT, permission=VIEW)
    return laboratory.list_batches(
        session,
        organization_id=caller.organization_id,
        project_id=project_id,
        status=status,
        limit=limit,
    )


def batch(
    session: Session,
    *,
    batch_id: uuid.UUID,
    caller: AgentPrincipal,
) -> dict[str, Any]:
    """One batch, with whatever the domain service considers its detail."""
    caller = caller.authorize(session)
    require(caller, department=DEPARTMENT, permission=VIEW)
    return laboratory.get_batch(session, batch_id=batch_id, organization_id=caller.organization_id)
