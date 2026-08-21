"""controlled authority has a ladder, and every refusal states why

Revision ID: d4000
Revises: d3000
Created: 2026-08-21

Two findings from the Supervisor's review of I5.

1. `testing.tests.authority_level` permits SIX values; migration 020 seeded
   FIVE templates and none claims `controlled`. Harmless until I5 wired
   approvals to the engine — after which completing review on a `controlled`
   test raised "no active approval template is configured", rolled the review
   back, and left the test permanently stuck at `awaiting_review`. The ladder
   is not invented: the code I5 deleted mapped `controlled` to
   `test.approve_lead`, so CONTROLLED_OVERSIGHT says that as two mandatory
   rungs.

2. `approval_route_steps_refusals_state_why` omitted
   `request_additional_test`, which is equally non-advancing — it leaves a
   permanent decision on a mandatory rung, so the route can never complete,
   and without a rationale the record says nothing about why.

Full reasoning in `migrations/031_controlled_authority_has_a_ladder.sql`.
Tracked as TODO I37 and I38.
"""

from __future__ import annotations

from collections.abc import Sequence

from migrations_alembic._sql import apply_sql

revision: str = "d4000"
down_revision: str | None = "d3000"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    apply_sql("031_controlled_authority_has_a_ladder.sql")


def downgrade() -> None:
    """Restore the narrower CHECK; LEAVE the CONTROLLED_OVERSIGHT templates.

    Reversing part 2 lets `request_additional_test` be recorded with no
    rationale again — an unexplained dead end on a mandatory rung.

    Part 1 is deliberately NOT reversed. The templates are ordinary
    configuration an administrator may have customised, and removing them
    would restore the state where a `controlled` test cannot be reviewed at
    all. A downgrade that re-breaks a level is worse than the change it
    reverts.
    """
    from alembic import op

    op.execute(
        "ALTER TABLE workflow.approval_route_steps "
        "DROP CONSTRAINT IF EXISTS approval_route_steps_refusals_state_why"
    )
    op.execute(
        """
        ALTER TABLE workflow.approval_route_steps
            ADD CONSTRAINT approval_route_steps_refusals_state_why CHECK (
                decision IS NULL
                OR decision NOT IN ('return_for_correction', 'reject',
                                    'request_retest', 'escalate')
                OR rationale IS NOT NULL
            )
        """
    )
