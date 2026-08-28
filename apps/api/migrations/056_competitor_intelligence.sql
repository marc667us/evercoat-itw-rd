-- =====================================================================
-- 056 — competitor intelligence, and ONE document register
--
-- Phase 3 of the Material Safety Data & Research Center.
--
-- ---------------------------------------------------------------------
-- 🔴 THE RULE THIS MIGRATION EXISTS TO OBEY
-- ---------------------------------------------------------------------
--
-- The specification, §14: **"Do not build a second document repository."**
--
-- A competitor product's LABEL, its photograph, its published Safety Data
-- Sheet and its technical literature are controlled documents in exactly
-- the sense `materials.material_documents` already means: bytes in object
-- storage, a checksum, a malware verdict, an expiry, a revision chain and
-- a classification. Standing a `competitors.product_documents` table up
-- beside it would fork all six of those invariants -- including 038's
-- write-once evidence rules and 037's single definition of usable -- and
-- the copy that drifted would be the one nobody looked at.
--
-- So the existing register is EXTENDED to carry a second kind of owner.
-- `material_id` becomes nullable, `competitor_product_id` appears beside
-- it, and a CHECK requires exactly one. That is additive (§36): every
-- existing row keeps a material, every existing query that filters
-- `WHERE material_id = :x` is unaffected by rows where it is NULL, and
-- the malware scan, checksum, expiry and supersession rules apply to a
-- competitor label without a line of new code.
--
-- ⚠️ THIS TABLE IS READ BY THE FORMULA-SUBMISSION GATE. `materials.usable_documents`
-- (037) decides whether a formula may be submitted, and this migration
-- recreates that view. The view's PREDICATE is unchanged -- approved,
-- scan-clean, present, unexpired, unsuperseded -- and it gains one
-- passed-through column. Nothing about which MATERIAL documents are
-- usable changes.
--
-- ---------------------------------------------------------------------
-- 🔴 THREE THINGS THE FIRST DRAFT OF THIS DESIGN GOT WRONG
-- ---------------------------------------------------------------------
--
-- Found by review before any of it was written:
--
--   (a) `supersedes_id` constrains the TENANT, not the OWNER. Once a
--       document can belong to a competitor, a competitor label could
--       supersede a material's SDS -- and because `usable_documents`
--       excludes anything with a newer approved successor, that SDS would
--       silently leave the view and change whether formula submission is
--       blocked. A trigger below requires same-owner supersession.
--
--   (b) The write-once set (038) protects the bytes and the verdict, not
--       the owner. An approved, scanned label could be re-pointed at a
--       different competitor product, carrying its clean verdict with it.
--       054 already made the safety interpretation's identity write-once
--       for the same reason; this does it for the document's owner.
--
--   (c) A composite FK from composition evidence to a document, carrying
--       the product, needs a unique key on exactly those columns. It did
--       not exist. Added below, which is what makes it possible to refuse
--       a document owned by product A being cited as evidence for
--       product B.
-- =====================================================================

BEGIN;

CREATE SCHEMA IF NOT EXISTS competitors;
ALTER SCHEMA competitors OWNER TO evercoat_owner;


-- ---------------------------------------------------------------------
-- The competitor product
-- ---------------------------------------------------------------------
--
-- `project_id` is NULLABLE and that is the specification's shape: *"A
-- competitor product or physical sample may be registered against an
-- existing Project or Product Requirement."* MAY. A competitor product is
-- usually a public thing the whole organization may see; NULL means
-- exactly that, and the RLS policy below reads it the same way
-- `knowledge.documents` does (042).
CREATE TABLE IF NOT EXISTS competitors.products (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id   UUID NOT NULL REFERENCES core.organizations (id),
    project_id        UUID,
    manufacturer      TEXT NOT NULL,
    product_name      TEXT NOT NULL,
    -- The competitor's own code for it, where we know it. Not ours.
    product_code      TEXT,
    market_segment    TEXT,
    notes             TEXT,
    registered_by     UUID NOT NULL REFERENCES core.users (id) ON DELETE RESTRICT,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    CONSTRAINT products_id_org_key UNIQUE (id, organization_id),
    -- Tenant-scoped, like every other code in this schema: a globally
    -- unique one would stop org B registering a product org A already has,
    -- and the refusal itself would disclose org A's record.
    CONSTRAINT products_org_name_key UNIQUE (organization_id, manufacturer, product_name),
    CONSTRAINT products_project_fk FOREIGN KEY (project_id, organization_id)
        REFERENCES projects.projects (id, organization_id) ON DELETE RESTRICT
);


