-- =====================================================================
-- 054 — Material Safety Data: the interpretation of a document, never the
--       document
--
-- Phase 1 of the Material Safety Data & Research Center
-- (`IMPLEMENTATION_PLAN_MATERIAL_SAFETY_DATA.md`). Written after Codex
-- reviewed the plan twice and returned FAIL both times; every rule below
-- exists because one of those passes showed the previous version of it
-- was wrong.
--
-- ---------------------------------------------------------------------
-- 🔴 THE ONE RULE THIS SCHEMA EXISTS TO OBEY
-- ---------------------------------------------------------------------
--
-- **The SDS record already exists.** `materials.material_documents` (015)
-- has carried `document_type = 'SDS'`, a `supersedes_id` revision chain,
-- `issued_on`/`expires_on`, a checksum, a scanner verdict (036) and a
-- classification (039) since Slice 3. `materials.usable_documents` (037)
-- is the ONE definition of a document that may be relied on, and the
-- formula-submission gate and `agents/tools/safety.py` both read it.
--
-- So this schema stores NO storage key, NO checksum, NO expiry and NO
-- supersedes pointer. It stores what an SDS *says*, keyed to the document
-- that says it. The specification's own §20 puts it plainly: *"Do not
-- copy those into sds_records. Reference material_id."*
--
-- A second opinion about whether an SDS is valid would let formula
-- submission block while this module reports the paperwork fine. That is
-- the failure 037 was created to end, and re-creating it inside the
-- safety module would be the same defect with a better name.
--
-- ---------------------------------------------------------------------
-- 🔴 CURRENCY IS DERIVED. THERE IS NO `status` COLUMN.
-- ---------------------------------------------------------------------
--
-- The first draft had `sds_versions.status ∈ (pending_review, confirmed,
-- superseded)`. Codex was right that a mutable status is a second opinion
-- waiting to drift out of step with the view, and that only one of its
-- consumers had been thought about.
--
-- `review_state` below describes the HUMAN REVIEW WORKFLOW and nothing
-- else. It is deliberately not named `status`, so that no future reader
-- can mistake it for an answer to "is this document current". That
-- question has exactly one answer and it is a join to
-- `materials.usable_documents`.
--
-- ---------------------------------------------------------------------
-- 🔴 THE TRAP IN "ONLY INTERPRET USABLE DOCUMENTS"
-- ---------------------------------------------------------------------
--
-- `usable_documents` EXCLUDES a document that a newer approved revision
-- supersedes (037:79-84). So revision N leaves the view the instant N+1
-- is approved -- and comparing N with N+1 is the entire point of the
-- feature. A rule of "an interpretation may only exist for a usable
-- document" would therefore destroy revision comparison at the exact
-- moment it becomes possible.
--
-- Hence three separate rules, and they are not the same rule worded
-- three ways:
--
--   S1a  CREATION requires the document be usable now. Trigger below.
--   S1b  An interpretation is NEVER deleted when its document later
--        leaves the view. It becomes history. CLAUDE.md §5: never
--        cascade-delete R&D history.
--   S1c  "Current" is always a join to the view, by every consumer.
--
-- ⚠️ S1a IS NOT RACE-FREE AND DOES NOT NEED TO BE. An earlier draft
-- claimed `SELECT ... FOR SHARE` on the document closed the race. It does
-- not: a share lock on D does not conflict with INSERTing a new row D'
-- that supersedes D, nor with approving D'. Codex found that.
--
-- The race is BENIGN because of S1c. If D is superseded immediately after
-- an interpretation of it is created, the result is an interpretation of
-- a superseded document -- which is precisely the legal S1b state every
-- revision reaches when its successor lands. Nothing false is recorded,
-- and no consumer shows it as current, because they all re-join the view.
-- A lock would buy the illusion of a boundary and nothing else.
-- `test_054_material_safety.py` asserts this rather than assuming it.
-- =====================================================================

BEGIN;

CREATE SCHEMA IF NOT EXISTS safety;
ALTER SCHEMA safety OWNER TO evercoat_owner;


