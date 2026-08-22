-- =====================================================================
-- 039 — one classification lattice, and export as its own permission
--
-- Closes I48, and gives I43 the thing it needs to exist.
--
-- ---------------------------------------------------------------------
-- WHY THERE HAD TO BE A DECISION AT ALL
-- ---------------------------------------------------------------------
--
-- The source folder defines data classification TWICE, in two files, with two
-- vocabularies:
--
--   itw evercoat security.txt §31
--       PUBLIC · INTERNAL · CONFIDENTIAL · R&D RESTRICTED · MASTER FORMULA
--   revised msd and reseach.txt §34
--       INTERNAL · CONFIDENTIAL · R&D RESTRICTED · FORMULA RESTRICTED ·
--       DIRECTOR CONTROLLED
--
-- They are not interchangeable, and the difference is load-bearing: only one
-- of them contains PUBLIC, and PUBLIC is what the outbound AI gate (ADR-029)
-- is defined in terms of. Codex raised it; left unreconciled it would have
-- been settled silently by whoever implemented a filter first.
--
-- RESOLUTION -- one totally ordered lattice:
--
--   PUBLIC < INTERNAL < CONFIDENTIAL < R&D_RESTRICTED < FORMULA_RESTRICTED
--          < DIRECTOR_CONTROLLED
--
-- `MASTER FORMULA` maps to FORMULA_RESTRICTED: §31 describes it as the
-- released master recipe, which is what §34's FORMULA_RESTRICTED names.
-- DIRECTOR_CONTROLLED is the ceiling and has no counterpart in §31; it is
-- additive rather than conflicting.
--
-- ---------------------------------------------------------------------
-- 🔴 THREE PROPERTIES, AND EACH IS A DECISION RATHER THAN A DETAIL
-- ---------------------------------------------------------------------
--
-- 1. IT IS DATA, NOT AN ENUM. A rank column makes "at most PUBLIC" a
--    comparison rather than a hand-maintained list of level names in six
--    query sites -- which is this repository's most repeated defect. A CHECK
--    constraint of six literals would have needed a migration to reorder and
--    could not express "below X" at all.
--
-- 2. CLASSIFICATION IS NOT AN ACCESS GROUP AND NOT A PERMISSION. It is a
--    property of the DATA -- how sensitive this thing is. WHO may see it is a
--    separate question answered by permissions and project membership.
--    Collapsing the two is the §6 defect this project has already found six
--    times, a role standing in for an authorization.
--
--    Concretely: `projects.projects.confidentiality` ('normal'|'restricted')
--    is NOT renamed or merged into this. It answers "is membership required
--    to see this project", which is an access scope. A restricted project may
--    hold a PUBLIC datasheet; a normal project may hold a FORMULA_RESTRICTED
--    master recipe. Two axes, deliberately.
--
-- 3. UNSET IS THE CEILING. The column default is DIRECTOR_CONTROLLED, so
--    anything created without a decision is maximally restricted. A NULL
--    defaulting to the middle of a lattice is a disclosure waiting for the
--    first row somebody forgets to label.
--
-- ⚠️ THE BACKFILL IS A STATED DECISION, NOT THE DEFAULT. Applying the ceiling
-- to existing rows would be "safe" and useless -- it would classify every
-- formula as director-controlled and, the moment a read filter lands, empty
-- the application. So existing rows get a level chosen on the merits and
-- named here, and any later disagreement is with a decision rather than with
-- an accident:
--
--   formulations.formulas          -> R&D_RESTRICTED   proprietary recipes;
--                                     the whole reason this platform exists
--   material_documents SDS         -> INTERNAL         a supplier's hazard
--                                     sheet is not our secret, and §11 says
--                                     safety information must reach whoever
--                                     handles the material
--   material_documents TDS/CoA/other -> INTERNAL       supplier documents
--   material_documents regulatory  -> CONFIDENTIAL     submissions and
--                                     correspondence are not routine reading
--
-- ---------------------------------------------------------------------
-- I43 — export is its own permission
-- ---------------------------------------------------------------------
--
-- Security source §32: exporting formula information creates an exfiltration
-- risk, so it must require an explicit `formula.export` permission, be logged
-- every time, and for highly sensitive formulas require a second approval.
--
-- Until now export was inseparable from read: anyone with `formula.view`
-- could take the whole recipe out, and nothing recorded that they had. §31's
-- rule that view/edit/approve/release/export are SEPARATE permissions was
-- unimplementable because one of the five did not exist.
-- =====================================================================

