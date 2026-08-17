"""opportunities: 'converted' status + one project per opportunity

Revision ID: a8000
Revises: a7000
Created: 2026-08-16
"""

from __future__ import annotations

from collections.abc import Sequence

from migrations_alembic._sql import apply_sql

revision: str = "a8000"
down_revision: str | None = "a7000"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    apply_sql("008_opportunity_converted_status.sql")


def downgrade() -> None:
    """Not implemented.

    The CHECK cannot be narrowed again once any row holds 'converted' --
    the constraint would be rejected by the rows it is meant to govern.
    Dropping the unique index would silently re-permit two projects
    claiming the same opportunity, which is the defect it exists to stop.
    """
    raise NotImplementedError("narrowing the status set would reject existing rows")