-- ---------------------------------------------------------------------
-- ONE document register — the existing table learns a second owner
-- ---------------------------------------------------------------------
ALTER TABLE materials.material_documents
    ALTER COLUMN material_id DROP NOT NULL;

ALTER TABLE materials.material_documents
    ADD COLUMN IF NOT EXISTS competitor_product_id UUID;

-- Exactly one owner. Never zero -- a document belonging to nothing is
-- unreachable and unauditable -- and never both, which would make "whose
-- document is this" have two answers.
ALTER TABLE materials.material_documents
    DROP CONSTRAINT IF EXISTS material_documents_one_owner;
ALTER TABLE materials.material_documents
    ADD CONSTRAINT material_documents_one_owner CHECK (
        (material_id IS NOT NULL) <> (competitor_product_id IS NOT NULL)
    );

ALTER TABLE materials.material_documents
    DROP CONSTRAINT IF EXISTS material_documents_competitor_fk;
ALTER TABLE materials.material_documents
    ADD CONSTRAINT material_documents_competitor_fk
    FOREIGN KEY (competitor_product_id, organization_id)
    REFERENCES competitors.products (id, organization_id) ON DELETE RESTRICT;

-- (c) above: the unique key a product-bound composite FK needs.
ALTER TABLE materials.material_documents
    DROP CONSTRAINT IF EXISTS material_documents_id_competitor_org_key;
ALTER TABLE materials.material_documents
    ADD CONSTRAINT material_documents_id_competitor_org_key
    UNIQUE (id, competitor_product_id, organization_id);

-- The three entry modes the operator asked for, plus the literature a
-- benchmark cites. `label` and `product_image` are PEERS, not variants:
-- one is the regulatory text, the other is a photograph of the tin, and
-- they support different claims.
ALTER TABLE materials.material_documents
    DROP CONSTRAINT material_documents_document_type_check;
ALTER TABLE materials.material_documents
    ADD CONSTRAINT material_documents_document_type_check CHECK (
        document_type IN ('TDS', 'SDS', 'CoA', 'regulatory', 'other',
                          'label', 'product_image', 'literature', 'patent')
    );

CREATE INDEX IF NOT EXISTS material_documents_competitor_idx
    ON materials.material_documents (organization_id, competitor_product_id)
    WHERE competitor_product_id IS NOT NULL;


-- (a) Supersession must be same-owner.
--
-- The FK constrains the tenant only, so without this a competitor label
-- could supersede a material's SDS and remove it from `usable_documents`
-- -- changing whether a formula may be submitted. A CHECK cannot read
-- another row, so it is a trigger.
CREATE OR REPLACE FUNCTION materials.supersession_stays_with_one_owner()
    RETURNS TRIGGER
    LANGUAGE plpgsql
    SET search_path TO 'materials', 'pg_temp'
AS $same_owner$
DECLARE
    old_material   UUID;
    old_competitor UUID;
BEGIN
    IF NEW.supersedes_id IS NULL THEN
        RETURN NEW;
    END IF;

    SELECT material_id, competitor_product_id
      INTO old_material, old_competitor
      FROM materials.material_documents
     WHERE id = NEW.supersedes_id AND organization_id = NEW.organization_id;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'the superseded document % does not exist in this organization',
            NEW.supersedes_id;
    END IF;

    IF NEW.material_id IS DISTINCT FROM old_material
       OR NEW.competitor_product_id IS DISTINCT FROM old_competitor THEN
        RAISE EXCEPTION
            'a document may only supersede one belonging to the SAME owner. '
            'Superseding across owners would remove the older document from '
            'materials.usable_documents -- which decides whether a formula may '
            'be submitted -- on the strength of an unrelated upload.';
    END IF;

    RETURN NEW;
