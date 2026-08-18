-- 015_materials_suppliers_formulations.sql
-- =====================================================================
-- Slice 3, back half -- the tables the calculation engine and the three
-- shipped web pages have been standing on nothing.
--
-- WHY THIS MIGRATION EXISTS, STATED PLAINLY. `apps/web` already ships
-- /materials, /suppliers and /formulations/[code]. The formulation
-- engine already exists, is pure, is property-tested, and is the single
-- owner of the arithmetic. Between them there was no schema: no
-- `materials`, no `suppliers`, no `formulas`, no `formula_versions`, no
-- `formula_components`, no route, no service. The figures on the live
-- site are baked at BUILD time by `scripts/build_demo_formulations.py`,
-- which is honest but is a demonstration, not a product.
--
-- That is this codebase's most-repeated defect running in its other
-- direction: normally a table exists with no write path; here a screen
-- exists with no table. The question is the same one -- WHICH PRODUCTION
-- PATH WRITES THIS? -- and until this migration the answer for every
-- figure on the formulation workspace was "a build script".
--
-- ONE VOCABULARY, NOT THREE. The status and role literals below are
-- taken from `apps/web/lib/demo/demo-data.json`, which the web pages
-- already render, rather than invented here. Two literals in two files
-- that nothing can check against each other is the recurring root cause
-- in this repository (nav vs router, landing vs pack, release.yml vs
-- _deploy-render.yml). `tests/db/test_015_materials_formulations.py`
-- compares these CHECK constraints against that JSON, so the two cannot
-- drift in silence.
--
-- Every rule migrations 001 and 003 established holds here without
-- exception:
--   * UNIQUE (id, organization_id) on every tenant-scoped table
--   * composite child->parent FKs carrying every scoping column
--   * RLS on organization AND, for project-owned rows, membership
--   * RESTRICT, never CASCADE, on anything holding R&D history
--   * NUMERIC for measured quantities, never float
--
-- THE THREE-COLUMN KEY, AND WHY IT IS NOT PARANOIA. A formula belongs to
-- a project; its versions and their components inherit that project. A
-- two-column (id, organization_id) FK proves a version cannot be attached
-- to another TENANT's formula and says nothing about whether it can be
-- attached to another PROJECT's formula inside the same tenant -- which
-- is exactly the confidentiality boundary /formulations exists to
-- respect. So `formulas` also carries UNIQUE (id, project_id,
-- organization_id) and the children reference all three columns. RLS
-- cannot do this job: referential integrity bypasses RLS even under
-- FORCE, so a reference is not a read.
--
-- PARTS
--   1  Administration section 3 -- units, product families (config rows)
--   2  Materials -- library, documents, lots
--   3  Suppliers -- and the M:M with materials
--   4  Formulations -- formulas, versions, components
--   5  Immutability, enforced in the database (CLAUDE.md section 8)
--   6  Indexes, RLS, ownership, grants
-- =====================================================================

BEGIN;

-- ---------------------------------------------------------------------
-- PART 1 -- Administration section 3: units and product families
-- ---------------------------------------------------------------------
-- IMPLEMENTATION_PLAN.md section H: "A configuration value referenced
-- anywhere in this plan must have an Administration screen in the same
-- slice or earlier, and the slice gate checks that." Units and product
-- families are named there as Slice 3's Administration section.
--
-- They are config ROWS, not a Python enum and not a CHECK constraint, for
-- the same reason pipeline stages are: a deployment adds a product family
-- without a migration.
--
-- `projects.requirements.unit` and `projects.projects.product_family` are
-- free text today and are deliberately NOT retro-constrained here. Adding
-- a FK to them would fail on any existing row whose spelling differs, and
-- silently rewriting R&D rows to satisfy a new constraint is not
-- acceptable -- the lesson already recorded against migration 012's
-- immediately-validated CHECKs. These tables are the canonical list a
-- form offers; tightening those columns is a later, deliberate migration
-- with a data audit in front of it.

CREATE TABLE IF NOT EXISTS materials.units (
    id              UUID NOT NULL DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES core.organizations(id) ON DELETE RESTRICT,
    code            TEXT NOT NULL,                      -- g/cm3, MPa, %, s
    name            TEXT NOT NULL,
    quantity_kind   TEXT NOT NULL,                      -- density, stress, time
    is_active       BOOLEAN NOT NULL DEFAULT TRUE,
    display_order   INTEGER NOT NULL DEFAULT 100,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (id),
    CONSTRAINT units_org_code_key UNIQUE (organization_id, code),
    CONSTRAINT units_id_org_key   UNIQUE (id, organization_id)
);

CREATE TABLE IF NOT EXISTS materials.product_families (
    id              UUID NOT NULL DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES core.organizations(id) ON DELETE RESTRICT,
    code            TEXT NOT NULL,
    name            TEXT NOT NULL,
    description     TEXT,
    is_active       BOOLEAN NOT NULL DEFAULT TRUE,
    display_order   INTEGER NOT NULL DEFAULT 100,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (id),
    CONSTRAINT product_families_org_code_key UNIQUE (organization_id, code),
    CONSTRAINT product_families_id_org_key   UNIQUE (id, organization_id)
);


