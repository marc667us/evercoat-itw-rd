-- 003_projects_pipeline_requirements.sql
-- =====================================================================
-- Slice 2 — innovation, projects, pipeline, requirements, tasks.
--
-- Extends the Slice 1 foundation. Every table here follows the rules
-- 001 established, without exception:
--
--   * UNIQUE (id, organization_id) on every tenant-scoped table
--   * composite child->parent FKs carrying both columns
--   * RLS on organization AND project membership
--   * RESTRICT, never CASCADE, on anything holding R&D history
--   * NUMERIC for measured quantities, never float
--
-- THE DECISION THAT SHAPES THIS MIGRATION: stage history is preserved,
-- not overwritten.
--
-- `projects.projects.current_stage` exists as a denormalised convenience
-- for list views. It is NOT the record. The record is
-- `workflow.project_stages` (one row per project per stage, with its own
-- lifecycle) plus `workflow.stage_transitions` (append-only, every move).
--
-- The source is explicit -- "the database should preserve complete stage
-- history rather than simply updating current_stage" -- and the reason is
-- the pipeline-bottleneck analytics the Lead dashboard depends on. "How
-- long does Rework take on average" is unanswerable from a single
-- mutable column. So is "who moved this project back to Formulation, and
-- why". Both are named requirements, and both need the history that a
-- naive implementation destroys on the first stage change.
--
-- PARTS
--   1  Innovation — opportunities
--   2  Projects — extend, milestones, risks
--   3  Pipeline — stage definitions (config), project stages, transitions
--   4  Requirements — structured, with verification
--   5  Tasks — My Work
--   6  RLS + grants
-- =====================================================================

BEGIN;

-- ---------------------------------------------------------------------
-- PART 1 — Innovation
-- ---------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS innovation.opportunities (
    id                  UUID NOT NULL DEFAULT gen_random_uuid(),
    organization_id     UUID NOT NULL REFERENCES core.organizations(id) ON DELETE RESTRICT,
    opportunity_code    TEXT NOT NULL,                    -- OPP-2026-006
    title               TEXT NOT NULL,
    market_need         TEXT,
    product_family      TEXT,
    target_application  TEXT,
    technical_concept   TEXT,
    status              TEXT NOT NULL DEFAULT 'draft'
                        CHECK (status IN ('draft','feasibility','awaiting_decision',
                                          'approved','rejected','on_hold')),
    priority            TEXT NOT NULL DEFAULT 'medium'
                        CHECK (priority IN ('low','medium','high','critical')),
    -- Director decision. Separate from status so "who decided, when, and
    -- why" survives a later status change.
    decision            TEXT CHECK (decision IN ('approve','reject','hold','more_information')),
    decided_by          UUID REFERENCES core.users(id) ON DELETE RESTRICT,
    decided_at          TIMESTAMPTZ,
    decision_rationale  TEXT,
    created_by          UUID NOT NULL REFERENCES core.users(id) ON DELETE RESTRICT,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (id),
    CONSTRAINT opportunities_org_code_key UNIQUE (organization_id, opportunity_code),
    CONSTRAINT opportunities_id_org_key   UNIQUE (id, organization_id),
    -- A decision without a decider is an unattributable approval.
    CONSTRAINT opportunities_decision_complete CHECK (
        (decision IS NULL AND decided_by IS NULL AND decided_at IS NULL)
        OR (decision IS NOT NULL AND decided_by IS NOT NULL AND decided_at IS NOT NULL)
    )
);


-- ---------------------------------------------------------------------
-- PART 2 — Projects
-- ---------------------------------------------------------------------
-- projects.projects was created in 001 as the resource-scope anchor.
-- Slice 2 adds the fields the module actually needs.

