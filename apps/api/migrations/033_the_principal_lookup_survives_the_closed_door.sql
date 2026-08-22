-- =====================================================================
-- 033 — the principal lookup survives the closed door
--
-- Companion to 032. Migration 032 alone breaks authentication for every
-- user, and this is the other half of that change. Neither should be
-- deployed without the other.
--
-- ---------------------------------------------------------------------
-- WHAT 032 BROKE, AND WHY IT WAS ALWAYS GOING TO
-- ---------------------------------------------------------------------
--
-- `app/core/security.py::get_principal` resolves the caller's identity,
-- roles and permissions with a raw query run inside `unscoped_session_scope()`
-- -- deliberately, because you cannot set a tenant GUC until you know which
-- tenant the caller belongs to. It reads `core.users`,
-- `core.organization_members`, `core.member_roles`, `core.roles`,
-- `core.role_permissions` and `core.permissions`.
--
-- Those are tenant-scoped tables with RLS policies. While
-- `core.rls_permissive()` returned TRUE the unscoped read was admitted. After
-- 032 it returns nothing, `row is None`, and `get_principal` raises
-- `PermissionDenied`.
--
-- MEASURED: 35 route tests across `tests/auth/` returned **403** to a
-- correctly authenticated caller holding the right permission. Not a subtle
-- degradation -- every authenticated request in the application.
--
-- 🔴 THE CODEBASE PREDICTED THIS IN WRITING AND NOBODY HAD A TRIPWIRE ON IT.
-- `unscoped_session_scope()`'s own docstring says: *"Once the FORCE RLS
-- cutover migration lands, this session sees nothing in tenant-scoped tables
-- anyway... That is the intended end state: the guard above catches the
-- mistake in development, and the database catches it in production."*
--
-- It was right, and that is exactly what happened. But the sentence was
-- written about `session_scope()` misuse -- an accident to be caught. The
-- principal lookup is a *deliberate, load-bearing* unscoped read, and the
-- docstring's "intended end state" silently included killing it.
--
-- Migration 024 left a tripwire for precisely this hazard on
-- `core.memberships_for_subject` and `tests/db/test_024_*` names the fix. But
-- 024's author was reasoning about `/api/me` -- ONE route. The same hazard
-- applied to `get_principal`, which is EVERY route, and no test named it.
-- **A tripwire on one instance of a pattern is not a tripwire on the
-- pattern.**
--
-- ---------------------------------------------------------------------
-- THE FIX — the pattern this codebase already reviewed and adopted
-- ---------------------------------------------------------------------
--
-- Move the query into a SECURITY DEFINER function owned by `evercoat_owner`,
-- exactly as 024 did for `memberships_for_subject`, 001 for
-- `core.is_project_member`, 011 for `audit.chain_row` and 015 for
-- `formulations.deny_component_mutation`.
--
-- The function then runs as its owner, and the owner is exempt from policies
-- on tables it owns **while RLS is ENABLED and not FORCED** -- which 032
-- deliberately preserves.
--
-- WHAT THIS IS NOT: it is not a hole. The function is scoped strictly to
-- `(p_sub, p_org)`, reads only `core.*` identity tables, returns nothing from
-- any project-scoped table, and cannot be steered -- a caller who passes an
-- organization they do not belong to gets zero rows, which is precisely what
-- the route already treats as "not a member". It answers exactly the question
-- the request must answer before tenancy exists, and nothing else.
--
-- ⚠️ AND IT CARRIES THE SAME FORCE-RLS CAVEAT AS 024. `evercoat_owner` is
-- NOLOGIN and holds no BYPASSRLS. When FORCE RLS is eventually enabled, this
-- function returns zero rows and every authenticated request 403s. The
-- migration that forces RLS must grant `evercoat_owner` BYPASSRLS or add
-- policies admitting these lookups, and must prove authentication still
-- works. `tests/db/test_033_*` fails at that moment and says so.
-- =====================================================================

BEGIN;

