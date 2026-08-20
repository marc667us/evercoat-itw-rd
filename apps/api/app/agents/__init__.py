"""The agent tier.

🔴 §0.2 — ORCHESTRATION FIRST, AND IT IS A STRUCTURE, NOT A STYLE.

Root `CLAUDE.md` §0.2 applies in full to this project even though ADR-002
waives §0.1's ADK requirement in favour of LangGraph:

    Root Orchestrator at app/agents/orchestrators/root_orchestrator.py
    Department Conductors at app/agents/conductors/<dept>_conductor.py
    Specialists never call other agents.
    API routes never call specialists directly.
    MSD is reached through the orchestrator.

So the only thing `app/api/msd.py` imports from this package is
`answer_question` on the root orchestrator. That is enforced by a test
(`tests/test_agent_topology.py`) rather than by convention, because a
convention is what the next person breaks at 2am.

🔴 THE FRAMEWORK IS NOT HERE YET, AND ITS ABSENCE IS DELIBERATE.

ADR-002 selects LangGraph, and `CLAUDE.md` §4 confines it to
`app/agents/graphs/`. There is no `graphs/` directory: MVP-1's MSD is
**structured tool-calls** (ADR-013/X9), because eight of the nine
mandated first-MSD capabilities need no RAG and no autonomous planning.
Adding a graph now would mean importing an orchestration framework to
run a `match` statement.

Everything in `tools/` is plain Python with typed signatures, callable
and testable with no framework imported. When a graph does arrive it
calls these same functions.
"""
