"""laboratory batches, weigh-up sheets, process data, deviations and samples

Revision ID: b8000
Revises: b7000
Created: 2026-08-18
"""

from __future__ import annotations

from collections.abc import Sequence

from migrations_alembic._sql import apply_sql

revision: str = "b8000"
down_revision: str | None = "b7000"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    apply_sql("017_laboratory_batches_samples.sql")


def downgrade() -> None:
    """Not implemented.

    A laboratory batch is the record of physical work that was actually
    carried out -- which lot of which material was weighed, by whom, to
    what mass, under what mixing conditions. It is the link that makes a
    test result traceable to a physical sample, which `CLAUDE.md` §5
    requires and which nothing else in the schema can reconstruct.

    Dropping these tables destroys that, and it cannot be partial:
    `laboratory.batches` holds a RESTRICT foreign key onto
    `formulations.formula_versions`, so a downgrade would have to decide
    what happens to a formula whose batches it is about to remove, and
    every answer to that is data loss.
    """
    raise NotImplementedError(
        "a batch records physical work that was done; it is retired by status, "
        "never dropped. See 017_laboratory_batches_samples.sql"
    )
