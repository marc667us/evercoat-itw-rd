-- =====================================================================
-- 055 — a safety review is an approval, not a second workflow engine
--
-- Phase 1 of the Material Safety Data & Research Center, part 2.
--
-- ---------------------------------------------------------------------
-- 🔴 WHAT THIS MIGRATION DOES NOT DO
-- ---------------------------------------------------------------------
--
-- It does not create an approval table, a queue, a decision type or a
-- notion of "signed off". §9 and CLAUDE.md §12 are explicit: **one shared
-- approval engine, never re-implemented per module**. 020 already has
-- route snapshotting, parallel groups, seven decision types and
-- segregation of duties, and `/approvals` already renders the queue.
--
-- So a safety review becomes a row `workflow.approval_routes` already
-- knows how to carry. The only things missing were an `entity_type` it
-- would accept and a template to snapshot.
--
-- ---------------------------------------------------------------------
-- 🔴 THE PERMISSIONS MOSTLY ALREADY EXISTED, UNENFORCED
-- ---------------------------------------------------------------------
--
-- `compliance.review_sds` — *"Review SDS and safety documentation"* — has
-- been seeded since 002:127 and granted to `qa_compliance_officer` since
-- 002:275, and **nothing in `apps/api/app` has ever read it**. It is one
-- of 29 permissions in that state, measured.
--
-- This migration does not mint `safety.review` beside it. A synonym for a
-- permission the catalogue already carries is the "two literals in two
-- files" defect this project keeps finding, and the specification's §30
-- asks for a capability, not for a particular string. The Material Safety
-- Data & Research Center becomes `compliance.review_sds`'s FIRST
-- enforcement point in the product's history.
--
-- Only two permissions are genuinely new, because only two acts have no
-- existing holder: approving a safety review, and exporting a restricted
-- safety dossier.
--
-- ⚠️ AND ONLY THE SAFETY ONES. The plan's research, competitor and
-- experiment permissions belong to the phases that BUILD those features.
-- Seeding a permission whose enforcement point does not exist yet is
-- precisely how the 29 orphans accumulated, and adding to that pile while
-- writing the migration that fixes part of it would be absurd.
--
-- ---------------------------------------------------------------------
-- 🔴 SEGREGATION OF DUTIES, AND WHY IT IS SATISFIABLE
-- ---------------------------------------------------------------------
--
-- Step 2 must be decided by somebody who did not decide step 1. That rule
-- is worthless if it makes the route uncompletable, so it was measured
-- before it was written:
--
--   compliance.review_sds  — 1 holder in the demonstration organization
--   qa_compliance_officer  — 1 member
--   product_development_lead — 1 member, a DIFFERENT person
--
-- `safety.approve` is therefore granted to BOTH the QA officer and the
-- lead. The QA officer reviews; the lead approves. With the grant to only
-- one role, `must_differ_from_group` would have produced a queue nobody
-- could ever clear — a control pointing at inert workflow, which is the
-- defect this project has counted 23 instances of.
-- =====================================================================

BEGIN;

-- ---------------------------------------------------------------------
-- PART 1 — the two genuinely new permissions
-- ---------------------------------------------------------------------
-- 🔴 `safety.export_restricted` WAS HERE AND HAS BEEN REMOVED.
--
-- This migration's own header says: *"Seeding a permission whose enforcement
-- point does not exist yet is precisely how the 29 orphans accumulated, and
-- adding to that pile while writing the migration that fixes part of it would
-- be absurd."* It then seeded and granted `safety.export_restricted`, which
-- nothing in `apps/api/app` or `apps/web` reads. Absurd, as predicted, and
-- found by the security review.
--
-- It belongs in the migration that ships the export route, so that whoever
-- writes that route has to decide again who may remove a hazard dossier from
-- the building -- rather than inheriting an already-granted permission.
--
-- `safety.approve` stays: it has a real enforcement point in the SAFETY_REVIEW
-- template's step 2, and the dual grant is what makes the segregation rule
-- satisfiable.
INSERT INTO core.permissions (code, domain, description) VALUES
    ('safety.approve', 'compliance',
     'Approve a safety review, closing the assessment of an SDS revision''s '
     'impact. Separate from compliance.review_sds because reviewing a change '
     'and signing it off are different acts, and §9 requires the second to be '
     'performable by somebody who did not perform the first.')
