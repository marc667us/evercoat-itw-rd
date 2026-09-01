"""Who reacts to what — the one module that knows both halves of a §22 chain.

🔴 WHY THIS FILE EXISTS AT ALL, AND WHY IT IS NOT IN `service.py`.

§22 asks for integration "through domain events rather than hard-coded
cross-module writes". The whole value is the DIRECTION: `formulations` must not
know that `material_safety` reacts to a formula version being created. If the
emitting module imported the consumer — or if `events/service.py` did, since
every emitter imports that — the import graph would be exactly the coupling the
events were supposed to remove, with a log added on the side.

So the registry lives in `service.py` and the *registration* lives here, and
this is the only module that imports both ends. It is imported once, from
`app/main.py`, at startup.

⚠️ IMPORTED FOR ITS SIDE EFFECT, WHICH IS UNUSUAL ENOUGH TO SAY OUT LOUD.
`main.py` calls `wire_domain_events()` explicitly rather than relying on import
order, because a bare `import wiring` reads as dead code to every linter and to
every reader, and something would eventually "clean it up" — at which point the
chains would silently stop reacting and every existing test would still pass.
`test_every_declared_event_type_has_a_consumer` is what turns that into a
failure instead of a silence.

⚠️ REGISTRATION IS IDEMPOTENT. `subscribe` refuses to add the same handler
twice, because `app.main` is imported more than once across a test session and
a duplicated subscriber would run one reaction twice on one event.
"""

from __future__ import annotations

from app.domains.events.service import FORMULA_VERSION_CREATED, subscribe

__all__ = ["wire_domain_events"]


def wire_domain_events() -> None:
    """Register every §22 reaction. Called once, from `app.main`.

    ⚠️ THE IMPORT IS INSIDE THE FUNCTION, DELIBERATELY. `material_safety`
    imports `formulations`, which imports `events.service` — importing the
    consumer at module scope here would drag that whole graph into
    `events.wiring` at import time and make the cycle a matter of import
    ordering rather than of design. Deferring it keeps `events` importable by
    anything, which is what lets an emitter depend on it without depending on
    its consumers.
    """
    from app.domains.material_safety.service import on_formula_version_created

    # §22 chain 1: FormulaVersionCreated -> the safety module evaluates ->
    # SafetyReviewRequired (migration 066).
    subscribe(FORMULA_VERSION_CREATED, on_formula_version_created)

    # ⚠️ CHAINS 3 AND 4 ARE NOT HERE, AND THAT IS NOT AN OVERSIGHT.
    #
    #   ResearchFindingApproved -> Knowledge Library indexes finding
    #   SDSRevisionUploaded -> comparison -> MaterialSafetyChanged
    #
    # Both replace a WORKING, TESTED direct call, and neither is mechanical.
    # `research.promote_finding` calls `knowledge.ingest_document` and needs
    # the returned document id to store in `findings.promoted_document_id` --
    # and an event that must hand a value back to its emitter is not an event,
    # it is a function call with a registry in front of it. Deciding whether
    # that column stops being written synchronously is a design change, not a
    # rewiring, and it is filed rather than guessed at.
