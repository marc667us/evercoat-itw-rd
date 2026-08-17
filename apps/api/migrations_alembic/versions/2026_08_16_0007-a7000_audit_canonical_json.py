"""audit hash chain: canonical JSON matching the Python writer

Revision ID: a7000
Revises: a6000
Created: 2026-08-16
"""

from __future__ import annotations

from collections.abc import Sequence

from migrations_alembic._sql import apply_sql

revision: str = "a7000"
down_revision: str | None = "a6000"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    apply_sql("007_audit_canonical_json.sql")


def downgrade() -> None:
    """Not implemented.

    Reverting restores a canonical form the Python writer cannot
    reproduce, so every audit row carrying a JSON payload would report
    tampering that did not happen.
    """
    raise NotImplementedError("reverting reintroduces false tamper reports")
