"""one shared approval engine: templates, snapshotted routes, parallel steps

Revision ID: c2000
Revises: c1000
Created: 2026-08-18
"""

from __future__ import annotations

from collections.abc import Sequence

from migrations_alembic._sql import apply_sql

revision: str = "c2000"
down_revision: str | None = "c1000"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    apply_sql("020_approval_engine.sql")


def downgrade() -> None:
    """Not implemented.

    `workflow.approval_route_steps` holds decisions, and §9 requires
    every approval to write an electronic decision record into PERMANENT
    audit history. A decided step is a signature; the schema goes to
    length to make one unchangeable, and a downgrade would delete every
    signature in the system in a single statement.

    The route snapshot is equally unrecoverable: it records the approval
    route as it stood WHEN THE DECISIONS WERE TAKEN, which the template
    it came from can no longer answer once edited.
    """
    raise NotImplementedError(
        "approval decisions are permanent signatures; see 020_approval_engine.sql"
    )
