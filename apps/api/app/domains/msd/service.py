"""MSD conversations, persisted.

Threads, turns and the evidence each answer was built from are OUR tables
in the `ai` schema (`CLAUDE.md` §4): *"Threads, turns, evidence links and
checkpoints are our tables in the ai schema — LangGraph state is derived
from ours and disposable."*

🔴 EVERY WRITE HERE GOES THROUGH THE CALLER'S OWN SESSION.

There is no service account. `ai.msd_threads` is owner-scoped and, after
migration 026, `ai.msd_turns` and `ai.msd_evidence` follow their thread —
so a caller physically cannot write a turn into somebody else's
conversation, rather than being trusted not to.
"""

from __future__ import annotations

import json
import uuid
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.agents.conductors.msd_conductor import MsdAnswer
from app.core.audit import AuditEvent, write_audit

__all__ = [
    "MsdNotFoundError",
    "list_threads",
    "list_turns",
    "open_thread",
    "record_exchange",
]


class MsdNotFoundError(LookupError):
    """No such thread for this caller.

    Deliberately the same answer whether the thread does not exist or
    belongs to somebody else — "you may not see it" and "it is not there"
    must be indistinguishable, or the error becomes a discovery channel.
    """


def open_thread(
    session: Session,
    *,
    organization_id: uuid.UUID,
    owner_id: uuid.UUID,
    title: str | None = None,
    project_id: uuid.UUID | None = None,
) -> dict[str, Any]:
    """Start a conversation owned by the caller."""
    row = (
        session.execute(
            text(
                """
                INSERT INTO ai.msd_threads
                    (organization_id, project_id, title, owner_id)
                VALUES (:org, :pid, :title, :owner)
                RETURNING id, title, project_id, created_at
                """
            ),
            {
                "org": organization_id,
                "pid": project_id,
                "title": title,
                "owner": owner_id,
            },
        )
        .mappings()
        .one()
    )
    return dict(row)


def record_exchange(
    session: Session,
    *,
    organization_id: uuid.UUID,
    thread_id: uuid.UUID,
    asked_by: uuid.UUID,
    question: str,
    answer: MsdAnswer,
) -> dict[str, Any]:
    """Store the question, the answer, and what the answer was built from.

    🔴 THE TURN NUMBER IS ALLOCATED FROM THE THREAD'S OWN MAX, INSIDE THE
    TRANSACTION.

    `msd_turns` declares `turn_number > 0` and a uniqueness constraint per
    thread. Counting in Python and passing the result would race two
    concurrent questions in the same thread onto the same number; the
    subquery makes the database allocate it under the same lock that
    inserts the row.

    🔴 THE DISCLAIMER IS NOT OPTIONAL AND CANNOT BE FORGOTTEN.

    `msd_turns_assistant_is_labelled` refuses an assistant turn whose
    `disclaimer` is NULL, so §7's *"AI-generated recommendation — requires
    technical review"* label is enforced by PostgreSQL rather than by
    everybody remembering to pass it.
    """
    # The thread must be visible to this caller. Under RLS an invisible
    # thread simply is not there, which is the refusal we want.
    exists = session.execute(
        text("SELECT 1 FROM ai.msd_threads WHERE id = :tid AND organization_id = :org"),
        {"tid": thread_id, "org": organization_id},
    ).scalar_one_or_none()
    if exists is None:
        raise MsdNotFoundError("no such MSD thread")

    def _insert(role: str, body: str, disclaimer: str | None, tool_calls: str | None) -> uuid.UUID:
        # Annotated rather than returned bare: `scalar_one()` is typed
        # `Any`, so returning it directly makes the declared UUID a
        # promise mypy cannot keep anyone to.
        new_id: uuid.UUID = session.execute(
            text(
                """
                INSERT INTO ai.msd_turns
                    (organization_id, thread_id, turn_number, role, body,
                     tool_calls, disclaimer, asked_by)
                VALUES (
                    :org, :tid,
                    (SELECT coalesce(max(turn_number), 0) + 1
                       FROM ai.msd_turns WHERE thread_id = :tid),
                    :role, :body, CAST(:tools AS jsonb), :disclaimer, :actor
                )
                RETURNING id
                """
            ),
            {
                "org": organization_id,
                "tid": thread_id,
                "role": role,
                "body": body,
                "tools": tool_calls,
                "disclaimer": disclaimer,
                "actor": asked_by,
            },
        ).scalar_one()
        return new_id

    _insert("user", question, None, None)
    answer_turn_id = _insert(
        "assistant",
        answer.body,
        answer.disclaimer,
        json.dumps(list(answer.tool_calls)) if answer.tool_calls else None,
    )

    for record in answer.evidence:
        session.execute(
            text(
                """
                INSERT INTO ai.msd_evidence
                    (organization_id, turn_id, entity_type, entity_id, excerpt)
                VALUES (:org, :turn, :etype, :eid, :excerpt)
                """
            ),
            {
                "org": organization_id,
                "turn": answer_turn_id,
                "etype": record.entity_type,
                "eid": record.entity_id,
                "excerpt": record.excerpt,
            },
        )

    # Audited: §11 lists "every MSD action that touched controlled
    # records" among the actions that must produce an audit event.
    write_audit(
        session,
        AuditEvent(
            action="msd.answered",
            entity_type="msd_turn",
            entity_id=str(answer_turn_id),
            organization_id=organization_id,
            user_id=asked_by,
            new_state={"intent": answer.intent, "evidence": len(answer.evidence)},
            reason="MSD answered a question",
        ),
    )

    session.execute(
        text("UPDATE ai.msd_threads SET updated_at = now() WHERE id = :tid"),
        {"tid": thread_id},
    )

    return {
        "turn_id": answer_turn_id,
        "body": answer.body,
        "disclaimer": answer.disclaimer,
        "intent": answer.intent,
        "href": answer.href,
        "suggestions": list(answer.suggestions),
        "evidence": [
            {
                "entity_type": r.entity_type,
                "entity_id": str(r.entity_id),
                "label": r.label,
            }
            for r in answer.evidence
        ],
    }


