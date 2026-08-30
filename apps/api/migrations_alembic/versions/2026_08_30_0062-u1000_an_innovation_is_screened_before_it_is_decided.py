"""an innovation is screened before it is decided

Revision ID: u1000
Revises: t1000
Created: 2026-08-30

Puts the Research Center between Opportunity and Project for innovations that
carry an investigation, so an idea taken off a competitor's card cannot become
a project on the strength of a pasted note.

🔴 THE PROBE CHECKS THE LINK IS TENANT-QUALIFIED, WHICH IS THE HALF A CHECK
   CONSTRAINT CANNOT DO.

RLS stops cross-tenant reads and not cross-tenant references. A single-column
FK here would let one tenant's investigation name another tenant's
opportunity, and nothing would complain.
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op
from sqlalchemy import text

from migrations_alembic._sql import apply_sql

revision: str = "u1000"
down_revision: str | None = "t1000"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    apply_sql("062_an_innovation_is_screened_before_it_is_decided.sql")

    bind = op.get_bind()

    columns = (
        bind.execute(
            text(
                """
            SELECT a.attname
              FROM pg_constraint c
              JOIN unnest(c.conkey) WITH ORDINALITY AS k(attnum, ord) ON TRUE
              JOIN pg_attribute a ON a.attrelid = c.conrelid AND a.attnum = k.attnum
             WHERE c.conname = 'investigations_opportunity_fk'
             ORDER BY k.ord
            """
            )
        )
        .scalars()
        .all()
    )

    if columns != ["opportunity_id", "organization_id"]:
        raise RuntimeError(
            "investigations_opportunity_fk is "
            f"{columns or 'absent'}, not (opportunity_id, organization_id). A "
            "single-column foreign key would let one tenant's investigation "
            "reference another tenant's opportunity -- referential integrity "
            "bypasses RLS, including under FORCE."
        )

    unique = bind.execute(
        text(
            "SELECT indisunique FROM pg_index i "
            " JOIN pg_class c ON c.oid = i.indexrelid "
            " WHERE c.relname = 'investigations_one_per_opportunity'"
        )
    ).scalar_one_or_none()
    if not unique:
        raise RuntimeError(
            "investigations_one_per_opportunity is missing or not unique; two "
            "investigations on one opportunity would make 'has this been "
            "screened?' depend on which row the gate happened to find"
        )


def downgrade() -> None:
    raise NotImplementedError(
        "062 is not reversible: dropping the link would silently un-gate every "
        "opportunity that had been screened through it."
    )