ALTER TABLE projects.projects
    ADD COLUMN IF NOT EXISTS opportunity_id      UUID,
    ADD COLUMN IF NOT EXISTS description         TEXT,
    ADD COLUMN IF NOT EXISTS commercial_objective TEXT,
    ADD COLUMN IF NOT EXISTS technical_objective  TEXT,
    ADD COLUMN IF NOT EXISTS priority            TEXT NOT NULL DEFAULT 'medium',
    ADD COLUMN IF NOT EXISTS lead_user_id        UUID,
    ADD COLUMN IF NOT EXISTS director_user_id    UUID,
    ADD COLUMN IF NOT EXISTS start_date          DATE,
    ADD COLUMN IF NOT EXISTS target_release_date DATE,
    ADD COLUMN IF NOT EXISTS authorized_by       UUID,
    ADD COLUMN IF NOT EXISTS authorized_at       TIMESTAMPTZ;

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'projects_priority_check') THEN
        ALTER TABLE projects.projects ADD CONSTRAINT projects_priority_check
            CHECK (priority IN ('low','medium','high','critical'));
    END IF;

    -- Composite FK: a project cannot descend from another organization's
    -- opportunity. RLS would hide the row but not prevent the reference.
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'projects_opportunity_fk') THEN
        ALTER TABLE projects.projects ADD CONSTRAINT projects_opportunity_fk
            FOREIGN KEY (opportunity_id, organization_id)
            REFERENCES innovation.opportunities (id, organization_id)
            ON DELETE RESTRICT;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'projects_lead_fk') THEN
        ALTER TABLE projects.projects ADD CONSTRAINT projects_lead_fk
            FOREIGN KEY (lead_user_id) REFERENCES core.users(id) ON DELETE RESTRICT;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'projects_director_fk') THEN
        ALTER TABLE projects.projects ADD CONSTRAINT projects_director_fk
            FOREIGN KEY (director_user_id) REFERENCES core.users(id) ON DELETE RESTRICT;
    END IF;
END
$$;

CREATE TABLE IF NOT EXISTS projects.milestones (
    id              UUID NOT NULL DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL,
    project_id      UUID NOT NULL,
    name            TEXT NOT NULL,
    description     TEXT,
    planned_date    DATE NOT NULL,
    actual_date     DATE,
    status          TEXT NOT NULL DEFAULT 'planned'
                    CHECK (status IN ('planned','in_progress','met','missed','cancelled')),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (id),
    CONSTRAINT milestones_id_org_key UNIQUE (id, organization_id),
    CONSTRAINT milestones_project_fk FOREIGN KEY (project_id, organization_id)
        REFERENCES projects.projects (id, organization_id) ON DELETE RESTRICT
);

CREATE TABLE IF NOT EXISTS projects.risks (
    id              UUID NOT NULL DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL,
    project_id      UUID NOT NULL,
    risk_code       TEXT NOT NULL,
    title           TEXT NOT NULL,
    description     TEXT,
    category        TEXT NOT NULL DEFAULT 'technical'
                    CHECK (category IN ('technical','material','process','schedule',
                                        'commercial','regulatory','supply')),
    -- Probability x impact, the standard matrix the Director dashboard
    -- renders. Stored as ordered levels rather than a computed score, so
    -- the scoring rule can change without rewriting history.
    probability     TEXT NOT NULL CHECK (probability IN ('low','medium','high')),
    impact          TEXT NOT NULL CHECK (impact IN ('low','medium','high')),
    status          TEXT NOT NULL DEFAULT 'open'
                    CHECK (status IN ('open','mitigating','closed','accepted','realised')),
    mitigation      TEXT,
    owner_user_id   UUID REFERENCES core.users(id) ON DELETE RESTRICT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (id),
    CONSTRAINT risks_org_code_key UNIQUE (organization_id, risk_code),
    CONSTRAINT risks_id_org_key   UNIQUE (id, organization_id),
    CONSTRAINT risks_project_fk FOREIGN KEY (project_id, organization_id)
        REFERENCES projects.projects (id, organization_id) ON DELETE RESTRICT
);


