"""a recipe carries its formula's classification

Revision ID: e5000
Revises: e4000
Created: 2026-08-22

First half of I69, which Codex raised as a BLOCKER against 039: *"Formula
identity carries the label while the actual recipe lives in child tables. This
makes the lattice largely decorative outside the one export query."*

039 classified `formulations.formulas` -- a code, a name and an owner. The
COMPOSITION is in `formula_components`, the genealogy in `formula_versions`,
the physical realisation in `laboratory.batches`, the investigation in
`quality.failures`. None carried a label.

🔴 INHERITANCE, NOT A COLUMN PER TABLE. Five copies of one fact is this
repository's most familiar defect, and a child that disagrees with its parent
is a disclosure rather than a distinction. Reclassifying the formula now
reclassifies everything derived from it in the same instant.

Invoker rights on purpose: it reads an RLS-protected table, so it answers only
for a formula the caller can already see. A definer version would be a
cross-tenant oracle (I56).

⚠️ It resolves a label; it does not enforce one. `GET /versions/{id}` still
returns a full composition to `formula.view` (I68). A foundation, not a
control.

Full reasoning in
`migrations/041_a_recipe_carries_its_formulas_classification.sql`.
"""

from __future__ import annotations

from collections.abc import Sequence

from migrations_alembic._sql import apply_sql

revision: str = "e5000"
down_revision: str | None = "e4000"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    apply_sql("041_a_recipe_carries_its_formulas_classification.sql")


def downgrade() -> None:
    from alembic import op

    op.execute("DROP FUNCTION IF EXISTS formulations.effective_classification(UUID)")