-- ---------------------------------------------------------------------
-- PART 2 -- Materials
-- ---------------------------------------------------------------------
-- THE FIVE STATUSES are the five the web already renders, and each one
-- has a permission in migration 002 that moves a material into it:
--
--   development   the default; the material is under evaluation
--   approved      material.approve_lab        -- usable in laboratory work
--   preferred     material.approve_production -- usable in production
--   restricted    material.restrict           -- HARD-BLOCKS submission
--   obsolete      material.restrict           -- retired, never deleted
--
-- `restricted` is load-bearing rather than decorative: the engine's
-- `validate_for_submission` returns RESTRICTED_MATERIAL for any component
-- drawn from that set, and section 8 says that block cannot be waived at
-- submission.
--
-- THE PROPERTY COLUMNS ARE NULLABLE ON PURPOSE. A material whose density
-- is unknown is a real and common state, and the engine already refuses
-- to compute rather than assuming a value ("density unknown for: ..."). A
-- NOT NULL with a default of 1.0 would turn an unknown into a confident
-- wrong answer, which rule 3 exists to prevent. Missing data surfaces as
-- a named submission block, never as a plausible number.

CREATE TABLE IF NOT EXISTS materials.materials (
    id                  UUID NOT NULL DEFAULT gen_random_uuid(),
    organization_id     UUID NOT NULL REFERENCES core.organizations(id) ON DELETE RESTRICT,
    material_code       TEXT NOT NULL,                  -- RM-RES-01
    name                TEXT NOT NULL,
    category            TEXT NOT NULL,                  -- Resin, Filler, Pigment...
    -- Drives binder:filler and resin:hardener in the engine. Constrained
    -- here and deliberately NOT duplicated as a Python enum -- the
    -- engine's `Component.role` is a plain string for exactly this
    -- reason, so that this table stays the single vocabulary.
    role                TEXT NOT NULL DEFAULT 'other'
                        CHECK (role IN ('resin','binder','hardener','catalyst',
                                        'filler','extender','pigment',
                                        'additive','solvent','other')),
    status              TEXT NOT NULL DEFAULT 'development'
                        CHECK (status IN ('development','approved','preferred',
                                          'restricted','obsolete')),
    description         TEXT,
    cas_number          TEXT,
    -- Measured properties. NUMERIC throughout; CLAUDE.md section 5
    -- forbids float for densities, percentages and masses, and the engine
    -- refuses a Python float at its boundary rather than converting one.
    density_g_cm3       NUMERIC(10,4) CHECK (density_g_cm3 IS NULL OR density_g_cm3 > 0),
    solids_fraction     NUMERIC(6,4)
        CHECK (solids_fraction IS NULL OR (solids_fraction BETWEEN 0 AND 1)),
    voc_fraction        NUMERIC(6,4)
        CHECK (voc_fraction IS NULL OR (voc_fraction BETWEEN 0 AND 1)),
    cost_per_kg         NUMERIC(12,4) CHECK (cost_per_kg IS NULL OR cost_per_kg >= 0),
    -- Equivalent weights, for the epoxy stoichiometry the engine computes.
    epoxy_equivalent_weight          NUMERIC(10,3)
        CHECK (epoxy_equivalent_weight IS NULL OR epoxy_equivalent_weight > 0),
    amine_hydrogen_equivalent_weight NUMERIC(10,3)
        CHECK (amine_hydrogen_equivalent_weight IS NULL OR amine_hydrogen_equivalent_weight > 0),
    -- Hazard data feeds the safety checks that hard-block submission.
    -- `failed_safety_checks` is passed INTO the engine and never derived
    -- inside it: a compliance decision does not belong in a maths module.
    hazard_summary      TEXT,
    requires_sds        BOOLEAN NOT NULL DEFAULT TRUE,
    restriction_reason  TEXT,
    notes               TEXT,
    created_by          UUID NOT NULL REFERENCES core.users(id) ON DELETE RESTRICT,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (id),
    CONSTRAINT materials_org_code_key UNIQUE (organization_id, material_code),
    CONSTRAINT materials_id_org_key   UNIQUE (id, organization_id),
    -- A restriction with no stated reason is unactionable: the chemist
    -- whose formula it blocks cannot tell a regulatory limit from a
    -- supply failure from a safety finding.
    CONSTRAINT materials_restriction_has_a_reason CHECK (
        status <> 'restricted' OR restriction_reason IS NOT NULL
    )
);

