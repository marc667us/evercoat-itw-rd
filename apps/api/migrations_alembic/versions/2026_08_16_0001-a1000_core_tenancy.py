"""core tenancy: roles, schemas, RLS, composite keys, audit hash chain

Revision ID: a1000
Revises:
Created: 2026-08-16
"""

from __future__ import annotations

from collections.abc import Sequence

from migrations_alembic._sql import apply_sql

revision: str = "a1000"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    apply_sql("001_core_tenancy.sql")


def downgrade() -> None:
    """Deliberately not implemented.

    Downgrading this migration means dropping every schema that holds
    R&D records. There is no circumstance in which that is the right
    automated response to a bad deploy -- the correct recovery is a
    restore from backup, which preserves the data this would destroy.

    A downgrade path here would be a loaded weapon in the deploy
    pipeline, one `alembic downgrade -1` away from deleting the
    formulation history the whole system exists to protect.
    """
    raise NotImplementedError("downgrade would drop all R&D schemas; restore from backup instead")
