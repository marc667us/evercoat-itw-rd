-- 002_seed_roles_permissions.sql
-- =====================================================================
-- The permission catalogue and the ten seeded roles.
--
-- Authorization is by PERMISSION, never by role name (CLAUDE.md §6).
-- Roles are seeded bundles that a deployment may re-cut in
-- Administration; permissions are the fixed vocabulary the code checks.
--
-- Why that distinction is not academic here:
--
--   * Master §12 names "Compliance / QA Officer" as one role, while the
--     approval routes require an INDEPENDENT QA actor and release may
--     require separate compliance evidence. Codex flagged the merge as a
--     risk (F3/F12). Modelling QA review, compliance review and
--     regulatory review as three permissions means a deployment with
--     three people assigns them to three people, and a deployment with
--     one person assigns them to one -- without the application
--     hard-coding either assumption.
--
--   * ADR-019's incompatible-duty rules ("QA approval may never come from
--     anyone who supplied a development-side approval on the same test")
--     are inexpressible against role names. They need permissions plus
--     per-test identity.
--
-- Every permission listed here is one the code actually checks. A
-- permission with no enforcement point is worse than none: it reads as a
-- control in an audit and is inert in production.
--
-- Idempotent: ON CONFLICT DO NOTHING throughout, so re-running is safe
-- and a later migration can add permissions without rewriting this one.
-- =====================================================================

BEGIN;

-- ---------------------------------------------------------------------
-- PART 1 — Permission catalogue
-- ---------------------------------------------------------------------

