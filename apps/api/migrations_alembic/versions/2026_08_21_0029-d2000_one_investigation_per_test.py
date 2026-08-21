"""one investigation per test, and an index for the conversation order

Revision ID: d2000
Revises: d1000
Created: 2026-08-21

Two findings from the Supervisor's review of the §10 wiring and migration 028.

1. `open_failure_for_failed_test` documented "opens OR LINKS" but nothing
   enforced it, and `POST /api/failures` accepts an arbitrary `test_id`. Two
   investigations naming one test made the link lookup raise
   `MultipleResultsFound`, which nothing catches — so that test could never be
   completed again. A permanent lockout on a safety-critical path. A partial
   unique index makes the documented invariant true.

2. 028's `id` tiebreaker made the sort total and unservable by 022's
   `(channel_id, posted_at DESC)` index, because `id` is not in it. Every
   channel read became a full sort. A matching index restores the fast path.

Full reasoning in
`migrations/029_one_investigation_per_test_and_an_index_for_the_thread.sql`.
Tracked as TODO I30 and I31.
"""

from __future__ import annotations

from collections.abc import Sequence

from migrations_alembic._sql import apply_sql

revision: str = "d2000"
down_revision: str | None = "d1000"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    apply_sql("029_one_investigation_per_test_and_an_index_for_the_thread.sql")


def downgrade() -> None:
    """Drop both indexes, and say what the first one costs.

    Reversing part 1 re-opens the permanent-lockout path: two investigations
    may again name one test. The service code survives it — it uses `LIMIT 1`
    rather than `.one_or_none()` and does not depend on this index — but the
    "opens OR LINKS" invariant goes back to being a comment. Stated rather
    than silently performed.

    Part 2 is a pure performance index and reversing it costs only speed.
    """
    from alembic import op

    op.execute("DROP INDEX IF EXISTS messaging.messages_channel_posted_id_idx")
    op.execute("DROP INDEX IF EXISTS quality.failures_one_per_test_uk")
