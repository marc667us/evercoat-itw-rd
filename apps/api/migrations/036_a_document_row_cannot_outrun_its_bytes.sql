-- =====================================================================
-- 036 — a document row cannot outrun its bytes
--
-- Closes the database half of I41.
--
-- ---------------------------------------------------------------------
-- THE DEFECT
-- ---------------------------------------------------------------------
--
-- `materials.material_documents` has carried `storage_key`,
-- `checksum_sha256` and `byte_size` since migration 015, all nullable, and
-- **nothing has ever written the bytes** — `boto3` was declared at Slice 1 and
-- never imported. `POST /api/materials/{id}/documents` writes the row and is
-- gated on `material.edit`.
--
-- Meanwhile `formulations/service.py` and `msd_conductor.py` both block
-- formula submission on `requires_sds AND sds_count = 0`. **They count rows.**
--
-- So the safety control the golden scenario exists to demonstrate is satisfied
-- by `storage_key = 'sds/anything.pdf'`, and no Safety Data Sheet need exist.
-- A chemist is told the hazard documentation is present; it is not.
--
-- ---------------------------------------------------------------------
-- WHAT THIS MIGRATION MAKES IMPOSSIBLE
-- ---------------------------------------------------------------------
--
-- A document reaches `status = 'approved'` only with:
--   * a checksum and a byte size — which, by the port's design, can only be
--     obtained by actually storing the bytes;
--   * `scan_status = 'clean'`;
--   * a named scanner and version, so an audit can say WHICH scanner cleared
--     it. "It was scanned" is not durable: a signature database from two years
--     ago is a different control from today's.
--
-- Enforced by CHECK constraint, not by the service — §6's rule that the
-- database owns verified technical facts, applied to the evidence FOR a
-- safety fact rather than to the fact itself. A service-layer check cannot see
-- a bulk import, a worker, a future route, or a fixture.
--
-- ---------------------------------------------------------------------
-- 🔴 THE BACKFILL, AND WHY IT IS NOT `quarantined`
-- ---------------------------------------------------------------------
--
-- Every existing row is a metadata-only registration whose bytes were never
-- stored. There is no honest way to call them approved.
--
-- But marking them `quarantined` would say something false in the other
-- direction — quarantine means "uploaded, awaiting a verdict", and nothing was
-- ever uploaded. They are a THIRD thing, so they get a third state:
-- **`legacy_unverified`**, meaning *"registered before bytes were required;
-- the document may well exist on a shelf, but this system has never held it"*.
--
-- The SDS gate refuses `legacy_unverified`, exactly as it refuses
-- `quarantined`. That is the point: the control starts working.
--
-- ⚠️ AND THAT WOULD DEADLOCK EVERY SEEDED FORMULA, so the seeder and the
-- golden scenario now upload real bytes in the same change. Tightening the
-- gate alone would reproduce the permanent-block defect recorded at
-- `domains/materials/service.py` — "a safety check that could only say
-- BLOCKED" — which is the failure this project already logged on 08-18.
--
-- ⚠️ CLASSIFICATION (I48) IS NOT IN THIS MIGRATION. The lattice touches read
-- paths across the whole application and deserves its own change and review.
-- Doing it here would make an already-broad migration unreviewable.
-- =====================================================================

BEGIN;

ALTER TABLE materials.material_documents
    ADD COLUMN IF NOT EXISTS status            TEXT,
    ADD COLUMN IF NOT EXISTS scan_status       TEXT,
    ADD COLUMN IF NOT EXISTS scanner_name      TEXT,
    ADD COLUMN IF NOT EXISTS scanner_version   TEXT,
    ADD COLUMN IF NOT EXISTS scan_signature    TEXT,
    ADD COLUMN IF NOT EXISTS scanned_at        TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS original_filename TEXT;

-- Backfill BEFORE the NOT NULLs, so the migration cannot half-apply.
UPDATE materials.material_documents
   SET status      = COALESCE(status, 'legacy_unverified'),
       scan_status = COALESCE(scan_status, 'not_scanned');

ALTER TABLE materials.material_documents
    ALTER COLUMN status      SET NOT NULL,
    ALTER COLUMN scan_status SET NOT NULL,
    ALTER COLUMN status      SET DEFAULT 'quarantined',
    ALTER COLUMN scan_status SET DEFAULT 'pending';

ALTER TABLE materials.material_documents
    DROP CONSTRAINT IF EXISTS material_documents_status_check;
