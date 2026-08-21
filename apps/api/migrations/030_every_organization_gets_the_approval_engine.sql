-- 030 — the approval engine must exist for organizations created AFTER 020
--
-- ─────────────────────────────────────────────────────────────────────────
-- WHAT WAS WRONG
-- ─────────────────────────────────────────────────────────────────────────
--
-- Migration 020 seeded §9's five approval templates with a ONE-TIME loop:
--
--     FOR org IN SELECT id FROM core.organizations LOOP ... END LOOP;
--
-- That is every organization **that existed when 020 ran**. There is no
-- trigger, and nothing else writes `workflow.approval_templates`.
--
-- 🔴 SO EVERY ORGANIZATION CREATED SINCE HAS AN APPROVAL ENGINE WITH NOTHING
-- IN IT. `open_route` looks its template up by `authority_level`, finds none,
-- and refuses — so **no approval can be routed at all for a new tenant**, and
-- §9's "one shared approval engine" is unreachable for exactly the customers
-- who arrive after deployment.
--
-- Measured 2026-08-21 before writing this: inserting a fresh organization and
-- counting its templates returns **0**.
--
-- 020's own header called the templates "shipped defaults", and said shipping
-- with none "would mean the approval engine had nothing to route with, and
-- 'configurable' would mean 'you must configure it before anything works'".
-- That reasoning was right and the implementation delivered it exactly once.
--
-- ─────────────────────────────────────────────────────────────────────────
-- THE FIX — A FUNCTION, A TRIGGER, AND A BACKFILL
-- ─────────────────────────────────────────────────────────────────────────
--
-- 1. `workflow.provision_approval_templates(uuid)` — 020's seeding body,
--    lifted verbatim, parameterised by organization. ONE definition, so the
--    templates a new tenant gets cannot drift from the templates an old one
--    has. Two copies of this list in two files is the defect this codebase
--    keeps rediscovering.
--
-- 2. An AFTER INSERT trigger on `core.organizations`. Provisioning belongs
--    where the organization is created, not in whichever application path
--    happens to create one — there are three today and a fourth will forget.
--
-- 3. A backfill for every organization that has none, so existing tenants
--    created between 020 and now are repaired rather than left behind.
--
-- Every INSERT is `ON CONFLICT DO NOTHING`, so this is idempotent: running it
-- against an organization that already has its templates changes nothing and
-- cannot overwrite a template an administrator has customised.


-- ---------------------------------------------------------------------
-- PART 0 -- auto-provisioned CONFIGURATION must not make an organization
--           permanently undeletable
-- ---------------------------------------------------------------------
--
-- `approval_templates` and `approval_template_steps` reference
-- `core.organizations` with ON DELETE RESTRICT. That was harmless while the
-- rows only appeared for organizations that existed when 020 ran. With PART 2
-- creating them automatically for EVERY organization, RESTRICT means an
-- organization can never be deleted again -- not even one created in error
-- with no data in it -- because the database itself put a child row under it
-- a microsecond after it was inserted.
--
-- 🔴 THIS IS NOT A RELAXATION OF §5. §5 forbids cascade-deleting **R&D
-- history**, and names the relationships it means: projects/formulas,
-- formula_versions/batches, batches/tests, materials used in formulas, and
-- released products. These two tables are neither history nor evidence --
-- they are derived CONFIGURATION that exists only because the organization
-- does, hold no decision, no signature and no measurement, and are recreated
-- from one function. Nothing is lost by them dying with their organization.
--
-- ⚠️ `workflow.approval_routes` and `approval_route_steps` KEEP RESTRICT, and
-- that is the important half. They hold the actual approvals -- the
-- electronic decision records §9 requires to be permanent -- so an
-- organization with any approval history is still refused deletion, by them.
-- Configuration cascades; history restricts.

ALTER TABLE workflow.approval_templates
    DROP CONSTRAINT IF EXISTS approval_templates_organization_id_fkey,
    ADD  CONSTRAINT approval_templates_organization_id_fkey
         FOREIGN KEY (organization_id) REFERENCES core.organizations(id)
         ON DELETE CASCADE;

ALTER TABLE workflow.approval_template_steps
    DROP CONSTRAINT IF EXISTS approval_template_steps_organization_id_fkey,
    ADD  CONSTRAINT approval_template_steps_organization_id_fkey
         FOREIGN KEY (organization_id) REFERENCES core.organizations(id)
         ON DELETE CASCADE;


