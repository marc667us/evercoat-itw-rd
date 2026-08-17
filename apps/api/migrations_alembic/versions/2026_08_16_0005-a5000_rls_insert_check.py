"""separate RLS read predicate from write check

Revision ID: a5000
Revises: a4000
Created: 2026-08-16
"""

from __future__ import annotations

from collections.abc import Sequence

from migrations_alembic._sql import apply_sql

revision: str = "a5000"
down_revision: str | None = "a4000"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    apply_sql("005_rls_insert_check.sql")


def downgrade() -> None:
    """Not implemented — reverting makes restricted projects uncreatable."""
    raise NotImplementedError("reverting would restore the INSERT chicken-and-egg")
