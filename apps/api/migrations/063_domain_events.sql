-- =====================================================================
-- 063 — DOMAIN EVENTS (spec §22, "Event integration")
-- =====================================================================
--
-- §22: *"Where practical, integrate through domain events rather than
-- hard-coded cross-module writes."*
--
-- ---------------------------------------------------------------------
-- 🔴 WHY THIS IS NOT `audit.events`. THE QUESTION WAS ASKED AND MEASURED.
-- ---------------------------------------------------------------------
--
-- This repository rejected a second document repository (ADR-033) for exactly
-- the shape this table could have, so the case was measured before it was
-- written rather than asserted afterwards. `audit.events` genuinely COULD have
-- carried these:
--
--   · `user_id` is NULLABLE, so a system-generated event fits;
--   · `evercoat_app` holds SELECT and INSERT and neither UPDATE nor DELETE,
--     so it is already an append-only log the application can read;
--   · its `id` is a monotonic bigint, so a consumer cursor needs no column on
--     the log at all -- the classic outbox pattern would have worked.
--
-- It is still the wrong home, for three reasons that are about MEANING and not
-- about mechanism:
--
--   1. `CLAUDE.md` §5: *"Audit is append-only and unreachable from ordinary UI
--      paths."* §22's events exist to be reached -- by another module, and by
--      a screen showing what happened to a record. Building that on audit
--      contradicts a stated rule of this system.
--   2. Audit's `action` vocabulary names USER ACTIONS (`formula_version.revised`).
--      A domain event names a FACT ABOUT THE DOMAIN (`FormulaVersionCreated`).
--      Overloading one string with both makes the integration contract and the
--      compliance record impossible to change independently.
--   3. The hash chain exists so audit is EVIDENCE. Putting every cross-module
--      reaction inside that write path makes a consumer's throughput an
--      audit-integrity concern, which is a bad trade in both directions.
--
-- ⚠️ THEY ARE WRITTEN TOGETHER, NOT INSTEAD OF EACH OTHER. Emitting an event
-- does not replace `write_audit`. An action that is audited and not announced
-- is invisible to other modules; an action announced and not audited is
-- untraceable. Both, in the caller's transaction, or neither.
--
-- ---------------------------------------------------------------------
-- 🔴 APPEND-ONLY IS ENFORCED BY A TRIGGER, NOT BY A GRANT ALONE.
-- ---------------------------------------------------------------------
--
-- A revoked UPDATE stops `evercoat_app`. It does not stop a migration, a
-- backfill, or a future role somebody adds with broader rights -- and this
-- project has a standing note that a REVOKE against a broader GRANT does
-- nothing. The trigger refuses UPDATE and DELETE for everyone, including the
-- owner, so the log cannot be rewritten by the account that would be used to
-- "fix" it.
--
-- ---------------------------------------------------------------------
-- ⚠️ NO `processed` COLUMN, DELIBERATELY.
-- ---------------------------------------------------------------------
--
-- A status column on an append-only log is a contradiction, and it is also the
-- wrong model: two consumers of the same event need two positions, not one
-- shared flag. Consumers that need a position get their own cursor table when
-- the first one needs it. The consumer this migration ships is SYNCHRONOUS --
-- it runs in the emitting transaction -- so it needs no cursor, and inventing
-- one now would be a table with no writer.
-- =====================================================================

BEGIN;

