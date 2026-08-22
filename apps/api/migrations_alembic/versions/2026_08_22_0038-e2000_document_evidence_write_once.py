"""document evidence is write-once

Revision ID: e2000
Revises: e1000
Created: 2026-08-22

Codex FAILed 036/037 with three BLOCKERs. 036 claimed a row "cannot claim a
file the store does not hold".

🔴 MEASURED FALSE. `evercoat_app` holds INSERT and UPDATE, and the CHECK
constraint validates the SHAPE of the evidence, not the evidence. A forged row
with `checksum_sha256 = repeat('a',64)`, `scanner_name =
'totally-real-scanner'` and a storage key naming nothing was accepted, and
`materials.usable_documents` counted it.

This makes the evidence columns write-once, closing two escalations: a
`legacy_unverified` row cannot be promoted by inventing a checksum, and safety
history cannot be rewritten by a compromised route, an injection, a worker or
a fixture.

It does NOT make a first-time approval truthful. PostgreSQL cannot verify an
object store, and no comment should imply otherwise -- I61 (one write path),
I62 (reconciliation) and I63 (content policy) carry the rest.

Full reasoning in `migrations/038_document_evidence_is_write_once.sql`.
"""

from __future__ import annotations

from collections.abc import Sequence

from migrations_alembic._sql import apply_sql

revision: str = "e2000"
down_revision: str | None = "e1000"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    apply_sql("038_document_evidence_is_write_once.sql")


def downgrade() -> None:
    from alembic import op

    op.execute(
        "DROP TRIGGER IF EXISTS material_documents_evidence_write_once "
        "ON materials.material_documents"
    )
    op.execute("DROP FUNCTION IF EXISTS materials.deny_document_evidence_rewrite()")