-- ---------------------------------------------------------------------
-- PART 3 — Pipeline
-- ---------------------------------------------------------------------
-- Stages are CONFIGURATION ROWS, not a code enum (ADR-017 / X-ref C17).
-- The MVP seeds 8 and the full build expands to 18; as rows that is an
-- INSERT, as an enum it is a migration plus a deploy.

CREATE TABLE IF NOT EXISTS workflow.stage_definitions (
    id                UUID NOT NULL DEFAULT gen_random_uuid(),
    organization_id   UUID NOT NULL REFERENCES core.organizations(id) ON DELETE RESTRICT,
    stage_code        TEXT NOT NULL,
    name              TEXT NOT NULL,
    sequence          INTEGER NOT NULL,
    entry_criteria    TEXT,
    required_deliverables TEXT,
    exit_criteria     TEXT,
    responsible_role  TEXT,
    requires_approval BOOLEAN NOT NULL DEFAULT FALSE,
    approval_role     TEXT,
    is_active         BOOLEAN NOT NULL DEFAULT TRUE,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (id),
    CONSTRAINT stage_definitions_org_code_key UNIQUE (organization_id, stage_code),
    CONSTRAINT stage_definitions_org_seq_key  UNIQUE (organization_id, sequence),
    CONSTRAINT stage_definitions_id_org_key   UNIQUE (id, organization_id),
    -- A stage that requires approval but names no approver role is a
    -- gate nobody can pass.
    CONSTRAINT stage_definitions_approval_complete CHECK (
        NOT requires_approval OR approval_role IS NOT NULL
    )
);

-- One row per project per stage. This is the record; current_stage is a
-- convenience.
CREATE TABLE IF NOT EXISTS workflow.project_stages (
    id                  UUID NOT NULL DEFAULT gen_random_uuid(),
    organization_id     UUID NOT NULL,
    project_id          UUID NOT NULL,
    stage_definition_id UUID NOT NULL,
    status              TEXT NOT NULL DEFAULT 'not_started'
                        CHECK (status IN ('not_started','active','awaiting_review',
                                          'awaiting_approval','passed','failed',
                                          'blocked','on_hold','rework_required','completed')),
    started_at          TIMESTAMPTZ,
    completed_at        TIMESTAMPTZ,
    blocked_reason      TEXT,
    -- Rework is a first-class relationship, not a status alone: "this
    -- stage was re-entered because of that failure" is exactly the link
    -- the bottleneck analytics need.
    rework_of_stage_id  UUID,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (id),
    CONSTRAINT project_stages_id_org_key UNIQUE (id, organization_id),
    CONSTRAINT project_stages_project_fk FOREIGN KEY (project_id, organization_id)
        REFERENCES projects.projects (id, organization_id) ON DELETE RESTRICT,
    CONSTRAINT project_stages_definition_fk FOREIGN KEY (stage_definition_id, organization_id)
        REFERENCES workflow.stage_definitions (id, organization_id) ON DELETE RESTRICT,
    CONSTRAINT project_stages_rework_fk FOREIGN KEY (rework_of_stage_id, organization_id)
        REFERENCES workflow.project_stages (id, organization_id) ON DELETE RESTRICT,
    CONSTRAINT project_stages_blocked_has_reason CHECK (
        status <> 'blocked' OR blocked_reason IS NOT NULL
    ),
    CONSTRAINT project_stages_completed_after_start CHECK (
        completed_at IS NULL OR started_at IS NULL OR completed_at >= started_at
    )
);

