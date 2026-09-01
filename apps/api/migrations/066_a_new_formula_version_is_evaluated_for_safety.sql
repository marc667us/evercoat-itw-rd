-- =====================================================================
-- 066 — SafetyReviewRequired (spec §22, first chain)
-- =====================================================================
--
-- §22's first chain, written out in the source:
--
--     FormulaVersionCreated
--             ↓
--     Safety module evaluates
--             ↓
--     SafetyReviewRequired
--
-- ---------------------------------------------------------------------
-- 🔴 WHAT THIS FIXES: AN EVENT WITH NO READER.
-- ---------------------------------------------------------------------
--
-- 063 shipped `FormulaVersionCreated` and `revise_version` has announced it
-- since. **Nothing has ever consumed it.** 063's own comment said so plainly
-- ("Nothing consumes it yet"), which was honest, and left the log carrying a
-- fact no module reacts to — the mirror of the defect this repository has
-- counted twenty-three of. A table with no writer reads as capability; an
-- event with no reader reads as integration. Neither is.
--
-- This migration adds the name the reaction announces. The reaction itself is
-- `material_safety.on_formula_version_created`, wired in
-- `app/domains/events/wiring.py`.
--
-- ---------------------------------------------------------------------
-- ⚠️ THE VOCABULARY STILL GROWS ONLY WITH ITS EMITTER.
-- ---------------------------------------------------------------------
--
-- 063's first draft declared seven types while three had a writer, and the
-- rule it settled on is that a name lands in this CHECK in the same commit as
-- the code that can produce it — never before.
-- `test_every_declared_event_type_has_an_emitter` reads the application source
-- and fails if this list grows past it, so adding `SafetyReviewRequired` here
-- without shipping the consumer that emits it would turn that test red.
--
-- ⚠️ AND THE SUBJECT TYPE IS UNCHANGED. `SafetyReviewRequired` is ABOUT the
-- formula version that triggered it, so it reuses `formula_version` — already
-- in `domain_events_subject_check`. `subject_type` is derived from
-- `event_type` in `EVENT_SUBJECTS` and is never a caller's argument, so a
-- mismatched pair cannot be constructed.
-- =====================================================================

BEGIN;

ALTER TABLE workflow.domain_events
    DROP CONSTRAINT IF EXISTS domain_events_type_check;

ALTER TABLE workflow.domain_events
    ADD CONSTRAINT domain_events_type_check CHECK (event_type IN (
        'FormulaVersionCreated',
        'TestResultFinalized',
        'ResearchInvestigationUpdatedByTestResult',
        -- 066. Announced by the safety module when a newly created formula
        -- version contains a material that requires a safety data sheet and
        -- has none on file. That is the SAME rule the submission gate uses
        -- (`formulations._safety_checks`), reached through the same function,
        -- so this can never become a second opinion about the same question.
        'SafetyReviewRequired'
    ));

COMMIT;