END
$same_owner$;

DROP TRIGGER IF EXISTS material_documents_supersedes_same_owner ON materials.material_documents;
CREATE TRIGGER material_documents_supersedes_same_owner
    BEFORE INSERT OR UPDATE OF supersedes_id ON materials.material_documents
    FOR EACH ROW EXECUTE FUNCTION materials.supersession_stays_with_one_owner();


-- (b) The owner joins the write-once set.
--
-- 038 protects `status`, `scan_status`, `checksum_sha256`, `byte_size` and
-- `storage_key` because "re-pointing a row at different bytes keeps the
-- old checksum and scan verdict attached to content nobody examined". The
-- same sentence is true of re-pointing a row at a different OWNER.
CREATE OR REPLACE FUNCTION materials.deny_document_owner_rewrite()
    RETURNS TRIGGER
    LANGUAGE plpgsql
    SET search_path TO 'materials', 'pg_temp'
AS $owner_write_once$
BEGIN
    IF NEW.material_id IS DISTINCT FROM OLD.material_id THEN
        RAISE EXCEPTION
            'material_documents.material_id is write-once (% -> %). Re-owning '
            'a document is superseding it; create a new row.',
            OLD.material_id, NEW.material_id;
    END IF;
    IF NEW.competitor_product_id IS DISTINCT FROM OLD.competitor_product_id THEN
        RAISE EXCEPTION
            'material_documents.competitor_product_id is write-once (% -> %). '
            'An approved, scanned label must not carry its verdict to a '
            'different product.',
            OLD.competitor_product_id, NEW.competitor_product_id;
    END IF;
    RETURN NEW;
END
$owner_write_once$;

DROP TRIGGER IF EXISTS material_documents_owner_write_once ON materials.material_documents;
CREATE TRIGGER material_documents_owner_write_once
    BEFORE UPDATE ON materials.material_documents
    FOR EACH ROW EXECUTE FUNCTION materials.deny_document_owner_rewrite();


-- ---------------------------------------------------------------------
-- `materials.usable_documents` — recreated, predicate UNCHANGED
-- ---------------------------------------------------------------------
--
-- 🔴 THE ONLY DIFFERENCE IS ONE PASSED-THROUGH COLUMN. Every clause 037
-- wrote is reproduced verbatim: approved, scan-clean, checksum and bytes
-- present, unexpired, and not superseded by an approved successor.
-- `security_invoker = true` is load-bearing and is kept -- without it the
-- view runs as `evercoat_owner` and reads across every tenant.
DROP VIEW IF EXISTS materials.usable_documents;

CREATE VIEW materials.usable_documents
    WITH (security_invoker = true) AS
SELECT id,
       organization_id,
       material_id,
       competitor_product_id,
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
   AND checksum_sha256 IS NOT NULL
   AND byte_size IS NOT NULL
   AND (expires_on IS NULL OR expires_on >= CURRENT_DATE)
   AND NOT EXISTS (
       SELECT 1 FROM materials.material_documents newer
        WHERE newer.supersedes_id = materials.material_documents.id
          AND newer.status = 'approved'
   );

-- 🔴 `DROP VIEW` DISCARDS OWNERSHIP AND GRANTS, AND BOTH MUST COME BACK.
--
-- 037 set them (`ALTER VIEW ... OWNER TO evercoat_owner`, `GRANT SELECT ...
-- TO evercoat_app, evercoat_report, evercoat_worker`) and a recreation that
-- omits them leaves a view nobody can read: 20 tests failed with "permission
-- denied for view usable_documents", including the formula-submission gate
-- and the safety trigger that reads it. The DDL succeeded; the capability
-- vanished.
ALTER VIEW materials.usable_documents OWNER TO evercoat_owner;
GRANT SELECT ON materials.usable_documents TO evercoat_app, evercoat_report, evercoat_worker;

