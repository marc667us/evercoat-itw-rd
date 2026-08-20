"""an MSD conversation is exactly as private as its thread

Revision ID: c8000
Revises: c7000
Created: 2026-08-20

Migration 022 gave `ai.msd_threads` an owner-scoped policy and said in
its own comment that a thread is visible "to its OWNER and to nobody
else" — then, in the same file, gave `ai.msd_turns` and `ai.msd_evidence`
policies carrying only `organization_id`. The room was private and the
words said in it were readable organization-wide.

`ai.msd_evidence` is the sharper half: it stores a 500-character EXCERPT
of each cited record, so a colleague outside a restricted project could
read extracts of its formulations out of somebody else's evidence rows.
Retrieval was filtered before the model saw anything; the record of what
it saw was not.

This is migration 025's twin, on the two tables immediately below it in
022's own DO-block loop. Found while building the MSD routes.
"""

from __future__ import annotations

from collections.abc import Sequence

from migrations_alembic._sql import apply_sql

revision: str = "c8000"
down_revision: str | None = "c7000"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    apply_sql("026_msd_turns_follow_their_thread.sql")


def downgrade() -> None:
    """Restore 022's organization-only policies, and say what that costs.

    Reversing this **reopens a disclosure**: every member of the
    organization can again read other people's MSD conversations, and the
    record excerpts those conversations cited. Stated rather than
    silently performed. Prefer fixing forward.

    Written out literally rather than built in a loop — Semgrep blocks an
    f-string in `op.execute` (`formatted-sql-query`), and it is right to:
    an identifier cannot be a bind parameter.
    """
    from alembic import op

    op.execute("DROP POLICY IF EXISTS thread_scope ON ai.msd_turns")
    op.execute("DROP POLICY IF EXISTS turn_scope ON ai.msd_evidence")
    op.execute(
        """
        CREATE POLICY org_scope ON ai.msd_turns
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
    op.execute(
        """
        CREATE POLICY org_scope ON ai.msd_evidence
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
    op.execute("DROP FUNCTION IF EXISTS core.can_read_msd_thread(UUID)")
