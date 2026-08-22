"""The RAG boundary. Slice 8, closing I23, and the property is one sentence.

🔴 A SIMILARITY SEARCH MUST NEVER RANK A PASSAGE ITS CALLER MAY NOT READ.

§7: *filter retrieval before the model sees anything -- never filter after
generation*. The fixture below is built so that the forbidden chunk is the
BEST match -- identical text, same search term -- because a test where the
restricted passage happened to rank poorly would pass while proving nothing.

Every assertion here is checked in both directions: that the boundary excludes
what it must, AND that the search returns something when it is allowed to. An
empty knowledge base satisfies "no leak" perfectly and is worthless as evidence.
"""

from __future__ import annotations

import uuid
from collections.abc import Iterator
from typing import Any

import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.agents.tools.knowledge import search_knowledge
from app.core.embedding import DIMENSIONS, EmbeddingUnavailableError, HashingEmbedding
from app.domains.knowledge.service import chunk_text, ingest_document, retrieve


def _scope(session: Session, org: uuid.UUID, user: uuid.UUID) -> None:
    session.execute(text("SELECT set_config('app.current_org', :o, true)"), {"o": str(org)})
    session.execute(text("SELECT set_config('app.current_user_id', :u, true)"), {"u": str(user)})


@pytest.fixture
def two_libraries(owner_session: Session, app_session: Session) -> Iterator[dict[str, Any]]:
    """One organization, two projects, and THE SAME TEXT ingested into both.

    🔴 THE SAME TEXT IS THE POINT. If the restricted document said something
    different, a search could miss it for reasons that have nothing to do with
    authorization, and this file would be measuring its own search terms.
    """
    suffix = uuid.uuid4().hex[:8]
    term = f"tricalcium{suffix}"
    body = (
        f"The {term} filler system requires a post-cure of 40 minutes at 60 C.\n\n"
        f"Sanding {term} below full cure causes surface porosity."
    )

    org = owner_session.execute(
        text("INSERT INTO core.organizations (code, name) VALUES (:c, :n) RETURNING id"),
        {"c": f"KNW-{suffix}", "n": "Knowledge Boundary Org"},
    ).scalar_one()
    outsider = owner_session.execute(
        text(
            "INSERT INTO core.users (keycloak_sub, email, display_name) "
            "VALUES (:s, :e, 'Outsider') RETURNING id"
        ),
        {"s": str(uuid.uuid4()), "e": f"knw-{suffix}@example.test"},
    ).scalar_one()
    owner_session.execute(
        text(
            "INSERT INTO core.organization_members (organization_id, user_id, status) "
            "VALUES (:o, :u, 'active')"
        ),
        {"o": org, "u": outsider},
    )

    ids: dict[str, Any] = {"org": org, "outsider": outsider, "term": term, "body": body}
    embedder = HashingEmbedding()

    for label, confidentiality in (("normal", "normal"), ("restricted", "restricted")):
        project = owner_session.execute(
            text(
                "INSERT INTO projects.projects "
                "(organization_id, project_code, name, confidentiality) "
                "VALUES (:o, :c, :n, :conf) RETURNING id"
            ),
            {
                "o": org,
                "c": f"RDP-{label[:1].upper()}-{suffix}",
                "n": f"{label} project",
                "conf": confidentiality,
            },
        ).scalar_one()
        _scope(owner_session, org, outsider)
        result = ingest_document(
            owner_session,
            organization_id=org,
            actor_id=outsider,
            title=f"{label} cure guidance {suffix}",
            body=body,
            source="procedure",
            embedder=embedder,
            project_id=project,
            classification="CONFIDENTIAL" if label == "restricted" else "INTERNAL",
        )
        ids[f"{label}_project"] = project
        ids[f"{label}_document"] = result["document_id"]

    owner_session.commit()
    yield ids

    app_session.rollback()
    # `rollback()`, never `begin()`. Tests that leave work uncommitted on
    # `owner_session` still hold an open transaction, and `begin()` raises
    # "a transaction is already begun" -- which surfaces as a teardown ERROR
    # on a test whose own assertions all passed. SQLAlchemy autobegins on the
    # next statement, so nothing needs to open one explicitly.
    owner_session.rollback()
    owner_session.execute(
        text("DELETE FROM knowledge.chunks WHERE organization_id = :o"), {"o": org}
    )
    owner_session.execute(
        text("DELETE FROM knowledge.documents WHERE organization_id = :o"), {"o": org}
    )
    owner_session.execute(
        text("DELETE FROM projects.project_members WHERE organization_id = :o"), {"o": org}
    )
    owner_session.execute(
        text("DELETE FROM projects.projects WHERE organization_id = :o"), {"o": org}
    )
    owner_session.execute(
        text("DELETE FROM core.organization_members WHERE organization_id = :o"), {"o": org}
    )
    owner_session.execute(text("DELETE FROM core.users WHERE id = :u"), {"u": outsider})
    owner_session.execute(text("DELETE FROM core.organizations WHERE id = :o"), {"o": org})
    owner_session.commit()


