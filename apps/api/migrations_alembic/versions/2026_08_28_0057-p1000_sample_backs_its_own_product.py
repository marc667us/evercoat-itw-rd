"""a sample backs a claim about its own product

Revision ID: p1000
Revises: o1000
Created: 2026-08-28

🔴 THE HOLE THE DOCUMENT FK CLOSED AND THE SAMPLE FK DID NOT.

056 bound `source_document_id` to the competitor product with a three-column
key. `composition_evidence_sample_fk` was left tenant-scoped, so product A's
physical sample could be recorded as the source of a claim about product B.

It was latent while no client sent `sample_id`. The commit that added the
sample picker made the field reachable from a browser, turning a dormant schema
gap into a live one — found by the Supervisor reviewing that commit, not by the
reviewer that reviewed the migration itself.
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op
from sqlalchemy import text

from migrations_alembic._sql import apply_sql

revision: str = "p1000"
down_revision: str | None = "o1000"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    apply_sql("057_a_sample_backs_a_claim_about_its_own_product.sql")

    bind = op.get_bind()

    # 🔴 ASSERT THE RESULTING CONSTRAINT, NEVER THAT THE STATEMENT RAN.
    #
    # `ADD CONSTRAINT` succeeding says the DDL parsed. What matters is that the
    # foreign key now carries the PRODUCT, because a two-column key would leave
    # the cross-product citation open while looking, from the migration log,
    # exactly like a fix.
    definition = bind.execute(
        text(
            """
            SELECT pg_get_constraintdef(oid)
              FROM pg_constraint
             WHERE conrelid = 'competitors.composition_evidence'::regclass
               AND conname = 'composition_evidence_sample_fk'
            """
        )
    ).scalar_one_or_none()
    if definition is None:
        raise RuntimeError("composition_evidence_sample_fk is missing after 057")
    if "competitor_product_id" not in definition:
        raise RuntimeError(
            "composition_evidence_sample_fk does not constrain the product: "
            f"{definition}. A sample from another product could still back a claim."
        )


def downgrade() -> None:
    """Put the tenant-scoped foreign key back, and drop the key it needed."""
    op.execute(
        text(
            """
            ALTER TABLE competitors.composition_evidence
                DROP CONSTRAINT IF EXISTS composition_evidence_sample_fk;
            ALTER TABLE competitors.composition_evidence
                ADD CONSTRAINT composition_evidence_sample_fk
                FOREIGN KEY (sample_id, organization_id)
                REFERENCES competitors.samples (id, organization_id)
                ON DELETE RESTRICT;
            ALTER TABLE competitors.samples
                DROP CONSTRAINT IF EXISTS samples_id_product_org_key;
            """
        )
    )
