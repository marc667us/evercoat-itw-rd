"""the user directory is not a global directory

Revision ID: e8000
Revises: e7000
Created: 2026-08-23

Closes I55, and closes a cross-tenant WRITE found while measuring it (I80).

032 made the database fail closed with no tenant context, but `core.users`
never had RLS enabled at all, so 032 did nothing for it. Measured today as
`evercoat_app` with no GUC: `core.organization_members` returned 0 rows and
`core.users` returned **571**, emails included.

The write half was worse. `invite_member`'s `ON CONFLICT (keycloak_sub) DO
UPDATE SET display_name` was run as `evercoat_app` under organization A's GUC
against a subject belonging only to organization B, and it renamed that user
and returned their real email address.

Full reasoning in `migrations/044_the_user_directory_is_not_global.sql`.
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op
from sqlalchemy import text

from migrations_alembic._sql import apply_sql

revision: str = "e8000"
down_revision: str | None = "e7000"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    apply_sql("044_the_user_directory_is_not_global.sql")


def downgrade() -> None:
    """Re-open the directory.

    🔴 This downgrade removes ONLY what 044 created, and that distinction has
    cost this project twice in one migration before (043's first two drafts
    revoked grants migration 002 had made). Here it is unambiguous: `core.users`
    had **no** RLS and **no** policies before 044 — measured, not assumed:
    `relrowsecurity = false` with zero rows in `pg_policy`. So dropping all
    three policies and disabling RLS restores exactly the prior state.

    `core.user_id_for_subject` is likewise new in 044 and is dropped. Nothing
    else referenced it before this migration existed.

    ⚠️ Running this returns the database to the state where every tenant's
    email addresses are readable by the runtime role with no context set.
    """
    op.execute(text("DROP FUNCTION IF EXISTS core.user_id_for_subject(TEXT)"))
    op.execute(
        text("DROP POLICY IF EXISTS users_updatable_within_a_shared_organization ON core.users")
    )
    op.execute(text("DROP POLICY IF EXISTS users_identity_may_be_created ON core.users"))
    op.execute(
        text("DROP POLICY IF EXISTS users_visible_within_a_shared_organization ON core.users")
    )
    op.execute(text("ALTER TABLE core.users DISABLE ROW LEVEL SECURITY"))
