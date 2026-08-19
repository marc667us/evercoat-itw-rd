-- 021_failures_hypotheses_evidence.sql
-- =====================================================================
-- Slice 6, second half -- failure investigation and reformulation. The
-- last two links in the owner's loop:
--
--   Project -> Formula -> Lab -> Test -> Analysis -> Approval
--            -> FAILURE -> REFORMULATION
--
-- The shape is the source's own (ITWRD App.txt §26-29), not a paraphrase:
--
--   §26  one failure has many hypotheses; each carries possible cause,
--        mechanism, confidence, source, AI/human origin and status
--   §27  a hypothesis has many evidence records and one evidence record
--        may support several hypotheses -- MANY TO MANY, via a bridge
--   §28  one failure has many corrective actions
--   §29  a formula version references the failure that drove it, through
--        `formula_version_drivers`, "because a formula version may have
--        several reasons for being created"
--
-- 🔴 HYPOTHESIS IS NOT ROOT CAUSE, AND THE DATABASE ENFORCES IT
-- -------------------------------------------------------------
-- `CLAUDE.md` §7: "AI hypothesis ≠ accepted root cause.
-- `failure_hypotheses.status ∈ {proposed, under_review, accepted,
-- rejected}`; ONLY A HUMAN moves it to `accepted`."
--
-- Three mechanisms, because one would not be enough:
--
--   * `origin` records whether a hypothesis came from a person or from
--     MSD, and it is immutable. An AI suggestion that could be relabelled
--     as human-authored would defeat the whole distinction.
--   * `accepted_by` is NOT NULL whenever the status is `accepted`, so an
--     accepted root cause always names the human who accepted it. There
--     is no system actor that can satisfy it.
--   * at most ONE accepted hypothesis per failure, by partial unique
--     index. Two accepted root causes is not a stronger conclusion, it is
--     an unresolved investigation wearing the badge of a resolved one.
--
-- `failure.accept_root_cause` is held by the LEAD ALONE (migration 002),
-- and deliberately not by the administrator. Migration 002 says why:
-- "administering the system is not the same authority as making a
-- technical decision".
--
-- PARTS
--   1  Failures
--   2  Hypotheses, evidence, and the many-to-many bridge
--   3  Corrective actions
--   4  Why a formula version exists -- the driver bridge
--   5  Immutability and the accepted-root-cause rules
--   6  Indexes, RLS, ownership, grants
-- =====================================================================

BEGIN;

-- ---------------------------------------------------------------------
-- PART 1 -- Failures
-- ---------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS quality.failures (
    id                  UUID NOT NULL DEFAULT gen_random_uuid(),
    organization_id     UUID NOT NULL REFERENCES core.organizations(id) ON DELETE RESTRICT,
    project_id          UUID NOT NULL,
    failure_code        TEXT NOT NULL,                  -- FI-2026-0007
    title               TEXT NOT NULL,
    description         TEXT,
    -- The test that triggered it. §21: "If a critical test fails ->
    -- Create Failure Investigation". Nullable because §28's corrective
    -- actions also cover failures noticed outside a test -- a batch
    -- deviation, a field complaint -- and forcing a test would mean
    -- inventing one.
    test_id             UUID,
    -- The formula version under investigation. This is what makes
    -- "which formulations have a history of failure?" answerable.
    formula_version_id  UUID,
    batch_id            UUID,
    severity            TEXT NOT NULL DEFAULT 'major'
                        CHECK (severity IN ('critical','major','minor')),
    status              TEXT NOT NULL DEFAULT 'open'
                        CHECK (status IN ('open','investigating','root_cause_accepted',
                                          'action_in_progress','closed','cancelled')),
    opened_by           UUID NOT NULL REFERENCES core.users(id) ON DELETE RESTRICT,
    opened_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
    -- Closing an investigation is the Lead's act (`failure.close`), and
    -- a closure with no stated conclusion teaches the next person
    -- nothing.
    closed_by           UUID REFERENCES core.users(id) ON DELETE RESTRICT,
    closed_at           TIMESTAMPTZ,
    closure_summary     TEXT,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (id),
    CONSTRAINT failures_org_code_key UNIQUE (organization_id, failure_code),
    CONSTRAINT failures_id_org_key UNIQUE (id, organization_id),
    CONSTRAINT failures_id_project_org_key UNIQUE (id, project_id, organization_id),
    CONSTRAINT failures_test_fk FOREIGN KEY (test_id, project_id, organization_id)
        REFERENCES testing.tests (id, project_id, organization_id) ON DELETE RESTRICT,
    CONSTRAINT failures_formula_version_fk
        FOREIGN KEY (formula_version_id, project_id, organization_id)
        REFERENCES formulations.formula_versions (id, project_id, organization_id)
        ON DELETE RESTRICT,
    CONSTRAINT failures_batch_fk FOREIGN KEY (batch_id, project_id, organization_id)
        REFERENCES laboratory.batches (id, project_id, organization_id) ON DELETE RESTRICT,
    CONSTRAINT failures_closure_complete CHECK (
        (closed_by IS NULL) = (closed_at IS NULL)
    ),
    CONSTRAINT failures_closed_states_have_a_closer CHECK (
        status <> 'closed' OR closed_by IS NOT NULL
    ),
    -- A closed investigation must say what was concluded. "Closed" with
    -- no summary is the investigation equivalent of a restriction with no
    -- reason -- and the next person to hit this failure reads exactly
    -- this field.
    CONSTRAINT failures_closure_states_its_conclusion CHECK (
        status <> 'closed' OR closure_summary IS NOT NULL
    )
);


