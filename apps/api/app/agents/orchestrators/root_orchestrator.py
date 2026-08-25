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
from typing import Any

from sqlalchemy.orm import Session

from app.agents.conductors import analysis_conductor, laboratory_conductor, testing_conductor
from app.agents.conductors.analysis_conductor import UnknownDashboardError
from app.agents.conductors.msd_conductor import MsdAnswer
from app.agents.conductors.msd_conductor import answer as msd_answer
from app.agents.ports import LanguageModelPort

__all__ = [
    "UnknownDashboardError",
    "analysis_dashboard",
    "answer_question",
    "laboratory_batch",
    "laboratory_batches",
    "testing_methods",
    "testing_test",
    "testing_tests",
]


def answer_question(
    session: Session,
    *,
    organization_id: uuid.UUID,
    user_id: uuid.UUID,
    role_codes: frozenset[str],
    question: str,
    project_id: uuid.UUID | None = None,
    permissions: frozenset[str] = frozenset(),
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
        permissions=permissions,
        model=model,
    )


# ---------------------------------------------------------------------------
# The other three departments.
#
# 🔴 THE RULE EARNS ITS KEEP HERE, AND THIS IS THE MOMENT IT PREDICTED.
#
# The module docstring above was written when there was exactly one
# department, and said so: *"Today it routes one department, and that is not
# an argument for skipping it. The rule earns its keep at the second
# department, when a route that had learned to import a conductor directly
# would keep doing so."* There are four now. Every one of them is reached
# through this module, and `tests/test_agent_topology.py` fails the build if
# an API module imports a conductor instead.
#
# These are STRUCTURAL entry points: they apply the department's permission
# gate (see `app/agents/boundary.py`) and dispatch to the domain service that
# owns the rules. None of them reasons, and none of them writes.
#
# ⚠️ THEY ARE READ-ONLY ON PURPOSE, AND THAT IS §4 RATHER THAN CAUTION.
# Humans approve. AI must not approve a test, change a controlled formula,
# move a result from YELLOW to GREEN, confirm a root cause or release a
# product. So no write-side service function is reachable from here at all --
# not `confirm_test`, not `approve`, not `authorize_batch`. A proposal an
# agent makes reaches a human through the approval engine, never through this
# door.
# ---------------------------------------------------------------------------


def laboratory_batches(
    session: Session,
    *,
    organization_id: uuid.UUID,
    permissions: frozenset[str],
    project_id: uuid.UUID | None = None,
    status: str | None = None,
    limit: int = 200,
) -> list[dict[str, Any]]:
    """Lab batches, through the laboratory conductor."""
    return laboratory_conductor.batches(
        session,
        organization_id=organization_id,
        permissions=permissions,
        project_id=project_id,
        status=status,
        limit=limit,
    )


def laboratory_batch(
    session: Session,
    *,
    batch_id: uuid.UUID,
    organization_id: uuid.UUID,
    permissions: frozenset[str],
) -> dict[str, Any]:
    """One lab batch, through the laboratory conductor."""
    return laboratory_conductor.batch(
        session,
        batch_id=batch_id,
        organization_id=organization_id,
        permissions=permissions,
    )


def testing_tests(
    session: Session,
    *,
    organization_id: uuid.UUID,
    permissions: frozenset[str],
    project_id: uuid.UUID | None = None,
    review_state: str | None = None,
    limit: int = 200,
) -> list[dict[str, Any]]:
    """The test queue, through the testing conductor."""
    return testing_conductor.tests(
        session,
        organization_id=organization_id,
        permissions=permissions,
        project_id=project_id,
        review_state=review_state,
        limit=limit,
    )


def testing_test(
    session: Session,
    *,
    test_id: uuid.UUID,
    organization_id: uuid.UUID,
    permissions: frozenset[str],
) -> dict[str, Any]:
    """One test and its derived disposition, through the testing conductor."""
    return testing_conductor.test(
        session,
        test_id=test_id,
        organization_id=organization_id,
        permissions=permissions,
    )


def testing_methods(
    session: Session,
    *,
    organization_id: uuid.UUID,
    permissions: frozenset[str],
    limit: int = 200,
) -> list[dict[str, Any]]:
    """Test methods, through the testing conductor."""
    return testing_conductor.methods(
        session,
        organization_id=organization_id,
        permissions=permissions,
        limit=limit,
    )


def analysis_dashboard(
    session: Session,
    *,
    name: str,
    user_id: uuid.UUID,
    organization_id: uuid.UUID,
    permissions: frozenset[str],
) -> dict[str, Any]:
    """One dashboard, through the analysis conductor."""
    return analysis_conductor.dashboard(
        session,
        name=name,
        user_id=user_id,
        organization_id=organization_id,
        permissions=permissions,
    )
