"""a new formula version is evaluated for safety

Revision ID: y1000
Revises: x1000
Created: 2026-09-01

§22's first chain. 063 shipped `FormulaVersionCreated` and `revise_version`
has announced it ever since — and nothing has ever consumed it. An event with
no reader reads as integration and is not one.

🔴 THE PROBE ASSERTS THE CONSTRAINT'S CONTENTS, NOT THAT THE ALTER RAN.
`DROP CONSTRAINT IF EXISTS` followed by `ADD CONSTRAINT` succeeds against a
table whose old constraint was already missing, and a CHECK that lost a value
surfaces as an insert failing at runtime rather than as a migration error. So
this reads the constraint definition back and asserts every name is in it —
including the three that were there before, because dropping one while adding
another is exactly the shape this would otherwise miss.
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op
from sqlalchemy import text

from migrations_alembic._sql import apply_sql

revision: str = "y1000"
down_revision: str | None = "x1000"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

EXPECTED = (
    "FormulaVersionCreated",
    "TestResultFinalized",
    "ResearchInvestigationUpdatedByTestResult",
    "SafetyReviewRequired",
)


def upgrade() -> None:
    apply_sql("066_a_new_formula_version_is_evaluated_for_safety.sql")

    bind = op.get_bind()

    definition = bind.execute(
        text(
            "SELECT pg_get_constraintdef(oid) FROM pg_constraint "
            " WHERE conrelid = 'workflow.domain_events'::regclass "
            "   AND conname = 'domain_events_type_check'"
        )
    ).scalar_one_or_none()

    if definition is None:
        raise RuntimeError(
            "domain_events_type_check is gone. The DROP ran and the ADD did not, "
            "which leaves the event vocabulary open — any string could be "
            "announced and no consumer would ever match it."
        )

    for name in EXPECTED:
        if name not in definition:
            raise RuntimeError(
                f"{name!r} is not in domain_events_type_check: {definition}. "
                "Recreating this constraint must never lose a value that "
                "already has an emitter."
            )


def downgrade() -> None:
    # Back to 063's three. Safe only because the reaction that emits the fourth
    # is removed in the same downgrade path — a row already carrying
    # 'SafetyReviewRequired' would make this ALTER fail, loudly, which is the
    # correct outcome rather than a silent data loss.
    op.execute(
        "ALTER TABLE workflow.domain_events DROP CONSTRAINT IF EXISTS domain_events_type_check"
    )
    op.execute(
        "ALTER TABLE workflow.domain_events "
        "ADD CONSTRAINT domain_events_type_check CHECK (event_type IN ("
        "'FormulaVersionCreated','TestResultFinalized',"
        "'ResearchInvestigationUpdatedByTestResult'))"
    )