-- ---------------------------------------------------------------------
-- PART 1 -- one definition of the shipped defaults
-- ---------------------------------------------------------------------
CREATE OR REPLACE FUNCTION workflow.provision_approval_templates(p_org UUID)
    RETURNS VOID
    LANGUAGE plpgsql
    -- SECURITY DEFINER: the trigger fires as whoever inserted the
    -- organization, and that role does not necessarily hold INSERT on the
    -- workflow schema. The function body writes only to
    -- `workflow.approval_template*` and only for the organization it is
    -- given, so it cannot be used to reach anything else.
    SECURITY DEFINER
    SET search_path = pg_catalog, public
    AS $fn$
DECLARE
    tpl UUID;
BEGIN
    -- SCREENING_SIMPLE: one development-side approval.
    INSERT INTO workflow.approval_templates
        (organization_id, template_code, name, authority_level, description)
    VALUES (p_org, 'SCREENING_SIMPLE', 'Screening (simple)', 'preliminary',
            'Tester to Chemist or Engineer. Screening is preliminary authority '
            'and is never confirmation evidence.')
    ON CONFLICT (organization_id, template_code) DO NOTHING
    RETURNING id INTO tpl;

    IF tpl IS NOT NULL THEN
        INSERT INTO workflow.approval_template_steps
            (organization_id, template_id, step_number, parallel_group,
             permission_required, step_label)
        VALUES (p_org, tpl, 1, 1, 'test.approve_development',
                'Development approval (Chemist or Engineer)');
    END IF;

    -- OVERSIGHT_STANDARD: engineer, with the lead reachable on
    -- escalation. The escalation step is OPTIONAL -- it exists on the
    -- route so an escalation has somewhere to land, and does not
    -- block completion when nobody escalates.
    INSERT INTO workflow.approval_templates
        (organization_id, template_code, name, authority_level, description)
    VALUES (p_org, 'OVERSIGHT_STANDARD', 'Oversight (standard)', 'development',
            'Tester to Engineer, escalating to the Lead when required.')
    ON CONFLICT (organization_id, template_code) DO NOTHING
    RETURNING id INTO tpl;

    IF tpl IS NOT NULL THEN
        INSERT INTO workflow.approval_template_steps
            (organization_id, template_id, step_number, parallel_group,
             permission_required, step_label, is_mandatory)
        VALUES
            (p_org, tpl, 1, 1, 'test.approve_development',
             'Engineer approval', TRUE),
            (p_org, tpl, 2, 2, 'test.approve_lead',
             'Lead approval (on escalation)', FALSE);
    END IF;

    -- VALIDATION_CONFIRMATION: engineer and chemist in PARALLEL, then
    -- the lead. Parallel because the two reviews are independent --
    -- process and formulation -- and serialising them only adds
    -- waiting.
    INSERT INTO workflow.approval_templates
        (organization_id, template_code, name, authority_level, description)
    VALUES (p_org, 'VALIDATION_CONFIRMATION', 'Validation confirmation', 'validation',
            'Tester to Engineer and Chemist (parallel), then Lead.')
    ON CONFLICT (organization_id, template_code) DO NOTHING
    RETURNING id INTO tpl;

    IF tpl IS NOT NULL THEN
        INSERT INTO workflow.approval_template_steps
            (organization_id, template_id, step_number, parallel_group,
             permission_required, step_label)
        VALUES
            (p_org, tpl, 1, 1, 'test.approve_development', 'Engineer approval'),
            (p_org, tpl, 2, 1, 'test.approve_development', 'Chemist approval'),
            (p_org, tpl, 3, 2, 'test.approve_lead',        'Lead approval');
    END IF;

    -- QUALIFICATION_CONFIRMATION: adds independent QA, which MUST NOT
    -- be anyone from the development group. ADR-019, carried as data.
    INSERT INTO workflow.approval_templates
        (organization_id, template_code, name, authority_level, description)
    VALUES (p_org, 'QUALIFICATION_CONFIRMATION', 'Qualification confirmation',
            'qualification',
            'Tester to Engineer and Chemist (parallel), then Lead, then '
            'independent QA who supplied no development-side approval.')
    ON CONFLICT (organization_id, template_code) DO NOTHING
    RETURNING id INTO tpl;

    IF tpl IS NOT NULL THEN
        INSERT INTO workflow.approval_template_steps
            (organization_id, template_id, step_number, parallel_group,
             permission_required, step_label, must_differ_from_group)
        VALUES
            (p_org, tpl, 1, 1, 'test.approve_development', 'Engineer approval', NULL),
            (p_org, tpl, 2, 1, 'test.approve_development', 'Chemist approval', NULL),
            (p_org, tpl, 3, 2, 'test.approve_lead',        'Lead approval', NULL),
            (p_org, tpl, 4, 3, 'test.approve_qa',          'Independent QA approval', 1);
    END IF;

    -- RELEASE_CRITICAL: the full ladder to the Director.
    INSERT INTO workflow.approval_templates
        (organization_id, template_code, name, authority_level, description)
    VALUES (p_org, 'RELEASE_CRITICAL', 'Release critical', 'release',
            'The full ladder: Engineer and Chemist, Lead, independent QA, '
            'then the Director.')
    ON CONFLICT (organization_id, template_code) DO NOTHING
    RETURNING id INTO tpl;

    IF tpl IS NOT NULL THEN
        INSERT INTO workflow.approval_template_steps
            (organization_id, template_id, step_number, parallel_group,
             permission_required, step_label, must_differ_from_group)
        VALUES
            (p_org, tpl, 1, 1, 'test.approve_development', 'Engineer approval', NULL),
            (p_org, tpl, 2, 1, 'test.approve_development', 'Chemist approval', NULL),
            (p_org, tpl, 3, 2, 'test.approve_lead',        'Lead approval', NULL),
            (p_org, tpl, 4, 3, 'test.approve_qa',          'Independent QA approval', 1),
            (p_org, tpl, 5, 4, 'test.approve_director',    'Director approval', NULL);
    END IF;

    tpl := NULL;
