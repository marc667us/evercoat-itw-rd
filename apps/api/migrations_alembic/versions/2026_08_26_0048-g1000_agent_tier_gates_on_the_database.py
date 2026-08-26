"""the agent tier gates on what the database says

Revision ID: g1000
Revises: f2000
Created: 2026-08-26

Closes I105.

I104 stopped the orchestrator accepting a permission set as an argument and
made `bind()` check the session's RLS GUCs against the caller. Codex named the
half that left open: `bind()` validates organization and user and never
validates permissions, so a forged principal carrying the real session
identity passes it while claiming arbitrary authorization.

`core.authorization_for_current_session()` derives BOTH the role codes and the
permission codes from the same two GUCs that RLS reads, so the gate and the
rows can no longer disagree about who is asking.

⚠️ BOTH roles and permissions, because roles are not decorative: unclaimed
work is matched with `t.assigned_role = ANY(:roles)` and MSD reaches that
through `msd_conductor`. The first draft derived only permissions — half of
the sentence Codex actually wrote.

⚠️ ADR-029 recorded a SECURITY DEFINER as REJECTED for I82. That rejection was
about a definer that WRITES — the write fires ADR-028's address guards, which
inside a definer run as the table owner and reopen I83's oracle. This function
is STABLE, takes no arguments, and writes nothing, so it has neither the write
that starts that chain nor the parameter that makes a lookup an oracle. Full
reasoning in
`migrations/048_the_agent_tier_gates_on_what_the_database_says.sql`.
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op
from sqlalchemy import text

from migrations_alembic._sql import apply_sql

revision: str = "g1000"
down_revision: str | None = "f2000"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    apply_sql("048_the_agent_tier_gates_on_what_the_database_says.sql")


def downgrade() -> None:
    """Drop the function.

    ⚠️ THE APPLICATION MUST BE ROLLED BACK FIRST, AND THIS FAILS LOUDLY IF IT
    IS NOT. `AgentPrincipal.authorize()` calls this function on every
    agent-tier entry, so a database downgraded under a running f2000+
    application refuses every conductor call rather than quietly granting
    anything. That is the correct direction to fail, and it is why the
    function is dropped rather than replaced by a permissive stub returning
    every permission code.
    """
    op.execute(text("DROP FUNCTION IF EXISTS core.authorization_for_current_session()"))
