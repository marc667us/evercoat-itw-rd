"""audit insert policy fail-closed; definer search_path hardened

Revision ID: b4000
Revises: b3000
Created: 2026-08-17
"""

from __future__ import annotations

from collections.abc import Sequence

from migrations_alembic._sql import apply_sql

revision: str = "b4000"
down_revision: str | None = "b3000"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    apply_sql("013_audit_policy_and_definer_hardening.sql")


def downgrade() -> None:
    """Not implemented.

    Reverting re-opens two holes: any scoped tenant session could append
    to the platform's system audit chain, and any accidentally unscoped
    connection would again be trusted to write rows attributed to every
    organization.
    """
    raise NotImplementedError("reverting re-opens audit forgery paths closed by 013")
