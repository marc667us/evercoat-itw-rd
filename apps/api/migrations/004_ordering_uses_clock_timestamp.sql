-- 004_ordering_uses_clock_timestamp.sql
-- =====================================================================
-- Make row ordering deterministic where order carries meaning.
--
-- THE BUG. `now()` in PostgreSQL returns TRANSACTION start time, not
-- statement time. Every row inserted inside one transaction therefore
-- shares an identical `created_at`, and `ORDER BY created_at` between
-- them is arbitrary.
--
-- Measured on this database:
--
--     BEGIN;
--     SELECT now();              -- 00:16:15.676033+00
--     SELECT pg_sleep(0.05);
--     SELECT now();              -- 00:16:15.676033+00   <-- identical
--     SELECT clock_timestamp();  -- 00:16:15.775975+00   <-- advanced
--
-- It surfaced as a failing test: a project sent Formulation -> Testing
-- -> back to Formulation could not reliably identify WHICH earlier visit
-- the rework pointed at, because both Formulation rows carried the same
-- created_at and the "most recent previous visit" lookup picked
-- whichever the planner happened to return first.
--
-- In production each transition is its own request and its own
-- transaction, so `now()` would usually differ and this would usually
-- work -- which is exactly what makes it dangerous. It fails only when
-- several transitions share a transaction (a seeder, a bulk import, a
-- Temporal workflow batching steps at Slice 11), and it fails by
-- silently mis-linking rework history rather than by erroring.
--
-- `clock_timestamp()` is the actual wall clock, evaluated per statement.
--
-- SCOPE. Only the two tables where creation order is load-bearing:
-- project_stages (which visit came first) and stage_transitions (the
-- order of the log). Everywhere else `now()` is correct and preferable,
-- because a transaction-consistent timestamp is the right semantic for
-- "when did this change happen".
-- =====================================================================

BEGIN;

ALTER TABLE workflow.project_stages
    ALTER COLUMN created_at SET DEFAULT clock_timestamp();

ALTER TABLE workflow.stage_transitions
    ALTER COLUMN transitioned_at SET DEFAULT clock_timestamp();

-- Ordering indexes now that the column is trustworthy for it.
CREATE INDEX IF NOT EXISTS project_stages_created_idx
    ON workflow.project_stages (project_id, stage_definition_id, created_at DESC);

COMMIT;