INSERT INTO core.permissions (code, domain, description) VALUES
    -- Projects -------------------------------------------------------
    ('project.view',              'project',   'View projects in scope'),
    ('project.create',            'project',   'Create an R&D project'),
    ('project.edit',              'project',   'Edit project metadata'),
    ('project.assign_member',     'project',   'Add or remove project members'),
    ('project.advance_stage',     'project',   'Advance a project stage gate'),
    ('project.authorize',         'project',   'Director authorization of a project'),

    -- Innovation -----------------------------------------------------
    ('opportunity.view',          'innovation','View innovation opportunities'),
    ('opportunity.create',        'innovation','Raise an opportunity'),
    ('opportunity.decide',        'innovation','Approve, reject or hold an opportunity'),

    -- Requirements ---------------------------------------------------
    ('requirement.view',          'requirement','View product requirements'),
    ('requirement.create',        'requirement','Create a requirement'),
    ('requirement.approve',       'requirement','Approve and lock requirements'),

    -- Materials ------------------------------------------------------
    ('material.view',             'material',  'View the raw material library'),
    ('material.create',           'material',  'Create a raw material record'),
    ('material.edit',             'material',  'Edit raw material data'),
    ('material.approve_lab',      'material',  'Promote a material to lab_approved'),
    ('material.approve_production','material', 'Promote a material to production_approved'),
    ('material.restrict',         'material',  'Mark a material restricted or obsolete'),
    ('supplier.manage',           'material',  'Maintain suppliers and lots'),

    -- Formulations ---------------------------------------------------
    ('formula.view',              'formula',   'View formulas in scope'),
    ('formula.view_cost',         'formula',   'See cost figures on a formula'),
    ('formula.create',            'formula',   'Create a formula'),
    ('formula.modify_draft',      'formula',   'Edit a draft formula version'),
    ('formula.clone',             'formula',   'Clone a version to create a revision'),
    ('formula.submit',            'formula',   'Submit a formula for review'),
    ('formula.approve_lab',       'formula',   'Approve a formula for laboratory trial'),
    ('formula.nominate_validation','formula',  'Nominate a formula as validation candidate'),

    -- Laboratory -----------------------------------------------------
    ('batch.view',                'laboratory','View laboratory batches'),
    ('batch.create',              'laboratory','Create a batch from an approved formula'),
    ('batch.execute',             'laboratory','Record weights, process data and deviations'),
    ('batch.complete',            'laboratory','Complete a batch'),
    ('batch.reject',              'laboratory','Reject a batch for process deviation'),
    ('sample.create',             'laboratory','Create and label samples'),

    -- Testing --------------------------------------------------------
    ('test.view',                 'testing',   'View tests and results'),
    ('test.plan',                 'testing',   'Create and release test plans'),
    ('test.execute',              'testing',   'Perform a test and enter raw measurements'),
    ('test.review',               'testing',   'Level 1 technical review of a result'),
    ('test.approve_development',  'testing',   'Development-side approval (Chemist/Engineer)'),
    ('test.approve_lead',         'testing',   'Lead approval of a result'),
    ('test.approve_qa',           'testing',   'Independent QA approval of a result'),
    ('test.approve_director',     'testing',   'Director approval on release-critical tests'),
    ('test.confirm',              'testing',   'Mark a result final_confirmed'),
    ('test.request_retest',       'testing',   'Request a retest'),
    ('method.manage',             'testing',   'Maintain test methods and versions'),
    ('equipment.manage',          'testing',   'Maintain equipment and calibration'),

    -- Failures -------------------------------------------------------
    ('failure.view',              'failure',   'View failure investigations'),
    ('failure.create',            'failure',   'Open a failure investigation'),
    ('failure.investigate',       'failure',   'Add evidence and hypotheses'),
    ('failure.accept_root_cause', 'failure',   'Promote a hypothesis to accepted root cause'),
    ('failure.close',             'failure',   'Close a failure investigation'),

    -- Industrialization ----------------------------------------------
    ('validation.manage',         'quality',   'Create and run validation programmes'),
    ('validation.approve',        'quality',   'Approve a validation gate'),
    ('stability.manage',          'quality',   'Create and run stability programmes'),
    ('pilot.manage',              'quality',   'Plan and execute pilot batches'),
    ('pilot.approve',             'quality',   'Approve a pilot gate'),
    ('qc.manage',                 'quality',   'Maintain QC specifications and results'),
    ('qualification.assemble',    'quality',   'Assemble a qualification dossier'),
    ('qualification.approve',     'quality',   'Approve qualification'),

    -- Product --------------------------------------------------------
    ('product.view',              'product',   'View released products'),
    ('product.release',           'product',   'Release a product — locks the master formula'),
    ('product.change_control',    'product',   'Raise and manage change requests'),
    ('complaint.manage',          'product',   'Record complaints and field issues'),
    ('capa.manage',               'product',   'Manage CAPA records'),

    -- Compliance -----------------------------------------------------
    -- Three distinct permissions, deliberately (Codex F3/F12). A single
    -- deployment may assign all three to one officer; the data model
    -- must not assume it.
    ('compliance.review_sds',     'compliance','Review SDS and safety documentation'),
    ('compliance.review_formula', 'compliance','Compliance review of a formulation'),
    ('regulatory.review',         'compliance','Regulatory and restricted-substance review'),

    -- Knowledge and AI -----------------------------------------------
    ('knowledge.view',            'knowledge', 'Search the Knowledge Library'),
    ('knowledge.ingest',          'knowledge', 'Ingest documents into the Knowledge Library'),
    ('knowledge.promote',         'knowledge', 'Promote a finding to controlled knowledge'),
    ('msd.use',                   'ai',        'Use MSD'),

    -- Analytics ------------------------------------------------------
    ('analytics.view',            'analytics', 'View analytics in scope'),
    ('analytics.portfolio',       'analytics', 'View organization-wide portfolio analytics'),
    ('report.generate',           'analytics', 'Generate controlled reports'),

    -- Administration -------------------------------------------------
    -- Administration ships incrementally beside whatever first depends on
    -- it (ADR-021). These exist now because Slice 1 delivers users,
    -- roles, permissions and organization settings.
    ('admin.users',               'admin',     'Manage users and memberships'),
    ('admin.roles',               'admin',     'Manage roles and role-permission mapping'),
    ('admin.organization',        'admin',     'Manage organization settings'),
    ('admin.stage_gates',         'admin',     'Configure pipeline stages and gates'),
    ('admin.reference_data',      'admin',     'Manage units, product families, statuses'),
    ('admin.workflow',            'admin',     'Configure approval templates and routes'),
    ('admin.notifications',       'admin',     'Manage notification templates'),
    ('admin.ai',                  'admin',     'Configure AI and model governance'),
    ('admin.audit',               'admin',     'Browse the audit trail'),
    ('admin.system',              'admin',     'System settings and feature flags')
ON CONFLICT (code) DO NOTHING;


