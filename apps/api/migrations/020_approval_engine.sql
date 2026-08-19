-- 020_approval_engine.sql
-- =====================================================================
-- Slice 6, first half -- ONE shared approval engine.
--
-- `CLAUDE.md` §9 opens with the rule this migration exists to make
-- structurally true: "One shared approval engine. Never re-implement
-- approval inside Formula, Test, Validation, Pilot, Qualification or
-- Release." `DATA_MODEL.md` §3.6 repeats it as a consequence: "Pilot,
-- Validation, Stability, Quality and Qualification add ZERO new approval
-- infrastructure."
--
-- That is why these tables are polymorphic over `(entity_type,
-- entity_id)` rather than being `test_approvals`. A per-entity approval
-- table is how a product ends up with five approval implementations that
-- agree on nothing -- and this repository's most repeated defect is
-- exactly that shape, two lists nothing can check against each other.
--
-- 🔴 ROUTE SNAPSHOTTING, AND WHY IT IS THE WHOLE POINT
-- ----------------------------------------------------
-- The plan specifies a "versioned approval engine with route
-- snapshotting". When an approval starts, the template's steps are
-- COPIED onto the route. Editing the template afterwards changes nothing
-- about approvals already in flight.
--
-- Without that, an administrator adding a QA step to
-- QUALIFICATION_CONFIRMATION would retroactively make every
-- previously-completed qualification incomplete -- results that were
-- signed off would silently become unapproved, and results half-way
-- through would acquire a signature nobody had asked for. A controlled
-- approval must be answerable in the terms that applied WHEN IT WAS
-- GIVEN, which is the same reasoning that makes a laboratory batch store
-- its weigh-up sheet rather than recompute it.
--
-- SEQUENTIAL AND PARALLEL, BOTH
-- -----------------------------
-- §9 requires both. `parallel_group` expresses it without a second
-- mechanism: steps sharing a group number may be decided in any order
-- and all must complete before the next group opens. A group of one is a
-- sequential step. There is no `is_parallel` boolean, because a boolean
-- cannot say WHICH steps are parallel WITH EACH OTHER.
--
-- INCOMPATIBLE DUTIES
-- -------------------
-- §9: "at qualification/release authority, the executing user may not
-- supply all mandatory approvals", and ADR-019 goes further -- QA
-- approval may never come from anyone who supplied a development-side
-- approval on the same record. `must_differ_from_group` carries that on
-- the step itself, so the rule travels with the snapshot rather than
-- living in code that a later template could contradict.
--
-- PARTS
--   1  Templates and their steps -- Administration configuration
--   2  Routes and route steps -- the snapshot
--   3  Seeding the five templates §9 names
--   4  Immutability
--   5  Indexes, RLS, ownership, grants
-- =====================================================================

BEGIN;

-- ---------------------------------------------------------------------
-- PART 1 -- Templates (configuration)
-- ---------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS workflow.approval_templates (
    id                  UUID NOT NULL DEFAULT gen_random_uuid(),
    organization_id     UUID NOT NULL REFERENCES core.organizations(id) ON DELETE RESTRICT,
    template_code       TEXT NOT NULL,          -- SCREENING_SIMPLE, RELEASE_CRITICAL
    name                TEXT NOT NULL,
    description         TEXT,
    -- Which authority level this template is the route FOR. A test at
    -- `qualification` authority finds its route by this column, so the
    -- mapping is data rather than a dictionary in Python that a
    -- deployment cannot change.
    authority_level     TEXT
                        CHECK (authority_level IS NULL OR authority_level IN
                               ('preliminary','development','controlled','validation',
                                'qualification','release')),
    is_active           BOOLEAN NOT NULL DEFAULT TRUE,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (id),
    CONSTRAINT approval_templates_org_code_key UNIQUE (organization_id, template_code),
    CONSTRAINT approval_templates_id_org_key   UNIQUE (id, organization_id),
    -- At most ONE active template per authority level. Two would make
    -- "which route applies?" ambiguous, and the engine would have to pick
    -- -- silently, and differently depending on ordering.
    CONSTRAINT approval_templates_authority_unique
        EXCLUDE (organization_id WITH =, authority_level WITH =)
        WHERE (is_active AND authority_level IS NOT NULL)
);

