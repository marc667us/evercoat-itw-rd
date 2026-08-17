"""stage_transitions: composite tenant FK on from_stage_id

Revision ID: b1000
Revises: a9000
Created: 2026-08-16
"""

from __future__ import annotations

from collections.abc import Sequence

from migrations_alembic._sql import apply_sql

revision: str = "b1000"
down_revision: str | None = "a9000"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    apply_sql("010_stage_transition_from_fk.sql")


def downgrade() -> None:
    """Not implemented.

    Dropping the constraint re-opens a cross-tenant reference hole that
    nothing in the application would detect.
    """
    raise NotImplementedError("dropping this FK re-opens a cross-tenant hole")
