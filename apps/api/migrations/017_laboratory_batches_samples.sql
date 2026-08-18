-- 017_laboratory_batches_samples.sql
-- =====================================================================
-- Slice 4 -- Laboratory. The third link in the loop the owner's plan says
-- the first 45 hours must establish:
--
--   Project -> Formula -> LAB -> Test -> Analysis -> Approval
--            -> Failure -> Reformulation
--
-- The source's own workflow (ITWRD App.txt, sections 15-16) is the shape
-- of this schema, not a paraphrase of it:
--
--   Formula -> Create Laboratory Batch -> Calculate Batch Quantities
--   -> Select Material Lots -> Generate Mixing Procedure
--   -> Lab Authorization -> Execute Batch
--
--   Batch Execution -> Material Verification -> Mixing
--   -> Process Data Capture -> Sample Creation -> Batch Completion
--   -> Chemist Review  (Accept for Testing | Reject for Process Deviation)
--
-- and during manufacture the technician records "planned weight, actual
-- weight, material lot, mixing RPM, mixing time, temperature, vacuum,
-- observations, deviations". Every one of those has a column or a row
-- here.
--
-- WHAT "LAB AUTHORIZATION" MAPS TO, SINCE IT HAS NO PERMISSION OF ITS OWN
-- ----------------------------------------------------------------------
-- Migration 002 seeds six laboratory permissions -- batch.view, .create,
-- .execute, .complete, .reject and sample.create -- and NO
-- `batch.authorize`. That gap was checked before writing this rather than
-- filled by inventing one: a permission no role holds is a control that
-- can never be exercised, which is exactly the defect migration 016 had
-- to close for `material.approve_production`.
--
-- It does not need one. The authorising act is the LEAD approving the
-- formula version for laboratory trial (`formula.approve_lab`), and a
-- batch cannot exist without it -- `create_batch` selects the version and
-- requires `status = 'approved'` in the same statement. The batch's own
-- draft -> authorized step is the Chemist confirming that lots are chosen
-- and the weigh-up is ready, which `batch.create` already covers.
--
-- PLANNED MASSES ARE STORED; THEY ARE NOT RE-DERIVED ON READ
-- ----------------------------------------------------------
-- They come from `scale_to_batch` at the moment the batch is created, and
-- then they are the SHEET. Recomputing them on every read would mean a
-- correction to a material's data silently changing what a technician was
-- told to weigh out last week -- and the actual masses beside them would
-- then be deviations from a plan that never existed. A batch is a
-- historical record of an instruction, not a live view of a formula.
--
-- PARTS
--   1  Lots gain the key that stops a lot being charged to the wrong line
--   2  Batches
--   3  Batch components -- planned vs actual, and the lot that was used
--   4  Process parameters, deviations, samples
--   5  Immutability
--   6  Indexes, RLS, ownership, grants
-- =====================================================================

BEGIN;

-- ---------------------------------------------------------------------
-- PART 1 -- the key that makes "charge lot L against line M" checkable
-- ---------------------------------------------------------------------
-- 🔴 WITHOUT THIS, A TECHNICIAN COULD CHARGE A RESIN LOT AGAINST THE
-- FILLER LINE AND THE DATABASE WOULD ACCEPT IT.
--
-- A plain `REFERENCES material_lots(id)` proves the lot exists. It says
-- nothing about whether the lot is a lot OF THE MATERIAL THE LINE CALLS
-- FOR, and that is the single most consequential mistake available on a
-- weigh-up bench. The application could compare them, and the application
-- comparing them is a check somebody can forget; a composite foreign key
-- is a mechanism.
--
-- Same shape as the three-column tenant+project key in migration 015: add
-- the discriminating column to the referenced unique constraint and carry
-- it in the child.
ALTER TABLE materials.material_lots
    ADD CONSTRAINT material_lots_id_material_org_key
        UNIQUE (id, material_id, organization_id);