-- ---------------------------------------------------------------------
-- PART 2 -- Hypotheses and evidence
-- ---------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS quality.failure_hypotheses (
    id                  UUID NOT NULL DEFAULT gen_random_uuid(),
    organization_id     UUID NOT NULL,
    project_id          UUID NOT NULL,
    failure_id          UUID NOT NULL,
    -- §26's fields, named as the source names them.
    possible_cause      TEXT NOT NULL,
    mechanism           TEXT,
    confidence          TEXT NOT NULL DEFAULT 'medium'
                        CHECK (confidence IN ('low','medium','high')),
    source              TEXT,                           -- literature, prior failure, DOE
    -- 🔴 WHERE IT CAME FROM. Immutable, by trigger.
    -- §7 draws the line between an AI suggestion and an accepted root
    -- cause; a hypothesis whose origin could be edited would erase the
    -- line entirely.
    origin              TEXT NOT NULL DEFAULT 'human'
                        CHECK (origin IN ('human','msd')),
    status              TEXT NOT NULL DEFAULT 'proposed'
                        CHECK (status IN ('proposed','under_review','accepted','rejected')),
    -- Only set when accepted, and required then. There is no system
    -- actor: a root cause is accepted by a named person or not at all.
    accepted_by         UUID REFERENCES core.users(id) ON DELETE RESTRICT,
    accepted_at         TIMESTAMPTZ,
    rejection_reason    TEXT,
    proposed_by         UUID NOT NULL REFERENCES core.users(id) ON DELETE RESTRICT,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (id),
    CONSTRAINT failure_hypotheses_id_org_key UNIQUE (id, organization_id),
    CONSTRAINT failure_hypotheses_failure_fk
        FOREIGN KEY (failure_id, project_id, organization_id)
        REFERENCES quality.failures (id, project_id, organization_id) ON DELETE RESTRICT,
    CONSTRAINT failure_hypotheses_acceptance_complete CHECK (
        (accepted_by IS NULL) = (accepted_at IS NULL)
    ),
    -- 🔴 AN ACCEPTED ROOT CAUSE NAMES THE HUMAN WHO ACCEPTED IT.
    CONSTRAINT failure_hypotheses_accepted_names_a_human CHECK (
        status <> 'accepted' OR accepted_by IS NOT NULL
    ),
    -- A rejection must say why: the next investigator needs to know what
    -- was already ruled out and on what basis.
    CONSTRAINT failure_hypotheses_rejection_states_why CHECK (
        status <> 'rejected' OR rejection_reason IS NOT NULL
    )
);

