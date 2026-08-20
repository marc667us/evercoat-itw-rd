"""MSD — the Material Science & Development Assistant, over HTTP.

🔴 THIS MODULE IMPORTS THE ROOT ORCHESTRATOR AND NOTHING ELSE FROM THE
AGENT TIER.

§0.2: *"API routes never call specialists directly. MSD is reached
through the orchestrator."* No conductor and no tool is imported here,
and `tests/test_agent_topology.py` fails the build if one ever is.

🔴 THE PRINCIPAL SUPPLIES THE IDENTITY. THE BODY NEVER DOES.

`organization_id`, `user_id` and the caller's roles come from the
resolved `Principal` — a signature-verified token plus a database lookup.
The request body carries a question and, optionally, a project to focus
on; it cannot name a user. A body that could would let somebody ask MSD
what is waiting for a colleague, which is the "AI as a permission-bypass
channel" §7 forbids.
"""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.agents.orchestrators.root_orchestrator import answer_question
from app.core.security import Principal, get_db, get_principal, require_permission
from app.domains.msd.service import (
    MsdNotFoundError,
    list_threads,
    list_turns,
    open_thread,
    record_exchange,
)

router = APIRouter()

__all__ = ["router"]


class ThreadCreate(BaseModel):
    title: str | None = Field(default=None, max_length=200)
    project_id: uuid.UUID | None = None


class AskCreate(BaseModel):
    # Bounded like a message body. A 2MB "question" is not a question,
    # and an unbounded field on a route that fans out into retrieval is
    # an obvious abuse surface on an API with no rate limiting (I18).
    question: str = Field(min_length=1, max_length=2000)
    project_id: uuid.UUID | None = None


@router.get("/threads", tags=["msd"])
def get_threads(
    principal: Principal = Depends(get_principal),
    session: Session = Depends(get_db),
) -> list[dict[str, Any]]:
    """The caller's own conversations.

    No permission dependency: a person's own MSD threads are theirs by
    definition, and `ai.msd_threads` is owner-scoped in the database, so
    this returns nobody else's regardless of what any check said.
    """
    return list_threads(session, organization_id=principal.organization_id)


@router.post("/threads", status_code=status.HTTP_201_CREATED, tags=["msd"])
def post_thread(
    payload: ThreadCreate,
    principal: Principal = Depends(get_principal),
    session: Session = Depends(get_db),
) -> dict[str, Any]:
    result = open_thread(
        session,
        organization_id=principal.organization_id,
        owner_id=principal.user_id,
        title=payload.title,
        project_id=payload.project_id,
    )
    session.commit()
    return result


@router.get("/threads/{thread_id}/turns", tags=["msd"])
def get_turns(
    thread_id: uuid.UUID,
    principal: Principal = Depends(get_principal),
    session: Session = Depends(get_db),
    limit: int = Query(default=200, ge=1, le=500),
) -> list[dict[str, Any]]:
    return list_turns(
        session,
        organization_id=principal.organization_id,
        thread_id=thread_id,
        limit=limit,
    )


@router.post("/threads/{thread_id}/ask", tags=["msd"])
def post_question(
    thread_id: uuid.UUID,
    payload: AskCreate,
    # 🔴 GATED ON `msd.use`, NOT ON BEING AUTHENTICATED.
    #
    # Every other capability in this application is permission-gated, and
    # an assistant that reaches across projects, materials, batches and
    # tests is not the one place to make an exception. The permission is
    # what an administrator revokes when MSD must be switched off for
    # somebody, without removing their access to the screens.
    principal: Principal = Depends(require_permission("msd.use")),
    session: Session = Depends(get_db),
) -> dict[str, Any]:
    """Ask MSD a question, inside the caller's authorization boundary.

    The answer is composed from records this caller can read, on this
    caller's own RLS-scoped session — filtering happens before anything
    reasons over the data, never after (§7).
    """
    try:
        answer = answer_question(
            session,
            organization_id=principal.organization_id,
            user_id=principal.user_id,
            role_codes=frozenset(principal.roles),
            question=payload.question,
            project_id=payload.project_id,
        )
        result = record_exchange(
            session,
            organization_id=principal.organization_id,
            thread_id=thread_id,
            asked_by=principal.user_id,
            question=payload.question,
            answer=answer,
        )
    except MsdNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc

    session.commit()
    return result
