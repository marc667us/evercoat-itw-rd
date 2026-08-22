"""knowledge permissions -- the tier finally gets a write path with a holder

Revision ID: e7000
Revises: e6000
Created: 2026-08-22

042 built the knowledge tier and NOTHING WROTE TO IT (I74). This adds
`knowledge.view` and `knowledge.ingest`, and the routes and screen that use
them land in the same commit -- a permission arriving without its consumer is
exactly how migration 016's "a permission no role held" defect was created.

`knowledge.view` is granted to nine of ten roles deliberately: for this tier
the permission is not the confidentiality boundary, RLS on `knowledge.chunks`
is. `knowledge.ingest` is narrow because ingestion SETS the classification of
text MSD will later quote.

Full reasoning in `migrations/043_knowledge_permissions.sql`.
"""

from __future__ import annotations

from collections.abc import Sequence

from migrations_alembic._sql import apply_sql

revision: str = "e7000"
down_revision: str | None = "e6000"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    apply_sql("043_knowledge_permissions.sql")


#  Roles this migration granted to, and ONLY those.
#
#  🔴 THE FIRST DRAFT OF THIS DOWNGRADE DELETED THE PERMISSIONS THEMSELVES AND
#  EVERY GRANT ON THEM. Both codes predate this migration -- they are migration
#  002's -- and 002 already granted `knowledge.view` to the Chemist, Engineer
#  and Lead. So the downgrade would have removed rows it never created and left
#  the database in a state 002 could not restore, which is worse than not being
#  reversible at all: `alembic downgrade` would have SUCCEEDED and silently
#  taken three roles' pre-existing access with it.
_VIEW_ADDED = (
    "product_development_director",
    "qa_compliance_officer",
    "administrator",
    "laboratory_technician",
    "production_engineer",
    "executive_viewer",
)
_INGEST_ADDED = (
    "product_development_lead",
    "product_development_director",
    "qa_compliance_officer",
    "administrator",
)


def downgrade() -> None:
    from alembic import op

    for code, roles in (("knowledge.view", _VIEW_ADDED), ("knowledge.ingest", _INGEST_ADDED)):
        op.execute(
            f"""
            DELETE FROM core.role_permissions rp
             USING core.permissions p, core.roles r
             WHERE p.id = rp.permission_id
               AND r.id = rp.role_id
               AND p.code = '{code}'
               AND r.code IN ({", ".join(f"'{role}'" for role in roles)})
            """  # noqa: S608 - literals from the tuples above, no input reaches here
        )

    # The permission ROWS are deliberately left alone. They belong to 002.
