"""the named project lead can always see their own project

Revision ID: a6000
Revises: a5000
Created: 2026-08-16
"""

from __future__ import annotations

from collections.abc import Sequence

from migrations_alembic._sql import apply_sql

revision: str = "a6000"
down_revision: str | None = "a5000"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    apply_sql("006_project_lead_can_see_own_project.sql")


def downgrade() -> None:
    """Not implemented — reverting makes restricted-project creation 500."""
    raise NotImplementedError("reverting would break RETURNING on restricted projects")
