"""a conversation has one order, and it is the order it was written in

Revision ID: d1000
Revises: c9000
Created: 2026-08-21

`messaging.messages.posted_at` defaulted to `now()`, which is
TRANSACTION-START time and therefore identical for every row written in one
transaction. `list_messages` ordered by `posted_at` with no tiebreaker, so a
thread whose messages were written together had no defined order at all and
PostgreSQL could return them differently between runs.

Found because `test_a_withdrawn_message_leaves_the_conversation_readable`
failed against a local PostgreSQL while passing in CI — the two databases
returned the same two rows in a different order. CI had been passing on heap
luck, not on correctness.

The DEFAULT becomes `clock_timestamp()`, which reads the real clock per
INSERT. The matching `ORDER BY m.posted_at, m.id` tiebreaker is in
`app/domains/messaging/service.py`; both are needed, and the SQL file says
why neither alone is sufficient.

Full reasoning in `migrations/028_a_conversation_has_a_stable_order.sql`.
Tracked as TODO I26.
"""

from __future__ import annotations

from collections.abc import Sequence

from migrations_alembic._sql import apply_sql

revision: str = "d1000"
down_revision: str | None = "c9000"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    apply_sql("028_a_conversation_has_a_stable_order.sql")


def downgrade() -> None:
    """Restore the `now()` default, and say what that costs.

    Reversing this returns `messaging.messages` to a state where every
    message written in a single transaction shares one timestamp and a
    conversation has no defined order. The ordering tiebreaker in
    `list_messages` would still make the result REPEATABLE, but repeatably
    in an order that is not the order anyone wrote in. Stated rather than
    silently performed. Prefer fixing forward.
    """
    from alembic import op

    op.execute("ALTER TABLE messaging.messages ALTER COLUMN posted_at SET DEFAULT now()")