-- ---------------------------------------------------------------------
-- The interpretation of one SDS revision
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS safety.sds_versions (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id   UUID NOT NULL REFERENCES core.organizations (id),

    -- 🔴 THE DOCUMENT IS THE SOURCE OF TRUTH AND LIVES ELSEWHERE.
    -- One interpretation per document: a second reading of the same PDF
    -- is a correction, not a new fact, and two rows would leave "what
    -- does this SDS say" with two answers.
    document_id       UUID NOT NULL,
    material_id       UUID NOT NULL,

    -- The revision as the MANUFACTURER labels it ("Rev 4.1", "2026-03"),
    -- which is not our `supersedes_id` chain and must not be confused
    -- with it. Free text because manufacturers do not agree on a format.
    supplier_revision TEXT,
    -- Who issued the SDS. NOT the supplier we buy from -- 015 already
    -- owns that relationship -- but the legal entity named on the sheet,
    -- which for a distributed product is often a different company.
    manufacturer      TEXT,
    effective_date    DATE,

    -- 🔴 THE HUMAN REVIEW WORKFLOW. NOT DOCUMENT CURRENCY. See the header.
    -- `pending_review` is the honest default: the specification requires
    -- that where a document cannot be reliably interpreted, the data
    -- "shall remain pending technical review rather than being treated as
    -- confirmed safety data".
    review_state      TEXT NOT NULL DEFAULT 'pending_review'
                      CHECK (review_state IN ('pending_review', 'confirmed', 'rejected')),
    reviewed_by       UUID REFERENCES core.users (id) ON DELETE RESTRICT,
    reviewed_at       TIMESTAMPTZ,

    interpreted_by    UUID NOT NULL REFERENCES core.users (id) ON DELETE RESTRICT,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),

    CONSTRAINT sds_versions_id_org_key UNIQUE (id, organization_id),
    -- One interpretation per document. See above.
    CONSTRAINT sds_versions_document_key UNIQUE (document_id, organization_id),
    CONSTRAINT sds_versions_document_fk FOREIGN KEY (document_id, organization_id)
        REFERENCES materials.material_documents (id, organization_id) ON DELETE RESTRICT,
    CONSTRAINT sds_versions_material_fk FOREIGN KEY (material_id, organization_id)
        REFERENCES materials.materials (id, organization_id) ON DELETE RESTRICT,
    -- A review that happened has a reviewer and a time; one that has not
    -- has neither. Both directions, so neither half can be written alone.
    CONSTRAINT sds_versions_review_complete CHECK (
        (review_state = 'pending_review')
        = (reviewed_by IS NULL AND reviewed_at IS NULL)
    )
);


-- ---------------------------------------------------------------------
-- S1a — a trigger, because a service check cannot stop a direct INSERT
-- ---------------------------------------------------------------------
--
-- 🔴 CODEX RAISED THIS AND IT WAS RIGHT. The plan said creation was
-- "enforced in the service". A service is not what executes an INSERT
-- issued by anything else holding the `evercoat_app` connection, and the
-- db suite issues exactly such INSERTs. A rule enforced only in Python is
-- a rule the database does not have.
--
-- It also verifies the document is an SDS. Interpreting a Certificate of
-- Analysis into hazard sections would produce a confident, wrong safety
-- record, and nothing else in the schema would notice.
CREATE OR REPLACE FUNCTION safety.sds_version_needs_a_usable_document()
    RETURNS TRIGGER
    LANGUAGE plpgsql
    SET search_path TO 'safety', 'materials', 'pg_temp'
AS $sds_usable$
DECLARE
    doc_type TEXT;
    doc_material UUID;
BEGIN
    SELECT document_type, material_id
      INTO doc_type, doc_material
      FROM materials.usable_documents
     WHERE id = NEW.document_id
       AND organization_id = NEW.organization_id;

    IF NOT FOUND THEN
        RAISE EXCEPTION
            'document % is not a usable document, so it cannot be interpreted '
            'as safety data. materials.usable_documents requires: approved, '
            'scanned clean, bytes present, not expired, not superseded.',
            NEW.document_id;
    END IF;

    IF doc_type <> 'SDS' THEN
        RAISE EXCEPTION
            'document % is a %, not an SDS. Interpreting it as hazard data '
            'would record a safety fact about the wrong kind of document.',
            NEW.document_id, doc_type;
    END IF;

    -- The interpretation must be filed against the material the document
    -- actually belongs to. Two composite FKs both hold, and would still
    -- both hold if these pointed at different materials.
    IF doc_material IS DISTINCT FROM NEW.material_id THEN
        RAISE EXCEPTION
            'document % belongs to material %, not %',
            NEW.document_id, doc_material, NEW.material_id;
    END IF;

    RETURN NEW;
END
$sds_usable$;

DROP TRIGGER IF EXISTS sds_versions_document_must_be_usable ON safety.sds_versions;
CREATE TRIGGER sds_versions_document_must_be_usable
    BEFORE INSERT ON safety.sds_versions
    FOR EACH ROW EXECUTE FUNCTION safety.sds_version_needs_a_usable_document();


-- ---------------------------------------------------------------------
-- The identity of an interpretation is immutable
-- ---------------------------------------------------------------------
--
-- The column grants above stop `evercoat_app` rewriting these. This stops
-- everyone else, including the owner and any future migration that widens a
-- grant without thinking about the trigger. `document_id` and `material_id`
-- are what S1a validated at insert; letting them move afterwards would make
-- that validation a formality.
--
-- Same shape and same reasoning as 038's `deny_document_evidence_rewrite`:
-- re-pointing a record at different evidence is superseding it, and
-- supersession creates a new row.
CREATE OR REPLACE FUNCTION safety.deny_interpretation_repoint()
    RETURNS TRIGGER
    LANGUAGE plpgsql
    SET search_path TO 'safety', 'pg_temp'