CREATE TABLE IF NOT EXISTS workflow.approval_template_steps (
    id                  UUID NOT NULL DEFAULT gen_random_uuid(),
    organization_id     UUID NOT NULL,
    template_id         UUID NOT NULL,
    step_number         INTEGER NOT NULL CHECK (step_number > 0),
    -- Steps sharing a group are PARALLEL with each other; the next group
    -- opens only when every mandatory step in this one has decided.
    parallel_group      INTEGER NOT NULL DEFAULT 1 CHECK (parallel_group > 0),
    -- Authorization is on PERMISSIONS, never role names. §6, and the
    -- reason ADR-019 gives: a role check cannot express a constraint that
    -- depends on per-record identity.
    permission_required TEXT NOT NULL,
    step_label          TEXT NOT NULL,
    is_mandatory        BOOLEAN NOT NULL DEFAULT TRUE,
    -- INCOMPATIBLE DUTIES. When set, whoever decides this step must not
    -- be anyone who decided a step in the named group. This is how "QA
    -- approval may never come from anyone who supplied a
    -- development-side approval" (ADR-019) is expressed as DATA, so it
    -- travels with the route snapshot.
    must_differ_from_group INTEGER CHECK (
        must_differ_from_group IS NULL OR must_differ_from_group > 0
    ),
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (id),
    CONSTRAINT approval_template_steps_id_org_key UNIQUE (id, organization_id),
    CONSTRAINT approval_template_steps_number_key UNIQUE (template_id, step_number),
    CONSTRAINT approval_template_steps_template_fk FOREIGN KEY (template_id, organization_id)
        REFERENCES workflow.approval_templates (id, organization_id) ON DELETE RESTRICT,
    -- A step cannot require difference from its own group: every member
    -- would have to differ from itself and nothing could ever be decided.
    CONSTRAINT approval_template_steps_group_is_not_self CHECK (
        must_differ_from_group IS NULL OR must_differ_from_group <> parallel_group
    )
);


-- ---------------------------------------------------------------------
-- PART 2 -- Routes: the snapshot
-- ---------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS workflow.approval_routes (
    id                  UUID NOT NULL DEFAULT gen_random_uuid(),
    organization_id     UUID NOT NULL REFERENCES core.organizations(id) ON DELETE RESTRICT,
    project_id          UUID NOT NULL,
    -- Polymorphic on purpose. One engine, every entity: `test` today,
    -- `formula_version`, `validation`, `pilot`, `qualification` and
    -- `product_release` later, with ZERO new tables.
    entity_type         TEXT NOT NULL
                        CHECK (entity_type IN ('test','formula_version','validation',
                                               'pilot','qualification','product_release')),
    entity_id           UUID NOT NULL,
    -- The template this came from, AND its code copied at the moment of
    -- copying. The foreign key answers "which template", the text answers
    -- "what was it called then" even if the template is later renamed or
    -- retired -- and a retired template must still explain a decided
    -- route.
    template_id         UUID,
    template_code       TEXT NOT NULL,
    status              TEXT NOT NULL DEFAULT 'open'
                        CHECK (status IN ('open','approved','rejected','cancelled')),
    opened_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
    closed_at           TIMESTAMPTZ,
    PRIMARY KEY (id),
    CONSTRAINT approval_routes_id_org_key UNIQUE (id, organization_id),
    -- ONE OPEN ROUTE PER ENTITY. Two would mean a result could be
    -- approved twice by different routes and nothing could say which
    -- decision governed.
    CONSTRAINT approval_routes_one_open_per_entity
        EXCLUDE (organization_id WITH =, entity_type WITH =, entity_id WITH =)
        WHERE (status = 'open'),
    CONSTRAINT approval_routes_template_fk FOREIGN KEY (template_id, organization_id)
        REFERENCES workflow.approval_templates (id, organization_id) ON DELETE RESTRICT,
    CONSTRAINT approval_routes_closure_complete CHECK (
        (status = 'open') = (closed_at IS NULL)
    )
);