-- 🔴 AT MOST ONE ACCEPTED ROOT CAUSE PER FAILURE.
-- Two accepted hypotheses is not a stronger conclusion; it is an
-- unresolved investigation wearing the badge of a resolved one, and every
-- corrective action downstream would be justified by an ambiguity.
CREATE UNIQUE INDEX IF NOT EXISTS failure_hypotheses_one_accepted_idx
    ON quality.failure_hypotheses (failure_id)
    WHERE status = 'accepted';

CREATE TABLE IF NOT EXISTS quality.failure_evidence (
    id                  UUID NOT NULL DEFAULT gen_random_uuid(),
    organization_id     UUID NOT NULL,
    project_id          UUID NOT NULL,
    failure_id          UUID NOT NULL,
    -- §27's list, exactly.
    evidence_type       TEXT NOT NULL
                        CHECK (evidence_type IN ('previous_experiment','literature',
                                                 'batch_deviation','material_lot_issue',
                                                 'test_trend','photograph','other')),
    summary             TEXT NOT NULL,
    detail              TEXT,
    -- What this evidence POINTS AT, when it points at a record in this
    -- system. Polymorphic because §27's list spans batches, lots, tests
    -- and documents, and six nullable foreign keys would be six columns
    -- that are almost always null.
    referenced_entity_type TEXT
                        CHECK (referenced_entity_type IS NULL OR referenced_entity_type IN
                               ('test','batch','material_lot','formula_version','document')),
    referenced_entity_id UUID,
    source_reference    TEXT,                           -- a citation, a URL, a report number
    -- Evidence from MSD is labelled, for the same reason a hypothesis is.
    origin              TEXT NOT NULL DEFAULT 'human'
                        CHECK (origin IN ('human','msd')),
    recorded_by         UUID NOT NULL REFERENCES core.users(id) ON DELETE RESTRICT,
    recorded_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (id),
    CONSTRAINT failure_evidence_id_org_key UNIQUE (id, organization_id),
    CONSTRAINT failure_evidence_failure_fk
        FOREIGN KEY (failure_id, project_id, organization_id)
        REFERENCES quality.failures (id, project_id, organization_id) ON DELETE RESTRICT,
    -- A reference is both halves or neither. A type with no id points at
    -- nothing; an id with no type cannot be resolved.
    CONSTRAINT failure_evidence_reference_complete CHECK (
        (referenced_entity_type IS NULL) = (referenced_entity_id IS NULL)
    )
);

-- §27: "A hypothesis may have several pieces of evidence, and one
-- evidence record may support several hypotheses. Use many-to-many."
--
-- The bridge carries `supports`, because the same observation can COUNT
-- AGAINST a hypothesis as readily as for it — and an investigation that
-- could only record confirming evidence is one that cannot rule anything
-- out.
CREATE TABLE IF NOT EXISTS quality.hypothesis_evidence (
    id                  UUID NOT NULL DEFAULT gen_random_uuid(),
    organization_id     UUID NOT NULL,
    hypothesis_id       UUID NOT NULL,
    evidence_id         UUID NOT NULL,
    relationship        TEXT NOT NULL DEFAULT 'supports'
                        CHECK (relationship IN ('supports','contradicts','inconclusive')),
    note                TEXT,
    linked_by           UUID NOT NULL REFERENCES core.users(id) ON DELETE RESTRICT,
    linked_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (id),
    CONSTRAINT hypothesis_evidence_id_org_key UNIQUE (id, organization_id),
    CONSTRAINT hypothesis_evidence_pair_key UNIQUE (hypothesis_id, evidence_id),
    CONSTRAINT hypothesis_evidence_hypothesis_fk
        FOREIGN KEY (hypothesis_id, organization_id)
        REFERENCES quality.failure_hypotheses (id, organization_id) ON DELETE RESTRICT,
    CONSTRAINT hypothesis_evidence_evidence_fk FOREIGN KEY (evidence_id, organization_id)
        REFERENCES quality.failure_evidence (id, organization_id) ON DELETE RESTRICT
);


-- ---------------------------------------------------------------------
-- PART 3 -- Corrective actions
-- ---------------------------------------------------------------------
-- §28's list, exactly: create new formula revision, repeat test, change
-- process, change raw material, start DOE.