-- TDS / SDS / CoA. METADATA AND AN OBJECT-STORAGE KEY, NEVER BYTES.
-- SECURITY.md section 6 forbids file content in database rows, and the
-- plan puts Garage behind `ObjectStoragePort` in Slice 1 for this exact
-- reason. The row is the controlled record; the object store holds the
-- file.
CREATE TABLE IF NOT EXISTS materials.material_documents (
    id              UUID NOT NULL DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL,
    material_id     UUID NOT NULL,
    document_type   TEXT NOT NULL
                    CHECK (document_type IN ('TDS','SDS','CoA','regulatory','other')),
    title           TEXT NOT NULL,
    -- An opaque key in the object store. Not a URL: a stored URL embeds
    -- the deployment's hostname in R&D data and breaks on every move.
    storage_key     TEXT NOT NULL,
    content_type    TEXT,
    byte_size       BIGINT CHECK (byte_size IS NULL OR byte_size >= 0),
    -- sha256 of the object, so a swapped file is detectable.
    checksum_sha256 TEXT CHECK (checksum_sha256 IS NULL OR checksum_sha256 ~ '^[0-9a-f]{64}$'),
    issued_on       DATE,
    expires_on      DATE,
    supersedes_id   UUID,
    uploaded_by     UUID NOT NULL REFERENCES core.users(id) ON DELETE RESTRICT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (id),
    CONSTRAINT material_documents_id_org_key UNIQUE (id, organization_id),
    CONSTRAINT material_documents_material_fk FOREIGN KEY (material_id, organization_id)
        REFERENCES materials.materials (id, organization_id) ON DELETE RESTRICT,
    CONSTRAINT material_documents_supersedes_fk FOREIGN KEY (supersedes_id, organization_id)
        REFERENCES materials.material_documents (id, organization_id) ON DELETE RESTRICT,
    CONSTRAINT material_documents_storage_key_unique UNIQUE (organization_id, storage_key),
    CONSTRAINT material_documents_validity_ordered CHECK (
        expires_on IS NULL OR issued_on IS NULL OR expires_on >= issued_on
    )
);


-- ---------------------------------------------------------------------
-- PART 3 -- Suppliers, and the many-to-many
-- ---------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS materials.suppliers (
    id              UUID NOT NULL DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES core.organizations(id) ON DELETE RESTRICT,
    supplier_code   TEXT NOT NULL,                      -- SUP-001
    name            TEXT NOT NULL,
    country         TEXT,
    status          TEXT NOT NULL DEFAULT 'pending'
                    CHECK (status IN ('pending','qualified','approved',
                                      'suspended','disqualified')),
    -- A, B, C, D. Free-form letters are how a rating becomes uncomparable.
    quality_rating  TEXT CHECK (quality_rating IS NULL OR quality_rating IN ('A','B','C','D')),
    contact_name    TEXT,
    contact_email   TEXT,
    notes           TEXT,
    created_by      UUID NOT NULL REFERENCES core.users(id) ON DELETE RESTRICT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (id),
    CONSTRAINT suppliers_org_code_key UNIQUE (organization_id, supplier_code),
    CONSTRAINT suppliers_id_org_key   UNIQUE (id, organization_id)
);

-- Materials to suppliers, many to many, carrying the commercial facts
-- that belong to the PAIR rather than to either side: this supplier's
-- part number for this material, their lead time, their quoted price.
CREATE TABLE IF NOT EXISTS materials.material_suppliers (
    id                  UUID NOT NULL DEFAULT gen_random_uuid(),
    organization_id     UUID NOT NULL,
    material_id         UUID NOT NULL,
    supplier_id         UUID NOT NULL,
    supplier_part_code  TEXT,
    is_primary          BOOLEAN NOT NULL DEFAULT FALSE,
    lead_time_days      INTEGER CHECK (lead_time_days IS NULL OR lead_time_days >= 0),
    quoted_price_per_kg NUMERIC(12,4)
        CHECK (quoted_price_per_kg IS NULL OR quoted_price_per_kg >= 0),
    currency            TEXT,
    qualified_on        DATE,
    notes               TEXT,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (id),
    CONSTRAINT material_suppliers_id_org_key UNIQUE (id, organization_id),
    CONSTRAINT material_suppliers_pair_key UNIQUE (organization_id, material_id, supplier_id),
    CONSTRAINT material_suppliers_material_fk FOREIGN KEY (material_id, organization_id)
        REFERENCES materials.materials (id, organization_id) ON DELETE RESTRICT,
    CONSTRAINT material_suppliers_supplier_fk FOREIGN KEY (supplier_id, organization_id)
        REFERENCES materials.suppliers (id, organization_id) ON DELETE RESTRICT,
    -- A price with no currency is a number, not a price.
    CONSTRAINT material_suppliers_price_has_currency CHECK (
        quoted_price_per_kg IS NULL OR currency IS NOT NULL
    )
);

-- AT MOST ONE PRIMARY SUPPLIER PER MATERIAL. A partial unique index
-- rather than a CHECK, because the rule spans rows. It lives in the
-- database because "the form only lets you tick one" is not a mechanism:
-- two concurrent requests each pass that check and both commit.
CREATE UNIQUE INDEX IF NOT EXISTS material_suppliers_one_primary_idx
    ON materials.material_suppliers (organization_id, material_id)
    WHERE is_primary;

