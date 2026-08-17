-- 010_stage_transition_from_fk.sql
-- =====================================================================
-- Close an ASYMMETRIC hole in workflow.stage_transitions.
--
-- Migration 003 gave `to_stage_id` a composite tenant-qualified foreign
-- key and gave `from_stage_id` NO foreign key at all:
--
--   stage_transitions_to_fk    FOREIGN KEY (to_stage_id, organization_id)
--                              REFERENCES workflow.project_stages (id, organization_id)
--   from_stage_id              -- nothing
--
-- Confirmed against the live catalogue, not read off the file: the table
-- carried exactly three foreign keys and none of them mentioned
-- from_stage_id.
--
-- WHY IT MATTERS. `from_stage_id` is nullable because the first
-- transition into a pipeline has no predecessor, and that nullability is
-- almost certainly why the constraint was skipped -- a nullable column
-- feels optional. It is not: a composite FK permits NULL perfectly well
-- and constrains every non-NULL value.
--
-- Without it, a tenant-A transition row can name a tenant-B
-- project_stage. Nothing in the application would notice, and the
-- project-dashboard "what changed" query joins straight through
-- from_stage_id to read a stage_code -- so another tenant's stage name
-- could be rendered on this tenant's dashboard. RLS does not help:
-- referential integrity bypasses it, and the join reads a row the
-- top-level organization_id predicate never touched (Codex C8).
--
-- ORPHAN CHECK BEFORE THE CONSTRAINT. Written to run as the migration
-- role, which is NOT a superuser on a deployed database. FORCE RLS has
-- previously broken a migration's own backfill and its own orphan check
-- on this platform, so the check is deliberately a plain aggregate over
-- the two tables rather than anything clever.
-- =====================================================================

BEGIN;

DO $$
DECLARE
    orphans BIGINT;
BEGIN
    SELECT COUNT(*) INTO orphans
    FROM workflow.stage_transitions t
    WHERE t.from_stage_id IS NOT NULL
      AND NOT EXISTS (
          SELECT 1 FROM workflow.project_stages ps
          WHERE ps.id = t.from_stage_id
            AND ps.organization_id = t.organization_id
      );

    IF orphans > 0 THEN
        RAISE EXCEPTION
            'cannot add stage_transitions_from_fk: % transition row(s) name a '
            'from_stage_id that does not exist in the same organization. These '
            'are cross-tenant or dangling references and must be investigated, '
            'not silently repaired -- stage_transitions is append-only history.',
            orphans;
    END IF;
END
$$;

ALTER TABLE workflow.stage_transitions
    DROP CONSTRAINT IF EXISTS stage_transitions_from_fk;

ALTER TABLE workflow.stage_transitions
    ADD CONSTRAINT stage_transitions_from_fk
    FOREIGN KEY (from_stage_id, organization_id)
    REFERENCES workflow.project_stages (id, organization_id)
    ON DELETE RESTRICT;

COMMENT ON COLUMN workflow.stage_transitions.from_stage_id IS
    'The stage being left. NULL only for the first transition into a '
    'pipeline, which has no predecessor. Composite FK on '
    '(from_stage_id, organization_id): nullable, but every non-NULL value '
    'must name a project_stage in the SAME organization.';

COMMIT;