COMMENT ON VIEW materials.usable_documents IS
    'Documents that may be relied on as evidence: stored, scanned clean, not '
    'expired, not superseded. THE ONLY thing a safety gate may count. Created '
    'by 037; extended by 056 to carry competitor_product_id, with the '
    'predicate unchanged. security_invoker=true is load-bearing: without it '
    'the view would run as evercoat_owner and read across every tenant.';


-- ---------------------------------------------------------------------
-- The physical sample
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS competitors.samples (
    id                    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id       UUID NOT NULL REFERENCES core.organizations (id),
    competitor_product_id UUID NOT NULL,
    sample_reference      TEXT NOT NULL,
    acquired_on           DATE,
    batch_marking         TEXT,
    observations          TEXT,
    registered_by         UUID NOT NULL REFERENCES core.users (id) ON DELETE RESTRICT,
    created_at            TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    CONSTRAINT samples_id_org_key UNIQUE (id, organization_id),
    CONSTRAINT samples_org_reference_key UNIQUE (organization_id, sample_reference),
    CONSTRAINT samples_product_fk FOREIGN KEY (competitor_product_id, organization_id)
        REFERENCES competitors.products (id, organization_id) ON DELETE RESTRICT
);


-- ---------------------------------------------------------------------
-- 🔴 THE COMPOSITION EVIDENCE MATRIX
-- ---------------------------------------------------------------------
--
-- The specification is unambiguous, and this table is the mechanism that
-- keeps the promise:
--
--     "The application shall NEVER automatically present an inferred
--      competitor recipe as a known or verified formula. Instead the
--      Center shall maintain a Composition Evidence Matrix that
--      distinguishes verified disclosed ingredients, laboratory-supported
--      findings, patent-supported possibilities, technical inferences,
--      model-based hypotheses, and unknown components. Each conclusion
--      shall retain its source and confidence level."
--
-- So there is no "competitor formula" table anywhere in this schema. There
-- is a list of claims, each carrying HOW it is known. Reading the matrix
-- gives a candidate composition; no row of it is ever a fact by itself.
--
-- 🔴 `evidence_source` AND `document_type` ARE DIFFERENT AXES.
--
-- An earlier design conflated them, which forced honest manual
-- transcription into a category that misdescribed it. A person reading the
-- back of a tin is not making an INFERENCE -- they are making an
-- observation, and `manual_observation` says so. What they cannot do is
-- call it `verified`, because there is no document to re-check.
CREATE TABLE IF NOT EXISTS competitors.composition_evidence (
    id                    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id       UUID NOT NULL REFERENCES core.organizations (id),
    competitor_product_id UUID NOT NULL,

    component_name        TEXT NOT NULL,
    cas_number            TEXT CHECK (cas_number IS NULL OR cas_number ~ '^[0-9]{2,7}-[0-9]{2}-[0-9]$'),
    -- What the component is FOR: resin, filler, catalyst. The whole point
    -- of benchmarking is understanding function, not just presence.
    component_function    TEXT,

    -- NUMERIC, never float (CLAUDE.md §5), and a RANGE: a label or an SDS
    -- discloses "10-25%", and a midpoint would invent precision.
    concentration_low     NUMERIC(7,4) CHECK (concentration_low IS NULL
                                              OR (concentration_low >= 0 AND concentration_low <= 100)),
    concentration_high    NUMERIC(7,4) CHECK (concentration_high IS NULL
                                              OR (concentration_high >= 0 AND concentration_high <= 100)),
    -- "the balance" is a real disclosure and is not a number.
    is_balance            BOOLEAN NOT NULL DEFAULT FALSE,

    evidence_source       TEXT NOT NULL CHECK (evidence_source IN (
                              'document', 'manual_observation', 'laboratory',
                              'literature', 'patent', 'inference', 'model')),
    -- The A-X ranking from the research source document.
    evidence_grade        TEXT NOT NULL CHECK (evidence_grade IN ('A','B','C','D','X')),
    confidence            TEXT NOT NULL DEFAULT 'possible'
                          CHECK (confidence IN ('verified','supported','probable','possible','unknown')),

    -- Typed provenance, one shape per source. See the CHECKs below.
    source_document_id    UUID,
    sample_id             UUID,
    test_id               UUID,
    -- Page, section, the quoted label field, the image region. "The SDS
    -- says so" is not evidence anybody else can re-check.
    source_locator        TEXT,
    rationale             TEXT,

    observed_by           UUID REFERENCES core.users (id) ON DELETE RESTRICT,
    verified_by           UUID REFERENCES core.users (id) ON DELETE RESTRICT,
    verified_at           TIMESTAMPTZ,
    recorded_by           UUID NOT NULL REFERENCES core.users (id) ON DELETE RESTRICT,
    created_at            TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),

    CONSTRAINT composition_evidence_id_org_key UNIQUE (id, organization_id),
    CONSTRAINT composition_evidence_product_fk
        FOREIGN KEY (competitor_product_id, organization_id)
        REFERENCES competitors.products (id, organization_id) ON DELETE RESTRICT,

    -- 🔴 THE DOCUMENT MUST BELONG TO THE SAME COMPETITOR PRODUCT.
    -- Without the product in the key, a label uploaded for product A could
    -- be cited as evidence for product B and every other constraint would
    -- still hold. This is what 056's new unique key on
    -- `material_documents` exists for.
    CONSTRAINT composition_evidence_document_fk
        FOREIGN KEY (source_document_id, competitor_product_id, organization_id)
        REFERENCES materials.material_documents (id, competitor_product_id, organization_id)
        ON DELETE RESTRICT,
    CONSTRAINT composition_evidence_sample_fk FOREIGN KEY (sample_id, organization_id)
        REFERENCES competitors.samples (id, organization_id) ON DELETE RESTRICT,
    CONSTRAINT composition_evidence_test_fk FOREIGN KEY (test_id, organization_id)
        REFERENCES testing.tests (id, organization_id) ON DELETE RESTRICT,

    CONSTRAINT composition_evidence_range_ordered CHECK (
        concentration_low IS NULL OR concentration_high IS NULL
        OR concentration_high >= concentration_low
    ),
    -- The balance is not also a range.
    CONSTRAINT composition_evidence_balance_has_no_range CHECK (
        NOT is_balance OR (concentration_low IS NULL AND concentration_high IS NULL)
    ),

    -- One shape per source, enforced rather than documented.
    CONSTRAINT composition_evidence_document_shape CHECK (
        evidence_source <> 'document' OR source_document_id IS NOT NULL
    ),
    CONSTRAINT composition_evidence_laboratory_shape CHECK (
        evidence_source <> 'laboratory' OR (sample_id IS NOT NULL OR test_id IS NOT NULL)
    ),
    -- A person's observation names the person and says what they saw.
    CONSTRAINT composition_evidence_observation_shape CHECK (
        evidence_source <> 'manual_observation'
        OR (observed_by IS NOT NULL AND rationale IS NOT NULL)
    ),
    -- Reasoning that does not say what it reasoned from is not evidence.
    CONSTRAINT composition_evidence_reasoned_shape CHECK (
        evidence_source NOT IN ('inference', 'model') OR rationale IS NOT NULL
    ),

    -- 🔴 `verified` CANNOT EXIST WITHOUT A NAME AND A TIME ON IT.
    CONSTRAINT composition_evidence_verification_complete CHECK (
        (confidence = 'verified') = (verified_by IS NOT NULL AND verified_at IS NOT NULL)
    ),
    -- ...and only a source that can be re-checked may be verified at all.
    CONSTRAINT composition_evidence_verifiable_source CHECK (
        confidence <> 'verified' OR evidence_source IN ('document', 'laboratory')
    )
);