CREATE TABLE IF NOT EXISTS workflow.approval_route_steps (
    id                  UUID NOT NULL DEFAULT gen_random_uuid(),
    organization_id     UUID NOT NULL,
    route_id            UUID NOT NULL,
    -- 🔴 COPIED FROM THE TEMPLATE, NOT REFERENCED.
    -- This is the snapshot. Editing the template after a route opens
    -- changes nothing here, which is what makes a decided approval
    -- answerable in the terms that applied when it was given.
    step_number         INTEGER NOT NULL CHECK (step_number > 0),
    parallel_group      INTEGER NOT NULL DEFAULT 1 CHECK (parallel_group > 0),
    permission_required TEXT NOT NULL,
    step_label          TEXT NOT NULL,
    is_mandatory        BOOLEAN NOT NULL DEFAULT TRUE,
    must_differ_from_group INTEGER,

    -- --- the decision, when it comes
    -- The seven types from §9. Richer than approve/reject deliberately:
    -- "return for correction" and "reject" have different consequences
    -- and collapsing them loses the difference.
    decision            TEXT CHECK (decision IS NULL OR decision IN
                               ('approve','approve_with_condition','return_for_correction',
                                'request_retest','reject','escalate','request_additional_test')),
    condition_text      TEXT,
    rationale           TEXT,
    decided_by          UUID REFERENCES core.users(id) ON DELETE RESTRICT,
    decided_at          TIMESTAMPTZ,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),

    PRIMARY KEY (id),
    CONSTRAINT approval_route_steps_id_org_key UNIQUE (id, organization_id),
    CONSTRAINT approval_route_steps_number_key UNIQUE (route_id, step_number),
    CONSTRAINT approval_route_steps_route_fk FOREIGN KEY (route_id, organization_id)
        REFERENCES workflow.approval_routes (id, organization_id) ON DELETE RESTRICT,
    -- A decision with no decider is an unattributable approval.
    CONSTRAINT approval_route_steps_decision_complete CHECK (
        (decision IS NULL AND decided_by IS NULL AND decided_at IS NULL)
        OR (decision IS NOT NULL AND decided_by IS NOT NULL AND decided_at IS NOT NULL)
    ),
    -- §9: conditional approval's stated limitation is MANDATORY and is
    -- preserved. An unconditioned conditional approval is a restriction
    -- nobody wrote down.
    CONSTRAINT approval_route_steps_condition_present CHECK (
        decision IS DISTINCT FROM 'approve_with_condition' OR condition_text IS NOT NULL
    ),
    -- A refusal must say why.
    CONSTRAINT approval_route_steps_refusals_state_why CHECK (
        decision IS NULL
        OR decision NOT IN ('return_for_correction','reject','request_retest','escalate')
        OR rationale IS NOT NULL
    )
);


-- ---------------------------------------------------------------------
-- PART 3 -- The five templates §9 names
-- ---------------------------------------------------------------------
-- Seeded for every organization that exists, and by the seed script for
-- new ones. They are CONFIGURATION rows, so a deployment may edit them --
-- but shipping with none would mean the approval engine had nothing to
-- route with, and "configurable" would mean "you must configure it
-- before anything works".
--
-- The routes, exactly as §9 states them:
--   SCREENING_SIMPLE           Tester -> Chemist/Engineer
--   OVERSIGHT_STANDARD         Tester -> Engineer (-> Lead on escalation)
--   VALIDATION_CONFIRMATION    Tester -> Engineer -> Chemist -> Lead
--   QUALIFICATION_CONFIRMATION Tester -> Engineer -> Chemist -> Lead -> QA
--   RELEASE_CRITICAL           Tester -> Engineer -> Chemist -> Lead -> QA -> Director
--
-- The "Tester" step is not an approval step: the tester EXECUTES, and
-- their execution is already recorded on the test. The routes below
-- therefore begin at the first APPROVING authority.

DO $seed$
DECLARE
    org RECORD;
    tpl UUID;