AS $no_repoint$
BEGIN
    IF NEW.document_id IS DISTINCT FROM OLD.document_id THEN
        RAISE EXCEPTION
            'safety.sds_versions.document_id is write-once (% -> %). An '
            'interpretation belongs to the sheet it was read from; record a '
            'new one against the new document.', OLD.document_id, NEW.document_id;
    END IF;
    IF NEW.material_id IS DISTINCT FROM OLD.material_id THEN
        RAISE EXCEPTION
            'safety.sds_versions.material_id is write-once (% -> %). Re-filing '
            'hazard data against a different substance is not an edit.',
            OLD.material_id, NEW.material_id;
    END IF;
    RETURN NEW;
END
$no_repoint$;

DROP TRIGGER IF EXISTS sds_versions_identity_is_write_once ON safety.sds_versions;
CREATE TRIGGER sds_versions_identity_is_write_once
    BEFORE UPDATE ON safety.sds_versions
    FOR EACH ROW EXECUTE FUNCTION safety.deny_interpretation_repoint();


-- ---------------------------------------------------------------------
-- The 16 standard sections, as text
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS safety.sds_sections (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES core.organizations (id),
    sds_version_id  UUID NOT NULL,
    -- GHS/REACH number these 1..16 and the order is part of the standard,
    -- so it is stored rather than derived from insertion order.
    section_number  SMALLINT NOT NULL CHECK (section_number BETWEEN 1 AND 16),
    heading         TEXT NOT NULL,
    body            TEXT,
    CONSTRAINT sds_sections_id_org_key UNIQUE (id, organization_id),
    CONSTRAINT sds_sections_one_per_number UNIQUE (sds_version_id, section_number),
    CONSTRAINT sds_sections_version_fk FOREIGN KEY (sds_version_id, organization_id)
        REFERENCES safety.sds_versions (id, organization_id) ON DELETE RESTRICT
);


-- ---------------------------------------------------------------------
-- Hazard classification
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS safety.hazard_classifications (
    id                 UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id    UUID NOT NULL REFERENCES core.organizations (id),
    sds_version_id     UUID NOT NULL,
    hazard_class       TEXT NOT NULL,
    hazard_category    TEXT,
    -- H317, H225... Constrained in shape but not against a list: the GHS
    -- codes change with each revision of the standard, and a hard-coded
    -- list would refuse a real code from a newer sheet.
    hazard_code        TEXT CHECK (hazard_code IS NULL OR hazard_code ~ '^[HP][0-9]{3}[A-Za-z+]*$'),
    signal_word        TEXT CHECK (signal_word IS NULL OR signal_word IN ('Danger', 'Warning')),
    statement          TEXT,
    CONSTRAINT hazard_classifications_id_org_key UNIQUE (id, organization_id),
    CONSTRAINT hazard_classifications_version_fk FOREIGN KEY (sds_version_id, organization_id)
        REFERENCES safety.sds_versions (id, organization_id) ON DELETE RESTRICT
);


-- ---------------------------------------------------------------------
-- Disclosed components
-- ---------------------------------------------------------------------
--
-- 🔴 NUMERIC, NEVER FLOAT (CLAUDE.md §5). These are concentrations on a
-- controlled safety record.
--
-- ⚠️ AND THEY ARE A RANGE, NOT A VALUE. An SDS discloses "10-25%", and
-- storing the midpoint would invent a precision the manufacturer
-- deliberately withheld. `concentration_high` alone is not enough either:
-- the range is the disclosure.
CREATE TABLE IF NOT EXISTS safety.chemical_components (
    id                 UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id    UUID NOT NULL REFERENCES core.organizations (id),
    sds_version_id     UUID NOT NULL,
    component_name     TEXT NOT NULL,
    -- CAS numbers have a check digit; the format is asserted, the digit is
    -- not, because a wrong-but-well-formed CAS is a data error and not a
    -- constraint violation.
    cas_number         TEXT CHECK (cas_number IS NULL OR cas_number ~ '^[0-9]{2,7}-[0-9]{2}-[0-9]$'),
    ec_number          TEXT,
    concentration_low  NUMERIC(7,4) CHECK (concentration_low IS NULL
                                           OR (concentration_low >= 0 AND concentration_low <= 100)),
    concentration_high NUMERIC(7,4) CHECK (concentration_high IS NULL
                                           OR (concentration_high >= 0 AND concentration_high <= 100)),
    CONSTRAINT chemical_components_id_org_key UNIQUE (id, organization_id),
    CONSTRAINT chemical_components_version_fk FOREIGN KEY (sds_version_id, organization_id)
        REFERENCES safety.sds_versions (id, organization_id) ON DELETE RESTRICT,
    CONSTRAINT chemical_components_range_ordered CHECK (
        concentration_low IS NULL OR concentration_high IS NULL
        OR concentration_high >= concentration_low
    )
);