CREATE TABLE IF NOT EXISTS quality.failure_actions (
    id                  UUID NOT NULL DEFAULT gen_random_uuid(),
    organization_id     UUID NOT NULL,
    project_id          UUID NOT NULL,
    failure_id          UUID NOT NULL,
    action_type         TEXT NOT NULL
                        CHECK (action_type IN ('formula_revision','repeat_test',
                                               'process_change','material_change',
                                               'start_doe','other')),
    description         TEXT NOT NULL,
    status              TEXT NOT NULL DEFAULT 'proposed'
                        CHECK (status IN ('proposed','approved','in_progress',
                                          'complete','cancelled')),
    assigned_to         UUID REFERENCES core.users(id) ON DELETE RESTRICT,
    due_date            DATE,
    completed_at        TIMESTAMPTZ,
    outcome             TEXT,
    raised_by           UUID NOT NULL REFERENCES core.users(id) ON DELETE RESTRICT,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (id),
    CONSTRAINT failure_actions_id_org_key UNIQUE (id, organization_id),
    CONSTRAINT failure_actions_failure_fk
        FOREIGN KEY (failure_id, project_id, organization_id)
        REFERENCES quality.failures (id, project_id, organization_id) ON DELETE RESTRICT,
    -- A completed action must say what happened. An action closed with no
    -- outcome is a task that was ticked, not a corrective action.
    CONSTRAINT failure_actions_completion_states_the_outcome CHECK (
        status <> 'complete' OR outcome IS NOT NULL
    ),
    CONSTRAINT failure_actions_completion_complete CHECK (
        (status = 'complete') = (completed_at IS NOT NULL)
    )
);


-- ---------------------------------------------------------------------
-- PART 4 -- Why does this formula version exist?
-- ---------------------------------------------------------------------
-- §29, verbatim in intent: "When a failure triggers a reformulation, the
-- new formula version should reference the originating failure. Use a
-- bridge... This is powerful because a formula version may have several
-- reasons for being created. It allows the system to answer: Why was F008
-- created?"
--
-- A bridge and not a `failure_id` column on the version, for the reason
-- the source gives: a revision may answer a failure AND chase a
-- requirement AND come out of an optimisation, and a single column
-- would force somebody to pick one and lose the rest.
CREATE TABLE IF NOT EXISTS formulations.formula_version_drivers (
    id                  UUID NOT NULL DEFAULT gen_random_uuid(),
    organization_id     UUID NOT NULL,
    project_id          UUID NOT NULL,
    formula_version_id  UUID NOT NULL,
    driver_type         TEXT NOT NULL
                        CHECK (driver_type IN ('failure','requirement','optimization',
                                               'cost','regulatory','customer_request','other')),
    failure_id          UUID,
    requirement_id      UUID,
    reason              TEXT NOT NULL,
    recorded_by         UUID NOT NULL REFERENCES core.users(id) ON DELETE RESTRICT,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (id),
    CONSTRAINT formula_version_drivers_id_org_key UNIQUE (id, organization_id),
    CONSTRAINT formula_version_drivers_version_fk
        FOREIGN KEY (formula_version_id, project_id, organization_id)
        REFERENCES formulations.formula_versions (id, project_id, organization_id)
        ON DELETE RESTRICT,
    CONSTRAINT formula_version_drivers_failure_fk
        FOREIGN KEY (failure_id, project_id, organization_id)
        REFERENCES quality.failures (id, project_id, organization_id) ON DELETE RESTRICT,
    CONSTRAINT formula_version_drivers_requirement_fk
        FOREIGN KEY (requirement_id, organization_id)
        REFERENCES projects.requirements (id, organization_id) ON DELETE RESTRICT,
    -- The named driver must actually be present. A row saying "this
    -- version exists because of a failure" with no failure attached
    -- answers "why was F008 created?" with the word "failure" and
    -- nothing else — which is worse than no row, because it looks like
    -- an answer.
    CONSTRAINT formula_version_drivers_failure_is_present CHECK (
        driver_type <> 'failure' OR failure_id IS NOT NULL
    ),
    CONSTRAINT formula_version_drivers_requirement_is_present CHECK (
        driver_type <> 'requirement' OR requirement_id IS NOT NULL
    ),
    -- One driver of each kind per version. Two "failure" rows pointing at
    -- the same failure is duplication, not a stronger reason.
    CONSTRAINT formula_version_drivers_unique
        UNIQUE (formula_version_id, driver_type, failure_id, requirement_id)
);


