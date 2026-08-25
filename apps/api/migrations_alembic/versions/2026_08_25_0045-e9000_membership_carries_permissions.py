"""a membership carries its permissions

Revision ID: e9000
Revises: e8000
Created: 2026-08-25

Closes I79.

`GET /api/me` returned `organizations[].roles` and no permissions, so
`apps/web/app/layout.tsx` handed the sidebar `ALL_NAV_PERMISSIONS` -- the whole
module map -- and every permission-shaped decision in the browser was made
against "this user holds everything". Not a security hole (§6 re-enforces every
control server-side, and it does), but every one of the nine workspaces wired on
2026-08-24 shows its full control set to every role, and the server correctly
answers 403 when one is pressed.

`core.memberships_for_subject` now returns the permission codes held in each
organization, resolved through the same `member_roles -> roles ->
role_permissions -> permissions` chain that `core.principal_for_subject` (033)
already walks for the server-side `Principal`. ONE definition of the mapping,
in the place that owns it, rather than a second copy in TypeScript that cannot
be type-checked into agreement with the first.

Full reasoning in `migrations/045_a_membership_carries_its_permissions.sql`.
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op
from sqlalchemy import text

from migrations_alembic._sql import apply_sql

revision: str = "e9000"
down_revision: str | None = "e8000"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    apply_sql("045_a_membership_carries_its_permissions.sql")


def downgrade() -> None:
    """Restore 024's six-column function, exactly.

    🔴 THE DOWNGRADE MUST ALSO RESTATE THE OWNER AND THE GRANT.

    `DROP FUNCTION` takes the ownership and the privileges with it, in this
    direction just as much as in the upgrade. A downgrade that recreates the
    function and stops leaves EXECUTE at PostgreSQL's default -- which is
    PUBLIC -- turning a deliberately narrow SECURITY DEFINER lookup into one
    every role in the database may call for an arbitrary subject.

    Restating a grant is idempotent; forgetting one is not, and this project
    has lost privileges to exactly that on 2026-08-22.
    """
    op.execute(text("DROP FUNCTION IF EXISTS core.memberships_for_subject(TEXT)"))
    op.execute(
        text(
            """
            CREATE FUNCTION core.memberships_for_subject(p_sub TEXT)
            RETURNS TABLE (
                user_id           UUID,
                email             TEXT,
                display_name      TEXT,
                organization_id   UUID,
                organization_name TEXT,
                organization_code TEXT,
                roles             TEXT[]
            )
                LANGUAGE sql
                STABLE
                SECURITY DEFINER
                SET search_path = core, pg_temp
            AS $$
                SELECT u.id,
                       u.email::TEXT,
                       u.display_name,
                       om.organization_id,
                       o.name,
                       o.code,
                       COALESCE(array_agg(DISTINCT r.code)
                                FILTER (WHERE r.code IS NOT NULL), '{}')
                FROM core.users u
                JOIN core.organization_members om
                  ON om.user_id = u.id
                 AND om.status  = 'active'
                JOIN core.organizations o
                  ON o.id = om.organization_id
                 AND o.status = 'active'
                LEFT JOIN core.member_roles mr ON mr.member_id = om.id
                LEFT JOIN core.roles        r  ON r.id = mr.role_id
                WHERE u.keycloak_sub = p_sub
                  AND u.status = 'active'
                GROUP BY u.id, u.email, u.display_name, om.organization_id,
                         o.name, o.code
                ORDER BY o.name
            $$
            """
        )
    )
    op.execute(text("ALTER FUNCTION core.memberships_for_subject(TEXT) OWNER TO evercoat_owner"))
    op.execute(text("REVOKE ALL ON FUNCTION core.memberships_for_subject(TEXT) FROM PUBLIC"))
    op.execute(text("GRANT EXECUTE ON FUNCTION core.memberships_for_subject(TEXT) TO evercoat_app"))
