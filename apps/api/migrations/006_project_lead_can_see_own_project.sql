-- 006_project_lead_can_see_own_project.sql
-- =====================================================================
-- Second RLS defect on the same statement, distinct from 005.
--
-- 005 fixed the WITH CHECK: `USING` was being reused as the insert
-- predicate, so creating a restricted project demanded membership of a
-- project that did not exist yet.
--
-- With that fixed, a bare INSERT succeeded — and the SAME statement with
-- `RETURNING` still failed, with the identical error text:
--
--     new row violates row-level security policy for table "projects"
--
-- Because **RETURNING reads the row back, and reading is governed by the
-- SELECT policy.** A restricted project is visible only to its members,
-- the creator is not a member yet, so the row it just wrote is invisible
-- to it and the statement fails. The error message says "new row
-- violates" and points at the write, which is not where the problem is.
--
-- THE FIX, and why it is a domain rule rather than a workaround.
--
-- The named Lead of a project should always be able to see that project.
-- That is true independently of this bug: a Lead who is somehow missing
-- from project_members should not be locked out of the project they own.
-- Adding `lead_user_id = core.current_user_id()` to the read predicate
-- states that rule, and incidentally makes creation work, because the
-- route sets lead_user_id to the creator.
--
-- It does NOT widen access. lead_user_id names one specific person, who
-- by definition already has authority over the project.
--
-- Found by a route test asserting the creator of a restricted project
-- can immediately open it. Without that test the product would have
-- shipped a "Create project" button that returned 500 for exactly the
-- projects most worth protecting.
-- =====================================================================

BEGIN;

DROP POLICY IF EXISTS project_scope ON projects.projects;

CREATE POLICY project_scope ON projects.projects
    USING (
        core.rls_permissive() AND core.current_org_id() IS NULL
        OR (
            organization_id = core.current_org_id()
            AND (
                confidentiality = 'normal'
                OR core.is_project_member(id)
                -- The Lead always sees their own project.
                OR lead_user_id = core.current_user_id()
            )
        )
    )
    WITH CHECK (
        core.rls_permissive() AND core.current_org_id() IS NULL
        OR organization_id = core.current_org_id()
    );

COMMIT;
