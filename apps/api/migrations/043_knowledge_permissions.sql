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
--   * `knowledge.view` was ALREADY granted by 002 to NINE of the ten roles --
--     every one except `executive_viewer`. This migration adds that one, and
--     re-states the other grants harmlessly (`_grant` is idempotent).
--
--     🔴 A SECOND CORRECTION, AND CI IS WHAT FOUND IT. This paragraph first
--     said 002 granted it "to the Chemist, Engineer and Lead only", and the
--     block below claimed `procurement_specialist` was a deliberate exclusion
--     with a reasoned justification. Both were false. The reasoning was
--     written against the LOCAL development database, which is long-lived and
--     had drifted; CI builds from the migrations every run and reported ten
--     holders where the test asserted nine. The database in front of you is
--     not the schema -- the migrations are.
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
-- WHY `knowledge.view` IS HELD BROADLY, STATED RATHER THAN HIDDEN
-- ---------------------------------------------------------------------
--
-- All ten seeded roles hold it, and that is deliberate: for the
-- knowledge library the permission is not what separates one reader from
-- another. RLS on `knowledge.chunks` does that -- every chunk carries its own
-- organization and project, and a search is filtered by PostgreSQL before it
-- ranks. Two users with identical permissions see different passages, because
-- they are members of different projects.
--
-- So `knowledge.view` gates whether the SCREEN and the search endpoint exist
-- for you at all; it does not decide what they return.
--
-- ---------------------------------------------------------------------
-- 🔴 CORRECTION: CLASSIFICATION IS **NOT** PART OF THAT BOUNDARY.
-- ---------------------------------------------------------------------
--
-- The paragraph above used to say the chunk's RLS predicate covers
-- "organization, project and classification". Codex challenged it and it was
-- wrong: `documents_scope` and `chunks_scope` test organization and project
-- membership and NEVER look at `classification`. Grep the migrations -- not
-- one policy in this schema mentions it.
--
-- That is not an oversight to be patched here. Migration 039 §2 decides it
-- explicitly and argues it at length:
--
--     CLASSIFICATION IS NOT AN ACCESS GROUP AND NOT A PERMISSION. It is a
--     property of the DATA -- how sensitive this thing is. WHO may see it is
--     a separate question answered by permissions and project membership.
--     Collapsing the two is the §6 defect this project has already found six
--     times, a role standing in for an authorization.
--
-- There is no per-user clearance level in this schema, so a classification in
-- an RLS predicate would have nothing to compare against. Adding one would
-- merge the two axes 039 deliberately kept apart.
--
-- ⚠️ SO THE HONEST STATEMENT OF WHAT A CLASSIFICATION DOES HERE: it is a
-- HANDLING LABEL that travels with the text -- into the UI, into MSD's
-- citations, and into ADR-029's outbound gate, which is where "at most PUBLIC"
-- is actually enforced. It is NOT a read boundary, and an
-- organization-wide (`project_id IS NULL`) DIRECTOR_CONTROLLED document IS
-- readable by every `knowledge.view` holder in the organization.
--
-- The person choosing a classification at ingestion must understand that. It
-- is why `knowledge.ingest` is narrow, and why the screen must not present
-- the chip as though it were a lock.
--
-- ⚠️ THERE IS NO EXCLUSION. All ten roles end up holding `knowledge.view`.
--
-- An earlier draft of this file argued at length that `procurement_specialist`
-- was deliberately left out, on the grounds that suppliers and lots are its
-- business and a technical library is not. That argument was invented to
-- justify a state the local database happened to be in: 002 has granted
-- procurement `knowledge.view` since the beginning, alongside `msd.use`, which
-- makes sense -- supplier hazard sheets and technical datasheets are exactly
-- the `material_document` source this library holds.
--
-- `executive_viewer` is the only role this migration actually adds to, and it
-- gets it for the ordinary reason a read-only oversight role gets a read
-- permission. What separates one reader from another here is project
-- membership, not this grant.
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

-- ---------------------------------------------------------------------
-- Prove both permissions have a holder, INSIDE THE TRANSACTION.
--
-- 🔴 THIS BLOCK USED TO SIT AFTER `COMMIT;` AND COULD NOT DO ITS JOB.
--
-- The file carries its own BEGIN/COMMIT so it can be applied standalone with
-- psql; `migrations_alembic/_sql.py` strips them on the Alembic path. After
-- the COMMIT, the grants are already durable on the psql path, so a probe that
-- raised would report a state it had just finished making permanent -- a
-- guard that runs after the thing it guards. The Supervisor found it.
--
-- Above the COMMIT it aborts the transaction on both paths, which is the only
-- version of this check worth having.
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

COMMIT;