-- ---------------------------------------------------------------------
-- Storage and incompatibility — properties of the MATERIAL, not of one
-- revision
-- ---------------------------------------------------------------------
--
-- These hang off the material rather than off `sds_versions` deliberately.
-- "Store below 25 °C" and "never beside peroxides" are facts about the
-- substance in the drum. Attaching them to a revision would mean the rule
-- silently expired whenever a new sheet arrived, which is the moment it
-- matters most.
CREATE TABLE IF NOT EXISTS safety.storage_rules (
    id                 UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id    UUID NOT NULL REFERENCES core.organizations (id),
    material_id        UUID NOT NULL,
    -- Canonical unit is °C (CLAUDE.md §5: value + unit, canonical units,
    -- never free strings). The unit is not stored because it cannot vary.
    min_temperature_c  NUMERIC(6,2),
    max_temperature_c  NUMERIC(6,2),
    segregation_class  TEXT,
    shelf_life_months  SMALLINT CHECK (shelf_life_months IS NULL OR shelf_life_months > 0),
    requirement        TEXT NOT NULL,
    -- Which sheet said so. Nullable: a storage rule may also come from an
    -- internal standard, and forcing an SDS would make those unrecordable.
    sds_version_id     UUID,
    recorded_by        UUID NOT NULL REFERENCES core.users (id) ON DELETE RESTRICT,
    created_at         TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    CONSTRAINT storage_rules_id_org_key UNIQUE (id, organization_id),
    CONSTRAINT storage_rules_material_fk FOREIGN KEY (material_id, organization_id)
        REFERENCES materials.materials (id, organization_id) ON DELETE RESTRICT,
    CONSTRAINT storage_rules_version_fk FOREIGN KEY (sds_version_id, organization_id)
        REFERENCES safety.sds_versions (id, organization_id) ON DELETE RESTRICT,
    CONSTRAINT storage_rules_temperature_ordered CHECK (
        min_temperature_c IS NULL OR max_temperature_c IS NULL
        OR max_temperature_c >= min_temperature_c
    )
);


CREATE TABLE IF NOT EXISTS safety.incompatibility_rules (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id     UUID NOT NULL REFERENCES core.organizations (id),
    material_id         UUID NOT NULL,
    -- Either a named material we also hold, or a hazard class. Exactly one
    -- -- a rule naming neither says nothing, and a rule naming both is two
    -- rules wearing one row.
    incompatible_with_material_id UUID,
    incompatible_hazard_class     TEXT,
    severity            TEXT NOT NULL
                        CHECK (severity IN ('prohibited', 'segregate', 'caution')),
    consequence         TEXT NOT NULL,
    sds_version_id      UUID,
    recorded_by         UUID NOT NULL REFERENCES core.users (id) ON DELETE RESTRICT,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    CONSTRAINT incompatibility_rules_id_org_key UNIQUE (id, organization_id),
    CONSTRAINT incompatibility_rules_material_fk FOREIGN KEY (material_id, organization_id)
        REFERENCES materials.materials (id, organization_id) ON DELETE RESTRICT,
    CONSTRAINT incompatibility_rules_other_fk
        FOREIGN KEY (incompatible_with_material_id, organization_id)
        REFERENCES materials.materials (id, organization_id) ON DELETE RESTRICT,
    CONSTRAINT incompatibility_rules_version_fk FOREIGN KEY (sds_version_id, organization_id)
        REFERENCES safety.sds_versions (id, organization_id) ON DELETE RESTRICT,
    CONSTRAINT incompatibility_rules_one_target CHECK (
        (incompatible_with_material_id IS NOT NULL) <> (incompatible_hazard_class IS NOT NULL)
    ),
    -- A material is not incompatible with itself, and a row saying so would
    -- quarantine it against every use.
    CONSTRAINT incompatibility_rules_not_self CHECK (
        incompatible_with_material_id IS NULL OR incompatible_with_material_id <> material_id
    )
);


-- ---------------------------------------------------------------------
-- Safety reviews — the controlled human act
-- ---------------------------------------------------------------------
--
-- ⚠️ `project_id` IS NOT NULL, AND THAT IS FORCED BY THE APPROVAL ENGINE.
-- `approvals.open_route` (domains/approvals/service.py:103) takes
-- `project_id` as a required argument. A review with no project could
-- never open a route, so it would be a review that cannot be approved --
-- a control pointing at inert workflow.
--
-- An SDS revision affecting four projects therefore produces four
-- reviews, which is also right on its own terms: each project's lead
-- approves for their own work, and a single organization-wide sign-off
-- would let one person clear a change for a restricted project they
-- cannot even see.
-- 🔴 THIS TABLE HAS NO STATUS COLUMN, AND THAT IS THE SECOND TIME THIS
-- MIGRATION MAKES THAT CHOICE.
--
-- The first draft gave it `review_state ∈ (open, cleared, action_required,
-- cancelled)` plus `closed_by`/`closed_at`. Codex found that NOTHING EVER
-- UPDATED IT: the approval route could be approved through `/approvals` while
-- the safety review sat at `open` for ever, and the migration's own header
-- claimed there was "no second notion of signed off". That claim was false.
--
-- A safety review IS its approval route. The route already has a status
-- (`open`/`approved`/`rejected`/`cancelled`), a decision per rung, a decider,
-- a timestamp and a rationale -- everything a closure state would have
-- duplicated and eventually contradicted. `approvals.route_for_entity(
-- 'safety_review', <id>)` is how the status is read, exactly as every other
-- entity in the engine reads it.
--
-- So this row records only what the ROUTE cannot: which revision, which
-- project, and why somebody opened it.
CREATE TABLE IF NOT EXISTS safety.safety_reviews (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id   UUID NOT NULL REFERENCES core.organizations (id),
    sds_version_id    UUID NOT NULL,
    project_id        UUID NOT NULL,
    reason            TEXT NOT NULL,
    opened_by         UUID NOT NULL REFERENCES core.users (id) ON DELETE RESTRICT,
    opened_at         TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    CONSTRAINT safety_reviews_id_org_key UNIQUE (id, organization_id),
    CONSTRAINT safety_reviews_version_fk FOREIGN KEY (sds_version_id, organization_id)
        REFERENCES safety.sds_versions (id, organization_id) ON DELETE RESTRICT,
    CONSTRAINT safety_reviews_project_fk FOREIGN KEY (project_id, organization_id)
        REFERENCES projects.projects (id, organization_id) ON DELETE RESTRICT,
    -- ONE review per revision per project, full stop -- not "one OPEN review",
    -- because there is no longer a state to qualify it with. A second would
    -- let two people decide the same change with no answer to which governed,
    -- and `approval_routes` enforces one open route per entity anyway (020's
    -- EXCLUDE constraint), so a second review would be undecidable in any case.
    CONSTRAINT safety_reviews_one_per_project
        UNIQUE (organization_id, sds_version_id, project_id)
);