-- ---------------------------------------------------------------------
-- PART 2 -- Batches
-- ---------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS laboratory.batches (
    id                  UUID NOT NULL DEFAULT gen_random_uuid(),
    organization_id     UUID NOT NULL REFERENCES core.organizations(id) ON DELETE RESTRICT,
    project_id          UUID NOT NULL,
    formula_version_id  UUID NOT NULL,
    -- LAB-RDP014-F001-LB001 in the source. Unique per organization, as
    -- CLAUDE.md section 5 requires by name: a globally unique batch number
    -- would stop Org B creating LB001 because Org A has one, and the
    -- constraint violation would itself disclose another tenant's record.
    batch_number        TEXT NOT NULL,
    planned_quantity_kg NUMERIC(14,4) NOT NULL CHECK (planned_quantity_kg > 0),
    -- The band around each planned line, in percent. Per batch because a
    -- pilot-scale trial and a 500 g bench trial cannot hold the same
    -- proportional tolerance, and the engine takes it as an argument for
    -- the same reason.
    tolerance_percent   NUMERIC(6,4) NOT NULL DEFAULT 1.0 CHECK (tolerance_percent >= 0),
    status              TEXT NOT NULL DEFAULT 'draft'
                        CHECK (status IN ('draft','authorized','in_progress',
                                          'completed','accepted','rejected','cancelled')),
    mixing_procedure    TEXT,
    purpose             TEXT,
    notes               TEXT,
    created_by          UUID NOT NULL REFERENCES core.users(id) ON DELETE RESTRICT,
    authorized_by       UUID REFERENCES core.users(id) ON DELETE RESTRICT,
    authorized_at       TIMESTAMPTZ,
    executed_by         UUID REFERENCES core.users(id) ON DELETE RESTRICT,
    started_at          TIMESTAMPTZ,
    completed_at        TIMESTAMPTZ,
    -- Chemist Review, section 16. The outcome is the status; this records
    -- who decided and why, because "rejected for process deviation" with
    -- no stated deviation is a verdict nobody can learn from.
    reviewed_by         UUID REFERENCES core.users(id) ON DELETE RESTRICT,
    reviewed_at         TIMESTAMPTZ,
    review_note         TEXT,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (id),
    CONSTRAINT batches_org_number_key UNIQUE (organization_id, batch_number),
    CONSTRAINT batches_id_org_key UNIQUE (id, organization_id),
    CONSTRAINT batches_id_project_org_key UNIQUE (id, project_id, organization_id),
    -- The batch inherits its formula version's project. A batch made
    -- against another project's formula would carry a project_id that
    -- contradicts its own contents, and the RLS policy reads project_id.
    CONSTRAINT batches_formula_version_fk
        FOREIGN KEY (formula_version_id, project_id, organization_id)
        REFERENCES formulations.formula_versions (id, project_id, organization_id)
        ON DELETE RESTRICT,
    -- Each attribution is complete or absent. A batch that says it was
    -- authorized but not by whom is an unattributable authorisation, the
    -- same rule migrations 003 and 015 apply to decisions and approvals.
    CONSTRAINT batches_authorization_complete CHECK (
        (authorized_by IS NULL) = (authorized_at IS NULL)
    ),
    CONSTRAINT batches_review_complete CHECK (
        (reviewed_by IS NULL) = (reviewed_at IS NULL)
    ),
    -- Status and evidence cannot disagree.
    CONSTRAINT batches_executed_states_have_authorization CHECK (
        status IN ('draft','cancelled') OR authorized_by IS NOT NULL
    ),
    CONSTRAINT batches_reviewed_states_have_a_reviewer CHECK (
        status NOT IN ('accepted','rejected') OR reviewed_by IS NOT NULL
    ),
    -- A rejection must say what went wrong. "Rejected" with no note is
    -- the batch equivalent of a restriction with no reason.
    CONSTRAINT batches_rejection_states_why CHECK (
        status <> 'rejected' OR review_note IS NOT NULL
    ),
    CONSTRAINT batches_completion_ordered CHECK (
        completed_at IS NULL OR started_at IS NULL OR completed_at >= started_at
    )
);


