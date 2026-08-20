"""a message is exactly as private as the channel it was posted in

Revision ID: c7000
Revises: c6000
Created: 2026-08-20

Migration 022 gave `messaging.channels` a policy carrying the PROJECT
predicate and gave `messaging.messages` — in the same file, in a
DO-block loop over six tables — a policy carrying only
`organization_id`. The words were therefore less protected than the room
they were said in: any authenticated member of the organization holding
a channel id could read a restricted project's channel, and any org
member could read a direct message between two other people.

`core.can_read_channel(UUID)` is the missing predicate, and it is
SECURITY INVOKER on purpose — as DEFINER it would see every channel
regardless of the project predicate and return TRUE for exactly the rows
it exists to refuse.

Full reasoning in `migrations/025_message_visibility_follows_its_channel.sql`.
The application-layer half of the same fix is in
`app/domains/messaging/service.py`; this is the independent database
layer `SECURITY.md` §1 requires.

Found during the 2026-08-20 API security audit.
"""

from __future__ import annotations

from collections.abc import Sequence

from migrations_alembic._sql import apply_sql

revision: str = "c7000"
down_revision: str | None = "c6000"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    apply_sql("025_message_visibility_follows_its_channel.sql")


def downgrade() -> None:
    """Restore 022's organization-only policies, and say what that costs.

    Reversible, unlike most migrations here: it creates no table and
    stores no data. But reversing it **reopens a confidentiality
    defect** — restricted-project conversations and other people's direct
    messages become readable by any member of the organization again.

    That is stated rather than silently performed, so a downgrade is a
    decision. If the intent is only to unblock a deployment, prefer
    fixing forward.
    """
    from alembic import op

    op.execute("DROP TRIGGER IF EXISTS channels_keep_their_scope ON messaging.channels")
    op.execute("DROP FUNCTION IF EXISTS messaging.deny_channel_retyping()")

    for table in (
        "messaging.messages",
        "messaging.message_links",
        "messaging.channel_members",
    ):
        op.execute(f"DROP POLICY IF EXISTS channel_scope ON {table}")
        op.execute(f"DROP POLICY IF EXISTS parent_message_scope ON {table}")
        op.execute(
            f"""
            CREATE POLICY org_scope ON {table}
            USING (
                core.rls_permissive() AND core.current_org_id() IS NULL
                OR organization_id = core.current_org_id()
            )
            WITH CHECK (
                core.rls_permissive() AND core.current_org_id() IS NULL
                OR organization_id = core.current_org_id()
            )
            """
        )
    # After the policies, never before: `channel_members.channel_scope`
    # references this function, and dropping it first would fail.
    op.execute("DROP FUNCTION IF EXISTS core.can_read_channel(UUID)")
