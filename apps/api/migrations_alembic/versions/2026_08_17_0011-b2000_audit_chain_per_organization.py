"""audit chain: per-organization by construction, not by RLS accident

Revision ID: b2000
Revises: b1000
Created: 2026-08-17
"""

from __future__ import annotations

from collections.abc import Sequence

from migrations_alembic._sql import apply_sql

revision: str = "b2000"
down_revision: str | None = "b1000"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    apply_sql("011_audit_chain_per_organization.sql")


def downgrade() -> None:
    """Not implemented.

    Reverting restores ``WITH CHECK (true)`` on the insert policy, which
    lets any session forge audit rows attributed to another organization,
    and restores a chain whose shape depends on the writer's RLS context.
    Both are the defects this migration closes.

    It would also leave the rows written under the new rule chained by a
    predicate the old trigger does not apply, so the revert itself creates
    the break it claims to undo.
    """
    raise NotImplementedError(
        "reverting re-opens audit forgery and re-introduces context-dependent chaining"
    )
