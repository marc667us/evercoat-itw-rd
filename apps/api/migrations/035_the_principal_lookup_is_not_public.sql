-- =====================================================================
-- 035 — the principal lookup is not PUBLIC
--
-- Fixes a hole introduced by 033, three commits earlier, and found by
-- comparing 033 against the migration it was modelled on.
--
-- ---------------------------------------------------------------------
-- WHAT WAS WRONG
-- ---------------------------------------------------------------------
--
-- PostgreSQL grants `EXECUTE` on a newly created function to **PUBLIC** by
-- default. 033 wrote:
--
--     GRANT EXECUTE ON FUNCTION core.principal_for_subject(TEXT, UUID)
--       TO evercoat_app;
--
-- and stopped there, so the grant to `evercoat_app` was redundant and the
-- function was callable by every role in the cluster.
--
-- MEASURED (`pg_proc.proacl`):
--
--     principal_for_subject    =X/evercoat_owner | evercoat_owner=X/... | evercoat_app=X/...
--     memberships_for_subject                      evercoat_owner=X/... | evercoat_app=X/...
--
-- The leading `=X` with no role name before it is PUBLIC. Migration 024
-- revoked it for `memberships_for_subject`; 033 did not, and 033 copied that
-- migration in every other respect.
--
-- ---------------------------------------------------------------------
-- WHY IT MATTERS MORE HERE THAN FOR AN ORDINARY FUNCTION
-- ---------------------------------------------------------------------
--
-- `core.principal_for_subject` is SECURITY DEFINER owned by `evercoat_owner`.
-- It therefore **bypasses RLS by design** — that is the entire point of 033,
-- because it must answer before a tenant context can exist.
--
-- So PUBLIC EXECUTE on it means: `evercoat_report` (read-only analytics),
-- `evercoat_worker`, `evercoat_breakglass`, and any role added later, can ask
-- for any subject's identity, roles and permissions in any organization,
-- through a function that is exempt from the isolation everything else is
-- subject to. A read-only reporting role could enumerate the authorization
-- model of every tenant.
--
-- 🔴 THE LESSON, AND IT IS THE ONE THIS REPOSITORY KEEPS RELEARNING: A
-- SECURITY BOUNDARY FIX CAN CARRY ITS OWN HOLE. 033 closed a total
-- authentication outage and, in the same 40 lines, opened a privilege
-- escalation path — because a default was left unstated. The default is the
-- dangerous direction: `GRANT` is visible in a diff and `REVOKE ... FROM
-- PUBLIC` is invisible by absence.
--
-- Every future SECURITY DEFINER function in this codebase revokes from PUBLIC
-- before granting. `tests/db/test_object_ownership.py` now asserts it, so the
-- omission fails a test rather than waiting for a reviewer to notice.
-- =====================================================================

BEGIN;

REVOKE ALL ON FUNCTION core.principal_for_subject(TEXT, UUID) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION core.principal_for_subject(TEXT, UUID) TO evercoat_app;

COMMIT;


DO $$
DECLARE
    v_acl TEXT;
BEGIN
    SELECT array_to_string(proacl, ' | ') INTO v_acl
      FROM pg_proc p JOIN pg_namespace n ON n.oid = p.pronamespace
     WHERE n.nspname = 'core' AND p.proname = 'principal_for_subject';

    -- An ACL entry beginning with '=' is PUBLIC. Its absence is the property
    -- being asserted; a NULL acl means "default", which IS public.
    IF v_acl IS NULL OR v_acl LIKE '=%' OR v_acl LIKE '%|=%' THEN
        RAISE EXCEPTION
            'core.principal_for_subject is still executable by PUBLIC (acl: %). '
            'It is SECURITY DEFINER and bypasses RLS, so every role in the '
            'cluster could read any tenant''s authorization model.', v_acl;
    END IF;
END $$;