-- Received lots. The traceability anchor Slice 4 will hang batches from,
-- so it exists now with the columns that slice needs rather than being
-- retro-fitted underneath it.
CREATE TABLE IF NOT EXISTS materials.material_lots (
    id                      UUID NOT NULL DEFAULT gen_random_uuid(),
    organization_id         UUID NOT NULL,
    material_id             UUID NOT NULL,
    supplier_id             UUID,
    lot_number              TEXT NOT NULL,
    received_on             DATE,
    manufactured_on         DATE,
    expires_on              DATE,
    quantity_received_kg    NUMERIC(14,4)
        CHECK (quantity_received_kg IS NULL OR quantity_received_kg >= 0),
    quantity_remaining_kg   NUMERIC(14,4)
        CHECK (quantity_remaining_kg IS NULL OR quantity_remaining_kg >= 0),
    status                  TEXT NOT NULL DEFAULT 'quarantine'
                            CHECK (status IN ('quarantine','released','on_hold',
                                              'rejected','consumed','expired')),
    coa_document_id         UUID,
    notes                   TEXT,
    created_by              UUID NOT NULL REFERENCES core.users(id) ON DELETE RESTRICT,
    created_at              TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at              TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (id),
    CONSTRAINT material_lots_id_org_key UNIQUE (id, organization_id),
    CONSTRAINT material_lots_number_key UNIQUE (organization_id, material_id, lot_number),
    CONSTRAINT material_lots_material_fk FOREIGN KEY (material_id, organization_id)
        REFERENCES materials.materials (id, organization_id) ON DELETE RESTRICT,
    CONSTRAINT material_lots_supplier_fk FOREIGN KEY (supplier_id, organization_id)
        REFERENCES materials.suppliers (id, organization_id) ON DELETE RESTRICT,
    CONSTRAINT material_lots_coa_fk FOREIGN KEY (coa_document_id, organization_id)
        REFERENCES materials.material_documents (id, organization_id) ON DELETE RESTRICT,
    -- Cannot have more left than arrived.
    CONSTRAINT material_lots_remaining_within_received CHECK (
        quantity_remaining_kg IS NULL OR quantity_received_kg IS NULL
        OR quantity_remaining_kg <= quantity_received_kg
    ),
    CONSTRAINT material_lots_dates_ordered CHECK (
        expires_on IS NULL OR manufactured_on IS NULL OR expires_on >= manufactured_on
    )
);


-- ---------------------------------------------------------------------
-- PART 4 -- Formulations
-- ---------------------------------------------------------------------
-- A formula is the identity ("FRM-014, the premium lightweight putty").
-- A formula VERSION is the composition. Nothing is edited in place once
-- it leaves draft; a change is a new version with a parent, a
-- change_reason and a technical_hypothesis (CLAUDE.md section 8).

CREATE TABLE IF NOT EXISTS formulations.formulas (
    id              UUID NOT NULL DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES core.organizations(id) ON DELETE RESTRICT,
    project_id      UUID NOT NULL,
    formula_code    TEXT NOT NULL,                      -- FRM-014, immutable
    name            TEXT NOT NULL,
    product_family  TEXT,
    description     TEXT,
    owner_user_id   UUID NOT NULL REFERENCES core.users(id) ON DELETE RESTRICT,
    status          TEXT NOT NULL DEFAULT 'active'
                    CHECK (status IN ('active','on_hold','archived')),
    created_by      UUID NOT NULL REFERENCES core.users(id) ON DELETE RESTRICT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (id),
    CONSTRAINT formulas_org_code_key UNIQUE (organization_id, formula_code),
    CONSTRAINT formulas_id_org_key   UNIQUE (id, organization_id),
    -- THE THREE-COLUMN KEY. Children reference (id, project_id,
    -- organization_id) so a version cannot be attached to a formula in
    -- another PROJECT, not merely in another tenant. See the header.
    CONSTRAINT formulas_id_project_org_key UNIQUE (id, project_id, organization_id),
    CONSTRAINT formulas_project_fk FOREIGN KEY (project_id, organization_id)
        REFERENCES projects.projects (id, organization_id) ON DELETE RESTRICT
);

