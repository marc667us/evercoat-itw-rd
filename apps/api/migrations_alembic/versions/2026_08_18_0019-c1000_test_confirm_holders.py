"""test.confirm had no holder; Slice 5 assigns it to Lead, QA and Director

Revision ID: c1000
Revises: b9000
Created: 2026-08-18
"""

from __future__ import annotations

from collections.abc import Sequence

from migrations_alembic._sql import apply_sql

revision: str = "c1000"
down_revision: str | None = "b9000"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    apply_sql("019_test_confirm_has_holders.sql")


def downgrade() -> None:
    """Not implemented.

    Reverting restores an orphaned permission: `test.confirm` held by no
    role, and therefore a `final_confirmed` transition no user of this
    system could ever make. `tests/db/test_002_roles_permissions.py`
    fails the moment that is true again -- and its allowlist entry for
    this permission was removed in the same change, deliberately, so
    there is nowhere for the orphan to hide.
    """
    raise NotImplementedError(
        "revoking this leaves test.confirm with no holder; see 019_test_confirm_has_holders.sql"
    )