-- ---------------------------------------------------------------------
-- PART 5 -- Immutability, and the acceptance rules
-- ---------------------------------------------------------------------

-- A hypothesis's ORIGIN is fixed. Relabelling an MSD suggestion as
-- human-authored would erase the distinction §7 draws.
CREATE OR REPLACE FUNCTION quality.deny_hypothesis_origin_change() RETURNS TRIGGER
    LANGUAGE plpgsql AS $fn$
BEGIN
    IF NEW.origin IS DISTINCT FROM OLD.origin THEN
        RAISE EXCEPTION
            'a hypothesis''s origin is fixed at % and cannot be changed; §7 '
            'distinguishes an AI suggestion from an accepted root cause', OLD.origin
            USING ERRCODE = 'insufficient_privilege';
    END IF;
    IF NEW.failure_id IS DISTINCT FROM OLD.failure_id THEN
        RAISE EXCEPTION 'a hypothesis cannot be moved to a different investigation'
            USING ERRCODE = 'insufficient_privilege';
    END IF;
    -- An ACCEPTED root cause is a technical decision. Reversing it
    -- silently would leave every corrective action justified by a
    -- conclusion the system no longer holds. Rejecting it requires
    -- reopening the investigation deliberately, which is a service-level
    -- act with its own audit record.
    IF OLD.status = 'accepted' AND NEW.status IS DISTINCT FROM OLD.status THEN
        RAISE EXCEPTION
            'the accepted root cause of this failure cannot be silently changed; '
            'reopen the investigation instead'
            USING ERRCODE = 'insufficient_privilege';
    END IF;
    RETURN NEW;
END
$fn$;

DROP TRIGGER IF EXISTS failure_hypotheses_origin_immutable ON quality.failure_hypotheses;
CREATE TRIGGER failure_hypotheses_origin_immutable
    BEFORE UPDATE ON quality.failure_hypotheses
    FOR EACH ROW EXECUTE FUNCTION quality.deny_hypothesis_origin_change();

-- Evidence is a record of what was observed. It is linked and unlinked,
-- never rewritten.
CREATE OR REPLACE FUNCTION quality.deny_evidence_rewrite() RETURNS TRIGGER
    LANGUAGE plpgsql AS $fn$
BEGIN
    IF TG_OP = 'DELETE' THEN
        RAISE EXCEPTION
            'evidence is not deleted; unlink it from the hypothesis it no longer '
            'supports, or record why it was set aside'
            USING ERRCODE = 'insufficient_privilege';
    END IF;
    IF NEW.summary IS DISTINCT FROM OLD.summary
       OR NEW.evidence_type IS DISTINCT FROM OLD.evidence_type
       OR NEW.origin IS DISTINCT FROM OLD.origin
       OR NEW.recorded_by IS DISTINCT FROM OLD.recorded_by
    THEN
        RAISE EXCEPTION
            'a recorded observation cannot be rewritten; record a new piece of '
            'evidence instead'
            USING ERRCODE = 'insufficient_privilege';
    END IF;
    RETURN NEW;
END
$fn$;

DROP TRIGGER IF EXISTS failure_evidence_is_a_record ON quality.failure_evidence;
CREATE TRIGGER failure_evidence_is_a_record
    BEFORE UPDATE OR DELETE ON quality.failure_evidence
    FOR EACH ROW EXECUTE FUNCTION quality.deny_evidence_rewrite();


-- ---------------------------------------------------------------------
-- PART 6 -- Indexes, RLS, ownership, grants
-- ---------------------------------------------------------------------

CREATE INDEX IF NOT EXISTS failures_org_status_idx
    ON quality.failures (organization_id, status);
CREATE INDEX IF NOT EXISTS failures_project_idx
    ON quality.failures (project_id, status);