BEGIN
    FOR org IN SELECT id FROM core.organizations LOOP

        -- SCREENING_SIMPLE: one development-side approval.
        INSERT INTO workflow.approval_templates
            (organization_id, template_code, name, authority_level, description)
        VALUES (org.id, 'SCREENING_SIMPLE', 'Screening (simple)', 'preliminary',
                'Tester to Chemist or Engineer. Screening is preliminary authority '
                'and is never confirmation evidence.')
        ON CONFLICT (organization_id, template_code) DO NOTHING
        RETURNING id INTO tpl;

        IF tpl IS NOT NULL THEN
            INSERT INTO workflow.approval_template_steps
                (organization_id, template_id, step_number, parallel_group,
                 permission_required, step_label)
            VALUES (org.id, tpl, 1, 1, 'test.approve_development',
                    'Development approval (Chemist or Engineer)');
        END IF;

        -- OVERSIGHT_STANDARD: engineer, with the lead reachable on
        -- escalation. The escalation step is OPTIONAL -- it exists on the
        -- route so an escalation has somewhere to land, and does not
        -- block completion when nobody escalates.
        INSERT INTO workflow.approval_templates
            (organization_id, template_code, name, authority_level, description)
        VALUES (org.id, 'OVERSIGHT_STANDARD', 'Oversight (standard)', 'development',
                'Tester to Engineer, escalating to the Lead when required.')
        ON CONFLICT (organization_id, template_code) DO NOTHING
        RETURNING id INTO tpl;

        IF tpl IS NOT NULL THEN
            INSERT INTO workflow.approval_template_steps
                (organization_id, template_id, step_number, parallel_group,
                 permission_required, step_label, is_mandatory)
            VALUES
                (org.id, tpl, 1, 1, 'test.approve_development',
                 'Engineer approval', TRUE),
                (org.id, tpl, 2, 2, 'test.approve_lead',
                 'Lead approval (on escalation)', FALSE);
        END IF;

        -- VALIDATION_CONFIRMATION: engineer and chemist in PARALLEL, then
        -- the lead. Parallel because the two reviews are independent --
        -- process and formulation -- and serialising them only adds
        -- waiting.
        INSERT INTO workflow.approval_templates
            (organization_id, template_code, name, authority_level, description)
        VALUES (org.id, 'VALIDATION_CONFIRMATION', 'Validation confirmation', 'validation',
                'Tester to Engineer and Chemist (parallel), then Lead.')
        ON CONFLICT (organization_id, template_code) DO NOTHING
        RETURNING id INTO tpl;

        IF tpl IS NOT NULL THEN
            INSERT INTO workflow.approval_template_steps
                (organization_id, template_id, step_number, parallel_group,
                 permission_required, step_label)
            VALUES
                (org.id, tpl, 1, 1, 'test.approve_development', 'Engineer approval'),
                (org.id, tpl, 2, 1, 'test.approve_development', 'Chemist approval'),
                (org.id, tpl, 3, 2, 'test.approve_lead',        'Lead approval');
        END IF;

        -- QUALIFICATION_CONFIRMATION: adds independent QA, which MUST NOT
        -- be anyone from the development group. ADR-019, carried as data.
        INSERT INTO workflow.approval_templates
            (organization_id, template_code, name, authority_level, description)
        VALUES (org.id, 'QUALIFICATION_CONFIRMATION', 'Qualification confirmation',
                'qualification',
                'Tester to Engineer and Chemist (parallel), then Lead, then '
                'independent QA who supplied no development-side approval.')
        ON CONFLICT (organization_id, template_code) DO NOTHING
        RETURNING id INTO tpl;

        IF tpl IS NOT NULL THEN
            INSERT INTO workflow.approval_template_steps
                (organization_id, template_id, step_number, parallel_group,
                 permission_required, step_label, must_differ_from_group)
            VALUES
                (org.id, tpl, 1, 1, 'test.approve_development', 'Engineer approval', NULL),
                (org.id, tpl, 2, 1, 'test.approve_development', 'Chemist approval', NULL),
                (org.id, tpl, 3, 2, 'test.approve_lead',        'Lead approval', NULL),
                (org.id, tpl, 4, 3, 'test.approve_qa',          'Independent QA approval', 1);
        END IF;

        -- RELEASE_CRITICAL: the full ladder to the Director.
        INSERT INTO workflow.approval_templates
            (organization_id, template_code, name, authority_level, description)
        VALUES (org.id, 'RELEASE_CRITICAL', 'Release critical', 'release',
                'The full ladder: Engineer and Chemist, Lead, independent QA, '
                'then the Director.')
        ON CONFLICT (organization_id, template_code) DO NOTHING
        RETURNING id INTO tpl;

        IF tpl IS NOT NULL THEN
            INSERT INTO workflow.approval_template_steps
                (organization_id, template_id, step_number, parallel_group,
                 permission_required, step_label, must_differ_from_group)
            VALUES
                (org.id, tpl, 1, 1, 'test.approve_development', 'Engineer approval', NULL),
                (org.id, tpl, 2, 1, 'test.approve_development', 'Chemist approval', NULL),
                (org.id, tpl, 3, 2, 'test.approve_lead',        'Lead approval', NULL),
                (org.id, tpl, 4, 3, 'test.approve_qa',          'Independent QA approval', 1),
                (org.id, tpl, 5, 4, 'test.approve_director',    'Director approval', NULL);
        END IF;

        tpl := NULL;
    END LOOP;
END
$seed$;


-- ---------------------------------------------------------------------
-- PART 4 -- Immutability
-- ---------------------------------------------------------------------
-- A DECIDED STEP IS A SIGNATURE. It cannot be changed, and it cannot be
-- un-decided: §9 requires every approval to write an electronic decision
-- record into permanent audit history, and a signature that can be
-- withdrawn silently is not a signature.
CREATE OR REPLACE FUNCTION workflow.deny_decided_step_change() RETURNS TRIGGER
    LANGUAGE plpgsql AS $fn$
