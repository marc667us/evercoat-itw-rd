"""project membership cannot be granted to yourself

Revision ID: c9000
Revises: c8000
Created: 2026-08-20

`projects.project_members` had a `USING` clause and no `WITH CHECK`, so
PostgreSQL reused `USING` — organization-only — for writes. Anything
holding an `evercoat_app` connection could insert its own membership row
for a restricted project, and `core.is_project_member()` (SECURITY
DEFINER) then answered TRUE for **every project-scoped policy in the
database**: projects, requirements, formulas, batches, tests, failures,
approvals and messaging. One INSERT opened all of them. UPDATE was the
same escalation by a different verb.

Not reachable over HTTP — the member routes require `project.assign_member`
AND `require_project_member()` — which is exactly why it belonged in the
database.

The fix needed a bootstrap that a visibility check cannot provide: a
Director may convert an opportunity into a RESTRICTED project led by
somebody else, and cannot read it afterwards. `projects.projects.lead_user_id`
is that bootstrap, and migration 006 already uses it the same way on the
read side.

Full reasoning in `migrations/027_project_membership_cannot_be_self_granted.sql`.
Tracked as TODO I20.
"""

from __future__ import annotations

from collections.abc import Sequence

from migrations_alembic._sql import apply_sql

revision: str = "c9000"
down_revision: str | None = "c8000"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    apply_sql("027_project_membership_cannot_be_self_granted.sql")


def downgrade() -> None:
    """Restore 001's write-open policy, and say what that costs.

    Reversing this **reopens a privilege escalation**: any holder of an
    `evercoat_app` connection can grant themselves membership of a
    restricted project and thereby read its formulas, batches, tests,
    failures and conversations. Stated rather than silently performed.
    Prefer fixing forward.
    """
    from alembic import op

    op.execute("DROP POLICY IF EXISTS project_member_scope ON projects.project_members")
    op.execute(
        """
        CREATE POLICY project_member_scope ON projects.project_members
        USING (
            core.rls_permissive() AND core.current_org_id() IS NULL
            OR organization_id = core.current_org_id()
        )
        """
    )
    op.execute("DROP FUNCTION IF EXISTS core.project_lead(UUID)")