-- ---------------------------------------------------------------------
-- Safety alerts — what a revision actually hit
-- ---------------------------------------------------------------------
--
-- 🔴 NO POLYMORPHIC (entity_type, entity_id) POINTER. Codex raised this
-- as a P1 and it was right: a text discriminator plus a bare UUID has no
-- referential integrity, so an alert can outlive, or never have matched,
-- the thing it claims to be about.
--
-- Typed, tenant-qualified, nullable columns instead, with a CHECK that at
-- least one is present. An alert attached to nothing is not an alert.
CREATE TABLE IF NOT EXISTS safety.safety_alerts (
    id                 UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id    UUID NOT NULL REFERENCES core.organizations (id),
    sds_version_id     UUID NOT NULL,
    project_id         UUID NOT NULL,

    -- What was hit. At least one, by CHECK.
    material_id        UUID,
    formula_version_id UUID,
    batch_id           UUID,

    severity           TEXT NOT NULL CHECK (severity IN ('critical', 'high', 'informational')),
    -- What CHANGED, in words, from `compare_revisions`. Not a verdict:
    -- `agents/tools/safety.py` established the rule that this platform
    -- reports record state and never assesses hazard, and this module
    -- inherits it. "H317 was added in revision 4.1" is a fact. "This is
    -- now unsafe at 4%" is a compliance determination and belongs to the
    -- `compliance.review_sds` holder.
    change_summary     TEXT NOT NULL,
    acknowledged_by    UUID REFERENCES core.users (id) ON DELETE RESTRICT,
    acknowledged_at    TIMESTAMPTZ,
    created_at         TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),

    CONSTRAINT safety_alerts_id_org_key UNIQUE (id, organization_id),
    CONSTRAINT safety_alerts_version_fk FOREIGN KEY (sds_version_id, organization_id)
        REFERENCES safety.sds_versions (id, organization_id) ON DELETE RESTRICT,
    CONSTRAINT safety_alerts_project_fk FOREIGN KEY (project_id, organization_id)
        REFERENCES projects.projects (id, organization_id) ON DELETE RESTRICT,
    CONSTRAINT safety_alerts_material_fk FOREIGN KEY (material_id, organization_id)
        REFERENCES materials.materials (id, organization_id) ON DELETE RESTRICT,
    CONSTRAINT safety_alerts_version_target_fk FOREIGN KEY (formula_version_id, organization_id)
        REFERENCES formulations.formula_versions (id, organization_id) ON DELETE RESTRICT,
    CONSTRAINT safety_alerts_batch_fk FOREIGN KEY (batch_id, organization_id)
        REFERENCES laboratory.batches (id, organization_id) ON DELETE RESTRICT,
    -- 🔴 ONE ALERT PER REVISION PER PROJECT. Raising alerts was not
    -- idempotent: the "Compare and raise alerts" control stays enabled after
    -- success and nothing in the list it reads from changes, so a second press
    -- created a duplicate row per project AND fired a second actionable
    -- notification at every project lead. A lead who is told twice learns to
    -- read the alert less carefully, which is the opposite of the point.
    -- Found by the Supervisor review.
    CONSTRAINT safety_alerts_one_per_project UNIQUE (organization_id, sds_version_id, project_id),
    CONSTRAINT safety_alerts_hits_something CHECK (
        material_id IS NOT NULL OR formula_version_id IS NOT NULL OR batch_id IS NOT NULL
    ),
    CONSTRAINT safety_alerts_acknowledgement_complete CHECK (
        (acknowledged_by IS NULL) = (acknowledged_at IS NULL)
    )
);