-- 🔴 AND THE VERIFIER MUST ACTUALLY HOLD THE PERMISSION.
--
-- Every constraint above can be satisfied in one statement by anything
-- able to write the table: set `confidence`, a qualifying `evidence_source`
-- and any `verified_by`, and the row passes. A CHECK cannot join.
--
-- What the database CAN establish is whether the person named is entitled
-- to have verified it. Forging a verification then means naming a real
-- compliance officer, in the right tenant, in a row that records it.
--
-- ⚠️ STATED AS WHAT IT IS: A MISUSE BARRIER, NOT A BOUNDARY. Anything
-- already running arbitrary SQL as `evercoat_app` is inside the trust
-- boundary and nothing in the row can exclude it. This removes every
-- ACCIDENTAL path and makes the deliberate one attributable. Same
-- distinction as I109/ADR-032.
CREATE OR REPLACE FUNCTION competitors.verification_names_a_reviewer()
    RETURNS TRIGGER
    LANGUAGE plpgsql
    SET search_path TO 'competitors', 'core', 'pg_temp'
AS $verifier$
BEGIN
    IF NEW.confidence <> 'verified' THEN
        RETURN NEW;
    END IF;

    IF NOT EXISTS (
        SELECT 1
          FROM core.organization_members om
          JOIN core.member_roles mr        ON mr.member_id = om.id
          JOIN core.role_permissions rp    ON rp.role_id = mr.role_id
          JOIN core.permissions p          ON p.id = rp.permission_id
         WHERE om.user_id = NEW.verified_by
           AND om.organization_id = NEW.organization_id
           AND om.status = 'active'
           AND p.code = 'compliance.review_sds'
    ) THEN
        RAISE EXCEPTION
            'composition evidence may only be marked verified by an active '
            'member holding compliance.review_sds in this organization. A '
            'competitor recipe presented as fact is the one thing this matrix '
            'exists to prevent.';
    END IF;

    RETURN NEW;
