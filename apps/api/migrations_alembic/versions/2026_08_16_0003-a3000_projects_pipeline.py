"""projects, pipeline with preserved stage history, requirements, tasks

Revision ID: a3000
Revises: a2000
Created: 2026-08-16
"""

from __future__ import annotations

from collections.abc import Sequence

from migrations_alembic._sql import apply_sql

revision: str = "a3000"
down_revision: str | None = "a2000"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    apply_sql("003_projects_pipeline_requirements.sql")


def downgrade() -> None:
    """Not implemented.

    Dropping these tables destroys stage history and requirement
    revisions -- the evidence trail that makes pipeline analytics and
    requirement verification possible at all. Roll forward.
    """
    raise NotImplementedError(
        "downgrade would destroy stage history and requirement revisions"
    )