CREATE TABLE IF NOT EXISTS formulations.formula_versions (
    id                      UUID NOT NULL DEFAULT gen_random_uuid(),
    organization_id         UUID NOT NULL,
    project_id              UUID NOT NULL,
    formula_id              UUID NOT NULL,
    -- The sequential issue number within the formula. Monotonic and
    -- unique per formula.
    --
    -- HOW BRANCHES ARE MODELLED, since the plan requires them
    -- (F001 -> F002 -> F003 -> F004-A / F004-B): the genealogy is
    -- `parent_version_id`, and a BRANCH IS TWO VERSIONS SHARING ONE
    -- PARENT. They still take distinct issue numbers -- 4 and 5 -- while
    -- both pointing at version 3, and their `version_code` carries the
    -- human branch label. Numbering the branches identically would need a
    -- composite (number, branch) key that nothing else in the product
    -- reads, and would make "which came first" unanswerable.
    version_number          INTEGER NOT NULL CHECK (version_number > 0),
    version_code            TEXT NOT NULL,              -- FRM-014-V004-A
    parent_version_id       UUID,
    status                  TEXT NOT NULL DEFAULT 'draft'
                            CHECK (status IN ('draft','submitted','approved',
                                              'rejected','superseded','released')),
    change_reason           TEXT,
    technical_hypothesis    TEXT,
    expected_effect         TEXT,
    -- Written AFTER testing, and therefore explicitly still writable once
    -- the version is frozen -- see the immutability trigger, which allows
    -- exactly this column and the disposition columns to move. A version
    -- whose observed effect could never be recorded would make the
    -- digital thread one-way.
    observed_effect         TEXT,
    -- Tolerance is per version because it is a formulation decision, not
    -- a global constant. The engine takes it as an argument for the same
    -- reason.
    total_tolerance_pct     NUMERIC(6,4) NOT NULL DEFAULT 0.01
                            CHECK (total_tolerance_pct >= 0),
    submitted_by            UUID REFERENCES core.users(id) ON DELETE RESTRICT,
    submitted_at            TIMESTAMPTZ,
    approved_by             UUID REFERENCES core.users(id) ON DELETE RESTRICT,
    approved_at             TIMESTAMPTZ,
    approval_note           TEXT,
    created_by              UUID NOT NULL REFERENCES core.users(id) ON DELETE RESTRICT,
    created_at              TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at              TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (id),
    CONSTRAINT formula_versions_id_org_key UNIQUE (id, organization_id),
    CONSTRAINT formula_versions_id_project_org_key UNIQUE (id, project_id, organization_id),
    CONSTRAINT formula_versions_number_key UNIQUE (organization_id, formula_id, version_number),
    CONSTRAINT formula_versions_code_key   UNIQUE (organization_id, version_code),
    CONSTRAINT formula_versions_formula_fk
        FOREIGN KEY (formula_id, project_id, organization_id)
        REFERENCES formulations.formulas (id, project_id, organization_id) ON DELETE RESTRICT,
    -- A parent in another project would splice two projects' genealogies.
    CONSTRAINT formula_versions_parent_fk
        FOREIGN KEY (parent_version_id, project_id, organization_id)
        REFERENCES formulations.formula_versions (id, project_id, organization_id)
        ON DELETE RESTRICT,
    -- Section 8: "Every version records parent_version_id, change_reason,
    -- technical_hypothesis". Version 1 has no parent and nothing to
    -- explain; every later version must say why it exists, or the
    -- genealogy records what changed and never why.
    CONSTRAINT formula_versions_revision_is_explained CHECK (
        parent_version_id IS NULL
        OR (change_reason IS NOT NULL AND technical_hypothesis IS NOT NULL)
    ),
    CONSTRAINT formula_versions_first_has_no_parent CHECK (
        (version_number = 1) = (parent_version_id IS NULL)
    ),
    -- An approval with no approver is an unattributable approval -- the
    -- rule migration 003 already applies to an opportunity decision.
    CONSTRAINT formula_versions_submission_complete CHECK (
        (submitted_by IS NULL) = (submitted_at IS NULL)
    ),
    CONSTRAINT formula_versions_approval_complete CHECK (
        (approved_by IS NULL) = (approved_at IS NULL)
    ),
    -- Status and evidence cannot disagree: a version cannot BE approved
    -- or released without having been approved BY somebody.
    CONSTRAINT formula_versions_approved_states_have_an_approver CHECK (
        status NOT IN ('approved','released') OR approved_by IS NOT NULL
    )
);

CREATE TABLE IF NOT EXISTS formulations.formula_components (
    id                  UUID NOT NULL DEFAULT gen_random_uuid(),
    organization_id     UUID NOT NULL,
    project_id          UUID NOT NULL,
    formula_version_id  UUID NOT NULL,
    material_id         UUID NOT NULL,
    -- Mass percent of the total formula. NUMERIC(9,4): four decimal
    -- places is what `normalize_to_100` quantizes to, so the database
    -- stores exactly what the engine produced instead of rounding it a
    -- second time.
    percentage          NUMERIC(9,4) NOT NULL CHECK (percentage >= 0),
    -- Overrides materials.role for this formula only (a resin used as a
    -- diluent). NULL means "use the material's role"; the service
    -- resolves it, so the vocabulary still lives in exactly one table.
    role_override       TEXT CHECK (role_override IS NULL OR role_override IN
                        ('resin','binder','hardener','catalyst','filler',
                         'extender','pigment','additive','solvent','other')),
    display_order       INTEGER NOT NULL DEFAULT 100,
    notes               TEXT,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (id),
    CONSTRAINT formula_components_id_org_key UNIQUE (id, organization_id),
    CONSTRAINT formula_components_version_fk
        FOREIGN KEY (formula_version_id, project_id, organization_id)
        REFERENCES formulations.formula_versions (id, project_id, organization_id)
        ON DELETE RESTRICT,
    -- A component drawn from another tenant's material library. RLS would
    -- hide that material from a read and would NOT prevent this
    -- reference; the composite key does.
    CONSTRAINT formula_components_material_fk FOREIGN KEY (material_id, organization_id)
        REFERENCES materials.materials (id, organization_id) ON DELETE RESTRICT,
    -- ONE LINE PER MATERIAL. The engine refuses to scale a formula with a
    -- duplicated component, because its result is keyed by material code
    -- and two lines silently overwrite each other -- masses that sum to
    -- LESS than the batch. Refusing it here means that state cannot be
    -- stored in the first place.
    CONSTRAINT formula_components_one_line_per_material
        UNIQUE (formula_version_id, material_id)
);