-- ---------------------------------------------------------------------
-- PART 3 -- Batch components: planned vs actual, and the lot used
-- ---------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS laboratory.batch_components (
    id                  UUID NOT NULL DEFAULT gen_random_uuid(),
    organization_id     UUID NOT NULL,
    project_id          UUID NOT NULL,
    batch_id            UUID NOT NULL,
    material_id         UUID NOT NULL,
    -- Chosen at "Select Material Lots", so NULL until then. Traceability
    -- to the physical drum is the whole point of the laboratory slice --
    -- CLAUDE.md's referential traceability rule ends at "no test result
    -- without traceability to the physical sample", and this is the link
    -- that makes the sample traceable to the material it was made from.
    material_lot_id     UUID,
    -- From `scale_to_batch` at creation. NUMERIC(14,4) so the engine's
    -- exact output is stored exactly.
    planned_mass_kg     NUMERIC(14,4) NOT NULL CHECK (planned_mass_kg > 0),
    -- NULL until weighed. NOT zero: an unweighed line and a line weighed
    -- to zero are different facts, and a default of 0 would let a batch
    -- complete with nothing in it while every total read correctly.
    actual_mass_kg      NUMERIC(14,4) CHECK (actual_mass_kg IS NULL OR actual_mass_kg >= 0),
    display_order       INTEGER NOT NULL DEFAULT 100,
    weighed_by          UUID REFERENCES core.users(id) ON DELETE RESTRICT,
    weighed_at          TIMESTAMPTZ,
    notes               TEXT,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (id),
    CONSTRAINT batch_components_id_org_key UNIQUE (id, organization_id),
    CONSTRAINT batch_components_batch_fk
        FOREIGN KEY (batch_id, project_id, organization_id)
        REFERENCES laboratory.batches (id, project_id, organization_id) ON DELETE RESTRICT,
    -- 🔴 THE LOT MUST BE A LOT OF THIS LINE'S MATERIAL.
    -- Three columns, so the database refuses a resin lot charged against
    -- the filler line. See PART 1.
    CONSTRAINT batch_components_lot_fk
        FOREIGN KEY (material_lot_id, material_id, organization_id)
        REFERENCES materials.material_lots (id, material_id, organization_id)
        ON DELETE RESTRICT,
    CONSTRAINT batch_components_material_fk
        FOREIGN KEY (material_id, organization_id)
        REFERENCES materials.materials (id, organization_id) ON DELETE RESTRICT,
    -- One line per material, as on the formula it came from.
    CONSTRAINT batch_components_one_line_per_material UNIQUE (batch_id, material_id),
    -- A weight with no weigher is a weight nobody can question.
    CONSTRAINT batch_components_weighing_complete CHECK (
        (actual_mass_kg IS NULL AND weighed_by IS NULL AND weighed_at IS NULL)
        OR (actual_mass_kg IS NOT NULL AND weighed_by IS NOT NULL AND weighed_at IS NOT NULL)
    )
);


-- ---------------------------------------------------------------------
-- PART 4 -- Process data, deviations, samples
-- ---------------------------------------------------------------------
-- "mixing RPM, mixing time, temperature, vacuum, observations" as ROWS
-- rather than columns.
--
-- Five fixed columns would have been shorter and would have been wrong:
-- the next product family adds shear rate, or cure temperature, or pot
-- life, and each one is then a migration plus a form change. CLAUDE.md
-- section 5 also requires measurements stored as VALUE + UNIT with
-- canonical units, which a column named `mixing_rpm` cannot express.
CREATE TABLE IF NOT EXISTS laboratory.batch_process_parameters (
    id                  UUID NOT NULL DEFAULT gen_random_uuid(),
    organization_id     UUID NOT NULL,
    project_id          UUID NOT NULL,
    batch_id            UUID NOT NULL,
    parameter_code      TEXT NOT NULL,          -- mixing_rpm, mixing_time, temperature, vacuum
    value               NUMERIC(16,4) NOT NULL,
    unit                TEXT NOT NULL,          -- rpm, min, degC, mbar
    stage               TEXT,                   -- charging, mixing, discharge
    recorded_by         UUID NOT NULL REFERENCES core.users(id) ON DELETE RESTRICT,
    recorded_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
    notes               TEXT,
    PRIMARY KEY (id),
    CONSTRAINT batch_process_parameters_id_org_key UNIQUE (id, organization_id),
    CONSTRAINT batch_process_parameters_batch_fk
        FOREIGN KEY (batch_id, project_id, organization_id)
        REFERENCES laboratory.batches (id, project_id, organization_id) ON DELETE RESTRICT
);

