"""one definition of a usable document

Revision ID: e1000
Revises: d9000
Created: 2026-08-22

Completes I41. Four queries in two modules counted raw `material_documents`
rows -- the formulation submission gate and the three MSD safety tools.
Copying the predicate into each is the "two literals in two files" defect, and
here the two files are the one that BLOCKS a submission and the one that TELLS
a chemist whether it will.

`materials.usable_documents` is the single definition: stored, scanned clean,
not expired, not superseded.

🔴 `security_invoker = true` is load-bearing. A view defaults to its OWNER's
privileges, and the owner here is `evercoat_owner`, which is exempt from RLS
(migration 032). Without the option the view would read across every tenant
and look like an ordinary view -- the same shape as I56.

Full reasoning in `migrations/037_one_definition_of_a_usable_document.sql`.
"""

from __future__ import annotations

from collections.abc import Sequence

from migrations_alembic._sql import apply_sql

revision: str = "e1000"
down_revision: str | None = "d9000"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    apply_sql("037_one_definition_of_a_usable_document.sql")


def downgrade() -> None:
    from alembic import op

    op.execute("DROP VIEW IF EXISTS materials.usable_documents")