ALTER TABLE materials.material_documents
    ADD CONSTRAINT material_documents_status_check CHECK (
        status IN ('quarantined', 'approved', 'rejected', 'superseded', 'legacy_unverified')
    );

ALTER TABLE materials.material_documents
    DROP CONSTRAINT IF EXISTS material_documents_scan_status_check;
ALTER TABLE materials.material_documents
    ADD CONSTRAINT material_documents_scan_status_check CHECK (
        scan_status IN ('pending', 'clean', 'infected', 'unavailable', 'not_scanned')
    );

-- 🔴 THE CONSTRAINT THAT CLOSES I41.
--
-- Approval requires evidence that the bytes exist and were cleared. The
-- checksum is the load-bearing part: `ObjectStoragePort` computes it from what
-- it actually wrote and returns it, and the caller cannot supply one — so a
-- row that carries a checksum is a row whose bytes were stored.
ALTER TABLE materials.material_documents
    DROP CONSTRAINT IF EXISTS material_documents_approved_has_evidence;
ALTER TABLE materials.material_documents
    ADD CONSTRAINT material_documents_approved_has_evidence CHECK (
        status <> 'approved'
        OR (
            checksum_sha256 IS NOT NULL
            AND byte_size    IS NOT NULL
            AND byte_size     > 0
            AND scan_status   = 'clean'
            AND scanner_name  IS NOT NULL
            AND scanner_version IS NOT NULL
            AND scanned_at    IS NOT NULL
        )
    );

-- A verdict of 'infected' must name what was found, or the record cannot be
-- acted on. Same reasoning as migration 031's refusal-needs-a-rationale rule.
ALTER TABLE materials.material_documents
    DROP CONSTRAINT IF EXISTS material_documents_infected_names_the_signature;
ALTER TABLE materials.material_documents
    ADD CONSTRAINT material_documents_infected_names_the_signature CHECK (
        scan_status <> 'infected' OR scan_signature IS NOT NULL
    );

-- Serves the SDS gate, which now filters on status and scan_status as well as
-- material and type. Without it the gate degrades to a scan of every document
-- a material has, on the hot path of formula submission.
CREATE INDEX IF NOT EXISTS material_documents_effective_idx
    ON materials.material_documents (material_id, document_type, status, scan_status);

COMMENT ON COLUMN materials.material_documents.status IS
    'quarantined = uploaded, awaiting a verdict. approved = bytes stored, '
    'scanned clean, usable as evidence. rejected = the scanner found '
    'something. superseded = replaced by a later revision. legacy_unverified '
    '= registered before migration 036 required bytes, so this system has '
    'never held the file. Only ''approved'' satisfies a safety gate.';

COMMENT ON COLUMN materials.material_documents.checksum_sha256 IS
    'SHA-256 of the stored bytes, computed BY THE OBJECT STORE while writing '
    'and returned to the caller. Callers cannot supply it, which is what makes '
    'it evidence that the file exists rather than a claim that it does.';

COMMIT;


-- ---------------------------------------------------------------------
-- Prove the constraint, without leaving rows behind.
--
-- Wrapped in its own transaction that is ROLLED BACK: this table is not
-- append-only, but a migration that seeds probe rows into a tenant's document
-- register is the mistake migration 034 already made once (into an append-only
-- ledger, irreversibly). Inspect where possible; where a behavioural check is
-- genuinely needed, undo it.
-- ---------------------------------------------------------------------
DO $$
DECLARE
    v_org      UUID;
    v_material UUID;
    v_user     UUID;
    v_blocked  BOOLEAN := FALSE;
BEGIN
    SELECT m.organization_id, m.id, m.created_by
      INTO v_org, v_material, v_user
      FROM materials.materials m
     LIMIT 1;

    IF v_material IS NULL THEN
        RAISE NOTICE '036: no material to probe against; constraint verified by definition only';
        RETURN;
    END IF;

    BEGIN
        INSERT INTO materials.material_documents
            (organization_id, material_id, document_type, title, storage_key,
             uploaded_by, status, scan_status)
        VALUES (v_org, v_material, 'SDS', '036 probe', '036-probe-key',
                v_user, 'approved', 'clean');
    EXCEPTION WHEN check_violation THEN
        v_blocked := TRUE;
    END;

    IF NOT v_blocked THEN
        RAISE EXCEPTION
            '036: a document with NO checksum and NO scanner reached status '
            '''approved''. The constraint that closes I41 is not in force.';
    END IF;
END $$;