CREATE TABLE IF NOT EXISTS laboratory.batch_deviations (
    id                  UUID NOT NULL DEFAULT gen_random_uuid(),
    organization_id     UUID NOT NULL,
    project_id          UUID NOT NULL,
    batch_id            UUID NOT NULL,
    -- Which line it concerns, when it concerns one. NULL for a process
    -- deviation that belongs to the batch as a whole.
    batch_component_id  UUID,
    description         TEXT NOT NULL,
    severity            TEXT NOT NULL DEFAULT 'minor'
                        CHECK (severity IN ('minor','major','critical')),
    -- Deviations are the evidence a Chemist Review turns on, so they are
    -- append-only in spirit: raised, then optionally resolved. They are
    -- never edited away.
    raised_by           UUID NOT NULL REFERENCES core.users(id) ON DELETE RESTRICT,
    raised_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
    resolution          TEXT,
    resolved_by         UUID REFERENCES core.users(id) ON DELETE RESTRICT,
    resolved_at         TIMESTAMPTZ,
    PRIMARY KEY (id),
    CONSTRAINT batch_deviations_id_org_key UNIQUE (id, organization_id),
    CONSTRAINT batch_deviations_batch_fk
        FOREIGN KEY (batch_id, project_id, organization_id)
        REFERENCES laboratory.batches (id, project_id, organization_id) ON DELETE RESTRICT,
    CONSTRAINT batch_deviations_component_fk
        FOREIGN KEY (batch_component_id, organization_id)
        REFERENCES laboratory.batch_components (id, organization_id) ON DELETE RESTRICT,
    CONSTRAINT batch_deviations_resolution_complete CHECK (
        (resolution IS NULL AND resolved_by IS NULL AND resolved_at IS NULL)
        OR (resolution IS NOT NULL AND resolved_by IS NOT NULL AND resolved_at IS NOT NULL)
    )
);

CREATE TABLE IF NOT EXISTS laboratory.samples (
    id                  UUID NOT NULL DEFAULT gen_random_uuid(),
    organization_id     UUID NOT NULL,
    project_id          UUID NOT NULL,
    batch_id            UUID NOT NULL,
    -- Unique per organization, named in CLAUDE.md section 5 alongside the
    -- batch number and for the same reason.
    sample_number       TEXT NOT NULL,
    quantity_g          NUMERIC(12,3) CHECK (quantity_g IS NULL OR quantity_g > 0),
    purpose             TEXT,
    storage_location    TEXT,
    status              TEXT NOT NULL DEFAULT 'available'
                        CHECK (status IN ('available','in_test','consumed','expired','discarded')),
    taken_by            UUID NOT NULL REFERENCES core.users(id) ON DELETE RESTRICT,
    taken_at            TIMESTAMPTZ NOT NULL DEFAULT now(),
    expires_on          DATE,
    notes               TEXT,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (id),
    CONSTRAINT samples_org_number_key UNIQUE (organization_id, sample_number),
    CONSTRAINT samples_id_org_key UNIQUE (id, organization_id),
    -- Slice 5's tests reference a sample and must not be able to reach one
    -- in another project.
    CONSTRAINT samples_id_project_org_key UNIQUE (id, project_id, organization_id),
    CONSTRAINT samples_batch_fk
        FOREIGN KEY (batch_id, project_id, organization_id)
        REFERENCES laboratory.batches (id, project_id, organization_id) ON DELETE RESTRICT
);


-- ---------------------------------------------------------------------
-- PART 5 -- Immutability
-- ---------------------------------------------------------------------
-- A weigh-up sheet is an INSTRUCTION that was issued, and the record of
-- what was actually done against it. Neither may be rewritten afterwards.

-- The planned masses freeze when the batch leaves draft; the actual
-- masses may only be recorded while it is being executed.
CREATE OR REPLACE FUNCTION laboratory.deny_component_mutation() RETURNS TRIGGER
    LANGUAGE plpgsql AS $fn$
DECLARE
    b_id     UUID;
    b_status TEXT;
    b_number TEXT;
