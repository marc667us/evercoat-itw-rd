"""the system audit chain is readable by the session that writes it

Revision ID: d7000
Revises: d6000
Created: 2026-08-22

Third companion to 032 (d5000). Found by RUNNING the suite, not by reading.

`audit.events` supports a legitimate SYSTEM chain (`organization_id IS NULL`)
written by migrations, maintenance scripts and bootstrap. After 032 an
unscoped session evaluated `organization_id = NULL` -> NULL -> not TRUE, so it
could not read the system chain **including the row it had just written**.

🔴 And that breaks the WRITE, because `INSERT ... RETURNING` is a READ -- the
same lesson this platform logged on 2026-08-19.

Fixed with NULL-safe equality: `organization_id IS NOT DISTINCT FROM
core.current_org_id()`. Scoped -> that tenant only; unscoped -> the system
chain only, never every tenant. Strictly tighter than before 032 and correct
where 032 alone was an outage.

Full reasoning in
`migrations/034_the_system_audit_chain_is_readable_by_its_own_writer.sql`.
"""

from __future__ import annotations

from collections.abc import Sequence

from migrations_alembic._sql import apply_sql

revision: str = "d7000"
down_revision: str | None = "d6000"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    apply_sql("034_the_system_audit_chain_is_readable_by_its_own_writer.sql")


def downgrade() -> None:
    from alembic import op

    op.execute("DROP POLICY IF EXISTS audit_org_isolation ON audit.events")
    op.execute(
        "CREATE POLICY audit_org_isolation ON audit.events "
        "USING (core.rls_permissive() AND core.current_org_id() IS NULL "
        "       OR organization_id = core.current_org_id())"
    )
