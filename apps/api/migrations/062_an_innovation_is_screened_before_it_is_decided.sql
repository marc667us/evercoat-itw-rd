-- =====================================================================
-- 062 — AN INNOVATION IS SCREENED BEFORE IT IS DECIDED
-- =====================================================================
--
-- Owner instruction, 2026-08-30: *"the innovation information must be screened
-- and researched at the material safety data and research center before
-- requirements are sent and pipeline follows up."*
--
-- The digital thread already runs Opportunity → Project → Requirement. This
-- puts the Research Center between the first two arrows for opportunities that
-- carry an investigation, so an idea taken off a competitor's card cannot
-- become a project on the strength of the note somebody pasted.
--
-- ---------------------------------------------------------------------
-- 🔴 A FOREIGN KEY, NOT A NAMING CONVENTION.
-- ---------------------------------------------------------------------
--
-- The obvious cheap version is to match an investigation to an opportunity by
-- putting the code in the title. This repository has already written down why
-- that fails: a check that infers a relationship from an identifier can be
-- renamed around, and nothing fails when it is. `pg_depend` is the standard it
-- set for itself. So the link is a column with a composite, tenant-qualified
-- foreign key, like every other child→parent reference here (ADR-014).
--
-- ---------------------------------------------------------------------
-- ⚠️ THE COLUMN IS NULLABLE, AND THE GATE IS THEREFORE CONDITIONAL.
-- ---------------------------------------------------------------------
--
-- Most opportunities in this application are not raised from the marketplace
-- and have no investigation. Making the column NOT NULL would gate every
-- opportunity ever created behind a Research Center step nobody asked for, and
-- would break `submit_opportunity` for the existing golden scenario on the
-- first run.
--
-- So: an opportunity WITH a linked investigation must have a finding recorded
-- before it can be submitted; one without is unchanged. The rule is enforced
-- in `submit_opportunity` and stated there, because it is a workflow rule
-- about two tables and a CHECK cannot see across them.
--
-- ⚠️ THAT MAKES THE PYTHON GATE LOAD-BEARING, and this file says so rather
-- than implying the database is holding it. What the database holds is the
-- LINK — that an investigation names a real opportunity in the same tenant,
-- and that neither can be deleted out from under the other.
-- =====================================================================

BEGIN;

ALTER TABLE research.investigations
    ADD COLUMN IF NOT EXISTS opportunity_id UUID;

-- Composite and tenant-qualified. RLS stops cross-tenant READS; it does not
-- stop cross-tenant REFERENCES, because referential integrity bypasses RLS
-- even under FORCE. `(id, organization_id)` is what makes this impossible to
-- point at another tenant's opportunity.
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
         WHERE conname = 'investigations_opportunity_fk'
    ) THEN
        ALTER TABLE research.investigations
            ADD CONSTRAINT investigations_opportunity_fk
            FOREIGN KEY (opportunity_id, organization_id)
            REFERENCES innovation.opportunities (id, organization_id)
            ON DELETE RESTRICT;
    END IF;
END
$$;

-- One investigation per opportunity. A second would make "has this been
-- screened?" ambiguous, and the gate would then depend on which row it found.
CREATE UNIQUE INDEX IF NOT EXISTS investigations_one_per_opportunity
    ON research.investigations (opportunity_id)
    WHERE opportunity_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS investigations_opportunity_idx
    ON research.investigations (organization_id, opportunity_id);

COMMENT ON COLUMN research.investigations.opportunity_id IS
    'The innovation this investigation screens. Set when an opportunity is '
    'raised from the public marketplace; submit_opportunity refuses to '
    'advance such an opportunity until the investigation records a finding.';

COMMIT;
