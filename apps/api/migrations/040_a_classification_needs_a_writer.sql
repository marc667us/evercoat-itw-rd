-- =====================================================================
-- 040 — a classification needs a writer
--
-- Fixes a defect introduced by 039 one commit earlier, found by asking this
-- project's own most-repeated question of my own work.
--
-- ---------------------------------------------------------------------
-- 🔴 WHICH PRODUCTION PATH *WRITES* IT?  NONE.
-- ---------------------------------------------------------------------
--
-- 039 added `formulations.formulas.classification`, defaulting to the ceiling
-- `DIRECTOR_CONTROLLED` so that anything created without a decision is
-- maximally restricted. That default is right.
--
-- What 039 did not add was anything that MAKES the decision. Measured after
-- it shipped, with CI green:
--
--   * `create_formula` does not set the column, so every NEW formula is
--     `DIRECTOR_CONTROLLED`;
--   * no service, route, or script anywhere writes it -- a grep for the column
--     across `app/` returns reads only;
--   * `export_version` refuses above `R&D_RESTRICTED`.
--
-- Therefore **every formula created from now on can never be exported, by
-- anybody, ever** -- and no path exists to change that.
--
-- This is the "safety check that could only say BLOCKED" shape recorded on
-- `domains/materials/service.py` and again in I67's own note two hours ago.
-- Writing that warning did not stop me shipping it one column over. The
-- lesson stands and is now instrumented rather than restated: a test asserts a
-- newly created formula is exportable by its own rules.
--
-- ---------------------------------------------------------------------
-- THE FIX, IN TWO HALVES
-- ---------------------------------------------------------------------
--
-- 1. `create_formula` classifies deliberately -- `R&D_RESTRICTED`, matching
--    039's backfill, because a formula under development is proprietary
--    development work and that is what the level means. The database default
--    STAYS the ceiling: it is the backstop for a path that forgets, not the
--    value the application intends.
--
-- 2. `formula.classify` -- reclassification is a real, audited act.
--
-- 🔴 AND IT IS THE SAME PERMISSION SET AS `formula.export`, ON PURPOSE.
-- Lowering a classification is the *precondition* for exporting: if a Chemist
-- could reclassify, the export ceiling would be a formality they step over in
-- two requests. Whoever may take a recipe out of the building is exactly who
-- may decide how sensitive it is, and nobody else.
--
-- ⚠️ Lowering is the dangerous direction and is audited as such -- the event
-- records both levels, so "who made this exportable, and when" is answerable.
-- =====================================================================

BEGIN;

INSERT INTO core.permissions (code, domain, description) VALUES
    ('formula.classify', 'formulation',
     'Set or change a formula''s data classification. Held by exactly the '
     'roles that hold formula.export, because lowering a classification is the '
     'precondition for exporting one.')
ON CONFLICT (code) DO NOTHING;

CREATE OR REPLACE FUNCTION core._grant(p_role TEXT, VARIADIC p_perms TEXT[])
    RETURNS VOID LANGUAGE plpgsql AS $grant$
BEGIN
    INSERT INTO core.role_permissions (role_id, permission_id)
    SELECT r.id, p.id
    FROM core.roles r
    JOIN core.permissions p ON p.code = ANY(p_perms)
    WHERE r.code = p_role
    ON CONFLICT DO NOTHING;
END
$grant$;

SELECT core._grant('product_development_lead', 'formula.classify');
SELECT core._grant('qa_compliance_officer',    'formula.classify');
SELECT core._grant('administrator',            'formula.classify');

DROP FUNCTION core._grant(TEXT, TEXT[]);

COMMIT;


DO $probe$
DECLARE
    v_export  TEXT[];
    v_classify TEXT[];
BEGIN
    SELECT array_agg(r.code ORDER BY r.code) INTO v_export
      FROM core.roles r
      JOIN core.role_permissions rp ON rp.role_id = r.id
      JOIN core.permissions p ON p.id = rp.permission_id
     WHERE p.code = 'formula.export';

    SELECT array_agg(r.code ORDER BY r.code) INTO v_classify
      FROM core.roles r
      JOIN core.role_permissions rp ON rp.role_id = r.id
      JOIN core.permissions p ON p.id = rp.permission_id
     WHERE p.code = 'formula.classify';

    -- 🔴 The two sets must be IDENTICAL. If reclassification is ever granted
    -- more widely than export, the export ceiling becomes a formality that a
    -- broader group steps over in two requests.
    IF v_export IS DISTINCT FROM v_classify THEN
        RAISE EXCEPTION
            '040: formula.export is held by % and formula.classify by %. They '
            'must match exactly -- lowering a classification is the '
            'precondition for exporting.', v_export, v_classify;
    END IF;
END $probe$;
