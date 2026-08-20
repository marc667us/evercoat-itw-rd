-- ---------------------------------------------------------------------
-- 027 — Project membership cannot be granted to yourself
-- ---------------------------------------------------------------------
--
-- 🔴 THE LARGEST OF THE FOUR, AND THE LAST ONE FOUND
--
-- `projects.project_members` (001:494) has a `USING` clause and **no
-- `WITH CHECK`**. PostgreSQL reuses `USING` as the check for writes, and
-- that clause is organization-only. `001:522` grants INSERT on the whole
-- `projects` schema to `evercoat_app`.
--
-- So anything holding an `evercoat_app` connection could write:
--
--     INSERT INTO projects.project_members
--         (organization_id, project_id, user_id, project_role, status)
--     VALUES (core.current_org_id(), '<a restricted project>',
--             core.current_user_id(), 'observer', 'active');
--
-- `core.is_project_member()` is SECURITY DEFINER and reads the table
-- regardless of policy, so it then answers TRUE — and **every
-- project-scoped policy in this database is written as
-- `confidentiality = 'normal' OR core.is_project_member(p.id)`**:
-- projects, requirements, formulas, batches, tests, failures, approvals
-- and messaging channels. One INSERT opens all of them.
--
-- The same applies to UPDATE. `USING` is organization-only, so a
-- restricted project's member rows are VISIBLE, and repointing somebody
-- else's row at yourself was the same escalation by a different verb.
--
-- Not reachable over HTTP: `api/projects.py`'s member routes require
-- `project.assign_member` **and** `require_project_member()`, so a caller
-- must already be inside. That is exactly why it belongs in the database
-- — `SECURITY.md` §1 asks what holds when the application layer does not.
--
-- 🔴 WHY THIS TOOK A SECOND ATTEMPT TO GET RIGHT
--
-- The obvious rule — "you may only add a member to a project you can
-- already see" — BREAKS PROJECT CREATION, and I recorded that as a reason
-- this could not be fixed without a database. That was half right and the
-- conclusion was wrong.
--
-- Measured instead of assumed, there are exactly four writers:
--
--   1. api/projects.py       creator adds THEMSELVES; the same statement
--                            sets `lead_user_id` to the creator
--   2. opportunities/service converts an opportunity; adds the DECLARED
--                            LEAD, who may be someone other than the
--                            actor, into a project that may be RESTRICTED
--   3. projects/members.py   add_member — actor is already a member
--   4. projects/members.py   remove_member — an UPDATE to `inactive`,
--                            actor already a member. There is no DELETE
--                            path anywhere.
--
-- Writer 2 is the hard one: a Director with `project.create` may convert
-- an opportunity into a RESTRICTED project led by somebody else, and
-- cannot read that project afterwards — correctly. A visibility-based
-- check refuses their enrolment INSERT and conversion stops working.
--
-- 🔴 AND THE ESCAPE HATCH I SAID DID NOT EXIST, DOES
--
-- I reported that `projects.projects` had no `created_by` column to
-- bootstrap through. It has `lead_user_id`, and **migration 006 already
-- uses it for precisely this purpose on the READ side** — "The Lead
-- always sees their own project."
--
-- So the second branch below admits a row that merely MATERIALISES what
-- the project row already declares. It grants no authority that did not
-- already exist: the declaration lives on `projects.projects`, and
-- changing it requires UPDATE on a row a non-member of a restricted
-- project cannot see. An attacker is not the declared lead, and cannot
-- make themselves one.

BEGIN;

-- ---------------------------------------------------------------------
-- The declared lead, readable regardless of policy
-- ---------------------------------------------------------------------
-- 🔴 SECURITY DEFINER, AND THE ARGUMENT HAS TO BE THAT IT CANNOT LEAK.
--
-- It takes a project id and returns ONE column: that project's declared
-- lead. It returns no name, no code, no confidentiality and no other
-- row. The most an unauthorised caller learns is that a project id they
-- already possess has a particular lead — and project ids are
-- `gen_random_uuid()`, unguessable, which is the same assumption
-- `core.is_project_member` rests on.
--
-- It must bypass RLS or it cannot answer the one question it exists for:
-- writer 2 above is a Director who legitimately cannot read the project
-- they just created. An invoker-rights version returns NULL there and
-- conversion breaks — which is the failure the first attempt made.
CREATE OR REPLACE FUNCTION core.project_lead(p_project UUID) RETURNS UUID
    LANGUAGE sql STABLE SECURITY DEFINER
    SET search_path = projects, core, pg_temp
AS $$
    SELECT p.lead_user_id FROM projects.projects p WHERE p.id = p_project
$$;

COMMENT ON FUNCTION core.project_lead(UUID) IS
    'The project''s declared lead. SECURITY DEFINER, owned by '
    'evercoat_owner: it must answer for a project the caller cannot read, '
    'because a Director may create a restricted project led by somebody '
    'else and must still be able to enrol that lead. Returns one column '
    'and no other row. See migration 027.';

-- Owned deliberately, like every other definer function here. Left owned
-- by the migration role it would run with SUPERUSER rights in CI, which
-- is far worse than the problem it solves.
ALTER FUNCTION core.project_lead(UUID) OWNER TO evercoat_owner;

-- PostgreSQL grants EXECUTE to PUBLIC on new functions, so a definer
-- function is callable by every role unless that is revoked. Revoked
-- first, then granted to the one role that needs it.
REVOKE ALL ON FUNCTION core.project_lead(UUID) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION core.project_lead(UUID) TO evercoat_app;

-- ---------------------------------------------------------------------
-- The policy
-- ---------------------------------------------------------------------
-- `USING` is deliberately UNCHANGED. This migration closes the WRITE
-- escalation; narrowing who may READ the membership list of a restricted
-- project is a separate change with its own blast radius (the members
-- screen, project dashboards, the `my_work` role-addressed predicate),
-- and bundling it here would make a security fix hard to review and
-- harder to revert. Recorded as a follow-up rather than smuggled in.
DROP POLICY IF EXISTS project_member_scope ON projects.project_members;
CREATE POLICY project_member_scope ON projects.project_members
    USING (
        core.rls_permissive() AND core.current_org_id() IS NULL
        OR organization_id = core.current_org_id()
    )
    WITH CHECK (
        core.rls_permissive() AND core.current_org_id() IS NULL
        OR (
            organization_id = core.current_org_id()
            AND (
                -- Already inside the project. Covers add_member and
                -- remove_member, whose routes require membership anyway.
                core.is_project_member(project_id)
                -- Or this row materialises the project's DECLARED lead.
                -- Covers both creation paths. NULL lead yields NULL, which
                -- is not TRUE, so an unset lead fails closed.
                OR core.project_lead(project_id) = user_id
            )
        )
    );

COMMIT;