ON CONFLICT (code) DO NOTHING;

-- 🔴 AND IT IS WITHDRAWN FROM DATABASES THAT ALREADY HAVE IT.
--
-- An earlier version of THIS migration seeded `safety.export_restricted`, and
-- that version was committed. So a database built from that commit carries a
-- granted permission that nothing reads, and simply deleting the INSERT above
-- would leave it there for ever -- the orphan would survive the fix for the
-- orphan.
--
-- Written as a corrective DELETE rather than left to the downgrade, because a
-- downgrade is not something a deployed database runs. Grants first: a
-- permission row cannot go while `role_permissions` still references it.
DELETE FROM core.role_permissions rp
 USING core.permissions p
 WHERE p.id = rp.permission_id AND p.code = 'safety.export_restricted';
DELETE FROM core.permissions WHERE code = 'safety.export_restricted';

-- `core._grant` is 039's helper; reused rather than re-declared.
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

-- Both roles, deliberately — see the header. Without the second grant the
-- segregation rule below cannot be satisfied by anybody.
SELECT core._grant('qa_compliance_officer',   'safety.approve');
SELECT core._grant('product_development_lead','safety.approve');



-- ---------------------------------------------------------------------
-- PART 2 — the approval engine accepts a safety review
-- ---------------------------------------------------------------------
--
-- 020:140 declares `entity_type` as an INLINE, UNNAMED check, so
-- PostgreSQL generated the name. It was read from `pg_constraint` rather
-- than assumed: it is `approval_routes_entity_type_check`. Dropping a
-- guessed name would either fail loudly or -- worse, with IF EXISTS --
-- silently leave the old constraint in place while this migration
-- reported success.
--
-- ⚠️ ONLY `safety_review` IS ADDED. `research_finding`,
-- `experiment_proposal`, `competitor_analysis` and `material_qualification`
-- are in the plan and belong to the phases that build their producers. An
-- accepted value with nothing able to write it is the same defect as a
-- table with no writer.
ALTER TABLE workflow.approval_routes
    DROP CONSTRAINT approval_routes_entity_type_check;
ALTER TABLE workflow.approval_routes
    ADD CONSTRAINT approval_routes_entity_type_check CHECK (
        entity_type IN ('test', 'formula_version', 'validation',
                        'pilot', 'qualification', 'product_release',
                        'safety_review')
    );

-- A safety review is not a test at `controlled` authority, and reusing an
-- existing level would snapshot the wrong ladder --
-- `approval_templates_authority_unique` allows exactly one active template
-- per level, and all six are claimed (measured: SCREENING_SIMPLE,
-- OVERSIGHT_STANDARD, CONTROLLED_OVERSIGHT, VALIDATION_CONFIRMATION,
-- QUALIFICATION_CONFIRMATION, RELEASE_CRITICAL).
ALTER TABLE workflow.approval_templates
    DROP CONSTRAINT approval_templates_authority_level_check;
ALTER TABLE workflow.approval_templates
    ADD CONSTRAINT approval_templates_authority_level_check CHECK (
        authority_level IS NULL OR authority_level IN
        ('preliminary', 'development', 'controlled', 'validation',
         'qualification', 'release', 'safety')
    );