-- ---------------------------------------------------------------------
-- PART 5 -- Immutability, in the database (CLAUDE.md section 8)
-- ---------------------------------------------------------------------
-- "A released master formula is read-only AT THE DATABASE LEVEL, not
-- merely hidden in the UI." A service-layer guard is a claim; a trigger
-- is a mechanism. This codebase has repeatedly found comments asserting
-- rules the code did not implement, so the rule goes where a future
-- endpoint, a backfill or a psql session cannot route around it.

-- Formula numbers are immutable once issued (section 8, first line).
CREATE OR REPLACE FUNCTION formulations.deny_code_change() RETURNS TRIGGER
    LANGUAGE plpgsql AS $fn$
BEGIN
    IF NEW.formula_code IS DISTINCT FROM OLD.formula_code THEN
        RAISE EXCEPTION
            'formula_code is immutable once issued (% -> %)',
            OLD.formula_code, NEW.formula_code
            USING ERRCODE = 'insufficient_privilege';
    END IF;
    IF NEW.organization_id IS DISTINCT FROM OLD.organization_id
       OR NEW.project_id IS DISTINCT FROM OLD.project_id THEN
        RAISE EXCEPTION 'a formula cannot be moved between projects or organizations'
            USING ERRCODE = 'insufficient_privilege';
    END IF;
    RETURN NEW;
END
$fn$;

DROP TRIGGER IF EXISTS formulas_code_immutable ON formulations.formulas;
CREATE TRIGGER formulas_code_immutable
    BEFORE UPDATE ON formulations.formulas
    FOR EACH ROW EXECUTE FUNCTION formulations.deny_code_change();


-- A version that has left `draft` is frozen except for the columns that
-- must still be able to move.
--
-- WHAT MAY STILL CHANGE, AND WHY EACH ONE:
--   status            the lifecycle itself
--   approved_by/_at   recording the approval that changes the status
--   approval_note     the conditional-approval limitation (section 9)
--   observed_effect   written after testing; section 8 requires it
--   updated_at        bookkeeping
--
-- Everything else -- the composition-defining fields, the parent, the
-- tolerance, the hypothesis -- is the controlled record.
CREATE OR REPLACE FUNCTION formulations.deny_version_mutation() RETURNS TRIGGER
    LANGUAGE plpgsql AS $fn$
BEGIN
    IF OLD.status = 'draft' THEN
        RETURN NEW;   -- a draft is a workspace
    END IF;

    IF NEW.version_number       IS DISTINCT FROM OLD.version_number
       OR NEW.version_code      IS DISTINCT FROM OLD.version_code
       OR NEW.formula_id        IS DISTINCT FROM OLD.formula_id
       OR NEW.parent_version_id IS DISTINCT FROM OLD.parent_version_id
       OR NEW.project_id        IS DISTINCT FROM OLD.project_id
       OR NEW.organization_id   IS DISTINCT FROM OLD.organization_id
       OR NEW.change_reason     IS DISTINCT FROM OLD.change_reason
       OR NEW.technical_hypothesis IS DISTINCT FROM OLD.technical_hypothesis
       OR NEW.expected_effect   IS DISTINCT FROM OLD.expected_effect
       OR NEW.total_tolerance_pct IS DISTINCT FROM OLD.total_tolerance_pct
       OR NEW.submitted_by      IS DISTINCT FROM OLD.submitted_by
       OR NEW.submitted_at      IS DISTINCT FROM OLD.submitted_at
       OR NEW.created_by        IS DISTINCT FROM OLD.created_by
    THEN
        RAISE EXCEPTION
            'formula version % is % and may not be edited in place; clone it '
            'to a new draft (CLAUDE.md section 8)', OLD.version_code, OLD.status
            USING ERRCODE = 'insufficient_privilege';
    END IF;

    -- A released master is read-only in every column but its observed
    -- effect. Nothing may un-release it: a released product's master
    -- formula is what production records and field performance point at.
    IF OLD.status = 'released' AND NEW.status IS DISTINCT FROM OLD.status THEN
        RAISE EXCEPTION 'a released formula version cannot change status'
            USING ERRCODE = 'insufficient_privilege';
    END IF;

    RETURN NEW;
END
$fn$;

DROP TRIGGER IF EXISTS formula_versions_immutable ON formulations.formula_versions;
CREATE TRIGGER formula_versions_immutable
    BEFORE UPDATE ON formulations.formula_versions
    FOR EACH ROW EXECUTE FUNCTION formulations.deny_version_mutation();


-- Components follow their version. THIS is the half that actually
-- protects the composition: freezing the version row while leaving its
-- component rows writable would let an approved formula be changed
-- without a single column of the version ever being touched.
CREATE OR REPLACE FUNCTION formulations.deny_component_mutation() RETURNS TRIGGER
    LANGUAGE plpgsql AS $fn$
DECLARE
    v_id     UUID;
    v_status TEXT;
    v_code   TEXT;