BEGIN
    IF OLD.decision IS NOT NULL THEN
        RAISE EXCEPTION
            'step % of this route was decided by % and cannot be changed; a '
            'decision is a signature', OLD.step_number, OLD.decided_by
            USING ERRCODE = 'insufficient_privilege';
    END IF;

    -- The SNAPSHOT is fixed even before it is decided. A route whose
    -- steps could be edited mid-flight is not a snapshot at all.
    IF NEW.step_number IS DISTINCT FROM OLD.step_number
       OR NEW.parallel_group IS DISTINCT FROM OLD.parallel_group
       OR NEW.permission_required IS DISTINCT FROM OLD.permission_required
       OR NEW.must_differ_from_group IS DISTINCT FROM OLD.must_differ_from_group
       OR NEW.is_mandatory IS DISTINCT FROM OLD.is_mandatory
       OR NEW.route_id IS DISTINCT FROM OLD.route_id
    THEN
        RAISE EXCEPTION
            'the route was snapshotted when it opened; its steps cannot be '
            'changed while it is in flight'
            USING ERRCODE = 'insufficient_privilege';
    END IF;

    RETURN NEW;
END
$fn$;

DROP TRIGGER IF EXISTS approval_route_steps_are_signatures ON workflow.approval_route_steps;
CREATE TRIGGER approval_route_steps_are_signatures
    BEFORE UPDATE ON workflow.approval_route_steps
    FOR EACH ROW EXECUTE FUNCTION workflow.deny_decided_step_change();

DROP TRIGGER IF EXISTS approval_route_steps_no_delete ON workflow.approval_route_steps;
CREATE TRIGGER approval_route_steps_no_delete
    BEFORE DELETE ON workflow.approval_route_steps
    FOR EACH ROW EXECUTE FUNCTION audit.deny_mutation();


-- ---------------------------------------------------------------------
-- PART 5 -- Indexes, RLS, ownership, grants
-- ---------------------------------------------------------------------

CREATE INDEX IF NOT EXISTS approval_templates_org_authority_idx
    ON workflow.approval_templates (organization_id, authority_level)
    WHERE is_active;
CREATE INDEX IF NOT EXISTS approval_template_steps_template_idx
    ON workflow.approval_template_steps (template_id, parallel_group, step_number);
CREATE INDEX IF NOT EXISTS approval_routes_entity_idx
    ON workflow.approval_routes (entity_type, entity_id);
CREATE INDEX IF NOT EXISTS approval_routes_open_idx
    ON workflow.approval_routes (organization_id, status)
    WHERE status = 'open';
CREATE INDEX IF NOT EXISTS approval_route_steps_route_idx
    ON workflow.approval_route_steps (route_id, parallel_group, step_number);
-- "What is waiting for me": undecided steps, by the permission they need.
CREATE INDEX IF NOT EXISTS approval_route_steps_pending_idx
    ON workflow.approval_route_steps (organization_id, permission_required)
    WHERE decision IS NULL;

ALTER TABLE workflow.approval_templates      ENABLE ROW LEVEL SECURITY;
ALTER TABLE workflow.approval_template_steps ENABLE ROW LEVEL SECURITY;
ALTER TABLE workflow.approval_routes         ENABLE ROW LEVEL SECURITY;
ALTER TABLE workflow.approval_route_steps    ENABLE ROW LEVEL SECURITY;

-- Templates are organization-wide configuration.
DO $policies$
DECLARE t TEXT;
BEGIN
    FOREACH t IN ARRAY ARRAY[
        'workflow.approval_templates', 'workflow.approval_template_steps',
        'workflow.approval_route_steps'
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

-- A ROUTE belongs to a project, because the thing being approved does.
-- `approval_route_steps` is organization-scoped above rather than
-- project-scoped: it has no `project_id`, and adding one would duplicate
-- a fact its route already holds. The route is the gate.
DROP POLICY IF EXISTS project_scope ON workflow.approval_routes;
CREATE POLICY project_scope ON workflow.approval_routes
    USING (
        core.rls_permissive() AND core.current_org_id() IS NULL
        OR (
            organization_id = core.current_org_id()
            AND EXISTS (
                SELECT 1 FROM projects.projects p
                WHERE p.id = approval_routes.project_id
                  AND (p.confidentiality = 'normal' OR core.is_project_member(p.id))
            )
        )
    )
    WITH CHECK (
        core.rls_permissive() AND core.current_org_id() IS NULL
        OR organization_id = core.current_org_id()
    );

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
        WHERE n.nspname = 'workflow'
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

GRANT SELECT, INSERT, UPDATE ON ALL TABLES IN SCHEMA workflow TO evercoat_app;
GRANT SELECT ON ALL TABLES IN SCHEMA workflow TO evercoat_worker, evercoat_report;

COMMIT;
