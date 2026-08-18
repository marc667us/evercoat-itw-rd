"""material.approve_production had no holder, so `preferred` was unreachable

Revision ID: b7000
Revises: b6000
Created: 2026-08-18
"""

from __future__ import annotations

from collections.abc import Sequence

from migrations_alembic._sql import apply_sql

revision: str = "b7000"
down_revision: str | None = "b6000"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    apply_sql("016_material_approve_production_has_a_holder.sql")


def downgrade() -> None:
    """Not implemented.

    Reverting restores the exact defect this migration exists to close: a
    permission that no role holds, and therefore a material status that no
    user of the system can ever set. `tests/db/test_002_roles_permissions.py`
    fails the moment that is true again, so a downgrade would leave the
    suite red with no way to explain why except by reading this docstring.
    """
    raise NotImplementedError(
        "revoking this leaves material.approve_production with no holder; "
        "see 016_material_approve_production_has_a_holder.sql"
    )
