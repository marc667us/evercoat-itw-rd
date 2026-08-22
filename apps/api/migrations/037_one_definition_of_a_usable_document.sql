-- =====================================================================
-- 037 — one definition of a usable document
--
-- Completes I41. 036 made it impossible for a row to claim bytes it does not
-- have; this makes every reader ask the same question about them.
--
-- ---------------------------------------------------------------------
-- WHY A VIEW AND NOT FOUR PREDICATES
-- ---------------------------------------------------------------------
--
-- Four queries count SDS documents, across two modules:
--
--   app/domains/formulations/service.py:1212   the submission safety gate
--   app/agents/tools/safety.py:65, 69, 106     what MSD tells a chemist
--
-- Copying `status = 'approved' AND scan_status = 'clean'` into each is this
-- repository's single most repeated defect -- "two literals in two files
-- cannot be type-checked into agreement" -- and here the two files are the one
-- that BLOCKS a submission and the one that TELLS A CHEMIST whether it will.
-- Those disagreeing is worse than either being wrong alone: the application
-- would refuse a formula while the assistant said the paperwork was in order.
--
-- So the definition lives in the database, and a future reader (a report, the
-- Research Center, an export) gets it right by default rather than by
-- remembering.
--
-- ---------------------------------------------------------------------
-- 🔴 security_invoker = true, AND IT IS LOAD-BEARING
-- ---------------------------------------------------------------------
--
-- By default a view executes with the privileges of its OWNER, which here is
-- `evercoat_owner` -- the role that is exempt from RLS because it owns the
-- tables and FORCE is not enabled (migration 032). A view created without this
-- option would therefore be a **cross-tenant read path**: every caller would
-- see every organization's documents through it, and it would look like an
-- ordinary view.
--
-- That is the same shape as the `is_project_member` hazard recorded as I56.
-- `security_invoker = true` (PostgreSQL 15+; this server is 16.14) makes the
-- view run as the CALLER, so `material_documents`' own RLS policy applies
-- exactly as it does to a direct query.
-- =====================================================================

BEGIN;

DROP VIEW IF EXISTS materials.usable_documents;

CREATE VIEW materials.usable_documents
    WITH (security_invoker = true) AS
SELECT id,
       organization_id,
       material_id,
       document_type,
       title,
       storage_key,
       content_type,
       byte_size,
       checksum_sha256,
       issued_on,
       expires_on,
       supersedes_id,
       uploaded_by,
       original_filename,
       scanner_name,
       scanner_version,
       scanned_at,
       created_at
  FROM materials.material_documents
 WHERE status      = 'approved'
   AND scan_status = 'clean'
   -- Belt and braces. 036's CHECK already makes this true of every approved
   -- row, so it can only ever be redundant -- which is the point: if that
   -- constraint is ever weakened, the safety gate does not silently widen
   -- with it.
   AND checksum_sha256 IS NOT NULL
   AND byte_size IS NOT NULL
   -- An expired Safety Data Sheet is not current hazard documentation.
   -- Nothing enforced this before, because nothing could: there were no
   -- documents.
   AND (expires_on IS NULL OR expires_on >= CURRENT_DATE)
   -- A superseded revision is history, not the answer to "what is on file".
   AND NOT EXISTS (
       SELECT 1 FROM materials.material_documents newer
        WHERE newer.supersedes_id = materials.material_documents.id
          AND newer.status = 'approved'
   );

COMMENT ON VIEW materials.usable_documents IS
    'Documents that may be relied on as evidence: stored, scanned clean, not '
    'expired, not superseded. THE ONLY thing a safety gate may count. Created '
    'by migration 037 because four queries in two modules were counting raw '
    'material_documents rows -- including the one that BLOCKS formula '
    'submission and the one that TELLS a chemist whether it will. '
    'security_invoker=true is load-bearing: without it the view would run as '
    'evercoat_owner and read across every tenant.';

-- Migration 014's rule: every object in an application schema belongs to
-- evercoat_owner, so the tenancy suite (which connects as that role) can reach
-- it. Caught by test_object_ownership, which is exactly what it is for --
-- CREATE VIEW leaves the view owned by whoever ran the migration, and CI runs
-- migrations as `postgres`.
ALTER VIEW materials.usable_documents OWNER TO evercoat_owner;

GRANT SELECT ON materials.usable_documents TO evercoat_app, evercoat_report, evercoat_worker;

COMMIT;


-- ---------------------------------------------------------------------
-- Prove security_invoker actually took. A view that silently ran as its
-- owner would be a cross-tenant read path that looks like an ordinary view.
-- ---------------------------------------------------------------------
DO $$
DECLARE
    v_options TEXT;
BEGIN
    SELECT array_to_string(reloptions, ',') INTO v_options
      FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
     WHERE n.nspname = 'materials' AND c.relname = 'usable_documents';

    IF v_options IS NULL OR v_options NOT ILIKE '%security_invoker=true%' THEN
        RAISE EXCEPTION
            'materials.usable_documents does not have security_invoker=true '
            '(reloptions: %). It would execute as evercoat_owner, which is '
            'exempt from RLS, making the view a cross-tenant read path.',
            COALESCE(v_options, '<none>');
    END IF;
END $$;
