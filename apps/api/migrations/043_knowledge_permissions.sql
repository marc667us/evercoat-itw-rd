-- 043_knowledge_permissions.sql
-- =====================================================================
-- The knowledge tier gets a WRITE PATH, and a write path needs a holder.
--
-- Migration 042 built `knowledge.documents` and `knowledge.chunks` with a
-- per-chunk authorization boundary, an embedder and a retrieval. Then the
-- Supervisor asked this project's standing question of it --
--
--     WHICH PRODUCTION PATH WRITES IT?
--
-- -- and the answer was NONE. `ingest_document` was reachable only from
-- `tests/db/test_042_knowledge_retrieval.py`. No route, no CLI, no job. On a
-- deployed instance the table was permanently empty, so MSD's knowledge branch
-- always fell through to the refusal and the entire slice's observable effect
-- was one extra round-trip per question. Recorded as I74.
--
-- That is the SEVENTH instance of this defect class on this platform (five
-- roles with no write path, one permission with no holder in 016, and now a
-- whole storage tier with no writer). The question that catches all of them is
-- the same one, which is why it is asked in writing every time.
--
-- ---------------------------------------------------------------------
-- CORRECTION, WRITTEN BEFORE THIS SHIPPED: THE PERMISSIONS ALREADY EXISTED.
-- ---------------------------------------------------------------------
--
-- The first draft of this header said "this migration adds the two permissions
-- the routes need". That was FALSE, and the test suite is what said so.
--
-- `knowledge.view` and `knowledge.ingest` have BOTH been in migration 002's
-- catalogue since the beginning. The INSERT below is therefore a no-op on any
-- database that has run 002 -- kept only so this file is self-contained on a
-- fresh one. What was actually missing was HOLDERS:
--
--   * `knowledge.view` was granted by 002 to the Chemist, Engineer and Lead
--     only. This adds the Director, QA, Laboratory Technician, Production
--     Engineer and Executive Viewer.
--   * `knowledge.ingest` WAS GRANTED TO NOBODY. It was a known, deliberately
--     allowlisted orphan in `tests/db/test_002_roles_permissions.py`, carrying
--     the note "Slice 8 -- Knowledge Library and RAG" and waiting for exactly
--     this migration. This is the same shape migration 019 closed for
--     `test.confirm`.
--
-- That allowlist asserts in BOTH directions, so granting the permission turned
-- the suite red naming `knowledge.ingest` -- and the entry has been removed in
-- the same commit. An allowlist that only failed on NEW orphans would have
-- gone on quietly claiming the Knowledge Library has no writer.
--
-- The routes and the screen are in the same commit as these grants. A
-- permission landing without its consumer is how 016's defect was created.
--
-- ---------------------------------------------------------------------
-- WHY `knowledge.view` IS GRANTED BROADLY, STATED RATHER THAN HIDDEN
-- ---------------------------------------------------------------------
--
-- Nine of the ten seeded roles get it, and that is deliberate: for the
-- knowledge library the permission is NOT the confidentiality boundary. RLS on
-- `knowledge.chunks` is -- every chunk carries its own organization, project
-- and classification, and a search is filtered by PostgreSQL before it ranks.
-- Two users with identical permissions see different passages, because they
-- are members of different projects.
--
-- So `knowledge.view` gates whether the SCREEN and the search endpoint exist
-- for you at all; it does not decide what they return. Pretending otherwise --
-- granting it narrowly and describing it as the control -- would be the
-- comment-claims-a-rule-that-does-not-exist defect this codebase keeps
-- finding, written into the authorization model itself.
--
-- `procurement_specialist` is the one exclusion. Its business is suppliers and
-- lots; it holds no `formula.view` and no `project.view`, so a technical
-- document library is outside the work it does. It can be added the day
-- somebody names a task that needs it.
--
-- ---------------------------------------------------------------------
-- WHY `knowledge.ingest` IS NARROW
-- ---------------------------------------------------------------------
--
-- Ingestion is not "uploading a file". It SETS THE CLASSIFICATION of text that
-- MSD will afterwards quote to whoever can retrieve it -- and the default is
-- the ceiling (`DIRECTOR_CONTROLLED`) precisely because getting it wrong in
-- the other direction is a disclosure. Choosing that value is a curation
-- decision about confidentiality, not a data-entry task.
--
-- Lead, Director, QA and Administrator hold it. Chemist and Engineer do not:
-- they are the largest population, they are the people most likely to paste in
-- a supplier PDF mid-experiment, and a mistaken `PUBLIC` on a competitor-
-- sensitive formulation note cannot be recalled once it has been quoted into
-- somebody's answer.
--
-- ⚠️ THIS IS NOT SEGREGATION OF DUTIES AND MUST NOT BE DESCRIBED AS IT. A Lead
-- may both ingest a document and retrieve it. The narrowness here buys a
-- smaller population making classification decisions, nothing more.
-- =====================================================================