def list_threads(
    session: Session, *, organization_id: uuid.UUID, limit: int = 50
) -> list[dict[str, Any]]:
    """The caller's own conversations. RLS makes "own" true, not the query."""
    rows = session.execute(
        text(
            """
            SELECT id, title, project_id, created_at, updated_at
            FROM ai.msd_threads
            WHERE organization_id = :org
            ORDER BY updated_at DESC
            LIMIT :limit
            """
        ),
        {"org": organization_id, "limit": limit},
    ).mappings()
    return [dict(r) for r in rows]


def list_turns(
    session: Session, *, organization_id: uuid.UUID, thread_id: uuid.UUID, limit: int = 200
) -> list[dict[str, Any]]:
    """One conversation, oldest first, with the evidence for each answer."""
    turns = [
        dict(r)
        for r in session.execute(
            text(
                """
                SELECT id, turn_number, role, body, disclaimer, created_at
                FROM ai.msd_turns
                WHERE thread_id = :tid AND organization_id = :org
                ORDER BY turn_number
                LIMIT :limit
                """
            ),
            {"tid": thread_id, "org": organization_id, "limit": limit},
        ).mappings()
    ]
    if not turns:
        # Either the thread has no turns or it is not this caller's. Both
        # are an empty conversation from here, deliberately.
        return []

    evidence = session.execute(
        text(
            """
            SELECT e.turn_id, e.entity_type, e.entity_id, e.excerpt
            FROM ai.msd_evidence e
            JOIN ai.msd_turns t
              ON t.id = e.turn_id AND t.organization_id = e.organization_id
            WHERE t.thread_id = :tid AND e.organization_id = :org
            """
        ),
        {"tid": thread_id, "org": organization_id},
    ).mappings()

    by_turn: dict[uuid.UUID, list[dict[str, Any]]] = {}
    for row in evidence:
        by_turn.setdefault(row["turn_id"], []).append(
            {
                "entity_type": row["entity_type"],
                "entity_id": str(row["entity_id"]),
                "excerpt": row["excerpt"],
            }
        )

    for turn in turns:
        turn["evidence"] = by_turn.get(turn["id"], [])
    return turns
