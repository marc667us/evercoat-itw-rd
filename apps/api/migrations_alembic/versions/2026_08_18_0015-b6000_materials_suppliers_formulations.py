"""materials, suppliers and formulations -- the tables Slice 3's screens had none of

Revision ID: b6000
Revises: b5000
Created: 2026-08-18
"""

from __future__ import annotations

from collections.abc import Sequence

from migrations_alembic._sql import apply_sql

revision: str = "b6000"
down_revision: str | None = "b5000"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    apply_sql("015_materials_suppliers_formulations.sql")


def downgrade() -> None:
    """Not implemented.

    Dropping these tables destroys formulation history, which is the one
    thing this product exists to keep. `CLAUDE.md` is explicit that R&D
    records are retired with a status -- `obsolete`, `archived`,
    `superseded` -- and never deleted; a downgrade that silently drops
    `formula_versions` would violate the rule the migration itself
    enforces with triggers.

    Reverting also cannot be partial. `formulations.formulas` has a
    RESTRICT foreign key onto `projects.projects`, so a downgrade would
    have to decide what happens to a project whose formulas it is about
    to remove, and there is no answer to that which is not data loss.
    """
    raise NotImplementedError(
        "formulation history is retired by status, never dropped; "
        "see 015_materials_suppliers_formulations.sql"
    )