BEGIN;

-- A no-op wherever 002 has run -- see the correction in the header. Present so
-- the file stands alone, and NOT re-describing the permissions: 002's
-- descriptions are the ones in the catalogue and an UPDATE here would make
-- the two files disagree about what the permission means.
INSERT INTO core.permissions (code, domain, description) VALUES
    ('knowledge.view',   'knowledge', 'Search the Knowledge Library'),
    ('knowledge.ingest', 'knowledge', 'Ingest documents into the Knowledge Library')
ON CONFLICT (code) DO NOTHING;

-- `core._grant` is created and dropped INSIDE each migration that grants, the
-- pattern 002/012/039/040 all follow -- it is scaffolding, not API, and leaving
-- it behind would be a permission-granting function sitting in the schema with
-- nothing owning it.
--
-- `core.role_permissions` is GLOBAL -- (role_id, permission_id), with no
-- organization column -- so these grants apply to every organization that
-- exists now and every one created later. There is no per-organization seeding
-- loop here, and therefore none of the "the engine was empty for every org
-- created after 020" defect that a one-time loop produced on this platform.
CREATE OR REPLACE FUNCTION core._grant(p_role TEXT, VARIADIC p_perms TEXT[])
    RETURNS VOID LANGUAGE plpgsql AS $grant$
BEGIN
    INSERT INTO core.role_permissions (role_id, permission_id)
    SELECT r.id, p.id
    FROM core.roles r
    JOIN core.permissions p ON p.code = ANY(p_perms)
    WHERE r.code = p_role
    ON CONFLICT DO NOTHING;
END
$grant$;

SELECT core._grant('product_development_chemist',  'knowledge.view');
SELECT core._grant('product_development_engineer', 'knowledge.view');
SELECT core._grant('laboratory_technician',        'knowledge.view');
SELECT core._grant('production_engineer',          'knowledge.view');
SELECT core._grant('executive_viewer',             'knowledge.view');

SELECT core._grant('product_development_lead',     'knowledge.view', 'knowledge.ingest');
SELECT core._grant('product_development_director', 'knowledge.view', 'knowledge.ingest');
SELECT core._grant('qa_compliance_officer',        'knowledge.view', 'knowledge.ingest');
SELECT core._grant('administrator',                'knowledge.view', 'knowledge.ingest');

DROP FUNCTION core._grant(TEXT, TEXT[]);

COMMIT;


-- ---------------------------------------------------------------------
-- Prove both permissions have a holder, in the migration itself.
--
-- 016 exists because a permission was defined and granted to nobody, and
-- nothing noticed for fourteen migrations. `tests/db/test_002_roles_permissions.py`
-- carries the general invariant; this is the local, immediate one.
-- ---------------------------------------------------------------------
DO $probe$
DECLARE
    v_code    TEXT;
    v_holders INT;
BEGIN
    FOREACH v_code IN ARRAY ARRAY['knowledge.view', 'knowledge.ingest'] LOOP
        SELECT count(*) INTO v_holders
          FROM core.role_permissions rp
          JOIN core.permissions p ON p.id = rp.permission_id
         WHERE p.code = v_code;

        IF v_holders = 0 THEN
            RAISE EXCEPTION
                '043: % is held by no role. A permission with no holder makes '
                'every path behind it unreachable for everyone, permanently -- '
                'which is the defect migration 016 exists to document.', v_code;
        END IF;
    END LOOP;
END $probe$;
