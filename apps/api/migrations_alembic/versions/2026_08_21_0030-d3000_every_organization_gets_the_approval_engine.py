"""every organization gets the approval engine, not just the ones 020 saw

Revision ID: d3000
Revises: d2000
Created: 2026-08-21

Migration 020 seeded §9's five approval templates with a ONE-TIME
`FOR org IN SELECT id FROM core.organizations LOOP`. There is no trigger and
nothing else writes `workflow.approval_templates`, so **every organization
created since has an approval engine with nothing in it** — `open_route`
finds no template for the authority level and refuses, and no approval can be
routed at all for a new tenant.

Measured before writing this: inserting a fresh organization and counting its
templates returns 0.

Fixed with one definition (`workflow.provision_approval_templates`), an
AFTER INSERT trigger on `core.organizations`, and a backfill for the
organizations 020 left behind. The migration verifies its own backfill and
raises if any organization is still without templates.

Full reasoning in
`migrations/030_every_organization_gets_the_approval_engine.sql`.
Tracked as TODO I32; unblocks I5.
"""

from __future__ import annotations

from collections.abc import Sequence

from migrations_alembic._sql import apply_sql

revision: str = "d3000"
down_revision: str | None = "d2000"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    apply_sql("030_every_organization_gets_the_approval_engine.sql")


def downgrade() -> None:
    """Drop the trigger and the function; LEAVE the provisioned templates.

    Reversing this returns the database to a state where a new organization
    silently gets no approval templates and no approval can be routed for it.
    Stated rather than silently performed.

    The rows the backfill created are deliberately NOT removed. They are
    ordinary configuration an administrator may since have customised, and a
    downgrade that deletes an organization's approval routing would be far
    more destructive than the defect it is reverting.
    """
    from alembic import op

    op.execute(
        "DROP TRIGGER IF EXISTS organizations_get_approval_templates ON core.organizations"
    )
    op.execute("DROP FUNCTION IF EXISTS workflow.provision_templates_on_new_org()")
    op.execute("DROP FUNCTION IF EXISTS workflow.provision_approval_templates(UUID)")
