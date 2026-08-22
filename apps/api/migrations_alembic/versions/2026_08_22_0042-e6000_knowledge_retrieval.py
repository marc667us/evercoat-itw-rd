"""knowledge retrieval, with authorization on every chunk

Revision ID: e6000
Revises: e5000
Created: 2026-08-22

Slice 8's foundation and the remaining half of I23.

🔴 EVERY CHUNK CARRIES ITS OWN organization, project and classification, so a
similarity search is filtered by RLS BEFORE it ranks. Deciding authorization
when the DOCUMENT is opened would be too late -- a vector search returns the
CHUNK, its text goes into an answer, and the check that would have refused it
never runs. Nothing about the answer would look wrong.

That is `IMPLEMENTATION_PLAN.md` §E and Codex F33: filter before retrieval,
never after generation.

The three columns are copied from the document by trigger rather than trusted
from the caller -- a chunk less restrictive than its document is I69's defect
applied to the row a retrieval actually returns.

`vector(384)` matches all-MiniLM-L6-v2's width (ADR-013), so the column does
not change when a real sentence-transformer replaces the default embedder.

Full reasoning in `migrations/042_knowledge_retrieval.sql`.
"""

from __future__ import annotations

from collections.abc import Sequence

from migrations_alembic._sql import apply_sql

revision: str = "e6000"
down_revision: str | None = "e5000"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    apply_sql("042_knowledge_retrieval.sql")


def downgrade() -> None:
    from alembic import op

    op.execute("DROP TABLE IF EXISTS knowledge.chunks")
    op.execute("DROP TABLE IF EXISTS knowledge.documents")
    op.execute("DROP FUNCTION IF EXISTS knowledge.chunk_inherits_document()")
    op.execute("DROP FUNCTION IF EXISTS knowledge.document_repropagates_to_chunks()")
    op.execute("DROP SCHEMA IF EXISTS knowledge CASCADE")
