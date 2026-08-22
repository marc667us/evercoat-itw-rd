-- =====================================================================
-- 038 — document evidence is write-once
--
-- Codex reviewed 036/037 and returned FAIL with three BLOCKERs. This closes
-- the part that is closable in the database, and states plainly the part that
-- is not.
--
-- ---------------------------------------------------------------------
-- 🔴 THE CLAIM 036 MADE WAS TOO STRONG, AND I MEASURED IT FALSE
-- ---------------------------------------------------------------------
--
-- 036's header says a row "cannot claim a file the store does not hold,
-- because the value that proves the file is only obtainable by storing it".
--
-- That is true of the SERVICE path and false of the DATABASE. `evercoat_app`
-- holds INSERT and UPDATE on this table, and the CHECK constraint validates
-- the SHAPE of the evidence, not the evidence. Measured 2026-08-22, connected
-- as `evercoat_app` with a tenant GUC set:
--
--     INSERT ... status='approved', scan_status='clean',
--                checksum_sha256=repeat('a',64),
--                scanner_name='totally-real-scanner',
--                storage_key='no-such-key-forged'
--     -> accepted, and materials.usable_documents counted it.
--
-- A fabricated checksum is 64 hex characters. Nothing compared it to anything.
--
-- ---------------------------------------------------------------------
-- WHAT THIS FIXES, AND WHAT IT HONESTLY CANNOT
-- ---------------------------------------------------------------------
--
-- FIXES: the evidence columns become **write-once** — settable at INSERT and
-- never changed. That closes two escalations Codex named:
--
--   * a `legacy_unverified` row cannot be promoted to `approved` by inventing
--     a checksum and scanner fields;
--   * safety history cannot be rewritten — by a compromised route, an
--     injection, a worker, a fixture or a future service — because an approved
--     document's verdict, checksum, size, key and scanner provenance are no
--     longer updatable at all.
--
-- Supersession still works: it is a NEW row pointing at the old one, which is
-- what a document register is. `expires_on` and `title` stay mutable, because
-- an issuer genuinely does revise those.
--
-- CANNOT FIX, and must not pretend to: **PostgreSQL cannot verify an object
-- store.** No constraint or trigger available here can establish that
-- `storage_key` names bytes that exist and hash to `checksum_sha256`. A writer
-- holding INSERT can still assert a first-time approval that is a lie.
--
-- The honest mitigations are architectural, and are recorded as issues rather
-- than implied by a comment:
--   I61  one write path — revoke direct INSERT and route through a single
--        audited function, so the surface is one reviewable place
--   I62  reconciliation — a worker that re-reads each approved object and
--        re-computes its checksum, quarantining rows whose bytes are missing
--        or changed. Also the only defence against an object DELETED or
--        REPLACED after approval, which Codex raised separately
--   I63  content policy — "scanned clean" is not "is a Safety Data Sheet"
-- =====================================================================

BEGIN;

CREATE OR REPLACE FUNCTION materials.deny_document_evidence_rewrite()
RETURNS TRIGGER
    LANGUAGE plpgsql
    SET search_path = materials, pg_temp
AS $fn$
BEGIN
    -- Columns named individually rather than compared as whole rows, so the
    -- error says WHICH one was rewritten. A generic "the row changed" sends
    -- the next reader through fourteen columns.
    IF NEW.status IS DISTINCT FROM OLD.status THEN
        RAISE EXCEPTION
            'material_documents.status is write-once (% -> %). A verdict is '
            'safety evidence: supersede it with a new row rather than '
            'rewriting this one.', OLD.status, NEW.status;
    END IF;
    IF NEW.scan_status IS DISTINCT FROM OLD.scan_status THEN
        RAISE EXCEPTION 'material_documents.scan_status is write-once (% -> %)',
            OLD.scan_status, NEW.scan_status;
    END IF;
    IF NEW.checksum_sha256 IS DISTINCT FROM OLD.checksum_sha256 THEN
        RAISE EXCEPTION 'material_documents.checksum_sha256 is write-once';
    END IF;
    IF NEW.byte_size IS DISTINCT FROM OLD.byte_size THEN
        RAISE EXCEPTION 'material_documents.byte_size is write-once';
    END IF;
    IF NEW.storage_key IS DISTINCT FROM OLD.storage_key THEN
        RAISE EXCEPTION
            'material_documents.storage_key is write-once. Repointing a row at '
            'different bytes keeps the old checksum and scan verdict attached '
            'to content nobody examined.';
    END IF;
    IF NEW.scanner_name IS DISTINCT FROM OLD.scanner_name
       OR NEW.scanner_version IS DISTINCT FROM OLD.scanner_version
       OR NEW.scanned_at IS DISTINCT FROM OLD.scanned_at THEN
        RAISE EXCEPTION
            'material_documents scanner provenance is write-once. A regulated '
            'audit must be able to say which scanner cleared this document.';
    END IF;
    IF NEW.material_id IS DISTINCT FROM OLD.material_id
       OR NEW.organization_id IS DISTINCT FROM OLD.organization_id
       OR NEW.document_type IS DISTINCT FROM OLD.document_type THEN
        RAISE EXCEPTION
            'a document cannot be moved to another material, organization or '
            'document type; that would re-use one file''s evidence for another '
            'claim';
    END IF;
    RETURN NEW;
END $fn$;

ALTER FUNCTION materials.deny_document_evidence_rewrite() OWNER TO evercoat_owner;

DROP TRIGGER IF EXISTS material_documents_evidence_write_once
    ON materials.material_documents;
CREATE TRIGGER material_documents_evidence_write_once
    BEFORE UPDATE ON materials.material_documents
    FOR EACH ROW
    EXECUTE FUNCTION materials.deny_document_evidence_rewrite();

COMMENT ON TRIGGER material_documents_evidence_write_once
    ON materials.material_documents IS
    'Evidence columns may be set once, at INSERT, and never changed. Closes '
    'the promote-a-legacy-row and rewrite-safety-history escalations Codex '
    'raised against migration 036. It does NOT make a first-time approval '
    'truthful -- PostgreSQL cannot verify an object store. See I61/I62/I63.';

COMMIT;


-- ---------------------------------------------------------------------
-- Prove the trigger, on a row that is NOT already approved.
-- ---------------------------------------------------------------------
DO $probe$
DECLARE
    v_blocked BOOLEAN := FALSE;
    v_id      UUID;
BEGIN
    SELECT id INTO v_id
      FROM materials.material_documents
     WHERE status <> 'approved'
     LIMIT 1;

    IF v_id IS NULL THEN
        RAISE NOTICE
            '038: no non-approved document to probe; the trigger is created '
            'but its refusal was not exercised here. tests/db covers it.';
        RETURN;
    END IF;

    BEGIN
        UPDATE materials.material_documents SET status = 'approved' WHERE id = v_id;
    EXCEPTION WHEN OTHERS THEN
        v_blocked := TRUE;
    END;

    IF NOT v_blocked THEN
        RAISE EXCEPTION
            '038: a document status was promoted to approved. The write-once '
            'trigger is not in force.';
    END IF;
END $probe$;