END
$fn$;

COMMENT ON FUNCTION workflow.provision_approval_templates(UUID) IS
    'Seeds CLAUDE.md §9''s five approval templates for one organization. '
    'Idempotent (ON CONFLICT DO NOTHING). The single definition of the '
    'shipped defaults -- migration 020 had this inline in a one-time loop, '
    'so organizations created afterwards had no templates and no approval '
    'could be routed for them at all.';


-- ---------------------------------------------------------------------
-- PART 2 -- a new organization gets them automatically
-- ---------------------------------------------------------------------
CREATE OR REPLACE FUNCTION workflow.provision_templates_on_new_org() RETURNS TRIGGER
    LANGUAGE plpgsql AS $trg$
BEGIN
    PERFORM workflow.provision_approval_templates(NEW.id);
    RETURN NEW;
END
$trg$;

DROP TRIGGER IF EXISTS organizations_get_approval_templates ON core.organizations;
CREATE TRIGGER organizations_get_approval_templates
    AFTER INSERT ON core.organizations
    FOR EACH ROW EXECUTE FUNCTION workflow.provision_templates_on_new_org();


-- ---------------------------------------------------------------------
-- PART 3 -- repair the organizations 020 left behind
-- ---------------------------------------------------------------------
DO $backfill$
DECLARE
    org RECORD;
    repaired INT := 0;
BEGIN
    FOR org IN
        SELECT o.id FROM core.organizations o
        WHERE NOT EXISTS (
            SELECT 1 FROM workflow.approval_templates t
            WHERE t.organization_id = o.id
        )
    LOOP
        PERFORM workflow.provision_approval_templates(org.id);
        repaired := repaired + 1;
    END LOOP;

    RAISE NOTICE 'approval templates provisioned for % organization(s) that had none',
                 repaired;
END
$backfill$;


-- ---------------------------------------------------------------------
-- PART 4 -- prove it, in the migration itself
-- ---------------------------------------------------------------------
-- A backfill that silently did nothing looks identical to one that worked.
DO $verify$
DECLARE
    without_templates INT;
BEGIN
    SELECT count(*) INTO without_templates
      FROM core.organizations o
     WHERE NOT EXISTS (
         SELECT 1 FROM workflow.approval_templates t
         WHERE t.organization_id = o.id
     );

    IF without_templates > 0 THEN
        RAISE EXCEPTION
            '% organization(s) still have no approval templates after the '
            'backfill; the provisioning function did not do what it claims',
            without_templates;
    END IF;
END
$verify$;