-- ---------------------------------------------------------------------
-- Row-level security
-- ---------------------------------------------------------------------
--
-- 🔴 `FORCE ROW LEVEL SECURITY` FROM BIRTH, WHICH THE OLDER TABLES DO NOT
-- HAVE.
--
-- CLAUDE.md §5 requires it of every proprietary table. The existing tables
-- have not cut over because I56/I58 carries an owed measurement about
-- `core.authorization_for_current_session()` reading six `core` tables as
-- `evercoat_owner`. **That reason does not apply to a table being created
-- today**: nothing owner-side reads these, so there is nothing to measure
-- and no cutover to stage. A new table born without FORCE would be one
-- more row on that backlog, added deliberately.
--
-- ⚠️ POLICIES ARE INSTALLED BEFORE FORCE IS ENABLED, in this order, in one
-- transaction. FORCE with no policy denies everything including the owner,
-- and the migration itself would be unable to verify its own work.
ALTER TABLE safety.sds_versions            ENABLE ROW LEVEL SECURITY;
ALTER TABLE safety.sds_sections            ENABLE ROW LEVEL SECURITY;
ALTER TABLE safety.hazard_classifications  ENABLE ROW LEVEL SECURITY;
ALTER TABLE safety.chemical_components     ENABLE ROW LEVEL SECURITY;
ALTER TABLE safety.storage_rules           ENABLE ROW LEVEL SECURITY;
ALTER TABLE safety.incompatibility_rules   ENABLE ROW LEVEL SECURITY;
ALTER TABLE safety.safety_reviews          ENABLE ROW LEVEL SECURITY;
ALTER TABLE safety.safety_alerts           ENABLE ROW LEVEL SECURITY;

-- Organization-scoped tables. A material is organization-wide, so there is
-- no project predicate to apply and inventing one would hide hazard data
-- from people who need it.
DROP POLICY IF EXISTS sds_versions_scope ON safety.sds_versions;
CREATE POLICY sds_versions_scope ON safety.sds_versions
    USING (organization_id = core.current_org_id());
DROP POLICY IF EXISTS sds_versions_insert ON safety.sds_versions;
CREATE POLICY sds_versions_insert ON safety.sds_versions
    FOR INSERT WITH CHECK (organization_id = core.current_org_id());

DROP POLICY IF EXISTS sds_sections_scope ON safety.sds_sections;
CREATE POLICY sds_sections_scope ON safety.sds_sections
    USING (organization_id = core.current_org_id());
DROP POLICY IF EXISTS sds_sections_insert ON safety.sds_sections;
CREATE POLICY sds_sections_insert ON safety.sds_sections
    FOR INSERT WITH CHECK (organization_id = core.current_org_id());

DROP POLICY IF EXISTS hazard_classifications_scope ON safety.hazard_classifications;
CREATE POLICY hazard_classifications_scope ON safety.hazard_classifications
    USING (organization_id = core.current_org_id());
DROP POLICY IF EXISTS hazard_classifications_insert ON safety.hazard_classifications;
CREATE POLICY hazard_classifications_insert ON safety.hazard_classifications
    FOR INSERT WITH CHECK (organization_id = core.current_org_id());

DROP POLICY IF EXISTS chemical_components_scope ON safety.chemical_components;
CREATE POLICY chemical_components_scope ON safety.chemical_components
    USING (organization_id = core.current_org_id());
DROP POLICY IF EXISTS chemical_components_insert ON safety.chemical_components;
CREATE POLICY chemical_components_insert ON safety.chemical_components
    FOR INSERT WITH CHECK (organization_id = core.current_org_id());

DROP POLICY IF EXISTS storage_rules_scope ON safety.storage_rules;
CREATE POLICY storage_rules_scope ON safety.storage_rules
    USING (organization_id = core.current_org_id());
DROP POLICY IF EXISTS storage_rules_insert ON safety.storage_rules;
CREATE POLICY storage_rules_insert ON safety.storage_rules
    FOR INSERT WITH CHECK (organization_id = core.current_org_id());

DROP POLICY IF EXISTS incompatibility_rules_scope ON safety.incompatibility_rules;
CREATE POLICY incompatibility_rules_scope ON safety.incompatibility_rules
    USING (organization_id = core.current_org_id());
DROP POLICY IF EXISTS incompatibility_rules_insert ON safety.incompatibility_rules;
CREATE POLICY incompatibility_rules_insert ON safety.incompatibility_rules
    FOR INSERT WITH CHECK (organization_id = core.current_org_id());

-- 🔴 REVIEWS AND ALERTS CARRY A PROJECT, SO THEY CARRY THE PROJECT
-- PREDICATE -- the same one `knowledge.documents` uses (042:271) and the
-- same one migration 006 established. SECURITY.md §3 is explicit that
-- permission and resource scope are separate gates; holding
-- `compliance.review_sds` says a role may review, not that they may see a
-- restricted project's work.
DROP POLICY IF EXISTS safety_reviews_scope ON safety.safety_reviews;
CREATE POLICY safety_reviews_scope ON safety.safety_reviews
    USING (
        organization_id = core.current_org_id()
        AND EXISTS (
            SELECT 1 FROM projects.projects p
             WHERE p.id = safety.safety_reviews.project_id
               AND p.organization_id = safety.safety_reviews.organization_id
               AND (p.confidentiality = 'normal' OR core.is_project_member(p.id))
        )
    );
