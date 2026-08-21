-- 031 — `controlled` authority gets a ladder, and every non-advancing
--       decision must say why
--
-- Both raised by the Supervisor against the I5 migration.
--
-- ─────────────────────────────────────────────────────────────────────────
-- PART 1 — SIX AUTHORITY LEVELS, FIVE TEMPLATES
-- ─────────────────────────────────────────────────────────────────────────
--
-- `testing.tests.authority_level` permits SIX values (migration 018):
-- preliminary, development, **controlled**, validation, qualification,
-- release. Migration 020 seeded FIVE templates and none of them claims
-- `controlled`.
--
-- 🔴 THAT BECAME FATAL WHEN I5 WIRED APPROVALS TO THE ENGINE. Completing
-- technical review now opens a route keyed on the test's authority level, so
-- a `controlled` test raised "no active approval template is configured for
-- controlled authority" — an unhandled error that rolled the review back and
-- left the test **permanently stuck at `awaiting_review`**. Before I5 the
-- level worked, so this is a regression introduced by wiring the engine in,
-- not a pre-existing gap that stayed harmless.
--
-- ⚠️ THE LADDER IS NOT INVENTED. The route this level used to require is
-- recorded in the code I5 deleted: `APPROVAL_PERMISSION["controlled"]` mapped
-- to `test.approve_lead`. So `controlled` authority has always meant "a lead
-- must sign it", and CONTROLLED_OVERSIGHT says exactly that as a two-rung
-- ladder — a development approval, then the lead — with both rungs MANDATORY,
-- which is what distinguishes it from OVERSIGHT_STANDARD where the lead rung
-- is optional.
--
-- Added to `workflow.provision_approval_templates` (migration 030) rather
-- than to a one-time loop, so organizations created afterwards get it too.
-- That is the defect 030 exists to prevent, and repeating it here would be a
-- poor way to honour it.

CREATE OR REPLACE FUNCTION workflow.provision_approval_templates(p_org UUID)
    RETURNS VOID
    LANGUAGE plpgsql
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
    tpl := NULL;

    -- OVERSIGHT_STANDARD: engineer, with the lead reachable on escalation.
    -- The escalation step is OPTIONAL -- it exists so an escalation has
    -- somewhere to land, and does not block completion when nobody escalates.
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
    tpl := NULL;

    -- CONTROLLED_OVERSIGHT: the level that had no template at all.
    -- BOTH rungs mandatory -- that is the whole difference from
    -- OVERSIGHT_STANDARD, and it is what `controlled` authority has always
    -- meant: a lead must sign it, not merely may.
    INSERT INTO workflow.approval_templates
        (organization_id, template_code, name, authority_level, description)
    VALUES (p_org, 'CONTROLLED_OVERSIGHT', 'Controlled oversight', 'controlled',
            'Tester to Engineer, then the Lead. Both approvals are required: '
            'controlled authority means the Lead signs it, not that the Lead '
            'may be asked to.')
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
             'Lead approval', TRUE);
    END IF;
    tpl := NULL;

    -- VALIDATION_CONFIRMATION: engineer and chemist in PARALLEL, then the
    -- lead. Parallel because the two reviews are independent -- process and
    -- formulation -- and serialising them only adds waiting.
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
    tpl := NULL;

    -- QUALIFICATION_CONFIRMATION: adds independent QA, which MUST NOT be
    -- anyone from the development group. ADR-019, carried as data.
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
    tpl := NULL;

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
END
$fn$;


-- Provision the new template for every organization that already exists.
DO $backfill$
BEGIN
    PERFORM workflow.provision_approval_templates(o.id) FROM core.organizations o;
END
$backfill$;


-- ─────────────────────────────────────────────────────────────────────────
-- PART 2 — `request_additional_test` MUST SAY WHY, LIKE EVERY OTHER REFUSAL
-- ─────────────────────────────────────────────────────────────────────────
--
-- `approval_route_steps_refusals_state_why` named four non-advancing
-- decisions and omitted `request_additional_test`, which is equally
-- non-advancing: it leaves a permanent decision on a mandatory rung that
-- `decide_step` will never accept a second decision on, so the route can
-- never complete.
--
-- 🔴 WITHOUT A RATIONALE THAT IS AN UNEXPLAINED DEAD END. The record says a
-- rung was stopped and nothing about why, and the person whose work it is has
-- no idea what to do next. §9 makes every decision an electronic record in
-- permanent audit history; a record that omits the one field that makes it
-- actionable is not one.

ALTER TABLE workflow.approval_route_steps
    DROP CONSTRAINT IF EXISTS approval_route_steps_refusals_state_why;

ALTER TABLE workflow.approval_route_steps
    ADD CONSTRAINT approval_route_steps_refusals_state_why CHECK (
        decision IS NULL
        OR decision NOT IN ('return_for_correction', 'reject', 'request_retest',
                            'escalate', 'request_additional_test')
        OR rationale IS NOT NULL
    );


-- ─────────────────────────────────────────────────────────────────────────
-- PART 3 — PROVE IT
-- ─────────────────────────────────────────────────────────────────────────
-- Every authority level a test may carry must have a template to route with,
-- or that level is unusable and the failure appears only when somebody plans
-- a test at it.
DO $verify$
DECLARE
    orphan TEXT;
BEGIN
    SELECT string_agg(DISTINCT missing.level, ', ')
      INTO orphan
      FROM (
          SELECT unnest(ARRAY['preliminary', 'development', 'controlled',
                              'validation', 'qualification', 'release']) AS level
      ) missing
      JOIN core.organizations o ON TRUE
     WHERE NOT EXISTS (
         SELECT 1 FROM workflow.approval_templates t
         WHERE t.organization_id = o.id
           AND t.authority_level = missing.level
           AND t.is_active
     );

    IF orphan IS NOT NULL THEN
        RAISE EXCEPTION
            'these authority levels have no active approval template: %. A test '
            'planned at one of them cannot be reviewed at all.', orphan;
    END IF;
END
$verify$;