BEGIN
    b_id := COALESCE(NEW.batch_id, OLD.batch_id);

    SELECT status, batch_number INTO b_status, b_number
    FROM laboratory.batches WHERE id = b_id;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'batch % does not exist', b_id
            USING ERRCODE = 'foreign_key_violation';
    END IF;

    -- Lines may be added, removed or re-planned only in draft.
    IF TG_OP <> 'UPDATE' AND b_status <> 'draft' THEN
        RAISE EXCEPTION
            'the weigh-up sheet for batch % is issued (status %); lines cannot '
            'be added or removed', b_number, b_status
            USING ERRCODE = 'insufficient_privilege';
    END IF;

    IF TG_OP = 'UPDATE' THEN
        -- The INSTRUCTION is frozen outside draft.
        IF b_status <> 'draft' AND (
               NEW.planned_mass_kg IS DISTINCT FROM OLD.planned_mass_kg
            OR NEW.material_id     IS DISTINCT FROM OLD.material_id
            OR NEW.batch_id        IS DISTINCT FROM OLD.batch_id
            OR NEW.project_id      IS DISTINCT FROM OLD.project_id
            OR NEW.organization_id IS DISTINCT FROM OLD.organization_id
        ) THEN
            RAISE EXCEPTION
                'the planned quantities for batch % are issued and cannot be '
                'changed; raise a deviation instead', b_number
                USING ERRCODE = 'insufficient_privilege';
        END IF;

        -- The RECORD of what was done is writable only while the batch is
        -- being executed. Recording a weight against a completed batch is
        -- how a reconciliation gets "corrected" after somebody has already
        -- reviewed it.
        IF (NEW.actual_mass_kg IS DISTINCT FROM OLD.actual_mass_kg
            OR NEW.material_lot_id IS DISTINCT FROM OLD.material_lot_id)
           AND b_status NOT IN ('draft', 'authorized', 'in_progress') THEN
            RAISE EXCEPTION
                'batch % is % -- weights and lots can no longer be recorded',
                b_number, b_status
                USING ERRCODE = 'insufficient_privilege';
        END IF;
    END IF;

    RETURN COALESCE(NEW, OLD);
END
$fn$;

-- SECURITY DEFINER for the reason migration 015's equivalent is: the
-- guard looks its subject up, and a session whose RLS view of
-- `laboratory.batches` is empty would otherwise find no row and pass.
-- A check that walks through its own gap is a defect this platform has
-- already recorded three times.
ALTER FUNCTION laboratory.deny_component_mutation() SECURITY DEFINER;
ALTER FUNCTION laboratory.deny_component_mutation()
    SET search_path = laboratory, pg_catalog;
ALTER FUNCTION laboratory.deny_component_mutation() OWNER TO evercoat_owner;

DROP TRIGGER IF EXISTS batch_components_follow_batch ON laboratory.batch_components;
CREATE TRIGGER batch_components_follow_batch
    BEFORE INSERT OR UPDATE OR DELETE ON laboratory.batch_components
    FOR EACH ROW EXECUTE FUNCTION laboratory.deny_component_mutation();

-- A batch number is the identity every test result will eventually cite.
CREATE OR REPLACE FUNCTION laboratory.deny_batch_identity_change() RETURNS TRIGGER
    LANGUAGE plpgsql AS $fn$
BEGIN
    IF NEW.batch_number IS DISTINCT FROM OLD.batch_number THEN
        RAISE EXCEPTION 'batch_number is immutable once issued (% -> %)',
            OLD.batch_number, NEW.batch_number
            USING ERRCODE = 'insufficient_privilege';
    END IF;
    IF NEW.formula_version_id IS DISTINCT FROM OLD.formula_version_id THEN
        RAISE EXCEPTION
            'a batch cannot be re-pointed at a different formula version; '
            'the material it contains was weighed from the original'
            USING ERRCODE = 'insufficient_privilege';
    END IF;
    IF NEW.organization_id IS DISTINCT FROM OLD.organization_id
       OR NEW.project_id IS DISTINCT FROM OLD.project_id THEN
        RAISE EXCEPTION 'a batch cannot be moved between projects or organizations'
            USING ERRCODE = 'insufficient_privilege';
    END IF;
    -- A reviewed batch is a closed record. Only the review note may still
    -- be extended, and only while the outcome stands.
    IF OLD.status IN ('accepted','rejected') AND NEW.status IS DISTINCT FROM OLD.status THEN
        RAISE EXCEPTION
            'batch % has been reviewed (%) and its outcome cannot be changed',
            OLD.batch_number, OLD.status
            USING ERRCODE = 'insufficient_privilege';
    END IF;
    RETURN NEW;
END
$fn$;

DROP TRIGGER IF EXISTS batches_identity_immutable ON laboratory.batches;
CREATE TRIGGER batches_identity_immutable
    BEFORE UPDATE ON laboratory.batches
    FOR EACH ROW EXECUTE FUNCTION laboratory.deny_batch_identity_change();


-- ---------------------------------------------------------------------
-- PART 6 -- Indexes, RLS, ownership, grants
-- ---------------------------------------------------------------------

CREATE INDEX IF NOT EXISTS batches_org_status_idx
    ON laboratory.batches (organization_id, status);