CREATE OR REPLACE FUNCTION core.principal_for_subject(p_sub TEXT, p_org UUID)
RETURNS TABLE (
    user_id         UUID,
    email           TEXT,
    display_name    TEXT,
    organization_id UUID,
    roles           TEXT[],
    permissions     TEXT[]
)
    LANGUAGE sql
    STABLE
    SECURITY DEFINER
    -- Fixed search_path: a SECURITY DEFINER function without one can be
    -- redirected by a caller-controlled search_path to shadowed objects.
    SET search_path = core, pg_temp
AS $$
    SELECT u.id,
           u.email::TEXT,
           u.display_name,
           om.organization_id,
           COALESCE(array_agg(DISTINCT r.code)
                    FILTER (WHERE r.code IS NOT NULL), '{}'),
           COALESCE(array_agg(DISTINCT p.code)
                    FILTER (WHERE p.code IS NOT NULL), '{}')
    FROM core.users u
    JOIN core.organization_members om
      ON om.user_id = u.id
     AND om.status  = 'active'
    LEFT JOIN core.member_roles     mr ON mr.member_id = om.id
    LEFT JOIN core.roles            r  ON r.id = mr.role_id
    LEFT JOIN core.role_permissions rp ON rp.role_id = r.id
    LEFT JOIN core.permissions      p  ON p.id = rp.permission_id
    WHERE u.keycloak_sub = p_sub
      AND u.status = 'active'
      AND om.organization_id = p_org
    GROUP BY u.id, u.email, u.display_name, om.organization_id
$$;

COMMENT ON FUNCTION core.principal_for_subject(TEXT, UUID) IS
    'Identity, roles and permissions for a verified Keycloak subject within '
    'one organization. SECURITY DEFINER because it must answer BEFORE the '
    'tenant GUC can be set -- the request cannot set a tenant until this tells '
    'it which tenant the caller belongs to. Scoped strictly to (subject, '
    'organization); a subject who is not an active member of that organization '
    'gets zero rows. Introduced by migration 033 because 032 closed the '
    'permissive escape hatch that the previous unscoped raw query relied on, '
    'which returned 403 for every authenticated request.';

-- 🔴 PIN THE OWNER. SECURITY DEFINER means "run as the owner", and the owner
-- is whoever executed CREATE FUNCTION unless it is set. CI applies migrations
-- as `postgres` (superuser, bypasses RLS entirely); another deployment applies
-- them as `evercoat_owner`. Leaving that to chance makes behaviour depend on
-- who ran the migration -- CI green, production 403 for everyone, nothing in
-- the diff to explain it. This platform has already recorded that shape:
-- *LOCAL IS SUPERUSER, RENDER IS NOT.*
ALTER FUNCTION core.principal_for_subject(TEXT, UUID) OWNER TO evercoat_owner;

-- The runtime role must be able to call it. It is the first thing every
-- authenticated request does.
GRANT EXECUTE ON FUNCTION core.principal_for_subject(TEXT, UUID) TO evercoat_app;

COMMIT;


-- ---------------------------------------------------------------------
-- Prove the effect rather than assert it.
-- ---------------------------------------------------------------------
DO $$
DECLARE
    v_owner    TEXT;
    v_secdef   BOOLEAN;
    v_overload INT;
BEGIN
    SELECT pg_get_userbyid(proowner), prosecdef
      INTO v_owner, v_secdef
      FROM pg_proc p JOIN pg_namespace n ON n.oid = p.pronamespace
     WHERE n.nspname = 'core' AND p.proname = 'principal_for_subject';

    IF v_owner IS DISTINCT FROM 'evercoat_owner' THEN
        RAISE EXCEPTION
            'core.principal_for_subject is owned by % -- the ALTER ... OWNER TO '
            'did not take, so behaviour now depends on who ran this migration',
            v_owner;
    END IF;

    IF NOT v_secdef THEN
        RAISE EXCEPTION
            'core.principal_for_subject is not SECURITY DEFINER; it will read '
            'as the caller, return nothing, and 403 every request';
    END IF;

    SELECT count(*) INTO v_overload
      FROM pg_proc p JOIN pg_namespace n ON n.oid = p.pronamespace
     WHERE n.nspname = 'core' AND p.proname = 'principal_for_subject';
    IF v_overload <> 1 THEN
        RAISE EXCEPTION
            'core.principal_for_subject has % definitions; expected 1', v_overload;
    END IF;
END $$;