END
$verifier$;

DROP TRIGGER IF EXISTS composition_evidence_verifier_holds_permission
    ON competitors.composition_evidence;
CREATE TRIGGER composition_evidence_verifier_holds_permission
    BEFORE INSERT OR UPDATE ON competitors.composition_evidence
    FOR EACH ROW EXECUTE FUNCTION competitors.verification_names_a_reviewer();


-- ---------------------------------------------------------------------
-- Benchmarks — measured comparison against our own work
-- ---------------------------------------------------------------------
--
-- ⚠️ IT CITES A TEST, IT DOES NOT GRADE ONE. Testing owns GREEN/YELLOW/RED
-- (§8 of the specification, and CLAUDE.md §10). This records that a
-- comparison was drawn and which real records it was drawn from.
CREATE TABLE IF NOT EXISTS competitors.benchmarks (
    id                    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id       UUID NOT NULL REFERENCES core.organizations (id),
    competitor_product_id UUID NOT NULL,
    project_id            UUID NOT NULL,
    formula_version_id    UUID,
    test_id               UUID,
    attribute             TEXT NOT NULL,
    competitor_value      TEXT,
    our_value             TEXT,
    -- In words. The arithmetic belongs to the engine (§3 rule 2), and a
    -- stored delta computed here would be a second answer to a question
    -- Testing already answers.
    gap_summary           TEXT NOT NULL,
    recorded_by           UUID NOT NULL REFERENCES core.users (id) ON DELETE RESTRICT,
    created_at            TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    CONSTRAINT benchmarks_id_org_key UNIQUE (id, organization_id),
    CONSTRAINT benchmarks_product_fk FOREIGN KEY (competitor_product_id, organization_id)
        REFERENCES competitors.products (id, organization_id) ON DELETE RESTRICT,
    CONSTRAINT benchmarks_project_fk FOREIGN KEY (project_id, organization_id)
        REFERENCES projects.projects (id, organization_id) ON DELETE RESTRICT,
    CONSTRAINT benchmarks_version_fk FOREIGN KEY (formula_version_id, organization_id)
        REFERENCES formulations.formula_versions (id, organization_id) ON DELETE RESTRICT,
    CONSTRAINT benchmarks_test_fk FOREIGN KEY (test_id, organization_id)
        REFERENCES testing.tests (id, organization_id) ON DELETE RESTRICT
);