-- ---------------------------------------------------------------------
-- PART 2 — The ten seeded roles
-- ---------------------------------------------------------------------
-- Codes match the Keycloak realm roles exactly. is_seeded marks them as
-- shipped defaults, so Administration can distinguish "we provided this"
-- from "this deployment created it" and never silently overwrite the
-- latter on a later migration.

INSERT INTO core.roles (code, name, is_seeded, description) VALUES
    ('product_development_chemist',  'Product Development Chemist',  TRUE,
     'Develops formulations, revisions and hypotheses. Cannot release a product.'),
    ('product_development_engineer', 'Product Development Engineer', TRUE,
     'Owns test plans, methods, pilot and scale-up. Cannot alter an approved formula.'),
    ('product_development_lead',     'Product Development Lead',     TRUE,
     'Controls projects, stage gates and development approvals.'),
    ('product_development_director', 'Product Development Director', TRUE,
     'Portfolio oversight, project authorization and product release.'),
    ('qa_compliance_officer',        'QA / Compliance Officer',      TRUE,
     'Independent quality, compliance and regulatory review.'),
    ('laboratory_technician',        'Laboratory Technician',        TRUE,
     'Executes approved batches and assigned tests; enters raw results.'),
    ('procurement_specialist',       'Procurement / Material Specialist', TRUE,
     'Maintains suppliers, lots, availability and material documentation.'),
    ('production_engineer',          'Production Engineer',          TRUE,
     'Owns manufacturing process design and production scale-up.'),
    ('executive_viewer',             'Executive Viewer',             TRUE,
     'Read-only portfolio access.'),
    ('administrator',                'Administrator',                TRUE,
     'System, user, role and configuration administration.')
ON CONFLICT (code) DO NOTHING;


-- ---------------------------------------------------------------------
-- PART 3 — Role to permission mapping
-- ---------------------------------------------------------------------

CREATE OR REPLACE FUNCTION core._grant(p_role TEXT, VARIADIC p_perms TEXT[])
    RETURNS VOID LANGUAGE plpgsql AS $$
BEGIN
    INSERT INTO core.role_permissions (role_id, permission_id)
    SELECT r.id, p.id
    FROM core.roles r
    JOIN core.permissions p ON p.code = ANY(p_perms)
    WHERE r.code = p_role
    ON CONFLICT DO NOTHING;
END
$$;

-- Chemist. Note what is ABSENT: no product.release, no test.approve_qa,
-- no admin.*. The source is explicit that a Chemist must not be able to
-- release a commercial master formulation, and that is enforced by the
-- absence of the permission, not by a UI that hides a button.
SELECT core._grant('product_development_chemist',
    'project.view','opportunity.view','requirement.view','requirement.create',
    'material.view','material.create','material.edit','supplier.manage',
    'formula.view','formula.view_cost','formula.create','formula.modify_draft',
    'formula.clone','formula.submit','formula.nominate_validation',
    'batch.view','batch.create','sample.create',
    'test.view','test.review','test.approve_development','test.request_retest',
    'failure.view','failure.create','failure.investigate',
    'validation.manage','stability.manage',
    'knowledge.view','knowledge.promote','msd.use',
    'analytics.view','report.generate');

-- Engineer. Owns testing and industrialization. Explicitly lacks
-- formula.modify_draft — an Engineer must not overwrite an approved
-- formula, only trigger a revision through the Chemist.
SELECT core._grant('product_development_engineer',
    'project.view','requirement.view','requirement.create',
    'material.view','formula.view','formula.view_cost',
    'batch.view','batch.complete','batch.reject','sample.create',
    'test.view','test.plan','test.review','test.approve_development',
    'test.request_retest','method.manage','equipment.manage',
    'failure.view','failure.create','failure.investigate',
    'validation.manage','stability.manage','pilot.manage','qc.manage',
    'qualification.assemble',
    'knowledge.view','knowledge.promote','msd.use',
    'analytics.view','report.generate');

SELECT core._grant('product_development_lead',
    'project.view','project.create','project.edit','project.assign_member',
    'project.advance_stage',
    'opportunity.view','opportunity.create',
    'requirement.view','requirement.create','requirement.approve',
    'material.view','material.approve_lab',
    'formula.view','formula.view_cost','formula.approve_lab',
    'formula.nominate_validation',
    'batch.view','test.view','test.approve_lead','test.request_retest',
    'failure.view','failure.accept_root_cause','failure.close',
    'validation.approve','pilot.approve','qualification.assemble',
    'knowledge.view','knowledge.promote','msd.use',
    'analytics.view','report.generate');

