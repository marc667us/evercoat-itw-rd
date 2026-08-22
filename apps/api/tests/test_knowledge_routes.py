"""The knowledge routes' contract, checked without a database or a server.

These are the properties that would otherwise only be noticed by a user: a
source vocabulary that disagrees with the CHECK constraint behind it, a write
route that forgot its permission, and a route reaching into the agent tier.
"""

from __future__ import annotations

import re
from pathlib import Path

from app.api.knowledge import SOURCES

API_ROOT = Path(__file__).resolve().parents[1]
MIGRATION = API_ROOT / "migrations" / "042_knowledge_retrieval.sql"


def test_the_source_vocabulary_agrees_with_the_check_constraint() -> None:
    """🔴 TWO LITERALS IN TWO FILES CANNOT BE TYPE-CHECKED INTO AGREEMENT.

    `SOURCES` exists so a bad `source` is a 422 naming the alternatives rather
    than a 500 out of `documents_source_check`. That is only true while the two
    lists say the same thing — and nothing in Python or PostgreSQL relates
    them, so the day somebody adds a source to the constraint the API starts
    rejecting a value the database would have accepted.

    This is the recurring root cause on this platform, so it gets an
    instrument rather than a comment asking people to remember.
    """
    sql = MIGRATION.read_text(encoding="utf-8")
    match = re.search(r"source IN \(([^)]*)\)", sql)
    assert match, "documents_source_check is not in 042 in the expected form"

    in_sql = {value.strip().strip("'") for value in match.group(1).split(",")}
    assert in_sql == set(SOURCES), (
        "app/api/knowledge.py SOURCES and migration 042's documents_source_check "
        f"disagree. Only in SQL: {sorted(in_sql - set(SOURCES))}. "
        f"Only in Python: {sorted(set(SOURCES) - in_sql)}."
    )


def test_the_routes_carry_the_permissions_they_should() -> None:
    """Reading is `knowledge.view`; writing is `knowledge.ingest`.

    🔴 THE WRITE ROUTE IS THE ONE THAT MATTERS. Ingestion SETS the
    classification of text MSD will afterwards quote to whoever can retrieve
    it. A POST that had picked up the read permission by copy-paste would let
    the whole `knowledge.view` population — nine of ten seeded roles — decide
    what is CONFIDENTIAL, which is the opposite of migration 043's argument.
    """
    source = (API_ROOT / "app" / "api" / "knowledge.py").read_text(encoding="utf-8")

    # 🔴 EVERY VERB, NOT JUST THE TWO IN USE, AND EACH HANDLER READ ALONE.
    #
    # The first version matched `(get|post)` and used `.*?` under DOTALL, which
    # has two holes the Supervisor named: a `delete` added later would be
    # INVISIBLE to the assertion, and the lazy wildcard binds a decorator to
    # the next `require_permission` ANYWHERE in the file rather than its own --
    # so a handler with no permission at all would silently borrow the next
    # one's and pass.
    #
    # Splitting on the decorator and searching only within each handler's own
    # text makes the pairing structural, and a missing permission shows up as
    # `None` instead of a neighbour's value.
    blocks = re.split(r"@router\.", source)[1:]
    found: dict[tuple[str, str], str | None] = {}
    for block in blocks:
        head = re.match(r'(get|post|put|patch|delete)\("([^"]+)"', block)
        assert head, f"a @router decorator was not in the expected form: {block[:60]!r}"
        # Stop at the next decorator or the end -- never spill into a sibling.
        body = block.split("\n@router.")[0]
        permission = re.search(r'require_permission\("([^"]+)"\)', body)
        found[(head.group(1), head.group(2))] = permission.group(1) if permission else None

    assert found == {
        ("get", "/documents"): "knowledge.view",
        ("post", "/documents"): "knowledge.ingest",
        ("get", "/search"): "knowledge.view",
    }, f"the knowledge routes' permissions changed: {found}"


def test_the_routes_never_import_the_agent_tier() -> None:
    """§0.2: *"API routes never call specialists directly."*

    `tests/test_agent_topology.py` asserts this across every route module, so
    this is a local restatement for the one most likely to be tempted: MSD's
    `search_knowledge` does almost exactly what `GET /search` does, and reusing
    it would be one import away.

    They differ in a way that matters, which is why the duplication is right:
    the tool applies a relevance cut because MSD QUOTES what it gets back, and
    this route does not because a person can judge a weak match themselves.
    """
    source = (API_ROOT / "app" / "api" / "knowledge.py").read_text(encoding="utf-8")
    assert "app.agents" not in source, (
        "app/api/knowledge.py imports the agent tier. The domain service is "
        "the shared layer; the tool is not a library for routes to call."
    )
