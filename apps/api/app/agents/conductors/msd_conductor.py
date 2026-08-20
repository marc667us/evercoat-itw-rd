"""MSD — the Material Science & Development Assistant conductor.

🔴 THIS COMPOSES AN ANSWER FROM TOOL RESULTS. IT DOES NOT GENERATE ONE.

Every sentence MSD returns is built here, from values a tool read out of
PostgreSQL on the caller's own RLS-scoped session. The language model —
when one is configured at all — is handed the finished text and may only
reword it (`app/agents/ports.py`).

That is what makes the evidence list honest. `ai.msd_evidence` records
which records an answer was built from, and
`verify_evidence_within_boundary` can later prove every one of them was
readable by the asker. Neither check means anything if the prose was
free-generated: you can prove which rows were RETRIEVED, but nothing can
prove a generated sentence was entailed by them.

It also means MSD degrades honestly. With no model present the answers
are plainer and identical in content — which is the configuration CI runs
in, the configuration the deployed site would run in, and the one the
zero-cost rule (§7: no essential dependency on a paid AI API) requires be
sufficient.

🔴 SPECIALISTS NEVER CALL OTHER AGENTS (§0.2).

This conductor calls TOOLS. It does not call another conductor and it is
not called by a route — `root_orchestrator` is the only caller, and
`tests/test_agent_topology.py` enforces both directions.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any, Literal

from sqlalchemy.orm import Session

from app.agents.ports import LanguageModelPort, NullLanguageModel
from app.agents.tools import explain_the_application, find_records, pending_work
from app.domains.msd.retrieval import RetrievedRecord

__all__ = ["DISCLAIMER", "MsdAnswer", "answer"]

#: §7, verbatim. The database REFUSES an assistant turn without a
#: disclaimer (`msd_turns_assistant_is_labelled`), so this is not a
#: convention that can lapse — an unlabelled answer cannot be stored.
DISCLAIMER = "AI-generated recommendation — requires technical review."

Intent = Literal["guidance", "pending_work", "find_records", "unsupported"]


@dataclass(frozen=True, slots=True)
class MsdAnswer:
    """What MSD says, and everything needed to audit why it said it."""

    body: str
    intent: Intent
    disclaimer: str = DISCLAIMER
    evidence: tuple[RetrievedRecord, ...] = ()
    #: Recorded into `ai.msd_turns.tool_calls`, so a turn can be replayed
    #: and questioned. Which tools ran is part of the answer's provenance.
    tool_calls: tuple[dict[str, Any], ...] = ()
    #: Where in the product to go next, when the answer has a destination.
    href: str | None = None
    suggestions: tuple[str, ...] = field(default_factory=tuple)


#: Concept Note §33's suggested actions, offered when MSD cannot help.
_SUGGESTIONS: tuple[str, ...] = (
    "What is waiting for me?",
    "What does yellow mean on a test?",
    "Show me the batches on the bench",
    "How do I create a formula revision?",
)


def classify(question: str) -> Intent:
    """Which capability this question needs.

    🔴 DETERMINISTIC, AND NOT A MODEL'S JOB.

    Routing by a model would make the same question reach different
    capabilities on different days, and there is no version of that which
    is debuggable. It also puts a model on the path of a question that
    might need no model at all.

    Ordered deliberately: an application-guidance question like "what
    does yellow mean" must NOT fall through to record retrieval, where
    "yellow" would be matched against formula names and return confident
    nonsense.
    """
    lowered = question.lower().strip()
    if not lowered:
        return "unsupported"

    # Guidance first — it is the only intent with written answers, and a
    # written answer always beats a search.
    if explain_the_application(lowered) is not None:
        return "guidance"

    if any(
        phrase in lowered
        for phrase in (
            "waiting for me",
            "my work",
            "assigned to me",
            "my tasks",
            "my queue",
            "waiting on me",
            "my approval",
            "awaiting my",
        )
    ):
        return "pending_work"

    if any(
        word in lowered
        for word in ("show", "find", "which", "list", "search", "formula", "material", "batch")
    ):
        return "find_records"

    return "unsupported"


def answer(
    session: Session,
    *,
    organization_id: uuid.UUID,
    user_id: uuid.UUID,
    role_codes: frozenset[str],
    question: str,
    project_id: uuid.UUID | None = None,
    model: LanguageModelPort | None = None,
) -> MsdAnswer:
    """Answer one question, inside the caller's boundary.

    `session` MUST be the caller's own RLS-scoped session — every tool
    that touches records depends on that, and none of them re-checks
    permissions in Python.
    """
    model = model or NullLanguageModel()
    intent = classify(question)

    if intent == "guidance":
        entry = explain_the_application(question)
        assert entry is not None  # noqa: S101 - classify() just proved it
        return MsdAnswer(
            body=model.rephrase(composed=entry.body, question=question),
            intent=intent,
            href=entry.href,
            tool_calls=({"tool": "explain_the_application", "topic": entry.topic},),
        )

    if intent == "pending_work":
        tasks = pending_work(
            session,
            organization_id=organization_id,
            user_id=user_id,
            role_codes=role_codes,
        )
        composed = _compose_work(tasks)
        return MsdAnswer(
            body=model.rephrase(composed=composed, question=question),
            intent=intent,
            href="/my-work",
            tool_calls=({"tool": "pending_work", "returned": len(tasks)},),
        )

    if intent == "find_records":
        records = find_records(
            session,
            organization_id=organization_id,
            question=question,
            project_id=project_id,
        )
        composed = _compose_records(records)
        return MsdAnswer(
            body=model.rephrase(composed=composed, question=question),
            intent=intent,
            evidence=tuple(records),
            tool_calls=({"tool": "find_records", "returned": len(records)},),
        )

    return MsdAnswer(
        body=(
            "I cannot answer that yet. In this version I can explain how the "
            "application works, tell you what is waiting for you, and find "
            "controlled records you have access to."
        ),
        intent="unsupported",
        suggestions=_SUGGESTIONS,
    )


def _compose_work(tasks: list[dict[str, Any]]) -> str:
    """The inbox, in sentences. Overdue named first because it is."""
    if not tasks:
        # NOT "you are all caught up". This screen's own lesson: an empty
        # result and a failed one must not read the same, and an assistant
        # that congratulates you on an empty list it could not fill is the
        # worst version of that.
        return "Nothing is currently assigned to you or waiting on your role."

    overdue = [t for t in tasks if t.get("is_overdue")]
    lines = [f"You have {len(tasks)} item{'s' if len(tasks) != 1 else ''} needing action."]
    if overdue:
        lines.append(f"{len(overdue)} of them {'is' if len(overdue) == 1 else 'are'} overdue.")
    for task in tasks[:5]:
        where = f" ({task['project_code']})" if task.get("project_code") else ""
        due = f", due {task['due_date']}" if task.get("due_date") else ""
        lines.append(f"· {task['title']}{where} — {task['status']}{due}")
    if len(tasks) > 5:
        lines.append(f"…and {len(tasks) - 5} more on My Work.")
    return "\n".join(lines)


def _compose_records(records: list[RetrievedRecord]) -> str:
    """What was found, grouped by kind, with nothing inferred.

    🔴 THE EMPTY CASE IS A SENTENCE ABOUT THE SEARCH, NOT ABOUT THE WORLD.

    "There are no formulas matching that" is a claim MSD cannot make: the
    caller's boundary may simply exclude them, and saying nothing exists
    would disclose the shape of what does. "I found nothing you have
    access to" is both true and non-disclosing.
    """
    if not records:
        return (
            "I found no records you have access to that match that. If you expect "
            "something here, you may not be a member of the project it belongs to."
        )

    by_type: dict[str, list[RetrievedRecord]] = {}
    for record in records:
        by_type.setdefault(record.entity_type, []).append(record)

    lines = [f"I found {len(records)} record{'s' if len(records) != 1 else ''} you can open."]
    for entity_type, group in by_type.items():
        lines.append(f"{entity_type.replace('_', ' ')} ({len(group)}):")
        lines.extend(f"· {r.label}" for r in group[:5])
    return "\n".join(lines)