-- ---------------------------------------------------------------------
-- PART 3 — the template, for every organization
-- ---------------------------------------------------------------------
--
-- 🔴 A BACKFILL ALONE WOULD HAVE BEEN A DEFECT, AND A TEST CAUGHT IT.
--
-- The first version of this migration inserted a template for every
-- organization that existed WHEN IT RAN, and stopped there. But
-- `core.organizations` carries an AFTER INSERT trigger --
-- `organizations_get_approval_templates` -> `workflow.provision_templates_on_new_org()`
-- -> `workflow.provision_approval_templates(uuid)` -- which provisions the
-- six existing templates for every organization created afterwards.
--
-- So every future tenant would have received the other six and NOT this
-- one, and `open_route(authority_level => 'safety')` would have raised
-- "no active template" the first time anybody pressed Safety Review. A
-- point-in-time backfill silently expires the moment the next organization
-- is created, and nothing about the migration would have looked wrong.
--
-- `test_every_organization_has_a_decidable_safety_template` found it by
-- creating an organization and asking.
--
-- ⚠️ SO THE TEMPLATE IS DEFINED ONCE, IN A FUNCTION, AND CALLED TWICE:
-- once per existing organization (the backfill), and once per new one (the
-- trigger). Writing the INSERT out in both places would be the "two
-- literals in two files cannot be type-checked into agreement" defect this
-- project keeps finding -- and the copy that drifts would be the one
-- nobody reads, because it only ever runs for tenants created later.
CREATE OR REPLACE FUNCTION workflow.provision_safety_review_template(p_org UUID)
    RETURNS VOID
    LANGUAGE plpgsql
    SECURITY DEFINER
    -- `pg_temp` LAST: 013's rule. Every reference in the body is
    -- schema-qualified so nothing is shadowable today, but a definer
    -- function that omits it is one careless edit from being so.
    SET search_path TO 'pg_catalog', 'public', 'pg_temp'
AS $safety_tpl$
DECLARE
    tpl UUID;
BEGIN
    INSERT INTO workflow.approval_templates
        (organization_id, template_code, name, description, authority_level, is_active)
    VALUES (p_org, 'SAFETY_REVIEW', 'Safety review of an SDS revision',
            'Opened when a revised Safety Data Sheet changes hazard information '
            'affecting an active project. Reviewed by compliance, approved by '
            'somebody who did not perform the review.',
            'safety', TRUE)
    ON CONFLICT (organization_id, template_code) DO NOTHING
    RETURNING id INTO tpl;

    IF tpl IS NOT NULL THEN
        INSERT INTO workflow.approval_template_steps
            (organization_id, template_id, step_number, parallel_group,
             permission_required, step_label, is_mandatory, must_differ_from_group)
        VALUES
            -- Step 1 — compliance reads the change.
            (p_org, tpl, 1, 1, 'compliance.review_sds',
             'Compliance review of the safety change', TRUE, NULL),
            -- Step 2 — somebody ELSE signs it off.
            --
            -- 🔴 `must_differ_from_group = 1` IS THE POINT OF HAVING TWO STEPS.
            -- Without it the same person reviews and approves, and the second
            -- signature records nothing the first did not. ADR-019 expresses
            -- incompatible duties as DATA so the rule travels with the route
            -- snapshot; this is that mechanism used for its purpose.
            (p_org, tpl, 2, 2, 'safety.approve',
             'Approval of the safety assessment', TRUE, 1);
    END IF;
END
$safety_tpl$;

-- 🔴 EXECUTE IS TAKEN AWAY FROM PUBLIC FIRST.
--
-- `CREATE FUNCTION` grants EXECUTE to PUBLIC by default. This one is
-- SECURITY DEFINER and takes an organization id as an argument, so left as
-- created, ANY role -- `evercoat_app`, `evercoat_report`, `evercoat_worker` --
-- could call it for ANOTHER TENANT'S id and write approval templates into that
-- tenant's workflow configuration with RLS entirely out of the loop.
--
-- Ten migrations in this repository already do this (024, 027, 035, 044, 045,
-- 048-053) and this one did not. Found by the security review.
REVOKE ALL ON FUNCTION workflow.provision_safety_review_template(UUID) FROM PUBLIC;