CREATE TABLE IF NOT EXISTS workflow.domain_events (
    id            BIGSERIAL PRIMARY KEY,
    organization_id UUID NOT NULL REFERENCES core.organizations (id),

    -- The event's name, e.g. 'FormulaVersionCreated'. Constrained by a CHECK
    -- rather than an enum: adding a value to an enum inside a transaction that
    -- also uses it is a PostgreSQL restriction this project has already met,
    -- and a CHECK is editable in one statement.
    event_type    TEXT NOT NULL,

    -- What the event is ABOUT. `subject_type` is the record kind and
    -- `subject_id` its id -- typed as UUID because every record this system
    -- announces has one.
    subject_type  TEXT NOT NULL,
    subject_id    UUID NOT NULL,

    -- Nullable: an event about an organization-wide record belongs to no
    -- project. Carried so RLS and a reader can scope by project without
    -- joining back to whichever table `subject_type` names.
    project_id    UUID,

    -- What a consumer needs that the subject row may no longer say. A test
    -- result that was RED when the event fired may be superseded later; the
    -- event records what was true at the time.
    payload       JSONB NOT NULL DEFAULT '{}'::jsonb,

    -- Nullable, because not every event has a person behind it. §22's chains
    -- are reactions, and a reaction has no actor.
    actor_id      UUID REFERENCES core.users (id),

    occurred_at   TIMESTAMPTZ NOT NULL DEFAULT now(),

    CONSTRAINT domain_events_id_org_key UNIQUE (id, organization_id),

    CONSTRAINT domain_events_org_fk
        FOREIGN KEY (organization_id) REFERENCES core.organizations (id),

    -- 🔴 THE VOCABULARY IS CLOSED, AND IT LISTS ONLY WHAT IS ACTUALLY EMITTED.
    --
    -- An event type nobody declared is a typo a consumer silently never
    -- matches -- the failure mode is silence, which is the one this project
    -- keeps paying for. So the CHECK is closed.
    --
    -- ⚠️ AND IT DOES NOT RUN AHEAD OF ITS EMITTERS. The first draft of this
    -- migration declared seven types while three had a writer: §22 names four
    -- chains and it was tempting to reserve the names. Four values that no code
    -- can produce is the same defect as a table with no writer, which this
    -- repository has counted twenty-three of -- it reads as capability and is
    -- decoration. `test_every_declared_event_type_has_an_emitter` parses the
    -- application source and fails if this list grows past it.
    --
    -- The vocabulary grows WITH its emitter, in the same commit, never before.
    CONSTRAINT domain_events_type_check CHECK (event_type IN (
        'FormulaVersionCreated',
        'TestResultFinalized',
        'ResearchInvestigationUpdatedByTestResult'
    )),

    CONSTRAINT domain_events_subject_check CHECK (subject_type IN (
        'formula_version',
        'test',
        'research_investigation'
    ))
);

COMMENT ON TABLE workflow.domain_events IS
    'Spec §22. Cross-module facts, announced rather than hard-coded. NOT the '
    'audit log: audit records who did what for compliance and is unreachable '
    'from ordinary UI paths (CLAUDE.md §5); this is reachable on purpose.';

-- Read paths. A consumer asks "what happened to this record?" and a screen
-- asks "what happened on this project?", so both are indexed.
CREATE INDEX IF NOT EXISTS domain_events_subject_idx
    ON workflow.domain_events (organization_id, subject_type, subject_id, id DESC);
CREATE INDEX IF NOT EXISTS domain_events_project_idx
    ON workflow.domain_events (organization_id, project_id, id DESC);
CREATE INDEX IF NOT EXISTS domain_events_type_idx
    ON workflow.domain_events (organization_id, event_type, id DESC);

-- ── append-only ──────────────────────────────────────────────────────────
CREATE OR REPLACE FUNCTION workflow.domain_events_append_only()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    RAISE EXCEPTION
        'workflow.domain_events is append-only; % is not permitted', TG_OP
        USING ERRCODE = 'restrict_violation';
END;
$$;

DROP TRIGGER IF EXISTS domain_events_no_update ON workflow.domain_events;
CREATE TRIGGER domain_events_no_update
    BEFORE UPDATE OR DELETE ON workflow.domain_events
    FOR EACH ROW EXECUTE FUNCTION workflow.domain_events_append_only();

-- ── RLS ──────────────────────────────────────────────────────────────────
-- 🔴 POLICIES BEFORE FORCE, IN THIS ORDER, IN THIS TRANSACTION. Migration 057
-- established that forcing RLS on a table with no policy locks out the owner
-- too, and the failure surfaces later as an empty result rather than an error.
ALTER TABLE workflow.domain_events ENABLE ROW LEVEL SECURITY;