def test_a_restricted_passage_is_never_ranked(
    app_session: Session, two_libraries: dict[str, Any]
) -> None:
    """🔴 THE TEST THIS FILE EXISTS FOR.

    Two documents hold IDENTICAL text. One is in a project the asker can see
    (normal confidentiality), one in a restricted project they are not a member
    of. The restricted chunk is exactly as good a match as the permitted one.

    It must not come back -- and not because this code dropped it, but because
    PostgreSQL never ranked it.
    """
    fx = two_libraries
    _scope(app_session, fx["org"], fx["outsider"])

    found = retrieve(
        app_session,
        organization_id=fx["org"],
        question=f"post cure time for {fx['term']}",
        embedder=HashingEmbedding(),
        limit=10,
    )
    documents = {r["document_id"] for r in found}

    assert fx["normal_document"] in documents, (
        "the search returned nothing from the project the asker CAN see, so this "
        "file's central assertion would pass against an empty table and prove nothing"
    )
    assert fx["restricted_document"] not in documents, (
        "a passage from a restricted project the asker is not a member of was "
        "retrieved. MSD is a permission-bypass channel and §7 is violated at its "
        "most important point."
    )


def test_the_restricted_passage_really_is_there_and_really_does_match(
    owner_session: Session, two_libraries: dict[str, Any]
) -> None:
    """🔴 FALSIFICATION. Without this, the test above is unfalsifiable.

    An empty `knowledge.chunks`, a broken embedder, or a query that matched
    nothing would ALL make the previous test pass. So: as the owner, with the
    boundary lifted, the restricted chunk must be present AND must rank for
    the same question. Only then does its absence above mean the boundary.
    """
    fx = two_libraries
    _scope(owner_session, fx["org"], fx["outsider"])

    found = retrieve(
        owner_session,
        organization_id=fx["org"],
        question=f"post cure time for {fx['term']}",
        embedder=HashingEmbedding(),
        limit=10,
    )
    documents = {r["document_id"] for r in found}

    assert fx["restricted_document"] in documents, (
        "the restricted passage does not rank for this question even with the "
        "boundary lifted, so the previous test's silence was never evidence"
    )


def test_membership_opens_the_boundary(
    owner_session: Session, app_session: Session, two_libraries: dict[str, Any]
) -> None:
    """The boundary is membership, not a permanent blocklist.

    Checked because a retrieval that returned nothing to anyone would satisfy
    every leak assertion in this file.
    """
    fx = two_libraries
    owner_session.execute(
        text(
            "INSERT INTO projects.project_members "
            "(organization_id, project_id, user_id, project_role) "
            "VALUES (:o, :p, :u, 'chemist')"
        ),
        {"o": fx["org"], "p": fx["restricted_project"], "u": fx["outsider"]},
    )
    owner_session.commit()

    _scope(app_session, fx["org"], fx["outsider"])
    found = retrieve(
        app_session,
        organization_id=fx["org"],
        question=f"post cure time for {fx['term']}",
        embedder=HashingEmbedding(),
        limit=10,
    )
    assert fx["restricted_document"] in {r["document_id"] for r in found}


def test_a_chunk_cannot_be_less_restricted_than_its_document(
    owner_session: Session, two_libraries: dict[str, Any]
) -> None:
    """Migration 042's trigger, tested where it can regress.

    The chunk is the row a retrieval RETURNS. A chunk claiming a weaker
    classification than its document would be the disclosure itself.
    """
    fx = two_libraries
    _scope(owner_session, fx["org"], fx["outsider"])
    owner_session.execute(
        text(
            "INSERT INTO knowledge.chunks "
            "(organization_id, document_id, project_id, classification, ordinal, "
            " content, embedder_name) "
            "VALUES (:o, :d, NULL, 'PUBLIC', 99, 'forged', 'probe')"
        ),
        {"o": fx["org"], "d": fx["restricted_document"]},
    )
    owner_session.flush()

    row = (
        owner_session.execute(
            text(
                "SELECT classification, project_id FROM knowledge.chunks "
                "WHERE document_id = :d AND ordinal = 99"
            ),
            {"d": fx["restricted_document"]},
        )
        .mappings()
        .one()
    )

    assert row["classification"] == "CONFIDENTIAL", (
        "a chunk kept a classification weaker than its document's"
    )
    assert row["project_id"] == fx["restricted_project"], (
        "a chunk claimed NULL project -- organization-wide visibility -- under a "
        "document scoped to a restricted project"
    )
    owner_session.rollback()