-- 🔴 THE `WITH CHECK` CARRIES THE PROJECT PREDICATE TOO, NOT JUST THE TENANT.
--
-- The first draft checked `organization_id` alone. Codex found the gap and it
-- is real: FOREIGN KEY checks bypass RLS, so a connection that cannot READ a
-- restricted project could still INSERT a row naming it -- writing a safety
-- review onto work it is not a member of, and being unable to see what it had
-- written. `USING` without a matching `WITH CHECK` protects reads and leaves
-- writes open, which is the shape migration 005 was created to fix elsewhere.
DROP POLICY IF EXISTS safety_reviews_insert ON safety.safety_reviews;
CREATE POLICY safety_reviews_insert ON safety.safety_reviews
    FOR INSERT WITH CHECK (
        organization_id = core.current_org_id()
        AND EXISTS (
            SELECT 1 FROM projects.projects p
             WHERE p.id = safety.safety_reviews.project_id
               AND p.organization_id = safety.safety_reviews.organization_id
               AND (p.confidentiality = 'normal' OR core.is_project_member(p.id))
        )
    );

DROP POLICY IF EXISTS safety_alerts_scope ON safety.safety_alerts;
CREATE POLICY safety_alerts_scope ON safety.safety_alerts
    USING (
        organization_id = core.current_org_id()
        AND EXISTS (
            SELECT 1 FROM projects.projects p
             WHERE p.id = safety.safety_alerts.project_id
               AND p.organization_id = safety.safety_alerts.organization_id
               AND (p.confidentiality = 'normal' OR core.is_project_member(p.id))
        )
    );
-- The same gap, the same fix. See safety_reviews_insert above.
DROP POLICY IF EXISTS safety_alerts_insert ON safety.safety_alerts;
CREATE POLICY safety_alerts_insert ON safety.safety_alerts
    FOR INSERT WITH CHECK (
        organization_id = core.current_org_id()
        AND EXISTS (
            SELECT 1 FROM projects.projects p
             WHERE p.id = safety.safety_alerts.project_id
               AND p.organization_id = safety.safety_alerts.organization_id
               AND (p.confidentiality = 'normal' OR core.is_project_member(p.id))
        )
    );

-- Now, and only now.
ALTER TABLE safety.sds_versions            FORCE ROW LEVEL SECURITY;
ALTER TABLE safety.sds_sections            FORCE ROW LEVEL SECURITY;
ALTER TABLE safety.hazard_classifications  FORCE ROW LEVEL SECURITY;
ALTER TABLE safety.chemical_components     FORCE ROW LEVEL SECURITY;
ALTER TABLE safety.storage_rules           FORCE ROW LEVEL SECURITY;
ALTER TABLE safety.incompatibility_rules   FORCE ROW LEVEL SECURITY;
ALTER TABLE safety.safety_reviews          FORCE ROW LEVEL SECURITY;
ALTER TABLE safety.safety_alerts           FORCE ROW LEVEL SECURITY;


-- ---------------------------------------------------------------------
-- Indexes — every FK used in a join, plus the queues
-- ---------------------------------------------------------------------
CREATE INDEX IF NOT EXISTS sds_versions_material_idx
    ON safety.sds_versions (organization_id, material_id);
CREATE INDEX IF NOT EXISTS sds_versions_review_idx
    ON safety.sds_versions (organization_id, review_state);
CREATE INDEX IF NOT EXISTS sds_sections_version_idx
    ON safety.sds_sections (sds_version_id, section_number);
CREATE INDEX IF NOT EXISTS hazard_classifications_version_idx
    ON safety.hazard_classifications (sds_version_id);
CREATE INDEX IF NOT EXISTS chemical_components_version_idx
    ON safety.chemical_components (sds_version_id);
CREATE INDEX IF NOT EXISTS chemical_components_cas_idx
    ON safety.chemical_components (organization_id, cas_number);
CREATE INDEX IF NOT EXISTS storage_rules_material_idx
    ON safety.storage_rules (organization_id, material_id);
CREATE INDEX IF NOT EXISTS incompatibility_rules_material_idx
    ON safety.incompatibility_rules (organization_id, material_id);
CREATE INDEX IF NOT EXISTS incompatibility_rules_other_idx
    ON safety.incompatibility_rules (organization_id, incompatible_with_material_id);
CREATE INDEX IF NOT EXISTS safety_reviews_queue_idx
    ON safety.safety_reviews (organization_id, opened_at DESC);
CREATE INDEX IF NOT EXISTS safety_reviews_project_idx
    ON safety.safety_reviews (organization_id, project_id);
