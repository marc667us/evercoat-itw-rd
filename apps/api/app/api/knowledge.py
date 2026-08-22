"""The knowledge library over HTTP — the write path migration 042 never had.

🔴 THIS MODULE IMPORTS THE DOMAIN SERVICE, NEVER THE AGENT TIER.

§0.2: *"API routes never call specialists directly."* `search_knowledge` in
`app/agents/tools/knowledge.py` is a specialist tool, and importing it here
would be the violation `tests/test_agent_topology.py` fails the build for. Both
this module and that tool call `app.domains.knowledge.service` — which is the
right layering anyway: the tool shapes passages for a language model, and this
route shapes them for a screen, and neither is a wrapper around the other.

🔴 THE PRINCIPAL SUPPLIES THE IDENTITY. THE BODY NEVER DOES.

`organization_id` and `ingested_by` come from the resolved `Principal`. The
body carries a title, a body and a classification; it cannot name an
organization or an author. A body that could would let somebody file a
document into another tenant's library, or attribute their own upload to a
colleague — and `ingested_by` is the only record of who made the
classification decision.

⚠️ WHAT THIS ROUTE DOES *NOT* DO, STATED SO NOBODY ASSUMES IT

It takes TEXT, not a file. There is no upload, no PDF extraction and no
malware scan on this path, because §7's ingestion pipeline (I41) is where
those belong and it is not built. A file upload added here later must go
through that pipeline, not around it — `storage_key` exists on the table for
exactly that day and is deliberately not settable from this body.
"""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.embedding import EmbeddingUnavailableError, build_embedder
from app.core.security import Principal, get_db, require_permission
from app.domains.knowledge.service import ingest_document, list_documents, retrieve

router = APIRouter()

__all__ = ["router"]

# Four sources, matching `documents_source_check` in migration 042. Listed here
# so a bad value is a 422 naming the alternatives rather than a 500 out of a
# CHECK constraint -- and so the two lists are visibly the same list when they
# drift, which is the "two literals in two files" failure this codebase keeps
# finding. `tests/test_knowledge_routes.py` asserts they agree.
SOURCES = ("internal_note", "material_document", "standard", "procedure", "external")

# The search box's page size. Deliberately larger than MSD's four passages: a
# person scanning a result list can evaluate ten, whereas an assistant quoting
# ten in a chat answer produces something nobody checks.
MAX_SEARCH_RESULTS = 10


class DocumentCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    # Bounded, because ingestion embeds every chunk and the per-document chunk
    # cap is enforced in the service on top of this. 200k characters is a long
    # technical procedure; it is not a PDF dump of a standards library.
    body: str = Field(min_length=1, max_length=200_000)
    source: str = Field(default="internal_note")
    project_id: uuid.UUID | None = None
    # 🔴 NO DEFAULT HERE, ON PURPOSE. The service and the column both default to
    # DIRECTOR_CONTROLLED -- the CEILING -- and repeating a default in the
    # request schema is how the ceiling quietly becomes whatever the API layer
    # happens to say. Omitting the field means "I did not decide", which the
    # database answers with the most restrictive value.
    classification: str | None = None


@router.get("/documents", tags=["knowledge"])
def get_documents(
    principal: Principal = Depends(require_permission("knowledge.view")),
    session: Session = Depends(get_db),
) -> list[dict[str, Any]]:
    """The library, as far as this caller is concerned.

    Two people with identical permissions get different lists, because RLS on
    `knowledge.documents` is the boundary and project membership differs. That
    is the intended behaviour, not a caching bug to be reported.
    """
    return list_documents(session, organization_id=principal.organization_id)


@router.post("/documents", status_code=status.HTTP_201_CREATED, tags=["knowledge"])
def post_document(
    payload: DocumentCreate,
    principal: Principal = Depends(require_permission("knowledge.ingest")),
    session: Session = Depends(get_db),
) -> dict[str, Any]:
    """Ingest a document and embed its chunks.

    ⚠️ SYNCHRONOUS, AND THAT IS A DECISION WITH A LIMIT. Embedding runs inline,
    so a long document holds the request open. The lexical default is fast
    enough that this is invisible; the neural embedder ADR-013 names is not,
    and moving ingestion onto the Celery worker is the change to make THEN,
    with a job record the screen can poll -- not a `BackgroundTasks` call that
    would return 201 before anything was stored and report failure to nobody.
    """
    if payload.source not in SOURCES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"source must be one of {', '.join(SOURCES)}",
        )

    try:
        embedder = build_embedder()
    except EmbeddingUnavailableError as exc:
        # 503, not 500: nothing the caller sent is wrong, and a retry after the
        # embedder is installed is the correct next action.
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="no embedder is available, so nothing could be indexed",
        ) from exc

    try:
        result = ingest_document(
            session,
            organization_id=principal.organization_id,
            actor_id=principal.user_id,
            title=payload.title,
            body=payload.body,
            source=payload.source,
            embedder=embedder,
            project_id=payload.project_id,
            # None means "not decided" -- omit the argument entirely so the
            # SERVICE applies the ceiling, rather than restating a default
            # here where it could drift from the one the column declares.
            **(
                {} if payload.classification is None else {"classification": payload.classification}
            ),
        )
    except ValueError as exc:
        # The service raises this for a body with no text and for the chunk cap.
        # Both are the caller's input, so both are 422 rather than a 500.
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc
    except EmbeddingUnavailableError as exc:
        # Reachable even after build_embedder() succeeded: a chunk can tokenize
        # to nothing on its own. Refusing the document is right -- a document
        # half of whose chunks are missing is worse than one that was rejected,
        # because retrieval would quietly never find the missing half.
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"the text could not be embedded: {exc}",
        ) from exc

    session.commit()
    return result


@router.get("/search", tags=["knowledge"])
def get_search(
    q: str = Query(min_length=1, max_length=2000),
    limit: int = Query(default=MAX_SEARCH_RESULTS, ge=1, le=MAX_SEARCH_RESULTS),
    principal: Principal = Depends(require_permission("knowledge.view")),
    session: Session = Depends(get_db),
) -> list[dict[str, Any]]:
    """Passages matching `q`, inside the caller's boundary.

    🔴 NO RELEVANCE CUT HERE, UNLIKE MSD'S TOOL, AND THE DIFFERENCE IS
    DELIBERATE.

    `search_knowledge` drops anything past `MAX_DISTANCE` because MSD QUOTES
    what it gets back as though it were responsive, so a poor match becomes a
    confident wrong answer. This endpoint returns a ranked list to a person who
    can see the distance and judge for themselves — the same reason a search
    engine shows page two. Applying the assistant's cut here would hide results
    a human asked for; omitting it there would put them in an answer.

    ⚠️ Recall is word-overlap unless a neural embedder is installed. See
    `app/core/embedding.py`; the screen must not imply the library "understood"
    the question.
    """
    try:
        embedder = build_embedder()
    except EmbeddingUnavailableError:
        return []

    try:
        passages = retrieve(
            session,
            organization_id=principal.organization_id,
            question=q,
            embedder=embedder,
            limit=limit,
        )
    except EmbeddingUnavailableError:
        # A query with no searchable words in it. "?" is a question the library
        # cannot answer, not an error worth a stack trace.
        return []

    return [
        {
            "content": p["content"],
            "title": p["title"],
            "source": p["source"],
            "document_id": p["document_id"],
            "ordinal": p["ordinal"],
            "classification": p["classification"],
            "distance": float(p["distance"]),
        }
        for p in passages
    ]