-- Append-only transition log. This is what makes "average days in
-- Rework" and "who sent this back, and why" answerable.
CREATE TABLE IF NOT EXISTS workflow.stage_transitions (
    id                UUID NOT NULL DEFAULT gen_random_uuid(),
    organization_id   UUID NOT NULL,
    project_id        UUID NOT NULL,
    from_stage_id     UUID,                      -- NULL on project start
    to_stage_id       UUID NOT NULL,
    from_status       TEXT,
    to_status         TEXT NOT NULL,
    transitioned_by   UUID NOT NULL REFERENCES core.users(id) ON DELETE RESTRICT,
    transitioned_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    reason            TEXT,
    PRIMARY KEY (id),
    CONSTRAINT stage_transitions_id_org_key UNIQUE (id, organization_id),
    CONSTRAINT stage_transitions_project_fk FOREIGN KEY (project_id, organization_id)
        REFERENCES projects.projects (id, organization_id) ON DELETE RESTRICT,
    CONSTRAINT stage_transitions_to_fk FOREIGN KEY (to_stage_id, organization_id)
        REFERENCES workflow.project_stages (id, organization_id) ON DELETE RESTRICT
);

-- Append-only, enforced. A transition log that can be rewritten answers
-- none of the questions it exists for.
CREATE OR REPLACE FUNCTION workflow.deny_transition_mutation() RETURNS TRIGGER
    LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION
        'workflow.stage_transitions is append-only; % is not permitted', TG_OP
        USING ERRCODE = 'insufficient_privilege';
END
$$;

DROP TRIGGER IF EXISTS stage_transitions_immutable ON workflow.stage_transitions;
CREATE TRIGGER stage_transitions_immutable
    BEFORE UPDATE OR DELETE ON workflow.stage_transitions
    FOR EACH ROW EXECUTE FUNCTION workflow.deny_transition_mutation();


-- ---------------------------------------------------------------------
-- PART 4 — Requirements
-- ---------------------------------------------------------------------
-- Structured records, never free text. The source is explicit that this
-- structure is what allows automatic test evaluation: a requirement of
-- "adhesion should be good" cannot be compared against 5.3 MPa.

CREATE TABLE IF NOT EXISTS projects.requirements (
    id                  UUID NOT NULL DEFAULT gen_random_uuid(),
    organization_id     UUID NOT NULL,
    project_id          UUID NOT NULL,
    requirement_code    TEXT NOT NULL,                 -- REQ-ADH-001
    category            TEXT NOT NULL DEFAULT 'technical'
                        CHECK (category IN ('technical','application','process',
                                            'safety','commercial','regulatory')),
    name                TEXT NOT NULL,
    description         TEXT,

    -- NUMERIC, never float. A requirement of >= 6.00 MPa compared against
    -- a float-rounded 5.999999 is a false failure, and in this system a
    -- false failure opens a failure investigation.
    target_value        NUMERIC(18, 6),
    minimum_value       NUMERIC(18, 6),
    maximum_value       NUMERIC(18, 6),
    canonical_unit      TEXT,
    -- Below the acceptance limit but within this margin renders YELLOW
    -- rather than GREEN ("PASS WITH LOW MARGIN"). Named here because
    -- CLAUDE.md 10 references requirement.warning_threshold and a
    -- configuration value with no column is a rule nobody can apply.
    warning_threshold   NUMERIC(18, 6),

    criticality         TEXT NOT NULL DEFAULT 'major'
                        CHECK (criticality IN ('critical','major','minor','informational')),
    verification_method TEXT NOT NULL DEFAULT 'test'
                        CHECK (verification_method IN ('test','inspection','analysis',
                                                       'demonstration','certification')),
    -- Set in Slice 5 when test methods exist. Nullable rather than a
    -- forward-declared FK to a table that does not yet exist.
    test_method_code    TEXT,
    source              TEXT,
    status              TEXT NOT NULL DEFAULT 'draft'
                        CHECK (status IN ('draft','under_review','approved','locked',
                                          'superseded','withdrawn')),
    revision            INTEGER NOT NULL DEFAULT 1,
    approved_by         UUID REFERENCES core.users(id) ON DELETE RESTRICT,
    approved_at         TIMESTAMPTZ,
    created_by          UUID NOT NULL REFERENCES core.users(id) ON DELETE RESTRICT,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (id),
    CONSTRAINT requirements_project_code_rev_key
        UNIQUE (project_id, requirement_code, revision),
    CONSTRAINT requirements_id_org_key UNIQUE (id, organization_id),
    CONSTRAINT requirements_project_fk FOREIGN KEY (project_id, organization_id)
        REFERENCES projects.projects (id, organization_id) ON DELETE RESTRICT,

    -- A numeric requirement needs a unit. "Adhesion >= 6" is ambiguous
    -- between MPa and N/mm2 by a factor that matters.
    CONSTRAINT requirements_numeric_needs_unit CHECK (
        (target_value IS NULL AND minimum_value IS NULL AND maximum_value IS NULL)
        OR canonical_unit IS NOT NULL
    ),
    -- min <= target <= max, where each is present. An unsatisfiable
    -- requirement is one nobody notices until a test fails against it.
    CONSTRAINT requirements_bounds_ordered CHECK (
        (minimum_value IS NULL OR maximum_value IS NULL OR minimum_value <= maximum_value)
        AND (minimum_value IS NULL OR target_value IS NULL OR minimum_value <= target_value)
        AND (maximum_value IS NULL OR target_value IS NULL OR target_value <= maximum_value)
    ),
    CONSTRAINT requirements_approval_complete CHECK (
        (approved_by IS NULL AND approved_at IS NULL)
        OR (approved_by IS NOT NULL AND approved_at IS NOT NULL)
    )
);