-- ⚠️ `core.current_org_id()`, NOT `core.current_org()`. Measured against
-- `pg_policies` on this database rather than recalled: every existing policy in
-- `research` names `current_org_id`, and a policy naming a function that does
-- not exist fails at CREATE rather than silently -- but a policy naming the
-- WRONG existing function would not.
--
-- Two policies, matching the convention every other table here follows: a
-- scope policy for ALL and a separate INSERT policy carrying the WITH CHECK.
-- One `ALL` policy with both clauses reads equivalently and is not how this
-- schema is written, and a reader comparing tables should not have to work out
-- whether the difference is meaningful.
-- 🔴 THE SAME PREDICATE EVERY OTHER TENANT TABLE USES, NOT A STRICTER ONE.
--
-- The first version was `organization_id = core.current_org_id()` alone, which
-- is tighter and WRONG here: it rejected inserts from every existing service
-- path that does not set the GUC, and `confirm_test` -- the emitter this
-- migration exists for -- was one of them. Two tests went red immediately
-- (`test_018_testing`, `test_golden_scenario`) and they were right to.
--
-- Measured from `pg_policies` on `testing.tests` rather than recalled. A table
-- whose policy differs from its neighbours' is not more secure, it is
-- inconsistent -- and the next reader cannot tell whether the difference was
-- reasoned or accidental.
--
-- ⚠️ `core.rls_permissive()` IS `SELECT TRUE` TODAY, and I19 is the open issue
-- that says so. This table inherits that weakness with every other one; it
-- does not add to it, and it must not be the one place that pretends the
-- issue is closed.
DROP POLICY IF EXISTS domain_events_scope ON workflow.domain_events;
CREATE POLICY domain_events_scope ON workflow.domain_events
    FOR ALL
    USING (
        (core.rls_permissive() AND core.current_org_id() IS NULL)
        OR organization_id = core.current_org_id()
    );

DROP POLICY IF EXISTS domain_events_insert ON workflow.domain_events;
CREATE POLICY domain_events_insert ON workflow.domain_events
    FOR INSERT
    WITH CHECK (
        (core.rls_permissive() AND core.current_org_id() IS NULL)
        OR organization_id = core.current_org_id()
    );

ALTER TABLE workflow.domain_events FORCE ROW LEVEL SECURITY;

-- ── ownership ────────────────────────────────────────────────────────────
-- 🔴 THE MIGRATION RUNS AS `postgres`, SO WITHOUT THIS THE TABLE IS OWNED BY
--    `postgres` AND `evercoat_owner` CANNOT TOUCH IT.
--
-- `MIGRATION_DATABASE_URL` is the superuser in CI (`ci.yml:78`) and on this
-- host, so a table created here is owned by `postgres` while every other table
-- in `workflow` is owned by `evercoat_owner`. The symptom is not a migration
-- failure -- it is `permission denied for table domain_events` later, from the
-- owner role the db tests and the backup run as.
--
-- This repository has already paid for it once: commit `0108d7d`, "the public
-- surface gets its API, and the migration was owned by the superuser".
-- `014_object_ownership.sql` sweeps ownership, but it ran fifty migrations ago
-- and cannot reach a table created after it. So it is stated here, explicitly,
-- the way `011_audit_chain_per_organization.sql` states it.
ALTER TABLE workflow.domain_events OWNER TO evercoat_owner;
ALTER SEQUENCE workflow.domain_events_id_seq OWNER TO evercoat_owner;
ALTER FUNCTION workflow.domain_events_append_only() OWNER TO evercoat_owner;

-- ── privileges ───────────────────────────────────────────────────────────
-- SELECT and INSERT only. The trigger refuses UPDATE/DELETE anyway; the grant
-- says so a second time, at the layer a reader checks first.
REVOKE ALL ON workflow.domain_events FROM PUBLIC;
GRANT SELECT, INSERT ON workflow.domain_events TO evercoat_app;
GRANT USAGE, SELECT ON SEQUENCE workflow.domain_events_id_seq TO evercoat_app;

-- The agent tier reads the thread and never announces on it: an agent must not
-- be able to manufacture a fact that another module reacts to.
GRANT SELECT ON workflow.domain_events TO evercoat_agent;

COMMIT;
