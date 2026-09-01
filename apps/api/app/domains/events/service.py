"""Domain events — spec §22, "Event integration".

§22: *"Where practical, integrate through domain events rather than hard-coded
cross-module writes."*

🔴 WHAT THIS IS HONESTLY DOING, AND WHAT IT IS NOT.

§22 names four chains. This ships ONE of them end to end —
`TestResultFinalized` → the Research Center → the related investigation
updated — plus the announcement of `FormulaVersionCreated`, which the safety
chain will consume when it is built.

It does **not** rewire any existing cross-module call. `revise_version` still
calls `record_driver` directly; the safety impact chain still calls
`material_usage` directly. Those work, they are tested, and replacing a working
direct call with an event is a migration of behaviour rather than an addition —
a different and riskier change than this one. Said plainly here so the next
reader does not conclude from the presence of an event bus that the modules are
already decoupled. They are not, yet.

🔴 THE CONSUMER IS SYNCHRONOUS, IN THE EMITTER'S TRANSACTION, AND THAT IS A
   DECISION RATHER THAN A SHORTCUT.

There is no worker, no queue and no cursor. `TestResultFinalized` is emitted
inside `confirm_test`'s transaction and its consumer runs there too, so:

- the reaction cannot be lost — there is no window where the test is confirmed
  and the investigation has not been told;
- a failing consumer fails the confirmation, loudly, instead of leaving the two
  modules disagreeing;
- nothing needs to record what has been processed, which is why the log has no
  `processed` column and no cursor table. Inventing either now would be a
  column with no reader.

⚠️ THE TRADE IS REAL AND IT IS NOT FREE. A slow or broken consumer makes
confirming a test slow or broken. That is acceptable while the consumer is one
indexed SELECT and one INSERT against the same database, and it stops being
acceptable the moment a consumer does I/O to anything else. When one does, it
moves behind `WorkflowPort` and gets a cursor — and this comment is the note
that says the current design was chosen with that boundary in mind.

⚠️ EMITTING DOES NOT REPLACE AUDITING. `write_audit` records who did what, for
compliance, and is unreachable from ordinary UI paths (`CLAUDE.md` §5). An
event announces a fact so another module can react. An action audited but not
announced is invisible to other modules; announced but not audited is
untraceable. Both, or neither.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

# ─── the vocabulary ──────────────────────────────────────────────────────────
#
# 🔴 EVERY NAME HERE HAS AN EMITTER IN THIS COMMIT, AND THE DATABASE AGREES.
#
# Migration 063's CHECK carries the same three strings. Two literals in two
# places cannot be type-checked into agreement, so
# `test_the_event_vocabulary_matches_the_database` reads the CHECK constraint
# out of `pg_constraint` and compares. A name added here and not there is
# refused by the database at runtime; a name added there and not here is a
# value nothing can produce.
FORMULA_VERSION_CREATED = "FormulaVersionCreated"
TEST_RESULT_FINALIZED = "TestResultFinalized"
INVESTIGATION_UPDATED_BY_TEST = "ResearchInvestigationUpdatedByTestResult"
# 066, §22's FIRST chain. Announced by the safety module when a newly created
# formula version contains a material that requires a safety data sheet and has
# none on file.
SAFETY_REVIEW_REQUIRED = "SafetyReviewRequired"

#: Event type -> the kind of record it is *about*.
EVENT_SUBJECTS: dict[str, str] = {
    FORMULA_VERSION_CREATED: "formula_version",
    TEST_RESULT_FINALIZED: "test",
    INVESTIGATION_UPDATED_BY_TEST: "research_investigation",
    # ABOUT the version that triggered it, so it reuses `formula_version`.
    SAFETY_REVIEW_REQUIRED: "formula_version",
}


# ─── the registry ────────────────────────────────────────────────────────────
#
# 🔴 THIS IS WHAT MAKES §22 DECOUPLING RATHER THAN A LOG.
#
# 063 shipped the log, the emitter and one chain, and said plainly that it
# rewired nothing: `revise_version` announced `FormulaVersionCreated` and
# **nothing consumed it**. An event with no reader reads as integration and is
# not one — the mirror of the table-with-no-writer defect this repository has
# counted twenty-three of.
#
# The direction is the whole point. A handler registers itself; the emitting
# module never learns who is listening and never imports them. `formulations`
# does not import `material_safety` — if it did, this would be a hard-coded
# cross-module call with extra ceremony, which is exactly what §22 asks us not
# to build.
#
# ⚠️ SYNCHRONOUS, IN THE EMITTER'S TRANSACTION, for the reasons this module's
# header already gives: the reaction cannot be lost, a failing consumer fails
# the write loudly instead of leaving two modules disagreeing, and nothing
# needs a cursor. The trade is real and unchanged — a slow consumer makes the
# emitting write slow — and it stops being acceptable the moment a consumer
# does I/O to anything but this database.
_SUBSCRIBERS: dict[str, list[Callable[..., Any]]] = {}


def subscribe(event_type: str, handler: Callable[..., Any]) -> None:
    """Register a reaction to one event type.

    Called from `app/domains/events/wiring.py` at import time, which is the one
    place that knows both halves. Registering the same handler twice is a
    no-op: `main.py` can be imported more than once in a test session and a
    duplicated subscriber would run the reaction twice on one event.
    """
    if event_type not in EVENT_SUBJECTS:
        raise DomainEventError(
            f"{event_type!r} is not a declared domain event, so nothing can "
            "ever announce it and this handler would never run."
        )
    handlers = _SUBSCRIBERS.setdefault(event_type, [])
    if handler not in handlers:
        handlers.append(handler)


def subscribers(event_type: str) -> tuple[Callable[..., Any], ...]:
    """Who reacts to this, in registration order. Readable by tests."""
    return tuple(_SUBSCRIBERS.get(event_type, ()))


def dispatch(
    session: Session,
    *,
    organization_id: uuid.UUID,
    event_type: str,
    subject_id: uuid.UUID,
    project_id: uuid.UUID | None = None,
    payload: dict[str, Any] | None = None,
    actor_id: uuid.UUID | None = None,
) -> list[Any]:
    """Announce a fact AND run whatever reacts to it.

    Returns each handler's result so a caller and a test can see what actually
    happened, rather than trusting that something did.

    ⚠️ AN EVENT WITH NO SUBSCRIBER IS NOT AN ERROR HERE. It is still recorded,
    because the log is also read by a screen showing what happened to a record.
    Whether a given type SHOULD have a consumer is a question for a test, not
    for this function — `test_every_declared_event_type_has_a_consumer` is
    where that is asserted, so a chain that quietly loses its reaction fails
    there rather than going unnoticed here.
    """
    event_id = emit(
        session,
        organization_id=organization_id,
        event_type=event_type,
        subject_id=subject_id,
        project_id=project_id,
        payload=payload,
        actor_id=actor_id,
    )
    results: list[Any] = []
    for handler in subscribers(event_type):
        results.append(
            handler(
                session,
                organization_id=organization_id,
                subject_id=subject_id,
                project_id=project_id,
                payload=payload or {},
                actor_id=actor_id,
                triggered_by_event=event_id,
            )
        )
    return results


class DomainEventError(RuntimeError):
    """An event this module refuses to record."""


def emit(
    session: Session,
    *,
    organization_id: uuid.UUID,
    event_type: str,
    subject_id: uuid.UUID,
    project_id: uuid.UUID | None = None,
    payload: dict[str, Any] | None = None,
    actor_id: uuid.UUID | None = None,
) -> int:
    """Announce one fact, in the caller's transaction.

    `subject_type` is NOT a parameter: it is derived from `event_type` through
    `EVENT_SUBJECTS`. A caller that could pass its own would eventually pass a
    mismatched pair — `TestResultFinalized` about a formula version — and every
    consumer filtering on subject type would silently miss it.

    Returns the event's id so a caller can assert the announcement happened
    rather than trusting that it did.
    """
    subject_type = EVENT_SUBJECTS.get(event_type)
    if subject_type is None:
        raise DomainEventError(
            f"{event_type!r} is not a declared domain event. Add it to "
            "EVENT_SUBJECTS and to migration 063's CHECK in the same commit as "
            "its emitter, never before one exists."
        )

    # `scalar_one()` is typed `Any` by SQLAlchemy, so the int is asserted here
    # rather than assumed. A `RETURNING id` that came back as something else
    # would mean the insert did not do what this function claims.
    event_id = session.execute(
        text(
            """
            INSERT INTO workflow.domain_events
                (organization_id, event_type, subject_type, subject_id,
                 project_id, payload, actor_id)
            VALUES (:org, :etype, :stype, :sid, :pid, CAST(:payload AS JSONB), :actor)
            RETURNING id
            """
        ),
        {
            "org": organization_id,
            "etype": event_type,
            "stype": subject_type,
            "sid": subject_id,
            "pid": project_id,
            "payload": _json(payload or {}),
            "actor": actor_id,
        },
    ).scalar_one()
    return int(event_id)


def events_for(
    session: Session,
    *,
    organization_id: uuid.UUID,
    subject_type: str,
    subject_id: uuid.UUID,
    limit: int = 100,
) -> list[dict[str, Any]]:
    """What has been announced about one record, newest first.

    RLS applies the tenant predicate. The explicit `organization_id` is the
    same belt-and-braces every read in this codebase carries.
    """
    rows = session.execute(
        text(
            """
            SELECT e.id, e.event_type, e.subject_type, e.subject_id,
                   e.project_id, e.payload, e.actor_id, e.occurred_at,
                   u.display_name AS actor_name
              FROM workflow.domain_events e
              LEFT JOIN core.users u ON u.id = e.actor_id
             WHERE e.organization_id = :org
               AND e.subject_type = :stype
               AND e.subject_id = :sid
             ORDER BY e.id DESC
             LIMIT :limit
            """
        ),
        {"org": organization_id, "stype": subject_type, "sid": subject_id, "limit": limit},
    ).mappings()

    return [
        {
            "id": r["id"],
            "event_type": r["event_type"],
            "subject_type": r["subject_type"],
            "subject_id": str(r["subject_id"]),
            "project_id": str(r["project_id"]) if r["project_id"] else None,
            "payload": r["payload"],
            # Null for a reaction, which has no person behind it. The screen
            # says "the system" rather than leaving a blank that reads as a
            # missing name.
            "actor_id": str(r["actor_id"]) if r["actor_id"] else None,
            "actor_name": r["actor_name"],
            "occurred_at": r["occurred_at"].isoformat(),
        }
        for r in rows
    ]


# ─── the one §22 chain that is wired end to end ──────────────────────────────


def announce_test_result_finalized(
    session: Session,
    *,
    organization_id: uuid.UUID,
    test_id: uuid.UUID,
    actor_id: uuid.UUID,
    payload: dict[str, Any],
) -> dict[str, Any]:
    """`TestResultFinalized` → the Research Center → the investigation updated.

    §22's second chain, and the only one wired end to end today.

    🔴 THE REACTION IS THE POINT. Emitting an event nothing consumes would be a
    log with no reader — this repository's most-repeated defect wearing a new
    hat. So this both announces the fact AND runs the Research Center's
    reaction, and returns what it did so a caller and a test can see it.

    ⚠️ IT UPDATES NO CONTROLLED RECORD. The reaction announces a second event
    against each affected investigation; it does not fabricate an evidence card
    or a finding. A researcher's evidence is theirs to write — §7's rule that
    conclusions become controlled records only by explicit human promotion is
    about AI, and the same reasoning applies to an automated reaction. What the
    researcher gets is the knowledge that the test they are waiting on has
    landed, and what it said.
    """
    event_id = emit(
        session,
        organization_id=organization_id,
        event_type=TEST_RESULT_FINALIZED,
        subject_id=test_id,
        project_id=payload.get("project_id"),
        payload={k: v for k, v in payload.items() if k != "project_id"},
        actor_id=actor_id,
    )

    # Investigations that NAME this test. `research.investigations.test_id` has
    # existed since migration 058 and nothing has ever reacted to it changing --
    # this is the production path that finally reads it.
    affected = session.execute(
        text(
            """
            SELECT id, investigation_code, project_id
              FROM research.investigations
             WHERE organization_id = :org
               AND test_id = :tid
               AND status <> 'closed'
            """
        ),
        {"org": organization_id, "tid": test_id},
    ).mappings()

    notified: list[str] = []
    for investigation in affected:
        emit(
            session,
            organization_id=organization_id,
            event_type=INVESTIGATION_UPDATED_BY_TEST,
            subject_id=investigation["id"],
            project_id=investigation["project_id"],
            payload={
                "test_id": str(test_id),
                "test_number": payload.get("test_number"),
                # 🔴 THE OUTCOME IS COPIED INTO THE EVENT, NOT LOOKED UP LATER.
                # A test can be superseded; the event records what was true when
                # the investigation was told, which is what a reader of a
                # timeline needs.
                "calculated_result": payload.get("calculated_result"),
                "triggered_by_event": event_id,
            },
            # No actor: a reaction has no person behind it. The person confirmed
            # a test; nobody notified this investigation.
            actor_id=None,
        )
        notified.append(investigation["investigation_code"])

    return {"event_id": event_id, "investigations_notified": notified}


def _json(value: dict[str, Any]) -> str:
    import json

    # `default=str` so a UUID or a Decimal in a payload serialises instead of
    # raising inside a write path that has already changed a controlled record.
    return json.dumps(value, default=str)
