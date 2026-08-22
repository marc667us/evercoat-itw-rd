"""a classification needs a writer

Revision ID: e4000
Revises: e3000
Created: 2026-08-22

Fixes a defect introduced by 039 one commit earlier, found by asking this
project's own most-repeated question of my own work: WHICH PRODUCTION PATH
WRITES IT?

None. 039 added `formulas.classification` defaulting to the ceiling
`DIRECTOR_CONTROLLED` -- correct as a backstop -- and added nothing that makes
the decision. `create_formula` does not set it, no service or route writes it,
and `export_version` refuses above `R&D_RESTRICTED`. So **every formula created
from then on could never be exported by anybody, ever**, with no path to change
it. CI was green.

That is the "safety check that could only say BLOCKED" shape recorded on
materials/service.py, and restated in I67's own note two hours earlier. Writing
the warning did not stop me shipping it one column over, so it is now
instrumented: a test asserts a newly created formula is exportable by its own
rules.

`formula.classify` is granted to EXACTLY the roles holding `formula.export`,
and the migration refuses to complete if the two sets differ -- lowering a
classification is the precondition for exporting one.

Full reasoning in `migrations/040_a_classification_needs_a_writer.sql`.
"""

from __future__ import annotations

from collections.abc import Sequence

from migrations_alembic._sql import apply_sql

revision: str = "e4000"
down_revision: str | None = "e3000"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    apply_sql("040_a_classification_needs_a_writer.sql")


def downgrade() -> None:
    from alembic import op

    op.execute(
        "DELETE FROM core.role_permissions WHERE permission_id IN "
        "(SELECT id FROM core.permissions WHERE code = 'formula.classify')"
    )
    op.execute("DELETE FROM core.permissions WHERE code = 'formula.classify'")