BEGIN
    v_id := COALESCE(NEW.formula_version_id, OLD.formula_version_id);

    SELECT status, version_code INTO v_status, v_code
    FROM formulations.formula_versions WHERE id = v_id;

    IF NOT FOUND THEN
        -- A guard that passes when it cannot see its subject is the
        -- "check that walks through its own gap" already recorded twice
        -- against this platform. Refuse instead.
        RAISE EXCEPTION 'formula version % does not exist', v_id
            USING ERRCODE = 'foreign_key_violation';
    END IF;

    IF v_status <> 'draft' THEN
        RAISE EXCEPTION
            'the composition of version % is frozen (status %); clone it to a '
            'new draft version (CLAUDE.md section 8)', v_code, v_status
            USING ERRCODE = 'insufficient_privilege';
    END IF;

    RETURN COALESCE(NEW, OLD);
END
$fn$;

-- SECURITY DEFINER, so the guard's own lookup cannot be defeated by a
-- session whose RLS view of `formula_versions` is empty -- an unscoped
-- writer would otherwise find no row.
--
-- The search_path is pinned for the reason migration 013 pinned
-- audit.chain_row()'s: a definer function that resolves its object names
-- through the CALLER's search_path is a privilege escalation waiting for
-- a schema that shadows it.
--
-- ONE KNOWN FUTURE RISK, recorded rather than assumed away. This is
-- caller-independent today because `formula_versions` has RLS ENABLED but
-- not FORCED and an owner is exempt from a non-forced policy. The planned
-- FORCE cutover removes that exemption and would make this lookup
-- RLS-filtered again -- the same shape as the audit chain's, and covered
-- by the same tripwire:
-- tests/db/test_011_audit_chain_scope.py::test_the_force_rls_cutover_must_revisit_the_chain_trigger
ALTER FUNCTION formulations.deny_component_mutation() SECURITY DEFINER;
ALTER FUNCTION formulations.deny_component_mutation()
    SET search_path = formulations, pg_catalog;
ALTER FUNCTION formulations.deny_component_mutation() OWNER TO evercoat_owner;

DROP TRIGGER IF EXISTS formula_components_follow_version ON formulations.formula_components;
CREATE TRIGGER formula_components_follow_version
    BEFORE INSERT OR UPDATE OR DELETE ON formulations.formula_components
    FOR EACH ROW EXECUTE FUNCTION formulations.deny_component_mutation();


-- ---------------------------------------------------------------------
-- PART 6 -- Indexes, RLS, ownership, grants
-- ---------------------------------------------------------------------
-- CLAUDE.md: index every FK used in joins, plus (organization_id, status)
-- and (raw_material_id, supplier_id).

CREATE INDEX IF NOT EXISTS materials_org_status_idx
    ON materials.materials (organization_id, status);
CREATE INDEX IF NOT EXISTS materials_org_role_idx
    ON materials.materials (organization_id, role);
CREATE INDEX IF NOT EXISTS suppliers_org_status_idx
    ON materials.suppliers (organization_id, status);
CREATE INDEX IF NOT EXISTS material_suppliers_pair_idx
    ON materials.material_suppliers (material_id, supplier_id);
CREATE INDEX IF NOT EXISTS material_suppliers_supplier_idx
    ON materials.material_suppliers (supplier_id);
CREATE INDEX IF NOT EXISTS material_documents_material_idx
    ON materials.material_documents (material_id, document_type);
CREATE INDEX IF NOT EXISTS material_lots_material_status_idx
    ON materials.material_lots (material_id, status);
CREATE INDEX IF NOT EXISTS formulas_project_idx
    ON formulations.formulas (project_id, status);
CREATE INDEX IF NOT EXISTS formula_versions_formula_idx
    ON formulations.formula_versions (formula_id, version_number);
CREATE INDEX IF NOT EXISTS formula_versions_parent_idx
    ON formulations.formula_versions (parent_version_id);
CREATE INDEX IF NOT EXISTS formula_versions_org_status_idx
    ON formulations.formula_versions (organization_id, status);
CREATE INDEX IF NOT EXISTS formula_components_version_idx
    ON formulations.formula_components (formula_version_id, display_order);
-- The reverse question -- "which formulas use this material?" -- is the
-- usage history the plan requires on the material detail screen.
CREATE INDEX IF NOT EXISTS formula_components_material_idx
    ON formulations.formula_components (material_id);

ALTER TABLE materials.units                 ENABLE ROW LEVEL SECURITY;
ALTER TABLE materials.product_families      ENABLE ROW LEVEL SECURITY;
ALTER TABLE materials.materials             ENABLE ROW LEVEL SECURITY;
ALTER TABLE materials.material_documents    ENABLE ROW LEVEL SECURITY;
ALTER TABLE materials.suppliers             ENABLE ROW LEVEL SECURITY;
ALTER TABLE materials.material_suppliers    ENABLE ROW LEVEL SECURITY;
ALTER TABLE materials.material_lots         ENABLE ROW LEVEL SECURITY;
ALTER TABLE formulations.formulas           ENABLE ROW LEVEL SECURITY;
ALTER TABLE formulations.formula_versions   ENABLE ROW LEVEL SECURITY;
ALTER TABLE formulations.formula_components ENABLE ROW LEVEL SECURITY;

