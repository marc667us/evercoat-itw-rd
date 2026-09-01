"""a landing page belongs to one organization

Revision ID: x1000
Revises: w1000
Created: 2026-09-01

064 gave the access request an owner and closed the cross-tenant READ. Codex's
second pass found it had left the cross-tenant WRITE open: the public INSERT
policy accepted any non-null organization, and permissive policies are ORed,
so the anonymous role could plant an applicant into any organization it could
name.

065 narrows that to organizations which have opted in.

🔴 THE PROBE ASSERTS PRIVILEGE AND BEHAVIOUR, NOT THAT THE STATEMENTS RAN.
PostgreSQL grants EXECUTE to PUBLIC on new functions by default, which this
repository treats as a live vulnerability — so the REVOKE is checked by asking
`has_function_privilege`, never by trusting that the line executed.
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op
from sqlalchemy import text

from migrations_alembic._sql import apply_sql

revision: str = "x1000"
down_revision: str | None = "w1000"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    apply_sql("065_a_landing_page_belongs_to_one_organization.sql")

    bind = op.get_bind()

    column = bind.execute(
        text(
            """
            SELECT data_type, is_nullable, column_default
              FROM information_schema.columns
             WHERE table_schema = 'core' AND table_name = 'organizations'
               AND column_name = 'accepts_public_access_requests'
            """
        )
    ).one_or_none()
    if column is None:
        raise RuntimeError(
            "core.organizations has no accepts_public_access_requests column, so "
            "the public INSERT policy has nothing to consult."
        )
    if column.is_nullable != "NO":
        raise RuntimeError(
            "accepts_public_access_requests is nullable. NULL is not false in a "
            "policy predicate -- it is unknown, which a policy treats as false "
            "in one place and reads as an oversight everywhere else."
        )

    # 🔴 DEFAULT FALSE. A new organization must not be reachable by the
    # anonymous role until somebody says so; a default of true would make every
    # future tenant opt OUT of a boundary rather than in to a feature.
    default_off = bind.execute(
        text("SELECT count(*) FROM core.organizations WHERE accepts_public_access_requests")
    ).scalar_one()
    if default_off != 0:
        raise RuntimeError(
            f"{default_off} organizations already accept public access requests "
            "immediately after the column was added, so the default is not false."
        )

    # ⚠️ THE PRIVILEGE, NOT THE GRANT STATEMENT.
    public_may, world_may = bind.execute(
        text(
            "SELECT has_function_privilege('evercoat_public',"
            "         'core.accepts_public_access_requests(uuid)','EXECUTE'),"
            "       has_function_privilege('public',"
            "         'core.accepts_public_access_requests(uuid)','EXECUTE')"
        )
    ).one()
    if not public_may:
        raise RuntimeError(
            "evercoat_public cannot EXECUTE the opt-in check, so its own INSERT "
            "policy can never evaluate to true and Sign Up is dead."
        )
    if world_may:
        raise RuntimeError(
            "EXECUTE is still held by PUBLIC. Postgres grants that by default on "
            "a new function and the REVOKE did not take."
        )

    policy = bind.execute(
        text(
            "SELECT with_check FROM pg_policies "
            " WHERE schemaname = 'public_intel' AND tablename = 'access_requests'"
            "   AND policyname = 'access_requests_public_insert'"
        )
    ).scalar_one_or_none()
    if policy is None or "accepts_public_access_requests" not in policy:
        raise RuntimeError(
            "the public INSERT policy does not consult the opt-in check: "
            f"{policy!r}. Any organization can still be written to."
        )


def downgrade() -> None:
    op.execute(
        "DROP POLICY IF EXISTS access_requests_public_insert ON public_intel.access_requests"
    )
    op.execute(
        "CREATE POLICY access_requests_public_insert ON public_intel.access_requests"
        " FOR INSERT TO evercoat_public WITH CHECK (organization_id IS NOT NULL)"
    )
    op.execute("DROP FUNCTION IF EXISTS core.accepts_public_access_requests(UUID)")
    op.execute(
        "ALTER TABLE core.organizations DROP COLUMN IF EXISTS accepts_public_access_requests"
    )
