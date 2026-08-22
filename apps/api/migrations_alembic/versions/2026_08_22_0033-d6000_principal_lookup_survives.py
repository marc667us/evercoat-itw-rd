"""the principal lookup survives the closed door

Revision ID: d6000
Revises: d5000
Created: 2026-08-22

Companion to 032 (d5000). **Neither should be deployed without the other.**

032 closed the permissive RLS escape hatch. `get_principal` resolves every
caller's identity, roles and permissions with a raw query inside
`unscoped_session_scope()` -- it must, because you cannot set a tenant GUC
until you know the caller's tenant. Those reads hit tenant-scoped `core.*`
tables, so after 032 they returned nothing and **every authenticated request
answered 403**. Measured: 35 route tests across `tests/auth/`.

The fix is the pattern this codebase already adopted for
`core.memberships_for_subject` (024), `core.is_project_member` (001),
`audit.chain_row` (011) and `formulations.deny_component_mutation` (015): a
SECURITY DEFINER function owned by `evercoat_owner`, which is exempt from
policies on tables it owns while RLS is ENABLED and not FORCED -- the state 032
deliberately preserves.

Full reasoning in
`migrations/033_the_principal_lookup_survives_the_closed_door.sql`.
"""

from __future__ import annotations

from collections.abc import Sequence

from migrations_alembic._sql import apply_sql

revision: str = "d6000"
down_revision: str | None = "d5000"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    apply_sql("033_the_principal_lookup_survives_the_closed_door.sql")


def downgrade() -> None:
    from alembic import op

    op.execute("DROP FUNCTION IF EXISTS core.principal_for_subject(TEXT, UUID)")