-- ---------------------------------------------------------------------
-- Row-level security — FORCE from birth, policies first
-- ---------------------------------------------------------------------
ALTER TABLE competitors.products              ENABLE ROW LEVEL SECURITY;
ALTER TABLE competitors.samples               ENABLE ROW LEVEL SECURITY;
ALTER TABLE competitors.composition_evidence  ENABLE ROW LEVEL SECURITY;
ALTER TABLE competitors.benchmarks            ENABLE ROW LEVEL SECURITY;

-- A product may be organization-wide (`project_id IS NULL`) or scoped to a
-- project. Same predicate shape as `knowledge.documents` (042:271), in
-- BOTH halves: `USING` alone protects reads and leaves writes open,
-- because foreign-key checks bypass RLS.
DROP POLICY IF EXISTS products_scope ON competitors.products;
CREATE POLICY products_scope ON competitors.products
    USING (
        organization_id = core.current_org_id()
        AND (
            project_id IS NULL
            OR EXISTS (
                SELECT 1 FROM projects.projects p
                 WHERE p.id = competitors.products.project_id
                   AND p.organization_id = competitors.products.organization_id
                   AND (p.confidentiality = 'normal' OR core.is_project_member(p.id))
            )
        )
    );
DROP POLICY IF EXISTS products_insert ON competitors.products;
CREATE POLICY products_insert ON competitors.products
    FOR INSERT WITH CHECK (
        organization_id = core.current_org_id()
        AND (
            project_id IS NULL
            OR EXISTS (
                SELECT 1 FROM projects.projects p
                 WHERE p.id = competitors.products.project_id
                   AND p.organization_id = competitors.products.organization_id
                   AND (p.confidentiality = 'normal' OR core.is_project_member(p.id))
            )
        )
    );

-- The children inherit the product's reach through a join to it, which is
-- what keeps the answer identical without denormalising `project_id` three
-- more times.
DROP POLICY IF EXISTS samples_scope ON competitors.samples;
CREATE POLICY samples_scope ON competitors.samples
    USING (
        organization_id = core.current_org_id()
        AND EXISTS (SELECT 1 FROM competitors.products cp
                     WHERE cp.id = competitors.samples.competitor_product_id
                       AND cp.organization_id = competitors.samples.organization_id)
    );
DROP POLICY IF EXISTS samples_insert ON competitors.samples;
CREATE POLICY samples_insert ON competitors.samples
    FOR INSERT WITH CHECK (
        organization_id = core.current_org_id()
        AND EXISTS (SELECT 1 FROM competitors.products cp
                     WHERE cp.id = competitors.samples.competitor_product_id
                       AND cp.organization_id = competitors.samples.organization_id)
    );

DROP POLICY IF EXISTS composition_evidence_scope ON competitors.composition_evidence;
CREATE POLICY composition_evidence_scope ON competitors.composition_evidence
    USING (
        organization_id = core.current_org_id()
        AND EXISTS (SELECT 1 FROM competitors.products cp
                     WHERE cp.id = competitors.composition_evidence.competitor_product_id
                       AND cp.organization_id = competitors.composition_evidence.organization_id)
    );
DROP POLICY IF EXISTS composition_evidence_insert ON competitors.composition_evidence;
CREATE POLICY composition_evidence_insert ON competitors.composition_evidence
    FOR INSERT WITH CHECK (
        organization_id = core.current_org_id()
        AND EXISTS (SELECT 1 FROM competitors.products cp
                     WHERE cp.id = competitors.composition_evidence.competitor_product_id
                       AND cp.organization_id = competitors.composition_evidence.organization_id)
    );

