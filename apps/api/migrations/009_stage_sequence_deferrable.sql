-- 009_stage_sequence_deferrable.sql
-- =====================================================================
-- Make the pipeline reorderable at all.
--
-- WHAT I GOT WRONG. `admin_stage_gates.reorder_stage_definitions` was
-- written on the belief that a single
--
--     UPDATE ... FROM unnest(:ids) WITH ORDINALITY
--
-- would be collision-free against UNIQUE (organization_id, sequence),
-- "because a non-deferrable unique constraint is checked once at
-- STATEMENT end". That is false in PostgreSQL. A non-deferrable UNIQUE
-- constraint is checked **per row, as each row is updated**. The single
-- statement therefore fails in exactly the same place as the naive
-- row-by-row version:
--
--     duplicate key value violates unique constraint
--     "stage_definitions_org_seq_key"
--     DETAIL: Key (organization_id, sequence)=(..., 1) already exists.
--
-- It was caught by writing the test that proves the claim rather than
-- asserting it in a comment. Nothing type-checks a belief about engine
-- semantics, and the reorder is the one operation an Administration
-- pipeline screen most obviously needs -- it would have failed on the
-- first swap a real administrator attempted.
--
-- THE FIX. DEFERRABLE INITIALLY IMMEDIATE.
--
-- Declaring the constraint DEFERRABLE changes HOW PostgreSQL enforces
-- it, not merely when it may be postponed. A non-deferrable unique
-- constraint is enforced by the index itself, per row. A deferrable one
-- is enforced by a constraint trigger, and with INITIALLY IMMEDIATE that
-- trigger fires at END OF STATEMENT.
--
-- That single change is what makes the reorder work. Intermediate
-- duplicates inside one statement are permitted; the state at the end of
-- the statement must still be unique.
--
--   * Ordinary writes are unaffected. For a one-row INSERT or UPDATE,
--     "end of statement" IS immediate, so a duplicate sequence is still
--     refused at the statement that causes it. Nothing became laxer --
--     asserted directly by
--     test_ordinary_writes_are_still_checked_immediately.
--
--   * The route does NOT issue SET CONSTRAINTS ... DEFERRED. It could,
--     which would push the check to COMMIT, but a violation would then
--     surface after the route returned -- past its error handling, as a
--     500 rather than a 409.
--
-- KNOWN CONSEQUENCE, recorded rather than discovered later: a DEFERRABLE
-- unique constraint cannot back an ON CONFLICT clause. Nothing uses
-- ON CONFLICT against this constraint today. Any future upsert on
-- stage_definitions must target the columns explicitly and will fail
-- loudly rather than silently -- which is why this is written down here.
-- =====================================================================

BEGIN;

ALTER TABLE workflow.stage_definitions
    DROP CONSTRAINT IF EXISTS stage_definitions_org_seq_key;

ALTER TABLE workflow.stage_definitions
    ADD CONSTRAINT stage_definitions_org_seq_key
    UNIQUE (organization_id, sequence)
    DEFERRABLE INITIALLY IMMEDIATE;

COMMENT ON CONSTRAINT stage_definitions_org_seq_key
    ON workflow.stage_definitions IS
    'Deferrable so a whole-pipeline reorder can pass through intermediate '
    'duplicate sequences inside one transaction. INITIALLY IMMEDIATE, so '
    'every ordinary write is still checked at the statement that causes '
    'it. Cannot back an ON CONFLICT clause.';

COMMIT;
