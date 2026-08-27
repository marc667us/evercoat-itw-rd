"""Knowledge — the department conductor.

§0.2: department conductors live at
`app/agents/conductors/<dept>_conductor.py`, specialists never call other
agents, and API routes never call specialists directly.

Structural, like `laboratory_conductor`: no tools, no model, no reasoning.

🔴 THIS DEPARTMENT ALREADY HAD TWO DOORS, AND THAT IS WHY IT NEEDS THIS ONE.

`app/agents/tools/knowledge.py` shapes passages for a language model and drops
anything past `MAX_DISTANCE`, because MSD QUOTES what it gets back and a poor
match becomes a confident wrong answer. `app/api/knowledge.py` shapes the same
passages for a person, with no relevance cut, because a reader can see the
distance and judge for themselves — the reason a search engine shows page two.

Both are right and neither is a wrapper around the other. What was missing is
that the HUMAN-facing read had no department gate on the agent path: this
conductor is that gate, and it deliberately keeps the route's semantics rather
than the tool's. Applying the assistant's cut here would hide results a person
asked for; omitting it there would put them in an answer.

⚠️ SO DO NOT "UNIFY" THESE TWO. The next reader who notices two retrieval
paths and merges them will pick one cut-off for both, and whichever they pick
is wrong for the other caller. The difference is the design.

🔴 THE SESSION IS THE CALLER'S OWN, AND `authorize()` CHECKS IT. It matters
more here than anywhere: RLS on `knowledge.documents` is the boundary, so two
people with IDENTICAL permissions get different lists because their project
membership differs. A conductor that reached around the caller's session would
return passages the asker cannot open, to an agent that then quoted them — §7's
"filter retrieval before the model sees anything", failed at the last step.

⚠️ READS ONLY (§4, §7). `ingest_document` is not reachable from here.
Promotion of an informal conclusion into controlled knowledge is a human act
by §7's own words, and a door that could ingest would be the channel by which
an assistant's own output became authoritative.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.agents.boundary import require
from app.agents.principal import AgentPrincipal
from app.core.embedding import EmbeddingUnavailableError, build_embedder
from app.domains.knowledge import service as knowledge

__all__ = ["DEPARTMENT", "documents", "search"]

DEPARTMENT = "knowledge"

# Named once rather than repeated per function. Measured on the seeded realm
# 2026-08-27: all ten roles hold it, which makes this the WIDEST department
# gate in the product — and the reason the boundary that actually matters here
# is RLS and project membership rather than the permission.
VIEW = "knowledge.view"

# The screen's page size, matching `app/api/knowledge.py`. Deliberately larger
# than MSD's four passages: a person scanning a result list can evaluate ten,
# whereas an assistant quoting ten in a chat answer produces something nobody
# checks.
MAX_SEARCH_RESULTS = 10


def documents(
    session: Session,
    *,
    caller: AgentPrincipal,
    limit: int = 100,
) -> dict[str, Any]:
    """The library as far as this caller is concerned, and how much of it.

    Returns an object rather than a bare array (I78): `total` and `limit` sit
    beside `documents`, so a caller can say *"showing the most recent 100 of
    247"* instead of silently omitting the rest.
    """
    caller = caller.authorize(session)
    require(caller, department=DEPARTMENT, permission=VIEW)
    return knowledge.list_documents(
        session,
        organization_id=caller.organization_id,
        limit=limit,
    )


def search(
    session: Session,
    *,
    caller: AgentPrincipal,
    question: str,
    limit: int = MAX_SEARCH_RESULTS,
) -> list[dict[str, Any]]:
    """Passages matching `question`, ranked, with NO relevance cut.

    ⚠️ AN UNANSWERABLE QUERY IS AN EMPTY LIST, NOT AN ERROR. `"?"` has no
    searchable words in it; `build_embedder()` falls back rather than raising,
    and `EmbeddingUnavailableError` here means the question itself carried
    nothing to match on. That is a question the library cannot answer, not a
    fault worth a stack trace.

    ⚠️ RECALL IS WORD-OVERLAP UNLESS A NEURAL EMBEDDER IS INSTALLED (I76/I77).
    Nothing here may imply the library "understood" the question, and the
    calibrated `MAX_DISTANCE` that guards MSD's quoting is not applied on this
    path at all — see the module docstring for why that asymmetry is deliberate.
    """
    caller = caller.authorize(session)
    require(caller, department=DEPARTMENT, permission=VIEW)

    embedder = build_embedder()
    try:
        return knowledge.retrieve(
            session,
            organization_id=caller.organization_id,
            question=question,
            embedder=embedder,
            limit=limit,
        )
    except EmbeddingUnavailableError:
        return []