-- A benchmark always names a project, so it always carries the predicate.
DROP POLICY IF EXISTS benchmarks_scope ON competitors.benchmarks;
CREATE POLICY benchmarks_scope ON competitors.benchmarks
    USING (
        organization_id = core.current_org_id()
        AND EXISTS (
            SELECT 1 FROM projects.projects p
             WHERE p.id = competitors.benchmarks.project_id
               AND p.organization_id = competitors.benchmarks.organization_id
               AND (p.confidentiality = 'normal' OR core.is_project_member(p.id))
        )
    );
DROP POLICY IF EXISTS benchmarks_insert ON competitors.benchmarks;
CREATE POLICY benchmarks_insert ON competitors.benchmarks
    FOR INSERT WITH CHECK (
        organization_id = core.current_org_id()
        AND EXISTS (
            SELECT 1 FROM projects.projects p
             WHERE p.id = competitors.benchmarks.project_id
               AND p.organization_id = competitors.benchmarks.organization_id
               AND (p.confidentiality = 'normal' OR core.is_project_member(p.id))
        )
    );

ALTER TABLE competitors.products              FORCE ROW LEVEL SECURITY;
ALTER TABLE competitors.samples               FORCE ROW LEVEL SECURITY;
ALTER TABLE competitors.composition_evidence  FORCE ROW LEVEL SECURITY;
ALTER TABLE competitors.benchmarks            FORCE ROW LEVEL SECURITY;


-- ---------------------------------------------------------------------
-- Indexes
-- ---------------------------------------------------------------------
CREATE INDEX IF NOT EXISTS products_project_idx
    ON competitors.products (organization_id, project_id);
CREATE INDEX IF NOT EXISTS samples_product_idx
    ON competitors.samples (organization_id, competitor_product_id);
CREATE INDEX IF NOT EXISTS composition_evidence_product_idx
    ON competitors.composition_evidence (organization_id, competitor_product_id);
CREATE INDEX IF NOT EXISTS composition_evidence_confidence_idx
    ON competitors.composition_evidence (organization_id, confidence);
CREATE INDEX IF NOT EXISTS benchmarks_product_idx
    ON competitors.benchmarks (organization_id, competitor_product_id);
CREATE INDEX IF NOT EXISTS benchmarks_version_idx
    ON competitors.benchmarks (organization_id, formula_version_id);


-- ---------------------------------------------------------------------
-- Ownership and grants
-- ---------------------------------------------------------------------
ALTER TABLE competitors.products             OWNER TO evercoat_owner;
ALTER TABLE competitors.samples              OWNER TO evercoat_owner;
ALTER TABLE competitors.composition_evidence OWNER TO evercoat_owner;
ALTER TABLE competitors.benchmarks           OWNER TO evercoat_owner;

GRANT USAGE ON SCHEMA competitors TO evercoat_app, evercoat_report;

-- 🔴 UPDATE PER COLUMN, NOT PER TABLE, for the reason 047/053 record: a
-- REVOKE against a broader grant does nothing, so the narrow grant has to
-- be the one that is written. The only update the application performs on
-- evidence is the verification transition.
GRANT SELECT, INSERT ON competitors.products             TO evercoat_app;
GRANT SELECT, INSERT ON competitors.samples              TO evercoat_app;
GRANT SELECT, INSERT ON competitors.composition_evidence TO evercoat_app;
GRANT SELECT, INSERT ON competitors.benchmarks           TO evercoat_app;
GRANT UPDATE (confidence, verified_by, verified_at)
    ON competitors.composition_evidence TO evercoat_app;

GRANT SELECT ON ALL TABLES IN SCHEMA competitors TO evercoat_report;


COMMENT ON TABLE competitors.composition_evidence IS
    'The Composition Evidence Matrix. NOT a competitor formula: a list of '
    'claims, each carrying how it is known (document / manual observation / '
    'laboratory / literature / patent / inference / model), an A-X evidence '
    'grade and a confidence. Reading it gives a candidate composition; no row '
    'is a fact on its own. "verified" requires a re-checkable source, a named '
    'verifier and a time, and a trigger requires that verifier to actually '
    'hold compliance.review_sds.';

COMMIT;
