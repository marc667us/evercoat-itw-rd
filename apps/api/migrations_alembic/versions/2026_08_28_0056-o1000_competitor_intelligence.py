"""competitor intelligence, and one document register

Revision ID: o1000
Revises: n1000
Created: 2026-08-28

Phase 3 of the Material Safety Data & Research Center: a competitor product's
label, photograph, published SDS and literature, and the Composition Evidence
Matrix built from them.

🔴 IT EXTENDS THE EXISTING DOCUMENT REGISTER RATHER THAN FORKING IT.

The specification §14 says "do not build a second document repository", and a
`competitors.product_documents` table would have forked six invariants that
`materials.material_documents` already enforces: object-storage keys,
checksums, malware verdicts, expiry, the revision chain and the classification
lattice -- plus 038's write-once evidence rules and 037's single definition of
usable. So `material_id` becomes nullable, `competitor_product_id` appears
beside it, and a CHECK requires exactly one.

⚠️ THIS TOUCHES THE TABLE THE FORMULA-SUBMISSION GATE READS. The view
`materials.usable_documents` is recreated with its predicate UNCHANGED --
approved, scan-clean, present, unexpired, unsuperseded -- gaining one
passed-through column. The assertions below prove that, rather than asserting
that the DDL ran.

🔴 THREE HOLES THE REVIEW FOUND BEFORE ANY OF IT WAS WRITTEN, all closed here:
supersession constrained the tenant and not the owner (so a competitor label
could have superseded a material's SDS and changed whether a formula may be
submitted); the write-once set protected the bytes and not the owner; and the
product-bound composite FK on evidence needed a unique key that did not exist.

⚠️ THE MATRIX IS NOT A FORMULA. There is deliberately no competitor-recipe
table. `competitors.composition_evidence` holds claims, each with its source
and confidence, and "verified" requires a re-checkable source, a named verifier
and a time -- with a trigger requiring that verifier to hold
`compliance.review_sds`. Stated as a misuse barrier, not a boundary.
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op
from sqlalchemy import text

from migrations_alembic._sql import apply_sql

revision: str = "o1000"
down_revision: str | None = "n1000"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    apply_sql("056_competitor_intelligence.sql")

    bind = op.get_bind()

    # 🔴 THE FORMULA-SUBMISSION GATE MUST SEE EXACTLY WHAT IT SAW BEFORE.
    #
    # `materials.usable_documents` decides whether a formula may be submitted.
    # This migration recreates it. If the recreation widened or narrowed the
    # predicate, formulas would start passing or failing submission for
    # reasons nobody chose -- and nothing else in the suite would say so,
    # because every test would still be testing a view that exists.
    #
    # Asserted as a COUNT OF MATERIAL DOCUMENTS, which is the number the gate
    # actually uses. Competitor rows are excluded so the comparison is
    # like-for-like.
    still_usable = bind.execute(
        text(
            """
            SELECT count(*) FROM materials.usable_documents
             WHERE material_id IS NOT NULL
            """
        )
    ).scalar_one()
    directly = bind.execute(
        text(
            """
            SELECT count(*) FROM materials.material_documents d
             WHERE d.material_id IS NOT NULL
               AND d.status = 'approved'
               AND d.scan_status = 'clean'
               AND d.checksum_sha256 IS NOT NULL
               AND d.byte_size IS NOT NULL
               AND (d.expires_on IS NULL OR d.expires_on >= CURRENT_DATE)
               AND NOT EXISTS (
                   SELECT 1 FROM materials.material_documents newer
                    WHERE newer.supersedes_id = d.id AND newer.status = 'approved')
            """
        )
    ).scalar_one()
    if still_usable != directly:
        raise RuntimeError(
            f"materials.usable_documents returns {still_usable} material documents "
            f"but the 037 predicate evaluated directly returns {directly}. The view "
            "was recreated with a different meaning, and it decides whether a "
            "formula may be submitted."
        )

    # `security_invoker` is load-bearing: without it the view runs as
    # `evercoat_owner` and reads across every tenant. A recreation that dropped
    # it would be invisible until a cross-tenant leak.
    invoker = bind.execute(
        text(
            """
            SELECT 'security_invoker=true' = ANY(c.reloptions)
              FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
             WHERE n.nspname = 'materials' AND c.relname = 'usable_documents'
            """
        )
    ).scalar()
    if not invoker:
        raise RuntimeError(
            "materials.usable_documents lost security_invoker=true; it would run "
            "as evercoat_owner and read across every tenant"
        )

    unforced = bind.execute(
        text(
            """
            SELECT string_agg(c.relname, ', ' ORDER BY c.relname)
              FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
             WHERE n.nspname = 'competitors' AND c.relkind = 'r'
               AND NOT (c.relrowsecurity AND c.relforcerowsecurity)
            """
        )
    ).scalar()
    if unforced:
        raise RuntimeError(f"competitor tables without FORCE ROW LEVEL SECURITY: {unforced}")


def downgrade() -> None:
    """Drop competitor intelligence and put the document register back.

    ⚠️ ORDER MATTERS. Competitor documents must go before the column that owns
    them, or `material_documents_one_owner` fails to validate against rows that
    have neither owner. And the view has to be restored to 037's exact shape,
    because `n1000` describes a schema in which it has no
    `competitor_product_id` column.
    """
    # 🔴 THE VIEW GOES FIRST. It SELECTS `competitor_product_id`, so dropping
    # that column while the view exists fails with "other objects depend on
    # it" -- which is exactly what happened the first time this ran, leaving
    # the downgrade at exit 1 with nothing reverted. A downgrade that has
    # never been executed is a claim, not a rollback.
    op.execute(text("DROP VIEW IF EXISTS materials.usable_documents"))

    op.execute(text("DROP SCHEMA IF EXISTS competitors CASCADE"))

    # Any document that belonged to a competitor product goes with it: its
    # owner no longer exists, and a document owned by nothing is exactly what
    # the one-owner CHECK forbids.
    op.execute(
        text("DELETE FROM materials.material_documents WHERE competitor_product_id IS NOT NULL")
    )

    op.execute(
        text(
            """
            DROP TRIGGER IF EXISTS material_documents_supersedes_same_owner
                ON materials.material_documents;
            DROP TRIGGER IF EXISTS material_documents_owner_write_once
                ON materials.material_documents;
            DROP FUNCTION IF EXISTS materials.supersession_stays_with_one_owner();
            DROP FUNCTION IF EXISTS materials.deny_document_owner_rewrite();
            ALTER TABLE materials.material_documents
                DROP CONSTRAINT IF EXISTS material_documents_one_owner,
                DROP CONSTRAINT IF EXISTS material_documents_competitor_fk,
                DROP CONSTRAINT IF EXISTS material_documents_id_competitor_org_key,
                DROP COLUMN IF EXISTS competitor_product_id;
            ALTER TABLE materials.material_documents
                ALTER COLUMN material_id SET NOT NULL;
            ALTER TABLE materials.material_documents
                DROP CONSTRAINT material_documents_document_type_check;
            ALTER TABLE materials.material_documents
                ADD CONSTRAINT material_documents_document_type_check CHECK (
                    document_type IN ('TDS','SDS','CoA','regulatory','other'));
            """
        )
    )

    # 037's view, verbatim, rebuilt now the column is gone.
    op.execute(
        text(
            """
            CREATE VIEW materials.usable_documents WITH (security_invoker = true) AS
            SELECT id, organization_id, material_id, document_type, title, storage_key,
                   content_type, byte_size, checksum_sha256, issued_on, expires_on,
                   supersedes_id, uploaded_by, original_filename, scanner_name,
                   scanner_version, scanned_at, created_at
              FROM materials.material_documents
             WHERE status = 'approved'
               AND scan_status = 'clean'
               AND checksum_sha256 IS NOT NULL
               AND byte_size IS NOT NULL
               AND (expires_on IS NULL OR expires_on >= CURRENT_DATE)
               AND NOT EXISTS (
                   SELECT 1 FROM materials.material_documents newer
                    WHERE newer.supersedes_id = materials.material_documents.id
                      AND newer.status = 'approved');
            -- 037 set both; DROP VIEW discarded them.
            ALTER VIEW materials.usable_documents OWNER TO evercoat_owner;
            GRANT SELECT ON materials.usable_documents
                TO evercoat_app, evercoat_report, evercoat_worker;
            """
        )
    )
