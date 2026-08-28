"""the interpretation of a safety data sheet is not the sheet

Revision ID: m1000
Revises: l1000
Created: 2026-08-28

Phase 1 of the Material Safety Data & Research Center.

The SDS record already existed. `materials.material_documents` has carried
`document_type = 'SDS'`, a `supersedes_id` revision chain, issue and expiry
dates, a checksum and a scanner verdict since 015/036, and
`materials.usable_documents` (037) is the single definition of a document that
may be relied on -- read by the formula-submission gate and by
`agents/tools/safety.py`.

So `safety.*` stores no storage key, no checksum, no expiry and no supersedes
pointer. It stores what a sheet SAYS, keyed to the document that says it.

🔴 THERE IS NO `status` COLUMN, AND THAT IS THE POINT. Currency is a join to
`materials.usable_documents`, every time, by every consumer. A stored status
would be a second opinion about whether a document is current, and 037 exists
because four queries in two modules had already disagreed about that once.
`review_state` describes the human review workflow and is named so it cannot be
mistaken for the other question.

⚠️ AND THE CREATION RULE IS A TRIGGER, NOT A SERVICE CHECK. A rule enforced in
Python is not a rule the database has: the db suite -- and anything else holding
the `evercoat_app` connection -- issues INSERTs that no service function sees.

⚠️ FORCE ROW LEVEL SECURITY FROM BIRTH, which the older tables do not have.
CLAUDE.md §5 requires it. The existing tables have not cut over because I56/I58
carries an owed measurement about owner-side reads; nothing owner-side reads
these, so that reason does not apply and a new table without FORCE would be one
more row on that backlog added on purpose. Policies are installed BEFORE FORCE
in the same transaction -- FORCE with no policy denies the owner too.
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op
from sqlalchemy import text

from migrations_alembic._sql import apply_sql

revision: str = "m1000"
down_revision: str | None = "l1000"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    apply_sql("054_material_safety_data.sql")

    # 🔴 ASSERT THE MIGRATION ACHIEVED ITS POINT rather than assuming the DDL
    # did anything. `FORCE ROW LEVEL SECURITY` is the one line here whose
    # absence is completely invisible: every test passes, every query works,
    # and the table is simply readable by its owner across tenants. A guard
    # that cannot fail is not a guard, so this one is asserted.
    unforced = (
        op.get_bind()
        .execute(
            text(
                """
                SELECT string_agg(c.relname, ', ' ORDER BY c.relname)
                  FROM pg_class c
                  JOIN pg_namespace n ON n.oid = c.relnamespace
                 WHERE n.nspname = 'safety'
                   AND c.relkind = 'r'
                   AND NOT (c.relrowsecurity AND c.relforcerowsecurity)
                """
            )
        )
        .scalar()
    )
    if unforced:
        raise RuntimeError(
            "safety tables without FORCE ROW LEVEL SECURITY after 054: "
            f"{unforced}. CLAUDE.md §5 requires it of every proprietary table, "
            "and without it the owner reads across every tenant."
        )


def downgrade() -> None:
    """Drop the safety schema.

    ⚠️ THIS DESTROYS SAFETY INTERPRETATIONS, and that is why it is a plain
    CASCADE rather than something cleverer. `l1000` describes a schema in which
    no interpretation exists; a downgrade that preserved the rows would leave
    them unreachable and undeleteable, which is worse than not having them.

    The documents themselves are untouched -- they never lived here. Every SDS,
    its bytes, its checksum, its scan verdict and its revision chain remain in
    `materials.material_documents`, which is the whole reason this schema was
    built to hold interpretation only. Re-applying 054 and re-interpreting is
    therefore possible; nothing irreplaceable is lost.
    """
    op.execute(text("DROP SCHEMA IF EXISTS safety CASCADE"))
