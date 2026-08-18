-- 018_testing_methods_tests_replicates.sql
-- =====================================================================
-- Slice 5 -- the Test Module. The fourth and fifth links in the loop the
-- owner's plan says the first 45 hours must establish:
--
--   Project -> Formula -> Lab -> TEST -> ANALYSIS -> Approval
--            -> Failure -> Reformulation
--
-- The plan calls this slice "maximum depth, non-deferrable", and the
-- source says exactly what that means (ITWRD App.txt, §"Maximum-Depth
-- Module Implementation Strategy"):
--
--   "the Test Module is not complete merely because a form exists to
--    enter test results. It is complete only when the test method,
--    sample, raw measurements, calculations, analysis, traffic-light
--    decision, multilevel approval, failure routing, recommendations,
--    messaging, dashboard, analytics, product-model eligibility, audit
--    trail, and Playwright tests are all functional."
--
-- This migration provides the schema for: methods and their versions,
-- equipment and calibration, tests, RAW MEASUREMENTS PER REPLICATE, and
-- the review/approval record. Failure routing is Slice 6; messaging and
-- dashboards are Slice 7. What is here is built to depth.
--
-- 🔴 THE FIVE STORED AXES, AND THE THREE DERIVED FIELDS THAT ARE NOT HERE
-- ----------------------------------------------------------------------
-- `DATA_MODEL.md` §3.1 fixes the names and forbids three others:
-- `approved_result`, `technical_status` and `calculated_status` drifted
-- across four earlier documents, and the Supervisor found that the drift
-- would have left a safety-critical field off the server-controlled
-- blocklist under its real name (S4).
--
--   execution_status   did the physical work happen?
--   validity_status    was it done to method?
--   calculated_result  what did the numbers say? SERVER-COMPUTED ONLY
--   review_state       where is it in technical review?
--   approval_state     where is it in the approval chain?
--
-- `display_color`, `final_status` and `final_confirmed` are DERIVED and
-- server-owned. Two of them are DELIBERATELY ABSENT AS COLUMNS:
-- `app/calculations/testing.py` computes the disposition from the five
-- axes on every read. A stored `display_color` would be a second
-- implementation of a fourteen-rule algorithm that nothing could check
-- against the first -- the two-literals-in-two-files defect this
-- repository keeps rediscovering, applied to the one field a chemist
-- most needs to trust.
--
-- `final_confirmed` IS stored, because it is not derived: it records a
-- human act (`test.confirm`), and rule 13 reads it.
--
-- PARTS
--   1  Administration section 5 -- methods, versions, equipment, calibration
--   2  Tests
--   3  Raw measurements, per replicate, always
--   4  Review and approval records
--   5  Immutability
--   6  Indexes, RLS, ownership, grants
-- =====================================================================

BEGIN;

-- ---------------------------------------------------------------------
-- PART 1 -- Administration section 5
-- ---------------------------------------------------------------------
-- ADR-021: a configuration value referenced anywhere must have an
-- Administration screen in the same slice or earlier. The plan names this
-- section explicitly for Slice 5 -- "Test methods, method versions,
-- approval templates, equipment + calibration, warning-threshold policy"
-- -- because the Test Module is meaningless without configurable methods.
--
-- `cv_limit`, `calibration_breach_policy` and `trend_rule` are read by
-- rules 6, 1/8 and 10 of the traffic light. Each one lives here as a
-- column on a row somebody can edit, not as a constant in Python.

CREATE TABLE IF NOT EXISTS testing.test_methods (
    id                  UUID NOT NULL DEFAULT gen_random_uuid(),
    organization_id     UUID NOT NULL REFERENCES core.organizations(id) ON DELETE RESTRICT,
    method_code         TEXT NOT NULL,                  -- TM-ADH-001
    name                TEXT NOT NULL,
    property_measured   TEXT NOT NULL,                  -- adhesion, density, sanding time
    -- Canonical unit for this method's results. CLAUDE.md section 5:
    -- measurements are value + unit with canonical units, never free
    -- strings -- adhesion in MPa, density in g/cm3, time in minutes.
    canonical_unit      TEXT NOT NULL,
    -- How many replicates a result needs to be complete. Rule 5 compares
    -- against this, so a method that required zero would make every test
    -- complete on its first measurement.
    replicates_required INTEGER NOT NULL DEFAULT 3 CHECK (replicates_required >= 1),
    -- Rule 6. NULL means this method has no variability limit, which is
    -- a real state for a qualitative method -- and is NOT the same as a
    -- limit of zero, which would fail every test with any scatter.
    cv_limit            NUMERIC(8,4) CHECK (cv_limit IS NULL OR cv_limit >= 0),
    -- Rules 1 and 8. What happens when the equipment used was out of
    -- calibration: `invalidate` makes the result ungradeable, `deviate`
    -- records a minor deviation for a reviewer to judge.
    calibration_breach_policy TEXT NOT NULL DEFAULT 'invalidate'
                        CHECK (calibration_breach_policy IN ('invalidate','deviate')),
    -- Rule 10. A rule expression evaluated by the analytics layer; NULL
    -- means this method raises no trend alerts.
    trend_rule          TEXT,
    standard_reference  TEXT,                           -- ASTM D4541, ISO 4624
    description         TEXT,
    is_active           BOOLEAN NOT NULL DEFAULT TRUE,
    created_by          UUID NOT NULL REFERENCES core.users(id) ON DELETE RESTRICT,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (id),
    CONSTRAINT test_methods_org_code_key UNIQUE (organization_id, method_code),
    CONSTRAINT test_methods_id_org_key   UNIQUE (id, organization_id)
);

-- A method that changes is a NEW VERSION, not an edit. A result recorded
-- under revision 2 must stay traceable to revision 2 even after revision
-- 3 exists -- otherwise "was this tested to the current method?" becomes
-- unanswerable, which is the question a qualification audit asks first.
CREATE TABLE IF NOT EXISTS testing.method_versions (
    id                  UUID NOT NULL DEFAULT gen_random_uuid(),
    organization_id     UUID NOT NULL,
    method_id           UUID NOT NULL,
    revision            INTEGER NOT NULL CHECK (revision > 0),
    summary_of_change   TEXT,
    effective_from      DATE NOT NULL DEFAULT CURRENT_DATE,
    retired_on          DATE,
    procedure_text      TEXT,
    created_by          UUID NOT NULL REFERENCES core.users(id) ON DELETE RESTRICT,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (id),
    CONSTRAINT method_versions_id_org_key UNIQUE (id, organization_id),
    CONSTRAINT method_versions_revision_key UNIQUE (organization_id, method_id, revision),
    CONSTRAINT method_versions_method_fk FOREIGN KEY (method_id, organization_id)
        REFERENCES testing.test_methods (id, organization_id) ON DELETE RESTRICT,
    CONSTRAINT method_versions_dates_ordered CHECK (
        retired_on IS NULL OR retired_on >= effective_from
    )
);

CREATE TABLE IF NOT EXISTS testing.equipment (
    id                  UUID NOT NULL DEFAULT gen_random_uuid(),
    organization_id     UUID NOT NULL REFERENCES core.organizations(id) ON DELETE RESTRICT,
    equipment_code      TEXT NOT NULL,
    name                TEXT NOT NULL,
    manufacturer        TEXT,
    serial_number       TEXT,
    location            TEXT,
    status              TEXT NOT NULL DEFAULT 'in_service'
                        CHECK (status IN ('in_service','out_of_service','retired')),
    -- Denormalised for the queue view: "which instruments are due?".
    -- The RECORD is `equipment_calibrations`; this is a convenience, and
    -- the calibration check reads the calibration rows rather than this.
    calibration_due_on  DATE,
    created_by          UUID NOT NULL REFERENCES core.users(id) ON DELETE RESTRICT,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (id),
    CONSTRAINT equipment_org_code_key UNIQUE (organization_id, equipment_code),
    CONSTRAINT equipment_id_org_key   UNIQUE (id, organization_id)
);

CREATE TABLE IF NOT EXISTS testing.equipment_calibrations (
    id                  UUID NOT NULL DEFAULT gen_random_uuid(),
    organization_id     UUID NOT NULL,
    equipment_id        UUID NOT NULL,
    calibrated_on       DATE NOT NULL,
    valid_until         DATE NOT NULL,
    certificate_ref     TEXT,
    performed_by        TEXT,                           -- often an external body
    outcome             TEXT NOT NULL DEFAULT 'pass'
                        CHECK (outcome IN ('pass','pass_with_adjustment','fail')),
    notes               TEXT,
    recorded_by         UUID NOT NULL REFERENCES core.users(id) ON DELETE RESTRICT,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (id),
    CONSTRAINT equipment_calibrations_id_org_key UNIQUE (id, organization_id),
    CONSTRAINT equipment_calibrations_equipment_fk FOREIGN KEY (equipment_id, organization_id)
        REFERENCES testing.equipment (id, organization_id) ON DELETE RESTRICT,
    CONSTRAINT equipment_calibrations_dates_ordered CHECK (valid_until >= calibrated_on)
);


-- ---------------------------------------------------------------------
-- PART 2 -- Tests
-- ---------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS testing.tests (
    id                  UUID NOT NULL DEFAULT gen_random_uuid(),
    organization_id     UUID NOT NULL REFERENCES core.organizations(id) ON DELETE RESTRICT,
    project_id          UUID NOT NULL,
    test_number         TEXT NOT NULL,                  -- T-2026-0041
    -- THE PHYSICAL SAMPLE. CLAUDE.md section 5's traceability rule ends
    -- at "no test result without traceability to the physical sample",
    -- so this is NOT NULL: a test with no sample is a number with no
    -- provenance, and every downstream approval would inherit that.
    sample_id           UUID NOT NULL,
    method_id           UUID NOT NULL,
    -- The revision in force when the test was run. Nullable because a
    -- method may have no versioned revisions yet; when present it pins
    -- the result to the procedure that produced it.
    method_version_id   UUID,
    equipment_id        UUID,
    -- What the test is being compared against. Nullable: an exploratory
    -- measurement has no requirement, and `evaluate_against_requirement`
    -- reports `inconclusive` rather than inventing a pass.
    requirement_id      UUID,

    -- --- the five stored axes, exactly as DATA_MODEL.md §3.1 names them
    execution_status    TEXT NOT NULL DEFAULT 'not_started'
                        CHECK (execution_status IN
                               ('not_started','in_progress','complete','abandoned')),
    validity_status     TEXT NOT NULL DEFAULT 'valid'
                        CHECK (validity_status IN ('valid','minor_deviation','invalid')),
    -- 🔴 SERVER-COMPUTED ONLY. Rule 2 of the seven non-negotiables: Python
    -- owns deterministic scientific calculation. No route accepts this
    -- field; `record_result` computes it from the raw replicates.
    calculated_result   TEXT CHECK (calculated_result IS NULL OR calculated_result IN
                               ('pass','fail','inconclusive','improved',
                                'no_significant_change','worsened')),
    review_state        TEXT NOT NULL DEFAULT 'awaiting_review'
                        CHECK (review_state IN
                               ('awaiting_review','under_review','returned_for_correction',
                                'retest_requested','escalated','reviewed')),
    approval_state      TEXT NOT NULL DEFAULT 'not_required'
                        CHECK (approval_state IN
                               ('not_required','pending','conditionally_approved',
                                'approved','rejected')),

    -- --- orthogonal to the derivation, and not part of it
    test_purpose        TEXT NOT NULL DEFAULT 'oversight'
                        CHECK (test_purpose IN
                               ('screening','oversight','confirmation','improvement')),
    -- SIX levels, not five. `validation` is required because
    -- VALIDATION_CONFIRMATION is a distinct approval template (ADR-012),
    -- and a green screening test is never qualification evidence.
    authority_level     TEXT NOT NULL DEFAULT 'development'
                        CHECK (authority_level IN
                               ('preliminary','development','controlled','validation',
                                'qualification','release')),

    -- --- derived and server-owned; the human act, not the colour
    final_confirmed     BOOLEAN NOT NULL DEFAULT FALSE,
    confirmed_by        UUID REFERENCES core.users(id) ON DELETE RESTRICT,
    confirmed_at        TIMESTAMPTZ,

    -- --- the conditional approval's limitation, preserved (§9)
    approval_condition  TEXT,
    next_approver_role  TEXT,
    trend_alert         BOOLEAN NOT NULL DEFAULT FALSE,

    planned_for         DATE,
    executed_by         UUID REFERENCES core.users(id) ON DELETE RESTRICT,
    executed_at         TIMESTAMPTZ,
    -- The test this one replaces, when a retest was requested. The link
    -- is what makes retest lineage answerable: "how many attempts did
    -- this formula need?" is a question a failure investigation asks.
    supersedes_test_id  UUID,
    notes               TEXT,
    created_by          UUID NOT NULL REFERENCES core.users(id) ON DELETE RESTRICT,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now(),

    PRIMARY KEY (id),
    CONSTRAINT tests_org_number_key UNIQUE (organization_id, test_number),
    CONSTRAINT tests_id_org_key UNIQUE (id, organization_id),
    CONSTRAINT tests_id_project_org_key UNIQUE (id, project_id, organization_id),
    -- The sample carries the project, so a test cannot be run against a
    -- sample from another project. Three columns, the same reasoning as
    -- migrations 015 and 017.
    CONSTRAINT tests_sample_fk FOREIGN KEY (sample_id, project_id, organization_id)
        REFERENCES laboratory.samples (id, project_id, organization_id) ON DELETE RESTRICT,
    CONSTRAINT tests_method_fk FOREIGN KEY (method_id, organization_id)
        REFERENCES testing.test_methods (id, organization_id) ON DELETE RESTRICT,
    CONSTRAINT tests_method_version_fk FOREIGN KEY (method_version_id, organization_id)
        REFERENCES testing.method_versions (id, organization_id) ON DELETE RESTRICT,
    CONSTRAINT tests_equipment_fk FOREIGN KEY (equipment_id, organization_id)
        REFERENCES testing.equipment (id, organization_id) ON DELETE RESTRICT,
    CONSTRAINT tests_requirement_fk FOREIGN KEY (requirement_id, organization_id)
        REFERENCES projects.requirements (id, organization_id) ON DELETE RESTRICT,
    CONSTRAINT tests_supersedes_fk FOREIGN KEY (supersedes_test_id, project_id, organization_id)
        REFERENCES testing.tests (id, project_id, organization_id) ON DELETE RESTRICT,

    -- A confirmation with no confirmer is an unattributable confirmation.
    CONSTRAINT tests_confirmation_complete CHECK (
        (final_confirmed = FALSE AND confirmed_by IS NULL AND confirmed_at IS NULL)
        OR (final_confirmed = TRUE AND confirmed_by IS NOT NULL AND confirmed_at IS NOT NULL)
    ),
    -- 🔴 CONFIRMATION ONLY FROM `approved`, NEVER FROM
    -- `conditionally_approved`. DATA_MODEL.md §3.5 states it as a
    -- transition guard; enforced here so no code path can reach it.
    -- A conditional approval carries a limitation, and confirming one
    -- would silently discard that limitation.
    CONSTRAINT tests_confirmation_requires_full_approval CHECK (
        final_confirmed = FALSE OR approval_state = 'approved'
    ),
    -- §9: a conditional approval's stated limitation is MANDATORY. An
    -- unconditioned conditional approval is a yellow light with nothing
    -- written on it.
    CONSTRAINT tests_conditional_approval_states_its_condition CHECK (
        approval_state <> 'conditionally_approved' OR approval_condition IS NOT NULL
    ),
    -- A test cannot supersede itself.
    CONSTRAINT tests_supersedes_is_not_self CHECK (supersedes_test_id IS DISTINCT FROM id)
);


-- ---------------------------------------------------------------------
-- PART 3 -- Raw measurements, per replicate, always
-- ---------------------------------------------------------------------
-- 🔴 NEVER ONLY THE AGGREGATE.
--
-- CLAUDE.md section 10 and DATA_MODEL.md §3.3 both say it, and the reason
-- is mechanical rather than stylistic: rule 5 compares `replicates_valid`
-- against the method's requirement and rule 6 compares the coefficient of
-- variation against its limit. NEITHER can be recomputed from a stored
-- mean. A schema that kept only the average would make two of the
-- fourteen rules permanently unevaluable, and they would fail silently --
-- as a light that never turns yellow.
CREATE TABLE IF NOT EXISTS testing.test_replicates (
    id                  UUID NOT NULL DEFAULT gen_random_uuid(),
    organization_id     UUID NOT NULL,
    project_id          UUID NOT NULL,
    test_id             UUID NOT NULL,
    replicate_number    INTEGER NOT NULL CHECK (replicate_number > 0),
    -- The measured value, and its unit. The unit is stored per replicate
    -- rather than only on the method because a result recorded in the
    -- wrong unit is the classic silent error, and keeping it beside the
    -- number is what makes a mismatch detectable.
    measured_value      NUMERIC(18,6) NOT NULL,
    unit                TEXT NOT NULL,
    -- An EXCLUDED replicate is not a missing one: it was performed, it
    -- stays on the record, and it was set aside for a stated reason.
    -- Deleting it would rewrite the raw data.
    is_excluded         BOOLEAN NOT NULL DEFAULT FALSE,
    exclusion_reason    TEXT,
    observed_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
    recorded_by         UUID NOT NULL REFERENCES core.users(id) ON DELETE RESTRICT,
    notes               TEXT,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (id),
    CONSTRAINT test_replicates_id_org_key UNIQUE (id, organization_id),
    CONSTRAINT test_replicates_number_key UNIQUE (test_id, replicate_number),
    CONSTRAINT test_replicates_test_fk FOREIGN KEY (test_id, project_id, organization_id)
        REFERENCES testing.tests (id, project_id, organization_id) ON DELETE RESTRICT,
    -- Excluding a replicate without saying why removes data from the
    -- calculation with no record of the judgement that removed it.
    CONSTRAINT test_replicates_exclusion_states_why CHECK (
        is_excluded = FALSE OR exclusion_reason IS NOT NULL
    )
);


-- ---------------------------------------------------------------------
-- PART 4 -- Review and approval records
-- ---------------------------------------------------------------------
-- Append-only. "Every approval writes an electronic decision record into
-- the permanent audit history" (§9), and a decision log that can be
-- rewritten answers none of the questions it exists for.
--
-- The shared approval ENGINE -- five templates, sequential and parallel
-- routing -- is Slice 6, as the plan schedules it. What is here is the
-- record every template will write into, so Slice 6 adds routing and not
-- a second decision table.
CREATE TABLE IF NOT EXISTS testing.test_decisions (
    id                  UUID NOT NULL DEFAULT gen_random_uuid(),
    organization_id     UUID NOT NULL,
    project_id          UUID NOT NULL,
    test_id             UUID NOT NULL,
    -- The seven decision types from §9. Richer than approve/reject
    -- deliberately: "return for correction" and "reject" have different
    -- consequences and collapsing them loses the difference.
    decision            TEXT NOT NULL
                        CHECK (decision IN ('approve','approve_with_condition',
                                            'return_for_correction','request_retest',
                                            'reject','escalate','request_additional_test')),
    -- Which stage of review this was: technical review, or an approval
    -- at a named authority.
    decision_stage      TEXT NOT NULL DEFAULT 'review'
                        CHECK (decision_stage IN ('review','approval','confirmation')),
    authority_level     TEXT
                        CHECK (authority_level IS NULL OR authority_level IN
                               ('preliminary','development','controlled','validation',
                                'qualification','release')),
    condition_text      TEXT,
    rationale           TEXT,
    decided_by          UUID NOT NULL REFERENCES core.users(id) ON DELETE RESTRICT,
    decided_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (id),
    CONSTRAINT test_decisions_id_org_key UNIQUE (id, organization_id),
    CONSTRAINT test_decisions_test_fk FOREIGN KEY (test_id, project_id, organization_id)
        REFERENCES testing.tests (id, project_id, organization_id) ON DELETE RESTRICT,
    -- A conditional approval must state its condition, here as well as on
    -- the test: the decision record is what an audit reads.
    CONSTRAINT test_decisions_condition_present CHECK (
        decision <> 'approve_with_condition' OR condition_text IS NOT NULL
    ),
    -- A refusal must say why. Returning work with no reason is how a
    -- reviewer's judgement becomes unrepeatable.
    CONSTRAINT test_decisions_refusals_state_why CHECK (
        decision NOT IN ('return_for_correction','reject','request_retest','escalate')
        OR rationale IS NOT NULL
    )
);


-- ---------------------------------------------------------------------
-- PART 5 -- Immutability
-- ---------------------------------------------------------------------

CREATE OR REPLACE FUNCTION testing.deny_decision_mutation() RETURNS TRIGGER
    LANGUAGE plpgsql AS $fn$
BEGIN
    RAISE EXCEPTION
        'testing.test_decisions is append-only; % is not permitted', TG_OP
        USING ERRCODE = 'insufficient_privilege';
END
$fn$;

DROP TRIGGER IF EXISTS test_decisions_immutable ON testing.test_decisions;
CREATE TRIGGER test_decisions_immutable
    BEFORE UPDATE OR DELETE ON testing.test_decisions
    FOR EACH ROW EXECUTE FUNCTION testing.deny_decision_mutation();


-- Raw measurements are the evidence. A replicate may be EXCLUDED, with a
-- reason, and its value may never be edited or deleted.
CREATE OR REPLACE FUNCTION testing.deny_replicate_rewrite() RETURNS TRIGGER
    LANGUAGE plpgsql AS $fn$
BEGIN
    IF TG_OP = 'DELETE' THEN
        RAISE EXCEPTION
            'raw measurements are never deleted; exclude the replicate with a '
            'stated reason instead'
            USING ERRCODE = 'insufficient_privilege';
    END IF;

    IF NEW.measured_value IS DISTINCT FROM OLD.measured_value
       OR NEW.unit IS DISTINCT FROM OLD.unit
       OR NEW.replicate_number IS DISTINCT FROM OLD.replicate_number
       OR NEW.test_id IS DISTINCT FROM OLD.test_id
       OR NEW.observed_at IS DISTINCT FROM OLD.observed_at
    THEN
        RAISE EXCEPTION
            'a recorded measurement cannot be changed; exclude this replicate '
            'and record a new one'
            USING ERRCODE = 'insufficient_privilege';
    END IF;

    RETURN NEW;
END
$fn$;

DROP TRIGGER IF EXISTS test_replicates_are_evidence ON testing.test_replicates;
CREATE TRIGGER test_replicates_are_evidence
    BEFORE UPDATE OR DELETE ON testing.test_replicates
    FOR EACH ROW EXECUTE FUNCTION testing.deny_replicate_rewrite();


-- The test's identity and its physical provenance are fixed once issued.
CREATE OR REPLACE FUNCTION testing.deny_test_identity_change() RETURNS TRIGGER
    LANGUAGE plpgsql AS $fn$
BEGIN
    IF NEW.test_number IS DISTINCT FROM OLD.test_number THEN
        RAISE EXCEPTION 'test_number is immutable once issued (% -> %)',
            OLD.test_number, NEW.test_number
            USING ERRCODE = 'insufficient_privilege';
    END IF;
    -- Re-pointing a test at a different sample or method would silently
    -- re-attribute measurements that were taken from something else.
    IF NEW.sample_id IS DISTINCT FROM OLD.sample_id
       OR NEW.method_id IS DISTINCT FROM OLD.method_id THEN
        RAISE EXCEPTION
            'a test cannot be re-pointed at a different sample or method; the '
            'measurements on it were taken from the original'
            USING ERRCODE = 'insufficient_privilege';
    END IF;
    IF NEW.organization_id IS DISTINCT FROM OLD.organization_id
       OR NEW.project_id IS DISTINCT FROM OLD.project_id THEN
        RAISE EXCEPTION 'a test cannot be moved between projects or organizations'
            USING ERRCODE = 'insufficient_privilege';
    END IF;
    RETURN NEW;
END
$fn$;

DROP TRIGGER IF EXISTS tests_identity_immutable ON testing.tests;
CREATE TRIGGER tests_identity_immutable
    BEFORE UPDATE ON testing.tests
    FOR EACH ROW EXECUTE FUNCTION testing.deny_test_identity_change();


-- ---------------------------------------------------------------------
-- PART 6 -- Indexes, RLS, ownership, grants
-- ---------------------------------------------------------------------
-- CLAUDE.md names `(formula_version_id, test_date)` among the indexes a
-- deployment needs. A test reaches its formula version through its
-- sample and batch, so the equivalent here is the sample link plus the
-- execution date.

CREATE INDEX IF NOT EXISTS tests_org_status_idx
    ON testing.tests (organization_id, execution_status);
CREATE INDEX IF NOT EXISTS tests_project_idx
    ON testing.tests (project_id, execution_status);
CREATE INDEX IF NOT EXISTS tests_sample_executed_idx
    ON testing.tests (sample_id, executed_at);
CREATE INDEX IF NOT EXISTS tests_method_idx
    ON testing.tests (method_id);
CREATE INDEX IF NOT EXISTS tests_requirement_idx
    ON testing.tests (requirement_id);
CREATE INDEX IF NOT EXISTS tests_supersedes_idx
    ON testing.tests (supersedes_test_id);
-- The review and approval queues: what is waiting for ME.
CREATE INDEX IF NOT EXISTS tests_review_queue_idx
    ON testing.tests (organization_id, review_state)
    WHERE review_state IN ('awaiting_review', 'under_review');
CREATE INDEX IF NOT EXISTS tests_approval_queue_idx
    ON testing.tests (organization_id, approval_state)
    WHERE approval_state = 'pending';
CREATE INDEX IF NOT EXISTS test_replicates_test_idx
    ON testing.test_replicates (test_id, replicate_number);
CREATE INDEX IF NOT EXISTS test_decisions_test_idx
    ON testing.test_decisions (test_id, decided_at);
CREATE INDEX IF NOT EXISTS equipment_calibrations_equipment_idx
    ON testing.equipment_calibrations (equipment_id, valid_until DESC);
CREATE INDEX IF NOT EXISTS method_versions_method_idx
    ON testing.method_versions (method_id, revision DESC);

ALTER TABLE testing.test_methods            ENABLE ROW LEVEL SECURITY;
ALTER TABLE testing.method_versions         ENABLE ROW LEVEL SECURITY;
ALTER TABLE testing.equipment               ENABLE ROW LEVEL SECURITY;
ALTER TABLE testing.equipment_calibrations  ENABLE ROW LEVEL SECURITY;
ALTER TABLE testing.tests                   ENABLE ROW LEVEL SECURITY;
ALTER TABLE testing.test_replicates         ENABLE ROW LEVEL SECURITY;
ALTER TABLE testing.test_decisions          ENABLE ROW LEVEL SECURITY;

-- ORGANIZATION-SCOPED: methods, equipment and calibration are laboratory
-- infrastructure shared across every project. A method visible only to
-- members of one project would have to be duplicated for the next, and
-- two copies of a method is how a result gets compared against the wrong
-- procedure.
DO $policies$
DECLARE t TEXT;
BEGIN
    FOREACH t IN ARRAY ARRAY[
        'testing.test_methods', 'testing.method_versions',
        'testing.equipment', 'testing.equipment_calibrations'
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

-- PROJECT-SCOPED: a test result IS the confidential outcome of a
-- restricted project's work. Migration 005's policy shape verbatim.
DO $policies$
DECLARE t TEXT;
BEGIN
    FOREACH t IN ARRAY ARRAY[
        'testing.tests', 'testing.test_replicates', 'testing.test_decisions'
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
        WHERE n.nspname = 'testing'
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

GRANT USAGE ON SCHEMA testing TO evercoat_app, evercoat_worker, evercoat_report;

-- No DELETE anywhere in this schema. Raw measurements are excluded, not
-- removed; decisions are append-only; tests are abandoned, not deleted.
GRANT SELECT, INSERT, UPDATE ON ALL TABLES IN SCHEMA testing TO evercoat_app;
GRANT SELECT ON ALL TABLES IN SCHEMA testing TO evercoat_worker, evercoat_report;

ALTER DEFAULT PRIVILEGES FOR ROLE evercoat_owner IN SCHEMA testing
    GRANT SELECT, INSERT, UPDATE ON TABLES TO evercoat_app;
ALTER DEFAULT PRIVILEGES FOR ROLE evercoat_owner IN SCHEMA testing
    GRANT SELECT ON TABLES TO evercoat_worker, evercoat_report;

COMMIT;
