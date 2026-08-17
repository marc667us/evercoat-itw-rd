"""stage_definitions: deferrable sequence constraint so reorder works

Revision ID: a9000
Revises: a8000
Created: 2026-08-16
"""

from __future__ import annotations

from collections.abc import Sequence

from migrations_alembic._sql import apply_sql

revision: str = "a9000"
down_revision: str | None = "a8000"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    apply_sql("009_stage_sequence_deferrable.sql")


def downgrade() -> None:
    """Not implemented.

    Reverting to a non-deferrable constraint breaks the pipeline reorder
    again -- the exact defect this migration exists to fix, and one that
    only surfaces when an administrator tries to move a stage.
    """
    raise NotImplementedError("a non-deferrable constraint breaks the reorder")