BEGIN;

-- ---------------------------------------------------------------------
-- PART 1 — the lattice
-- ---------------------------------------------------------------------
-- Global reference data, like core.roles and core.permissions: no
-- organization_id, because a level means the same thing in every tenant and a
-- per-tenant lattice would make "at most PUBLIC" tenant-dependent.
CREATE TABLE IF NOT EXISTS core.classifications (
    code        TEXT PRIMARY KEY,
    rank        INT  NOT NULL UNIQUE,
    description TEXT NOT NULL
);

INSERT INTO core.classifications (code, rank, description) VALUES
    ('PUBLIC',              10, 'Publishable. THE ONLY level an external AI runtime or outbound query may carry (ADR-029).'),
    ('INTERNAL',            20, 'Ordinary internal working material, including supplier hazard and technical documents.'),
    ('CONFIDENTIAL',        30, 'Commercially sensitive: pricing, supplier terms, regulatory correspondence.'),
    ('R&D_RESTRICTED',      40, 'Proprietary development work -- formulas, test evidence, failure investigations.'),
    ('FORMULA_RESTRICTED',  50, 'Released master formulations. §31''s MASTER FORMULA maps here.'),
    ('DIRECTOR_CONTROLLED', 60, 'The ceiling, and the default for anything created without a decision.')
ON CONFLICT (code) DO NOTHING;

-- Comparison as a function so no caller hand-writes a level list. `core` is
-- fixed in the search_path because this is used inside policies and views.
CREATE OR REPLACE FUNCTION core.classification_rank(p_code TEXT)
    RETURNS INT
    LANGUAGE sql
    STABLE
    SET search_path = core, pg_temp
AS $$ SELECT rank FROM core.classifications WHERE code = p_code $$;

COMMENT ON FUNCTION core.classification_rank(TEXT) IS
    'Rank of a classification level, for "at most X" comparisons. Returns '
    'NULL for an unknown level -- and NULL compares as neither above nor '
    'below, so a caller must treat NULL as DENY. See migration 039.';

-- ---------------------------------------------------------------------
-- PART 2 — the columns
-- ---------------------------------------------------------------------
ALTER TABLE formulations.formulas
    ADD COLUMN IF NOT EXISTS classification TEXT;
ALTER TABLE materials.material_documents
    ADD COLUMN IF NOT EXISTS classification TEXT;

-- Backfill on the merits (see the header), BEFORE the NOT NULL.
UPDATE formulations.formulas
   SET classification = 'R&D_RESTRICTED'
 WHERE classification IS NULL;

UPDATE materials.material_documents
   SET classification = CASE
           WHEN document_type = 'regulatory' THEN 'CONFIDENTIAL'
           ELSE 'INTERNAL'
       END
 WHERE classification IS NULL;

ALTER TABLE formulations.formulas
    ALTER COLUMN classification SET NOT NULL,
    ALTER COLUMN classification SET DEFAULT 'DIRECTOR_CONTROLLED';
ALTER TABLE materials.material_documents
    ALTER COLUMN classification SET NOT NULL,
    ALTER COLUMN classification SET DEFAULT 'DIRECTOR_CONTROLLED';

-- FK rather than CHECK: the lattice is data, so a level that does not exist
-- must be unwritable, and adding a level must not require a migration to
-- every table that carries one.
ALTER TABLE formulations.formulas
    DROP CONSTRAINT IF EXISTS formulas_classification_fk;
ALTER TABLE formulations.formulas
    ADD CONSTRAINT formulas_classification_fk
    FOREIGN KEY (classification) REFERENCES core.classifications (code);

