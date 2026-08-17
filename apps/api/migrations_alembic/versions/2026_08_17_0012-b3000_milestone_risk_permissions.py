"""milestone/risk permissions, grants and the invariants their writers need

Revision ID: b3000
Revises: b2000
Created: 2026-08-17
"""

from __future__ import annotations

from collections.abc import Sequence

from migrations_alembic._sql import apply_sql

revision: str = "b3000"
down_revision: str | None = "b2000"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    apply_sql("012_milestone_risk_permissions.sql")


def downgrade() -> None:
    """Not implemented.

    Removing the permissions would orphan the routes that require them:
    every caller would receive 403 with no indication that the cause was a
    migration rather than their role. Dropping the CHECK constraints
    re-admits milestones that are 'met' with no date and risks that are
    'mitigating' with no mitigation, both of which render on a dashboard
    as if they meant something.
    """
    raise NotImplementedError("dropping these permissions 403s every milestone and risk route")
