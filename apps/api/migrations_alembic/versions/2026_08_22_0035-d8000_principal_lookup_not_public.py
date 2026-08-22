"""the principal lookup is not PUBLIC

Revision ID: d8000
Revises: d7000
Created: 2026-08-22

Fixes a hole introduced by 033 (d6000) and found by comparing it against
migration 024, which it was modelled on.

PostgreSQL grants EXECUTE on a new function to PUBLIC by default. 033 granted
to `evercoat_app` and never revoked from PUBLIC, so a SECURITY DEFINER
function that **bypasses RLS by design** was callable by every role --
including `evercoat_report`, the read-only analytics role. Measured in
`pg_proc.proacl` as a leading `=X/evercoat_owner`.

🔴 A security fix can carry its own hole. 033 closed a total authentication
outage and in the same change opened a privilege-escalation path, because a
DEFAULT was left unstated -- GRANT is visible in a diff, REVOKE FROM PUBLIC is
invisible by absence.

Full reasoning in `migrations/035_the_principal_lookup_is_not_public.sql`.
"""

from __future__ import annotations

from collections.abc import Sequence

from migrations_alembic._sql import apply_sql

revision: str = "d8000"
down_revision: str | None = "d7000"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    apply_sql("035_the_principal_lookup_is_not_public.sql")


def downgrade() -> None:
    from alembic import op

    op.execute("GRANT EXECUTE ON FUNCTION core.principal_for_subject(TEXT, UUID) TO PUBLIC")