-- 🔴 THE OWNER IS DELIBERATELY NOT CHANGED.
--
-- A SECURITY DEFINER function executes with its OWNER's privileges, so
-- reassigning one changes what it may do while looking like tidying. 014
-- leaves functions alone for exactly this reason and
-- `test_security_definer_functions_were_not_swept_along` states that intent
-- so a later consistency pass cannot quietly widen the sweep. Its sibling
-- `workflow.provision_approval_templates` is owned by `postgres`; this one
-- matches it. An earlier draft added `OWNER TO evercoat_owner` here and the
-- test caught it.

-- The backfill: every organization that already exists.
SELECT workflow.provision_safety_review_template(o.id) FROM core.organizations o;

-- And every organization created from now on. The existing trigger function
-- is extended rather than replaced, so the six templates it already
-- provisions keep being provisioned in exactly the same way.
-- 🔴 THE TRIGGER FUNCTION BECOMES `SECURITY DEFINER`, AND THAT IS FORCED BY
-- THE REVOKE ABOVE.
--
-- 030 created it as SECURITY INVOKER, so its body runs with the privileges of
-- whoever inserted the organization. That worked only because
-- `provision_approval_templates` was executable by PUBLIC. Revoking PUBLIC
-- EXECUTE on the safety function -- which is what closes the cross-tenant write
-- path -- therefore broke organization creation outright: 712 errors,
-- "permission denied for function provision_safety_review_template", every one
-- of them from this PERFORM.
--
-- The alternative was to grant EXECUTE back to `evercoat_app`, which would have
-- reopened the exact hole: the function takes an organization id as an
-- ARGUMENT, so any role that can call it can write approval templates into any
-- tenant with RLS out of the loop.
--
-- As a definer function owned by the migration runner, the trigger can call
-- what it needs while no ordinary role can call the safety function directly.
-- The privilege follows the TRIGGER PATH rather than the caller -- the same
-- move I109/ADR-032 made for sign-in, and for the same reason: a check inside
-- a function cannot authorize a caller the function cannot identify.
--
-- ⚠️ A DELIBERATE CHANGE TO 030's FUNCTION, RECORDED HERE RATHER THAN MADE
-- QUIETLY. It runs on INSERT to `core.organizations` only, and its whole body
-- is two PERFORMs of fixed, id-parameterised provisioning.
CREATE OR REPLACE FUNCTION workflow.provision_templates_on_new_org()
    RETURNS TRIGGER
    LANGUAGE plpgsql
    SECURITY DEFINER
    SET search_path TO 'pg_catalog', 'public', 'pg_temp'
AS $on_new_org$
BEGIN
    PERFORM workflow.provision_approval_templates(NEW.id);
    PERFORM workflow.provision_safety_review_template(NEW.id);
    RETURN NEW;
END
$on_new_org$;

-- It is a trigger function: nothing should call it by hand either.
REVOKE ALL ON FUNCTION workflow.provision_templates_on_new_org() FROM PUBLIC;


-- ---------------------------------------------------------------------
-- PART 4 — notification types need no migration, and that is deliberate
-- ---------------------------------------------------------------------
--
-- `messaging.notifications.notification_type` is free TEXT with no CHECK
-- (022:174, whose comment gives `approval.awaiting, failure.opened...` as
-- examples). So `sds.updated`, `safety.alert` and `safety.review_required`
-- are additive with no DDL at all, written through `core.notifications.notify()`
-- -- THE single writer -- exactly as every other module does.
--
-- Recorded here rather than left silent so the next reader does not go
-- looking for the enum that constrains them.

-- 🔴 THE HELPER DOES NOT OUTLIVE THE MIGRATION THAT USED IT.
--
-- 043 established the rule and `test_the_grant_helper_did_not_survive_the
-- _migration` enforces it: `core._grant` is a migration-time convenience, and
-- a permission-granting function left resident in `core` is a standing way to
-- widen authorization from anywhere that can call it.
DROP FUNCTION IF EXISTS core._grant(TEXT, TEXT[]);

COMMIT;