CREATE INDEX IF NOT EXISTS batches_formula_version_idx
    ON laboratory.batches (formula_version_id);
CREATE INDEX IF NOT EXISTS batches_project_idx
    ON laboratory.batches (project_id, status);
CREATE INDEX IF NOT EXISTS batch_components_batch_idx
    ON laboratory.batch_components (batch_id, display_order);
-- "which batches used this lot?" -- the recall question. If a supplier
-- lot turns out to be off-specification, this is the query that finds
-- every batch and therefore every test result that depends on it.
CREATE INDEX IF NOT EXISTS batch_components_lot_idx
    ON laboratory.batch_components (material_lot_id);
CREATE INDEX IF NOT EXISTS batch_process_parameters_batch_idx
    ON laboratory.batch_process_parameters (batch_id, parameter_code);
CREATE INDEX IF NOT EXISTS batch_deviations_batch_idx
    ON laboratory.batch_deviations (batch_id, severity);
CREATE INDEX IF NOT EXISTS samples_batch_idx
    ON laboratory.samples (batch_id, status);
CREATE INDEX IF NOT EXISTS samples_org_status_idx
    ON laboratory.samples (organization_id, status);

ALTER TABLE laboratory.batches                    ENABLE ROW LEVEL SECURITY;
ALTER TABLE laboratory.batch_components           ENABLE ROW LEVEL SECURITY;
ALTER TABLE laboratory.batch_process_parameters   ENABLE ROW LEVEL SECURITY;
ALTER TABLE laboratory.batch_deviations           ENABLE ROW LEVEL SECURITY;
ALTER TABLE laboratory.samples                    ENABLE ROW LEVEL SECURITY;

-- PROJECT-SCOPED, byte-for-byte the policy shape migration 005 settled:
-- membership in USING, organization only in WITH CHECK, because requiring
-- membership to WRITE makes the first row of a restricted project
-- impossible to create.
DO $policies$
DECLARE t TEXT;
BEGIN
    FOREACH t IN ARRAY ARRAY[
        'laboratory.batches', 'laboratory.batch_components',
        'laboratory.batch_process_parameters', 'laboratory.batch_deviations',
        'laboratory.samples'
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

DO $ownership$
DECLARE r RECORD;
BEGIN
    IF NOT (SELECT rolsuper FROM pg_roles WHERE rolname = current_user)
       AND NOT pg_has_role(current_user, 'evercoat_owner', 'MEMBER') THEN
        RAISE EXCEPTION
            'role % can neither bypass ownership checks nor act as evercoat_owner',
            current_user;
    END IF;

    FOR r IN
        SELECT n.nspname AS schema_name, c.relname AS object_name, c.relkind AS kind
        FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
        WHERE n.nspname = 'laboratory'
          AND c.relkind IN ('r', 'p', 'S', 'v', 'm')
          AND pg_get_userbyid(c.relowner) <> 'evercoat_owner'
    LOOP
        IF r.kind = 'S' THEN
            EXECUTE format('ALTER SEQUENCE %I.%I OWNER TO evercoat_owner',
                           r.schema_name, r.object_name);
        ELSE
            EXECUTE format('ALTER TABLE %I.%I OWNER TO evercoat_owner',
                           r.schema_name, r.object_name);
        END IF;
    END LOOP;
END
$ownership$;

GRANT USAGE ON SCHEMA laboratory
    TO evercoat_app, evercoat_worker, evercoat_report;

-- DELETE only on batch_components, and only so a DRAFT sheet can have a
-- line removed before it is issued -- the trigger above refuses it the
-- moment the batch leaves draft. Everything else is retired by status.
GRANT SELECT, INSERT, UPDATE ON ALL TABLES IN SCHEMA laboratory TO evercoat_app;
GRANT DELETE ON laboratory.batch_components TO evercoat_app;
GRANT SELECT ON ALL TABLES IN SCHEMA laboratory
    TO evercoat_worker, evercoat_report;

ALTER DEFAULT PRIVILEGES FOR ROLE evercoat_owner IN SCHEMA laboratory
    GRANT SELECT, INSERT, UPDATE ON TABLES TO evercoat_app;
ALTER DEFAULT PRIVILEGES FOR ROLE evercoat_owner IN SCHEMA laboratory
    GRANT SELECT ON TABLES TO evercoat_worker, evercoat_report;

COMMIT;