ALTER TABLE materials.material_documents
    DROP CONSTRAINT IF EXISTS material_documents_classification_fk;
ALTER TABLE materials.material_documents
    ADD CONSTRAINT material_documents_classification_fk
    FOREIGN KEY (classification) REFERENCES core.classifications (code);

-- Migration 014's rule: every object in an application schema belongs to
-- `evercoat_owner`. CREATE TABLE leaves it owned by whoever ran the migration
-- -- `postgres` here and in CI -- and then the owner role cannot even SELECT
-- it, so `classification_rank` (a plain SQL function, running as its caller)
-- fails with "permission denied" for every db test. Caught by running them.
ALTER TABLE core.classifications OWNER TO evercoat_owner;
ALTER FUNCTION core.classification_rank(TEXT) OWNER TO evercoat_owner;

GRANT SELECT ON core.classifications TO evercoat_app, evercoat_report, evercoat_worker;

-- ---------------------------------------------------------------------
-- PART 3 — I43: export is its own permission
-- ---------------------------------------------------------------------
INSERT INTO core.permissions (code, domain, description) VALUES
    ('formula.export', 'formulation',
     'Export a formula''s full composition out of the application. Separate '
     'from formula.view because reading a recipe on screen and removing it '
     'are different acts (security source §32). Every export is audited.')
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

-- 🔴 DELIBERATELY NARROW, AND NOT GIVEN TO THE DIRECTOR.
--
-- Security source §31: *"The Director should not automatically receive edit
-- access merely because the Director has high organizational rank."* The same
-- reasoning applies harder to export, which is the exfiltration act itself.
-- Seniority is not a need to remove recipes from the building.
--
-- The Lead owns the development work and the QA officer owns the controlled
-- record, so those two hold it. A Chemist can read and edit a formula and
-- cannot export it -- which is the separation §31 asks for, and is only
-- meaningful because it is asymmetric.
SELECT core._grant('product_development_lead', 'formula.export');
SELECT core._grant('qa_compliance_officer',    'formula.export');
SELECT core._grant('administrator',            'formula.export');

DROP FUNCTION core._grant(TEXT, TEXT[]);

COMMIT;


-- ---------------------------------------------------------------------
-- Prove the properties that matter, without leaving rows behind.
-- ---------------------------------------------------------------------
DO $probe$
DECLARE
    v_public INT;
    v_ceil   INT;
    v_holds  INT;
BEGIN
    SELECT core.classification_rank('PUBLIC'),
           core.classification_rank('DIRECTOR_CONTROLLED')
      INTO v_public, v_ceil;

    IF v_public IS NULL OR v_ceil IS NULL OR v_public >= v_ceil THEN
        RAISE EXCEPTION
            '039: the lattice is not ordered (PUBLIC=%, DIRECTOR_CONTROLLED=%). '
            'The outbound AI gate is defined as "PUBLIC only" and needs this '
            'ordering to mean anything.', v_public, v_ceil;
    END IF;

    IF core.classification_rank('NO_SUCH_LEVEL') IS NOT NULL THEN
        RAISE EXCEPTION '039: an unknown classification returned a rank';
    END IF;

    -- A Chemist must NOT hold export. The grant list above is only a
    -- separation of duties if it is asymmetric, and a future "grant everything
    -- to everyone" convenience migration should fail here.
    SELECT count(*) INTO v_holds
      FROM core.roles r
      JOIN core.role_permissions rp ON rp.role_id = r.id
      JOIN core.permissions p ON p.id = rp.permission_id
     WHERE p.code = 'formula.export'
       AND r.code IN ('product_development_chemist', 'product_development_director',
                      'laboratory_technician', 'executive_viewer');

    IF v_holds > 0 THEN
        RAISE EXCEPTION
            '039: formula.export was granted to a role that must not hold it. '
            'Export is the exfiltration act; §31 says seniority is not a '
            'reason to hold it.';
    END IF;
END $probe$;