def test_a_chunk_embedded_by_another_embedder_is_not_compared(
    owner_session: Session, two_libraries: dict[str, Any]
) -> None:
    """Vectors from two embedders are not comparable, and the mixing is silent.

    Cosine distance between them is still a number and the rows still come
    back ranked. The `embedder_name` filter makes the stale chunks INVISIBLE
    rather than wrong -- a recall gap someone notices, not a ranking nobody
    can question.
    """

    class _Other(HashingEmbedding):
        name = "another-embedder"

    fx = two_libraries
    _scope(owner_session, fx["org"], fx["outsider"])
    found = retrieve(
        owner_session,
        organization_id=fx["org"],
        question=f"post cure time for {fx['term']}",
        embedder=_Other(),
        limit=10,
    )
    assert found == [], (
        "chunks written by one embedder were ranked against another embedder's "
        "query vector; the comparison is meaningless and nothing said so"
    )


def test_the_tool_returns_passages_and_the_caller_sees_the_boundary(
    app_session: Session, two_libraries: dict[str, Any]
) -> None:
    """The tool wrapper honours the same boundary as the service."""
    fx = two_libraries
    _scope(app_session, fx["org"], fx["outsider"])
    passages = search_knowledge(
        app_session, organization_id=fx["org"], question=f"post cure {fx['term']}"
    )
    assert passages, "the tool returned nothing where the service returns rows"
    assert all(p["document_id"] != fx["restricted_document"] for p in passages)
    # Attribution is not optional -- §7 requires evidence links on every answer.
    assert all(p["title"] and p["source"] for p in passages)


def test_a_question_with_no_words_is_not_an_error(
    app_session: Session, two_libraries: dict[str, Any]
) -> None:
    """A bare '???' is a question the base cannot answer, not a stack trace."""
    fx = two_libraries
    _scope(app_session, fx["org"], fx["outsider"])
    assert search_knowledge(app_session, organization_id=fx["org"], question="???") == []


def test_the_chunk_cap_is_enforced_not_documented(
    owner_session: Session, two_libraries: dict[str, Any]
) -> None:
    """Y4's storage budget refuses rather than warns."""
    fx = two_libraries
    _scope(owner_session, fx["org"], fx["outsider"])
    # Each paragraph alone exceeds TARGET_CHUNK_CHARS, so packing cannot merge
    # them: 250 paragraphs is 250 chunks. The first version of this test used
    # SHORT paragraphs, which packed to ~16 chunks and never reached the cap --
    # a test that could not fail, caught by running it.
    huge = "\n\n".join(f"paragraph {n} about coatings " + ("filler " * 120) for n in range(250))
    with pytest.raises(ValueError, match="exceeds"):
        ingest_document(
            owner_session,
            organization_id=fx["org"],
            actor_id=fx["outsider"],
            title="too big",
            body=huge,
            source="external",
            embedder=HashingEmbedding(),
        )
    owner_session.rollback()


def test_the_embedding_is_deterministic_across_processes() -> None:
    """A vector written today must match a query embedded tomorrow.

    Python's `hash()` is salted per interpreter, so a hashing vectoriser built
    on it works perfectly until the server restarts and then silently stops
    matching. `hashlib` is the fix and this is the guard.
    """
    import subprocess
    import sys

    here = HashingEmbedding().embed("thixotropic polyester filler")
    out = subprocess.run(
        [
            sys.executable,
            "-c",
            "from app.core.embedding import HashingEmbedding;"
            "print(HashingEmbedding().embed('thixotropic polyester filler')[:8])",
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    assert str(here[:8]) == out.stdout.strip(), (
        "the same text embedded in another process produced a different vector; "
        "every stored vector would stop matching after a restart, with no error"
    )


def test_the_vector_width_matches_the_column() -> None:
    """384 in two places. A mismatch is a runtime error on every insert."""
    assert len(HashingEmbedding().embed("adhesion")) == DIMENSIONS


def test_empty_text_refuses_rather_than_returning_a_zero_vector() -> None:
    """A zero vector is equidistant from everything.

    It would return whatever the index ordered first: confident, arbitrary,
    and indistinguishable from a working search.
    """
    with pytest.raises(EmbeddingUnavailableError):
        HashingEmbedding().embed("   ")


def test_chunking_keeps_paragraphs_whole() -> None:
    """A half-sentence retrieved as evidence reads as a misquotation."""
    body = "\n\n".join(["First paragraph.", "Second paragraph.", "Third paragraph."])
    assert chunk_text(body, target=20) == [
        "First paragraph.",
        "Second paragraph.",
        "Third paragraph.",
    ]