CREATE INDEX IF NOT EXISTS failures_test_idx ON quality.failures (test_id);
-- "Which formulations have a history of failure?" -- the question a
-- chemist asks before starting from an existing version.
CREATE INDEX IF NOT EXISTS failures_formula_version_idx
    ON quality.failures (formula_version_id);
CREATE INDEX IF NOT EXISTS failure_hypotheses_failure_idx
    ON quality.failure_hypotheses (failure_id, status);
CREATE INDEX IF NOT EXISTS failure_evidence_failure_idx
    ON quality.failure_evidence (failure_id, evidence_type);
CREATE INDEX IF NOT EXISTS hypothesis_evidence_hypothesis_idx
    ON quality.hypothesis_evidence (hypothesis_id);
CREATE INDEX IF NOT EXISTS hypothesis_evidence_evidence_idx
    ON quality.hypothesis_evidence (evidence_id);
CREATE INDEX IF NOT EXISTS failure_actions_failure_idx
    ON quality.failure_actions (failure_id, status);
-- "Why was F008 created?" -- §29's question, in one index.
CREATE INDEX IF NOT EXISTS formula_version_drivers_version_idx
    ON formulations.formula_version_drivers (formula_version_id);
-- And its inverse: "what did this failure change?"
CREATE INDEX IF NOT EXISTS formula_version_drivers_failure_idx
    ON formulations.formula_version_drivers (failure_id);

ALTER TABLE quality.failures              ENABLE ROW LEVEL SECURITY;
ALTER TABLE quality.failure_hypotheses    ENABLE ROW LEVEL SECURITY;
ALTER TABLE quality.failure_evidence      ENABLE ROW LEVEL SECURITY;
ALTER TABLE quality.hypothesis_evidence   ENABLE ROW LEVEL SECURITY;
ALTER TABLE quality.failure_actions       ENABLE ROW LEVEL SECURITY;
ALTER TABLE formulations.formula_version_drivers ENABLE ROW LEVEL SECURITY;

-- PROJECT-SCOPED. A failure investigation names what went wrong with a
-- restricted project's formulation, which is at least as confidential as
-- the formulation itself.
DO $policies$
DECLARE t TEXT;
BEGIN
    FOREACH t IN ARRAY ARRAY[
        'quality.failures', 'quality.failure_hypotheses', 'quality.failure_evidence',
        'quality.failure_actions', 'formulations.formula_version_drivers'
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

-- The bridge has no `project_id` of its own -- it would duplicate a fact
-- both its parents already hold -- so it is organization-scoped and the
-- hypothesis it points at is the gate.
DROP POLICY IF EXISTS org_scope ON quality.hypothesis_evidence;
CREATE POLICY org_scope ON quality.hypothesis_evidence
    USING (
        core.rls_permissive() AND core.current_org_id() IS NULL
        OR organization_id = core.current_org_id()
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
        WHERE n.nspname IN ('quality', 'formulations')
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

GRANT USAGE ON SCHEMA quality TO evercoat_app, evercoat_worker, evercoat_report;

-- DELETE only on the hypothesis/evidence bridge: unlinking a piece of
-- evidence from a hypothesis is a legitimate correction, and it destroys
-- neither the evidence nor the hypothesis. Everything else is retired by
-- status.
GRANT SELECT, INSERT, UPDATE ON ALL TABLES IN SCHEMA quality TO evercoat_app;
GRANT DELETE ON quality.hypothesis_evidence TO evercoat_app;
GRANT SELECT ON ALL TABLES IN SCHEMA quality TO evercoat_worker, evercoat_report;
GRANT SELECT, INSERT, UPDATE ON formulations.formula_version_drivers TO evercoat_app;
GRANT SELECT ON formulations.formula_version_drivers
    TO evercoat_worker, evercoat_report;

ALTER DEFAULT PRIVILEGES FOR ROLE evercoat_owner IN SCHEMA quality
    GRANT SELECT, INSERT, UPDATE ON TABLES TO evercoat_app;
ALTER DEFAULT PRIVILEGES FOR ROLE evercoat_owner IN SCHEMA quality
    GRANT SELECT ON TABLES TO evercoat_worker, evercoat_report;

COMMIT;