-- ---------------------------------------------------------------------
-- PART 5 — Tasks (My Work)
-- ---------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS workflow.tasks (
    id               UUID NOT NULL DEFAULT gen_random_uuid(),
    organization_id  UUID NOT NULL,
    project_id       UUID,                              -- NULL for org-level work
    task_type        TEXT NOT NULL,
    title            TEXT NOT NULL,
    description      TEXT,
    priority         TEXT NOT NULL DEFAULT 'medium'
                     CHECK (priority IN ('low','medium','high','critical')),
    status           TEXT NOT NULL DEFAULT 'open'
                     CHECK (status IN ('open','in_progress','blocked','completed',
                                       'delegated','cancelled')),
    assigned_user_id UUID REFERENCES core.users(id) ON DELETE RESTRICT,
    assigned_role    TEXT,
    due_date         DATE,
    -- What produced this task, and what it points at. Generic on purpose:
    -- a task can arise from a formula, test, failure, stage or message,
    -- and one polymorphic pair beats six nullable FK columns.
    source_event     TEXT,
    entity_type      TEXT,
    entity_id        UUID,
    required_action  TEXT,
    completed_at     TIMESTAMPTZ,
    completed_by     UUID REFERENCES core.users(id) ON DELETE RESTRICT,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (id),
    CONSTRAINT tasks_id_org_key UNIQUE (id, organization_id),
    CONSTRAINT tasks_project_fk FOREIGN KEY (project_id, organization_id)
        REFERENCES projects.projects (id, organization_id) ON DELETE RESTRICT,
    -- A task nobody owns is a task nobody does. One of the two must be set.
    CONSTRAINT tasks_has_an_owner CHECK (
        assigned_user_id IS NOT NULL OR assigned_role IS NOT NULL
    ),
    CONSTRAINT tasks_completion_complete CHECK (
        (completed_at IS NULL AND completed_by IS NULL)
        OR (completed_at IS NOT NULL AND completed_by IS NOT NULL)
    )
);


-- ---------------------------------------------------------------------
-- PART 6 — Indexes, RLS, grants
-- ---------------------------------------------------------------------

CREATE INDEX IF NOT EXISTS opportunities_org_status_idx
    ON innovation.opportunities (organization_id, status);
CREATE INDEX IF NOT EXISTS milestones_project_idx
    ON projects.milestones (project_id, planned_date);
CREATE INDEX IF NOT EXISTS risks_project_status_idx
    ON projects.risks (project_id, status);
