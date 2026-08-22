"""a document row cannot outrun its bytes

Revision ID: d9000
Revises: d8000
Created: 2026-08-22

Closes the database half of I41. `materials.material_documents` has carried
`storage_key`, `checksum_sha256` and `byte_size` since migration 015, all
nullable, and nothing ever wrote the bytes -- while the SDS safety gate counts
ROWS. So `storage_key = 'sds/anything.pdf'` satisfied the control the golden
scenario exists to demonstrate.

A document now reaches `status = 'approved'` only with a checksum, a byte size,
`scan_status = 'clean'`, and a NAMED scanner and version -- by CHECK
constraint, because a service-layer rule cannot see a bulk import, a worker or
a fixture. The checksum is load-bearing: `ObjectStoragePort` computes it from
what it actually wrote and callers cannot supply one.

Existing rows become `legacy_unverified` rather than `quarantined`, because
quarantine means "uploaded, awaiting a verdict" and nothing was ever uploaded.

Full reasoning in `migrations/036_a_document_row_cannot_outrun_its_bytes.sql`.
"""

from __future__ import annotations

from collections.abc import Sequence

from migrations_alembic._sql import apply_sql

revision: str = "d9000"
down_revision: str | None = "d8000"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    apply_sql("036_a_document_row_cannot_outrun_its_bytes.sql")


def downgrade() -> None:
    """Written out literally rather than looped.

    The first version built these with f-strings over a tuple of names, and
    Semgrep blocked the build on `formatted-sql-query` and
    `sqlalchemy-execute-raw-query`. The names are hardcoded constants and a DDL
    identifier cannot be a bind parameter, so it was not exploitable -- but the
    rule is right that the SHAPE is the dangerous one, and a `# nosemgrep`
    here would suppress the guard for whatever this file becomes later.
    Eleven literal statements cost nothing and leave nothing to argue about.
    """
    from alembic import op

    op.execute(
        "ALTER TABLE materials.material_documents "
        "DROP CONSTRAINT IF EXISTS material_documents_approved_has_evidence"
    )
    op.execute(
        "ALTER TABLE materials.material_documents "
        "DROP CONSTRAINT IF EXISTS material_documents_infected_names_the_signature"
    )
    op.execute(
        "ALTER TABLE materials.material_documents "
        "DROP CONSTRAINT IF EXISTS material_documents_status_check"
    )
    op.execute(
        "ALTER TABLE materials.material_documents "
        "DROP CONSTRAINT IF EXISTS material_documents_scan_status_check"
    )
    op.execute("DROP INDEX IF EXISTS materials.material_documents_effective_idx")
    op.execute("ALTER TABLE materials.material_documents DROP COLUMN IF EXISTS status")
    op.execute("ALTER TABLE materials.material_documents DROP COLUMN IF EXISTS scan_status")
    op.execute("ALTER TABLE materials.material_documents DROP COLUMN IF EXISTS scanner_name")
    op.execute("ALTER TABLE materials.material_documents DROP COLUMN IF EXISTS scanner_version")
    op.execute("ALTER TABLE materials.material_documents DROP COLUMN IF EXISTS scan_signature")
    op.execute("ALTER TABLE materials.material_documents DROP COLUMN IF EXISTS scanned_at")
    op.execute("ALTER TABLE materials.material_documents DROP COLUMN IF EXISTS original_filename")
