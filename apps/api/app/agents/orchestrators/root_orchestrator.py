"""Root Orchestrator — the only door into the agent tier.

🔴 §0.2, LITERALLY: *"API routes never call specialists directly. MSD is
reached through the orchestrator."*

Today it routes one department, and that is not an argument for skipping
it. The rule earns its keep at the second department, when a route that
had learned to import a conductor directly would keep doing so — and the
orchestrator is also the single place where cross-cutting obligations
belong: the authorization boundary is asserted here for every request,
whatever department serves it.

`tests/test_agent_topology.py` enforces the structure rather than trusting
it: no module under `app/api/` may import a conductor or a tool.
"""

from __future__ import annotations

import uuid

from sqlalchemy.orm import Session

from app.agents.conductors.msd_conductor import MsdAnswer
from app.agents.conductors.msd_conductor import answer as msd_answer
from app.agents.ports import LanguageModelPort

__all__ = ["answer_question"]


def answer_question(
    session: Session,
    *,
    organization_id: uuid.UUID,
    user_id: uuid.UUID,
    role_codes: frozenset[str],
    question: str,
    project_id: uuid.UUID | None = None,
    model: LanguageModelPort | None = None,
) -> MsdAnswer:
    """Answer a question as the given principal.

    🔴 EVERY ARGUMENT HERE COMES FROM A VERIFIED PRINCIPAL, NOT FROM THE
    REQUEST BODY.

    `organization_id`, `user_id` and `role_codes` are read from the
    `Principal` the route resolved — which was built from a
    signature-verified token and a database lookup, not from anything the
    caller typed. A body that could name its own `user_id` would let
    somebody ask MSD what is waiting for a colleague.

    `session` must be the caller's own RLS-scoped session. That is the
    mechanism §7 relies on: retrieval returns what this person can open,
    so filtering happens BEFORE anything reasons over it, and never after.
    """
    return msd_answer(
        session,
        organization_id=organization_id,
        user_id=user_id,
        role_codes=role_codes,
        question=question,
        project_id=project_id,
        model=model,
    )
