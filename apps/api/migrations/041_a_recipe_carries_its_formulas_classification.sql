-- =====================================================================
-- 041 — a recipe carries its formula's classification
--
-- First half of I69. Codex's BLOCKER against 039, stated plainly:
--
--   *"Formula identity carries the label while the actual recipe lives in
--    child tables. This makes the lattice largely decorative outside the one
--    export query."*
--
-- That is exactly right. 039 classified `formulations.formulas` -- a row
-- holding a code, a name and an owner. The COMPOSITION is in
-- `formula_components`, the genealogy in `formula_versions`, the physical
-- realisation in `laboratory.batches`, and the investigation of what went
-- wrong in `quality.failures`. None of them carried a label, so
-- "FORMULA_RESTRICTED" described the label on the folder and not the papers
-- inside it.
--
-- ---------------------------------------------------------------------
-- 🔴 INHERITANCE, NOT A COLUMN PER TABLE
-- ---------------------------------------------------------------------
--
-- The obvious fix is `ALTER TABLE ... ADD COLUMN classification` five times.
-- That would be wrong, and wrong in this repository's most familiar way: five
-- copies of one fact, which nothing can keep in agreement. A component that
-- says INTERNAL while its formula says FORMULA_RESTRICTED is not a useful
-- disagreement -- it is a disclosure, and whichever query happens to read the
-- child wins.
--
-- A recipe's sensitivity IS its formula's sensitivity. So the label is
-- resolved through the parent, by one function, and reclassifying the formula
-- reclassifies everything derived from it in the same instant. That also gives
-- I49's purge-on-reclassification something coherent to act on later.
--
-- ---------------------------------------------------------------------
-- WHY IT IS NOT `SECURITY DEFINER`
-- ---------------------------------------------------------------------
--
-- Deliberately an ordinary invoker-rights function. It reads
-- `formulations.formulas`, which is RLS-protected, so it resolves a
-- classification only for a formula the CALLER can already see and returns
-- NULL otherwise. A definer version would answer for every tenant -- turning a
-- helper into a cross-tenant oracle, which is the shape recorded as I56 and
-- the one 037's `security_invoker=true` exists to avoid.
--
-- NULL therefore means "not visible to you, or no such version", and callers
-- must treat it as DENY -- the same contract as `core.classification_rank`.
--
-- ⚠️ WHAT THIS DOES NOT DO. It resolves a label; it does not enforce one.
-- `GET /versions/{id}` still returns a full composition to anyone with
-- `formula.view` (I68), and tests, samples, messages and MSD transcripts still
-- carry no label at all (I69's second half). This migration makes the label
-- ANSWERABLE for the recipe subtree, which is the prerequisite for enforcing
-- it anywhere. It is a foundation, not a control, and saying otherwise would
-- be the third overclaim of the day.
-- =====================================================================

BEGIN;

CREATE OR REPLACE FUNCTION formulations.effective_classification(p_version_id UUID)
    RETURNS TEXT
    LANGUAGE sql
    STABLE
    SET search_path = formulations, core, pg_temp
AS $$
    SELECT f.classification
    FROM formulations.formula_versions v
    JOIN formulations.formulas f
      ON f.id = v.formula_id
     AND f.organization_id = v.organization_id
    WHERE v.id = p_version_id
$$;

COMMENT ON FUNCTION formulations.effective_classification(UUID) IS
    'The classification a formula VERSION inherits from its formula. There is '
    'no per-version column on purpose: a child that disagrees with its parent '
    'is a disclosure, not a useful distinction. Invoker rights, so it answers '
    'only for a formula the caller can already see -- NULL means "not visible '
    'or no such version" and callers must treat it as DENY. Migration 041.';

GRANT EXECUTE ON FUNCTION formulations.effective_classification(UUID)
    TO evercoat_app, evercoat_report, evercoat_worker;

ALTER FUNCTION formulations.effective_classification(UUID) OWNER TO evercoat_owner;

COMMIT;


-- ---------------------------------------------------------------------
-- Prove the inheritance resolves, and that it is NOT definer-rights.
-- ---------------------------------------------------------------------
DO $probe$
DECLARE
    v_version UUID;
    v_direct  TEXT;
    v_derived TEXT;
    v_secdef  BOOLEAN;
BEGIN
    SELECT prosecdef INTO v_secdef
      FROM pg_proc p JOIN pg_namespace n ON n.oid = p.pronamespace
     WHERE n.nspname = 'formulations' AND p.proname = 'effective_classification';

    IF v_secdef THEN
        RAISE EXCEPTION
            '041: effective_classification is SECURITY DEFINER. It would then '
            'answer for every tenant, turning a helper into a cross-tenant '
            'oracle (see I56).';
    END IF;

    SELECT v.id, f.classification
      INTO v_version, v_direct
      FROM formulations.formula_versions v
      JOIN formulations.formulas f
        ON f.id = v.formula_id AND f.organization_id = v.organization_id
     LIMIT 1;

    IF v_version IS NULL THEN
        RAISE NOTICE '041: no formula version to probe against; tests/db covers it';
        RETURN;
    END IF;

    SELECT formulations.effective_classification(v_version) INTO v_derived;

    IF v_derived IS DISTINCT FROM v_direct THEN
        RAISE EXCEPTION
            '041: a version resolved % but its formula is classified %',
            v_derived, v_direct;
    END IF;
END $probe$;
