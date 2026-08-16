"""seed the permission catalogue and the ten default roles

Revision ID: a2000
Revises: a1000
Created: 2026-08-16
"""

from __future__ import annotations

from collections.abc import Sequence

from migrations_alembic._sql import apply_sql

revision: str = "a2000"
down_revision: str | None = "a1000"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    apply_sql("002_seed_roles_permissions.sql")


def downgrade() -> None:
    """Not implemented.

    Removing roles and permissions would strip authorization from every
    existing membership -- locking every user out of an organization
    that still holds its data. Seed corrections go forward as a new
    revision, never backward.
    """
    raise NotImplementedError(
        "downgrade would revoke all role-permission mappings; roll forward instead"
    )