-- The landing page's list: unacknowledged first, newest first.
CREATE INDEX IF NOT EXISTS safety_alerts_open_idx
    ON safety.safety_alerts (organization_id, created_at DESC)
    WHERE acknowledged_at IS NULL;
CREATE INDEX IF NOT EXISTS safety_alerts_project_idx
    ON safety.safety_alerts (organization_id, project_id);
CREATE INDEX IF NOT EXISTS safety_alerts_version_idx
    ON safety.safety_alerts (sds_version_id);


-- ---------------------------------------------------------------------
-- Ownership and grants
-- ---------------------------------------------------------------------
--
-- Migration 014's rule: every object in an application schema belongs to
-- `evercoat_owner`. CREATE TABLE leaves it owned by whoever ran the
-- migration -- `postgres` here and in CI -- and the owner role then cannot
-- read its own tables.
ALTER TABLE safety.sds_versions            OWNER TO evercoat_owner;
ALTER TABLE safety.sds_sections            OWNER TO evercoat_owner;
ALTER TABLE safety.hazard_classifications  OWNER TO evercoat_owner;
ALTER TABLE safety.chemical_components     OWNER TO evercoat_owner;
ALTER TABLE safety.storage_rules           OWNER TO evercoat_owner;
ALTER TABLE safety.incompatibility_rules   OWNER TO evercoat_owner;
ALTER TABLE safety.safety_reviews          OWNER TO evercoat_owner;
ALTER TABLE safety.safety_alerts           OWNER TO evercoat_owner;
ALTER FUNCTION safety.sds_version_needs_a_usable_document() OWNER TO evercoat_owner;
ALTER FUNCTION safety.deny_interpretation_repoint() OWNER TO evercoat_owner;

GRANT USAGE ON SCHEMA safety TO evercoat_app, evercoat_report;

-- 🔴 UPDATE IS GRANTED PER COLUMN, NOT PER TABLE.
--
-- The first version granted table-level UPDATE on all eight, which handed
-- `evercoat_app` the ability to rewrite the very columns the S1a trigger
-- exists to protect. A `BEFORE INSERT` trigger says nothing about UPDATE, so
-- `UPDATE safety.sds_versions SET document_id = <an expired CoA>` would have
-- defeated every S1a invariant after the fact -- the composite FKs still hold,
-- so nothing raises -- and `current_safety_position` would then render hazard
-- data for the wrong substance as the current position.
--
-- ⚠️ ISSUED INSTEAD OF THE TABLE-LEVEL GRANT, NEVER AFTER IT. 047 and 053 both
-- record the same lesson: **a REVOKE against a broader grant does nothing**, so
-- narrowing has to be the grant that is written, not a correction applied to
-- one. Assert the resulting PRIVILEGE, never the statement.
--
-- Six of the eight are INSERT-only because nothing updates them: a reading is
-- a reading, and a correction is a new document.
GRANT SELECT, INSERT ON safety.sds_versions           TO evercoat_app;
GRANT SELECT, INSERT ON safety.sds_sections           TO evercoat_app;
GRANT SELECT, INSERT ON safety.hazard_classifications TO evercoat_app;
GRANT SELECT, INSERT ON safety.chemical_components    TO evercoat_app;
GRANT SELECT, INSERT ON safety.storage_rules          TO evercoat_app;
GRANT SELECT, INSERT ON safety.incompatibility_rules  TO evercoat_app;
GRANT SELECT, INSERT ON safety.safety_reviews         TO evercoat_app;
GRANT SELECT, INSERT ON safety.safety_alerts          TO evercoat_app;

-- The only two updates the application performs: a reviewer's verdict on a
-- transcription, and a reader acknowledging an alert.
GRANT UPDATE (review_state, reviewed_by, reviewed_at)
    ON safety.sds_versions TO evercoat_app;
GRANT UPDATE (acknowledged_by, acknowledged_at)
    ON safety.safety_alerts TO evercoat_app;

-- 🔴 NO DELETE, ANYWHERE. CLAUDE.md §5: never cascade-delete R&D history;
-- retire with a status. An interpretation of a superseded sheet is exactly
-- the history that makes revision comparison possible (S1b), and a DELETE
-- privilege is the one way to lose it.
GRANT SELECT ON ALL TABLES IN SCHEMA safety TO evercoat_report;


COMMENT ON TABLE safety.sds_versions IS
    'The INTERPRETATION of one SDS revision. The document itself, its '
    'validity, its revision chain and its classification belong to '
    'materials.material_documents, and materials.usable_documents is the '
    'only definition of usable. This table stores what the sheet SAYS. '
    'It has no status column on purpose: currency is a join to the view, '
    'never a stored opinion. review_state describes the human review '
    'workflow and nothing else.';

COMMENT ON TABLE safety.safety_alerts IS
    'What a revision hit: materials, formula versions and open batches, '
    'found through materials.material_usage(). Typed nullable FKs rather '
    'than a polymorphic (entity_type, entity_id) pair, so an alert cannot '
    'point at something that does not exist. Reports the CHANGE, never a '
    'hazard verdict -- that is the compliance.review_sds holder''s act.';

COMMIT;
