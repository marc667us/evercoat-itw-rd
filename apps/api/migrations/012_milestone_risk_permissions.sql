-- 012_milestone_risk_permissions.sql
-- =====================================================================
-- Permissions for milestones and risks, which have had TABLES and
-- DASHBOARD COUNTS since migration 003 and no way to create a row.
--
-- HOW THIS WAS FOUND. By asking of every entity the question that has now
-- caught five roles on a sibling platform and two entities here: WHICH
-- PRODUCTION PATH WRITES IT?
--
--   projects.milestones  -- no INSERT anywhere in the repository. Not in
--                           a route, not in a service, not even in a test
--                           fixture. The dashboard's total/met/missed/
--                           overdue counters have never been non-zero.
--   projects.risks       -- exactly one INSERT, in
--                           tests/db/test_slice2_dashboard.py. No
--                           production writer at all.
--
-- A count with no way to create the thing it counts is not a feature that
-- is merely incomplete; it is a panel that renders a confident zero. The
-- reader cannot distinguish "this project has no risks" from "this
-- product cannot record risks".
--
-- The permission catalogue in migration 002 seeded codes for every future
-- domain -- formula, batch, test, failure, product, compliance -- and had
-- none for milestone or risk. So this is not a grant that was forgotten;
-- the permissions were never defined.
--
-- WHY THE SPLIT IS create/manage FOR RISKS BUT NOT MILESTONES
-- -----------------------------------------------------------
-- Milestones are the project PLAN. Setting and moving dates is the Lead's
-- and Director's job, and a single `milestone.manage` matches that: there
-- is no useful authority that can add a milestone but not move one.
--
-- Risks are different, and the split mirrors `failure.create` versus
-- `failure.close` already in the catalogue. A Chemist who notices that a
-- resin supplier is single-sourced must be able to RAISE that risk --
-- requiring a Lead to do it is how risks go unrecorded. But deciding a
-- risk is closed, accepted, or has been realised is a project-management
-- judgement with schedule and commercial consequences, so it stays with
-- the Lead and Director.
--
-- WHAT IS DELIBERATELY NOT ADDED: milestone.view / risk.view. Reading
-- these is already governed by project membership plus RLS -- the
-- dashboard route requires require_project_member() and the policies from
-- 003 restrict the rows. Adding view permissions would mean granting them
-- to all ten roles to preserve current behaviour, which is a migration
-- that changes nothing except the number of rows in role_permissions.
-- =====================================================================

BEGIN;

-- ---------------------------------------------------------------------
-- PART 1 — Permission catalogue
-- ---------------------------------------------------------------------

INSERT INTO core.permissions (code, domain, description) VALUES
    ('milestone.manage', 'project', 'Create, reschedule and close project milestones'),
    ('risk.create',      'project', 'Raise a project risk'),
    ('risk.manage',      'project', 'Edit, mitigate, close or accept a project risk')
ON CONFLICT (code) DO NOTHING;

-- ---------------------------------------------------------------------
-- PART 2 — Grants
-- ---------------------------------------------------------------------
-- Same helper shape as migration 002. Recreated here because 002 drops it
-- at the end -- deliberately, so the grant vocabulary is defined by the
-- migration that uses it rather than left lying around as a public API.

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

-- Lead owns the project plan: both milestones and the full risk lifecycle.
SELECT core._grant('product_development_lead',
    'milestone.manage', 'risk.create', 'risk.manage');

-- Director has portfolio oversight and carries the commercial consequence
-- of a slipped milestone or a realised risk.
SELECT core._grant('product_development_director',
    'milestone.manage', 'risk.create', 'risk.manage');

-- Raise-only. These roles do the technical work that surfaces a risk in
-- the first place; none of them may close one.
SELECT core._grant('product_development_chemist',  'risk.create');
SELECT core._grant('product_development_engineer', 'risk.create');

-- QA raises compliance and regulatory risks. Consistent with the
-- catalogue's existing treatment of QA: it holds review and approval
-- authority, not project-management authority, so no risk.manage.
SELECT core._grant('qa_compliance_officer', 'risk.create');

DROP FUNCTION core._grant(TEXT, TEXT[]);

-- ---------------------------------------------------------------------
-- PART 3 — Invariants the write paths depend on
-- ---------------------------------------------------------------------
-- A milestone recorded as met or missed with no date it was met or missed
-- ON is not a record of anything. Conversely a milestone still in flight
-- must not carry a completion date -- that combination is what makes the
-- dashboard's `overdue` filter (status IN planned/in_progress AND
-- planned_date < today) mean what it says.
--
-- Enforced in the database rather than only in the service, because the
-- seeder, a future importer and a support script are all writers too.

ALTER TABLE projects.milestones
    DROP CONSTRAINT IF EXISTS milestones_actual_date_matches_status;

ALTER TABLE projects.milestones
    ADD CONSTRAINT milestones_actual_date_matches_status CHECK (
        (status IN ('met', 'missed')     AND actual_date IS NOT NULL)
        OR
        (status NOT IN ('met', 'missed') AND actual_date IS NULL)
    );

COMMENT ON CONSTRAINT milestones_actual_date_matches_status ON projects.milestones IS
    'A milestone that is met or missed records WHEN. One still planned or '
    'in progress has no completion date. Without this the overdue filter '
    'silently includes closed milestones.';

-- A risk being actively mitigated must say what the mitigation IS.
-- 'mitigating' with a NULL mitigation is a status that reassures a
-- reader without committing anyone to an action.
ALTER TABLE projects.risks
    DROP CONSTRAINT IF EXISTS risks_mitigating_states_the_mitigation;

ALTER TABLE projects.risks
    ADD CONSTRAINT risks_mitigating_states_the_mitigation CHECK (
        status <> 'mitigating'
        OR (mitigation IS NOT NULL AND length(btrim(mitigation)) > 0)
    );

COMMENT ON CONSTRAINT risks_mitigating_states_the_mitigation ON projects.risks IS
    'Status ''mitigating'' requires a stated mitigation. A risk marked as '
    'being handled, with no description of how, reads as covered on the '
    'dashboard while nobody owns an action.';

COMMIT;
