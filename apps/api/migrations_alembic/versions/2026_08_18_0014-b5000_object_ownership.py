"""tables and sequences owned by evercoat_owner, as ADR-017 always claimed

Revision ID: b5000
Revises: b4000
Created: 2026-08-18
"""

from __future__ import annotations

from collections.abc import Sequence

from migrations_alembic._sql import apply_sql

revision: str = "b5000"
down_revision: str | None = "b4000"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    apply_sql("014_object_ownership.sql")


def downgrade() -> None:
    """Not implemented.

    There is nothing to revert to. Ownership was never decided by a
    migration: the developer database had been repaired by hand and CI
    repaired a different subset in its workflow file, so "the previous
    state" is a different value on every database this has ever run
    against. A downgrade would have to pick one of them and would be
    guessing.

    Reverting would also hand the schema back to whichever superuser
    happened to run alembic, which is the condition this migration exists
    to end.
    """
    raise NotImplementedError(
        "ownership had no single prior state to restore; see 014_object_ownership.sql"
    )
