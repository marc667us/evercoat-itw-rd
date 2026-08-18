"""test methods, equipment, calibration, tests, raw replicates and decisions

Revision ID: b9000
Revises: b8000
Created: 2026-08-18
"""

from __future__ import annotations

from collections.abc import Sequence

from migrations_alembic._sql import apply_sql

revision: str = "b9000"
down_revision: str | None = "b8000"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    apply_sql("018_testing_methods_tests_replicates.sql")


def downgrade() -> None:
    """Not implemented.

    `testing.test_replicates` holds RAW MEASUREMENTS -- the physical
    evidence every approval, release and qualification in this product is
    ultimately founded on. The schema goes to some length to make them
    unrewritable (excluded with a reason, never deleted or edited), and a
    downgrade that dropped the table would do in one statement what every
    trigger here exists to prevent.

    `testing.test_decisions` is append-only for the same reason: §9
    requires every approval to write an electronic decision record into
    permanent audit history, and permanent means it does not have a
    downgrade path.
    """
    raise NotImplementedError(
        "raw measurements and decision records are permanent evidence; "
        "see 018_testing_methods_tests_replicates.sql"
    )
