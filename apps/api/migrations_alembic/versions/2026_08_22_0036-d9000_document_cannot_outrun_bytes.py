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
    from alembic import op

    for constraint in (
        "material_documents_approved_has_evidence",
        "material_documents_infected_names_the_signature",
        "material_documents_status_check",
        "material_documents_scan_status_check",
    ):
        op.execute(
            f"ALTER TABLE materials.material_documents DROP CONSTRAINT IF EXISTS {constraint}"
        )
    op.execute("DROP INDEX IF EXISTS materials.material_documents_effective_idx")
    for column in (
        "status",
        "scan_status",
        "scanner_name",
        "scanner_version",
        "scan_signature",
        "scanned_at",
        "original_filename",
    ):
        op.execute(f"ALTER TABLE materials.material_documents DROP COLUMN IF EXISTS {column}")
