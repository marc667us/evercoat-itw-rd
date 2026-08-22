"""the database fails closed when no tenant context is set

Revision ID: d5000
Revises: d4000
Created: 2026-08-22

Closes I19. `core.rls_permissive()` was `SELECT TRUE`, and every RLS policy in
this database is written `USING (core.rls_permissive() AND
core.current_org_id() IS NULL OR <real predicate>)` -- so with no tenant GUC
set, the left branch admitted every row.

Measured as `evercoat_app` with no GUC before this migration: **119
organizations, 137 projects**. The entire database, every tenant. The only
thing preventing a cross-tenant read was `session_scope()` raising in Python,
which makes `SECURITY.md` §1's "any one layer failing must not expose data"
false as written.

🔴 This does NOT enable `FORCE ROW LEVEL SECURITY`, deliberately. Every table
is owned by `evercoat_owner` and 0 tables are FORCEd, so the owner stays
exempt -- which is what keeps migrations, the seeder, and above all
`core.memberships_for_subject` working. That function is SECURITY DEFINER,
owned by `evercoat_owner`, and runs BEFORE a tenant is chosen because it is
what tells a signed-in browser which organizations exist for it. Forcing RLS
in the same change would return zero rows there and take sign-in down for
every user -- exactly as `tests/db/test_024_memberships_for_subject.py`
predicted in a tripwire written for this moment.

Full reasoning in `migrations/032_the_database_fails_closed.sql`.
"""

from __future__ import annotations

from collections.abc import Sequence

from migrations_alembic._sql import apply_sql

revision: str = "d5000"
down_revision: str | None = "d4000"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    apply_sql("032_the_database_fails_closed.sql")


def downgrade() -> None:
    """Reopen the escape hatch.

    Present because a downgrade path that does not exist is a downgrade path
    that gets improvised under pressure. Running this restores the state in
    which the runtime role reads every tenant's rows whenever tenant context
    is absent -- it is an emergency lever, not a rollback of a feature.
    """
    from alembic import op

    op.execute(
        "CREATE OR REPLACE FUNCTION core.rls_permissive() RETURNS BOOLEAN "
        "LANGUAGE sql IMMUTABLE AS $$ SELECT TRUE $$"
    )
