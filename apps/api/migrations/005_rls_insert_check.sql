-- 005_rls_insert_check.sql
-- =====================================================================
-- Fix: creating a RESTRICTED project was impossible.
--
-- THE BUG, exactly as PostgreSQL reported it:
--
--     new row violates row-level security policy for table "projects"
--
-- When a policy declares only `USING` and no `WITH CHECK`, PostgreSQL
-- applies the USING expression as the WITH CHECK for INSERT and UPDATE.
-- The projects policy read:
--
--     USING (organization_id = current_org
--            AND (confidentiality = 'normal' OR core.is_project_member(id)))
--
-- On INSERT that becomes a demand that the inserting user ALREADY be a
-- member of a project which does not exist yet. Chicken and egg: the
-- membership row can only be written after the project row exists, and
-- the project row cannot be written without the membership.
--
-- Normal projects inserted fine, so this was invisible until something
-- created a restricted one -- which is the case that matters most,
-- because restricted is what protects a confidential formulation.
--
-- THE FIX. Separate the two questions the policy is answering:
--
--   USING      -- may I SEE this row?   organization + membership
--   WITH CHECK -- may I WRITE this row? organization only
--
-- That is not a weakening. A user can only insert into their own
-- organization, which is the tenancy guarantee. Confidentiality governs
-- who may READ a project, and applying a read predicate to a write is a
-- category error that happens to be the PostgreSQL default.
--
-- Found by a route test asserting that the creator of a restricted
-- project can immediately open it -- the case where RLS would otherwise
-- be doing exactly the right thing and the product would look like the
-- save had silently failed.
-- =====================================================================

BEGIN;

DROP POLICY IF EXISTS project_scope ON projects.projects;

CREATE POLICY project_scope ON projects.projects
    -- Read: organization AND (public within the org, or a member).
    USING (
        core.rls_permissive() AND core.current_org_id() IS NULL
        OR (
            organization_id = core.current_org_id()
            AND (confidentiality = 'normal' OR core.is_project_member(id))
        )
    )
    -- Write: organization only. Membership cannot be a precondition for
    -- creating the thing membership refers to.
    WITH CHECK (
        core.rls_permissive() AND core.current_org_id() IS NULL
        OR organization_id = core.current_org_id()
    );

-- The same defect exists on every project-scoped child table created in
-- 003: their policies test project membership in USING, which becomes
-- the INSERT check. A Chemist adding the first requirement to a
-- restricted project they belong to would pass, but the ordering
-- fragility is identical and not worth leaving in place.
DO $$
DECLARE t TEXT;
BEGIN
    FOREACH t IN ARRAY ARRAY[
        'projects.milestones', 'projects.risks', 'projects.requirements',
        'workflow.project_stages', 'workflow.stage_transitions', 'workflow.tasks'
    ]
    LOOP
        EXECUTE format('DROP POLICY IF EXISTS project_scope ON %s', t);
        EXECUTE format($p$
            CREATE POLICY project_scope ON %s
            USING (
                core.rls_permissive() AND core.current_org_id() IS NULL
                OR (
                    organization_id = core.current_org_id()
                    AND (
                        project_id IS NULL
                        OR EXISTS (
                            SELECT 1 FROM projects.projects p
                            WHERE p.id = %s.project_id
                              AND (p.confidentiality = 'normal'
                                   OR core.is_project_member(p.id))
                        )
                    )
                )
            )
            WITH CHECK (
                core.rls_permissive() AND core.current_org_id() IS NULL
                OR organization_id = core.current_org_id()
            )
        $p$, t, t);
    END LOOP;
END
$$;

COMMIT;
