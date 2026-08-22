"""one classification lattice, and export as its own permission

Revision ID: e3000
Revises: e2000
Created: 2026-08-22

Closes I48, and gives I43 the thing it needs to exist.

The source folder defines data classification TWICE with two vocabularies, and
only ONE of them contains `PUBLIC` -- which is what the outbound AI gate
(ADR-029) is defined in terms of. Codex raised it; unreconciled it would have
been settled silently by whoever wrote a filter first.

    PUBLIC < INTERNAL < CONFIDENTIAL < R&D_RESTRICTED < FORMULA_RESTRICTED
           < DIRECTOR_CONTROLLED

Three decisions rather than details:
  * it is DATA with a rank, so "at most PUBLIC" is a comparison rather than a
    level list repeated at six query sites;
  * classification is NOT an access group -- `projects.confidentiality` stays
    separate because it answers "is membership required", a different axis;
  * unset is the CEILING, so anything created without a decision is maximally
    restricted.

The BACKFILL is a stated decision, not the default: formulas ->
R&D_RESTRICTED, supplier documents -> INTERNAL, regulatory -> CONFIDENTIAL.
Applying the ceiling to existing rows would be "safe" and useless.

I43: `formula.export` now exists, and is deliberately NOT granted to the
Director -- §31 says seniority is not a reason, and export is the exfiltration
act itself.

Full reasoning in `migrations/039_one_classification_lattice.sql`.
"""

from __future__ import annotations

from collections.abc import Sequence

from migrations_alembic._sql import apply_sql

revision: str = "e3000"
down_revision: str | None = "e2000"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    apply_sql("039_one_classification_lattice.sql")


def downgrade() -> None:
    from alembic import op

    op.execute(
        "ALTER TABLE formulations.formulas DROP CONSTRAINT IF EXISTS formulas_classification_fk"
    )
    op.execute(
        "ALTER TABLE materials.material_documents "
        "DROP CONSTRAINT IF EXISTS material_documents_classification_fk"
    )
    op.execute("ALTER TABLE formulations.formulas DROP COLUMN IF EXISTS classification")
    op.execute("ALTER TABLE materials.material_documents DROP COLUMN IF EXISTS classification")
    op.execute("DROP FUNCTION IF EXISTS core.classification_rank(TEXT)")
    op.execute("DROP TABLE IF EXISTS core.classifications")
    op.execute(
        "DELETE FROM core.role_permissions WHERE permission_id IN "
        "(SELECT id FROM core.permissions WHERE code = 'formula.export')"
    )
    op.execute("DELETE FROM core.permissions WHERE code = 'formula.export'")