-- Director. Holds product.release. Deliberately lacks formula.create and
-- batch.execute — the Director approves work, and separation of duties
-- means not also performing it.
SELECT core._grant('product_development_director',
    'project.view','project.authorize','project.advance_stage',
    'opportunity.view','opportunity.decide',
    'requirement.view','material.view','formula.view','formula.view_cost',
    'batch.view','test.view','test.approve_director',
    'failure.view','qualification.approve',
    'product.view','product.release','product.change_control',
    'knowledge.view','msd.use',
    'analytics.view','analytics.portfolio','report.generate');

-- QA / Compliance. Holds all three compliance permissions by default and
-- the independent QA approval. A deployment that separates these people
-- re-cuts the bundle in Administration; the model does not assume one
-- actor (Codex F3/F12).
SELECT core._grant('qa_compliance_officer',
    'project.view','requirement.view','material.view','material.restrict',
    'formula.view','batch.view',
    'test.view','test.approve_qa','test.request_retest',
    'failure.view','qc.manage','qualification.approve',
    'product.view','complaint.manage','capa.manage',
    'compliance.review_sds','compliance.review_formula','regulatory.review',
    'knowledge.view','msd.use','analytics.view','report.generate');

-- Technician. Executes; does not review or approve anything. This is the
-- clearest case for permissions over roles: test.execute without
-- test.review is exactly the segregation the approval routes assume.
SELECT core._grant('laboratory_technician',
    'project.view','material.view','formula.view',
    'batch.view','batch.execute','batch.complete','sample.create',
    'test.view','test.execute','knowledge.view','msd.use');

SELECT core._grant('procurement_specialist',
    'material.view','material.create','material.edit','supplier.manage',
    'knowledge.view','msd.use','analytics.view');

SELECT core._grant('production_engineer',
    'project.view','formula.view','batch.view','test.view',
    'pilot.manage','qc.manage','knowledge.view','msd.use','analytics.view');

SELECT core._grant('executive_viewer',
    'project.view','product.view','analytics.view','analytics.portfolio');

-- Administrator manages configuration. It does NOT get product.release,
-- test.confirm or failure.accept_root_cause: administering the system is
-- not the same authority as making a technical decision, and an admin
-- account that can silently release a product is a governance hole.
SELECT core._grant('administrator',
    'admin.users','admin.roles','admin.organization','admin.stage_gates',
    'admin.reference_data','admin.workflow','admin.notifications',
    'admin.ai','admin.audit','admin.system',
    'project.view','material.view','knowledge.view','analytics.view');

DROP FUNCTION core._grant(TEXT, TEXT[]);

COMMIT;

-- =====================================================================
-- CORRECTED 2026-08-18. This block previously said "Verified by
-- tests/db/test_002_roles_permissions.py" and listed six properties.
-- THAT FILE DID NOT EXIST. Not one of the six was checked by anything,
-- in the file that defines the entire authorization model -- which is the
-- worst possible place for a safety net made of prose, because every
-- other security claim in this product is downstream of these grants.
--
-- It is also how `material.approve_production` came to be defined here
-- and granted to no role at all, leaving the material status `preferred`
-- unreachable by any user. Migration 016 closes that.
--
-- The file now exists. What it ACTUALLY checks:
--   * every permission here has at least one holder
--     (the check that would have caught approve_production; two further
--      orphans -- test.confirm and knowledge.ingest -- are allowlisted
--      with the slice that will assign them, and the allowlist fails if
--      an entry later gains a holder)
--   * every permission the application CHECKS exists here
--     (guards against a require_permission() typo that 403s forever)
--   * no role holds both test.approve_development and test.approve_qa
--   * six load-bearing absences, including: chemist has no
--     product.release, engineer no formula.modify_draft, administrator
--     neither product.release nor test.confirm, director no
--     formula.create, procurement no material.approve_production
--   * the ten canonical roles are all seeded
--
-- What it does NOT check, named rather than implied: the reverse
-- direction, "every permission here is referenced somewhere in source".
-- It would fail today and correctly so -- most of batch.*, test.*,
-- failure.* and product.release belong to Slices 4-7 and nothing reads
-- them yet. Implementing it with a large allowlist would prove nothing.
-- ======================================================================