-- ORGANIZATION-SCOPED. The material library and the supplier list are
-- org-wide reference data: a chemist on one project must be able to see
-- every material or they cannot formulate at all. Confidentiality lives
-- on the formulas that USE a material, not on the raw material.
DO $policies$
DECLARE t TEXT;
BEGIN
    FOREACH t IN ARRAY ARRAY[
        'materials.units', 'materials.product_families', 'materials.materials',
        'materials.material_documents', 'materials.suppliers',
        'materials.material_suppliers', 'materials.material_lots'
    ]
    LOOP
        EXECUTE format('DROP POLICY IF EXISTS org_scope ON %s', t);
        EXECUTE format($p$
            CREATE POLICY org_scope ON %s
            USING (
                core.rls_permissive() AND core.current_org_id() IS NULL
                OR organization_id = core.current_org_id()
            )
            WITH CHECK (
                core.rls_permissive() AND core.current_org_id() IS NULL
                OR organization_id = core.current_org_id()
            )
        $p$, t);
    END LOOP;
END
$policies$;

-- PROJECT-SCOPED. A formula inherits its project's confidentiality -- the
-- composition of a restricted project's formulation is the single most
-- sensitive record in this product. The policy shape is the one migration
-- 005 settled: membership in USING, organization only in WITH CHECK,
-- because requiring membership in order to WRITE makes the first row of a
-- restricted project impossible to create.
DO $policies$
DECLARE t TEXT;
BEGIN
    FOREACH t IN ARRAY ARRAY[
        'formulations.formulas', 'formulations.formula_versions',
        'formulations.formula_components'
    ]
    LOOP
        EXECUTE format('DROP POLICY IF EXISTS project_scope ON %s', t);
        EXECUTE format($p$
            CREATE POLICY project_scope ON %s
            USING (
                core.rls_permissive() AND core.current_org_id() IS NULL
                OR (
                    organization_id = core.current_org_id()
                    AND EXISTS (
                        SELECT 1 FROM projects.projects p
                        WHERE p.id = %s.project_id
                          AND (p.confidentiality = 'normal'
                               OR core.is_project_member(p.id))
                    )
                )
            )
            WITH CHECK (
                core.rls_permissive() AND core.current_org_id() IS NULL
                OR organization_id = core.current_org_id()
            )
        $p$, t, t);
    END LOOP;
END
$policies$;

-- OWNERSHIP. Migration 014 made the migration the single decider of who
-- owns schema objects, and tests/db/test_object_ownership.py fails if a
-- later migration creates a table without doing it. This IS that later
-- migration, so it does the work itself rather than relying on 014 being
-- re-run -- which alembic will never do.
DO $ownership$
DECLARE r RECORD;
BEGIN
    IF NOT (SELECT rolsuper FROM pg_roles WHERE rolname = current_user)
       AND NOT pg_has_role(current_user, 'evercoat_owner', 'MEMBER') THEN
        RAISE EXCEPTION
            'role % can neither bypass ownership checks nor act as evercoat_owner; '
            'run migrations as a superuser or GRANT evercoat_owner TO %',
            current_user, current_user;
    END IF;

    FOR r IN
        SELECT n.nspname AS schema_name, c.relname AS object_name, c.relkind AS kind
        FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
        WHERE n.nspname IN ('materials', 'formulations')
          AND c.relkind IN ('r', 'p', 'S', 'v', 'm')
          AND pg_get_userbyid(c.relowner) <> 'evercoat_owner'
    LOOP
        IF r.kind = 'S' THEN
            EXECUTE format('ALTER SEQUENCE %I.%I OWNER TO evercoat_owner',
                           r.schema_name, r.object_name);
        ELSIF r.kind = 'v' THEN
            EXECUTE format('ALTER VIEW %I.%I OWNER TO evercoat_owner',
                           r.schema_name, r.object_name);
        ELSIF r.kind = 'm' THEN
            EXECUTE format('ALTER MATERIALIZED VIEW %I.%I OWNER TO evercoat_owner',
                           r.schema_name, r.object_name);
        ELSE
            EXECUTE format('ALTER TABLE %I.%I OWNER TO evercoat_owner',
                           r.schema_name, r.object_name);
        END IF;
    END LOOP;
END
$ownership$;

GRANT USAGE ON SCHEMA materials, formulations
    TO evercoat_app, evercoat_worker, evercoat_report;

-- DELETE is deliberately absent, as it is in 014. R&D history is retired
-- with a status and never removed: `obsolete` on a material, `archived`
-- on a formula, `superseded` on a version. The single exception the
-- services need is removing a component line from a DRAFT version, which
-- is why formula_components alone is granted DELETE -- and the trigger
-- above refuses it the moment that version leaves draft.
GRANT SELECT, INSERT, UPDATE ON ALL TABLES IN SCHEMA materials, formulations
    TO evercoat_app;
GRANT DELETE ON formulations.formula_components TO evercoat_app;
GRANT SELECT ON ALL TABLES IN SCHEMA materials, formulations
    TO evercoat_worker, evercoat_report;

ALTER DEFAULT PRIVILEGES FOR ROLE evercoat_owner IN SCHEMA materials, formulations
    GRANT SELECT, INSERT, UPDATE ON TABLES TO evercoat_app;
ALTER DEFAULT PRIVILEGES FOR ROLE evercoat_owner IN SCHEMA materials, formulations
    GRANT SELECT ON TABLES TO evercoat_worker, evercoat_report;

COMMIT;