CREATE INDEX IF NOT EXISTS project_stages_project_idx
    ON workflow.project_stages (project_id, status);
CREATE INDEX IF NOT EXISTS stage_transitions_project_time_idx
    ON workflow.stage_transitions (project_id, transitioned_at);
CREATE INDEX IF NOT EXISTS requirements_project_status_idx
    ON projects.requirements (project_id, status);
-- The My Work query: my open tasks, most urgent first.
CREATE INDEX IF NOT EXISTS tasks_assignee_open_idx
    ON workflow.tasks (assigned_user_id, status, due_date)
    WHERE status IN ('open', 'in_progress', 'blocked');

ALTER TABLE innovation.opportunities     ENABLE ROW LEVEL SECURITY;
ALTER TABLE projects.milestones          ENABLE ROW LEVEL SECURITY;
ALTER TABLE projects.risks               ENABLE ROW LEVEL SECURITY;
ALTER TABLE projects.requirements        ENABLE ROW LEVEL SECURITY;
ALTER TABLE workflow.stage_definitions   ENABLE ROW LEVEL SECURITY;
ALTER TABLE workflow.project_stages      ENABLE ROW LEVEL SECURITY;
ALTER TABLE workflow.stage_transitions   ENABLE ROW LEVEL SECURITY;
ALTER TABLE workflow.tasks               ENABLE ROW LEVEL SECURITY;

-- Organization-scoped: opportunities and stage definitions are org-wide
-- configuration, not project-confidential.
DROP POLICY IF EXISTS opportunities_org ON innovation.opportunities;
CREATE POLICY opportunities_org ON innovation.opportunities
    USING (core.rls_permissive() AND core.current_org_id() IS NULL
           OR organization_id = core.current_org_id());

DROP POLICY IF EXISTS stage_definitions_org ON workflow.stage_definitions;
CREATE POLICY stage_definitions_org ON workflow.stage_definitions
    USING (core.rls_permissive() AND core.current_org_id() IS NULL
           OR organization_id = core.current_org_id());

-- Project-scoped: these inherit the parent project's confidentiality, so
-- a restricted project's milestones, risks, requirements, stages and
-- tasks are invisible to non-members. Organization isolation alone would
-- leave them readable by any colleague (Codex F32).
DO $$
DECLARE t TEXT;
BEGIN
    FOREACH t IN ARRAY ARRAY[
        'projects.milestones', 'projects.risks', 'projects.requirements',
        'workflow.project_stages', 'workflow.stage_transitions', 'workflow.tasks'
    ]
    LOOP
        EXECUTE format('DROP POLICY IF EXISTS project_scope ON %s', t);
        EXECUTE format($p$
            CREATE POLICY project_scope ON %s
            USING (
                core.rls_permissive() AND core.current_org_id() IS NULL
                OR (
                    organization_id = core.current_org_id()
                    AND (
                        project_id IS NULL
                        OR EXISTS (
                            SELECT 1 FROM projects.projects p
                            WHERE p.id = %s.project_id
                              AND (p.confidentiality = 'normal'
                                   OR core.is_project_member(p.id))
                        )
                    )
                )
            )
        $p$, t, t);
    END LOOP;
END
$$;

GRANT SELECT, INSERT, UPDATE ON ALL TABLES IN SCHEMA innovation, projects, workflow
    TO evercoat_app;
GRANT SELECT ON ALL TABLES IN SCHEMA innovation, projects, workflow
    TO evercoat_worker, evercoat_report;

ALTER DEFAULT PRIVILEGES FOR ROLE evercoat_owner IN SCHEMA innovation, workflow
    GRANT SELECT, INSERT, UPDATE ON TABLES TO evercoat_app;
ALTER DEFAULT PRIVILEGES FOR ROLE evercoat_owner IN SCHEMA innovation, workflow
    GRANT SELECT ON TABLES TO evercoat_worker, evercoat_report;

COMMIT;
