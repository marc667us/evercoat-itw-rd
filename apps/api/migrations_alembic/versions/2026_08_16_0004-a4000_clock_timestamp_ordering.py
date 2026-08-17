"""row ordering uses clock_timestamp where order carries meaning

Revision ID: a4000
Revises: a3000
Created: 2026-08-16
"""

from __future__ import annotations

from collections.abc import Sequence

from migrations_alembic._sql import apply_sql

revision: str = "a4000"
down_revision: str | None = "a3000"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    apply_sql("004_ordering_uses_clock_timestamp.sql")


def downgrade() -> None:
    """Not implemented.

    Reverting to now() reintroduces non-deterministic ordering of stage
    visits, which mis-links rework history silently rather than erroring.
    """
    raise NotImplementedError("reverting would reintroduce ambiguous stage ordering")
