-- 045 -- a membership carries its permissions (I79)
--
-- WHAT THIS CLOSES.
--
-- `GET /api/me` returns `organizations[].roles` and NO permissions, so
-- `apps/web/app/layout.tsx` hands the sidebar `ALL_NAV_PERMISSIONS` -- the
-- complete module map -- and every permission-shaped decision in the browser
-- is made against "the user holds everything".
--
-- That is not a security hole. §6 is explicit that frontend permission checks
-- are cosmetic and every control is re-enforced server-side, and it is. The
-- cost is honesty: a laboratory technician is shown Administration, Product
-- Release and the director dashboard, presses one, and the server correctly
-- answers 403. Nine workspaces were wired on 2026-08-24 and every one of them
-- renders its full control set for every role, so this compounds with each
-- screen added.
--
-- 🔴 AUTHORIZE ON PERMISSIONS, NEVER ON ROLE NAMES (§6), AND THAT RULE HAS TO
-- REACH THE BROWSER TOO. The client currently holds role CODES and nothing
-- else, so any gating written today would have to map role -> permission in
-- TypeScript. That mapping already exists, in the database, as
-- `core.role_permissions`. A second copy in the web tier is the two-literals
-- problem this project has already been bitten by: two spellings of one rule,
-- in two languages, that cannot be type-checked into agreement.
--
-- So the function that answers "which organizations may this subject act in"
-- now also answers "and what may they do in each" -- one definition, in the
-- place that owns it.
--
-- WHY A DROP AND NOT A REPLACE.
--
-- `CREATE OR REPLACE FUNCTION` cannot change a function's return type;
-- PostgreSQL answers `cannot change return type of existing function`. The
-- signature is unchanged, so the drop is unambiguous -- but a DROP takes the
-- OWNER, the REVOKE and the GRANT with it. All three are restated below.
--
-- 🔴 RESTATING A GRANT IS IDEMPOTENT; FORGETTING ONE IS NOT. 2026-08-22 lost
-- privileges exactly this way. After this migration `evercoat_app` must still
-- hold EXECUTE and PUBLIC must still hold none, or `/api/me` 403s for every
-- caller in the application -- which is precisely how 032 broke 35 routes.

BEGIN;

DROP FUNCTION IF EXISTS core.memberships_for_subject(TEXT);

CREATE FUNCTION core.memberships_for_subject(p_sub TEXT)
RETURNS TABLE (
    user_id           UUID,
    email             TEXT,
    display_name      TEXT,
    organization_id   UUID,
    organization_name TEXT,
    organization_code TEXT,
    roles             TEXT[],
    -- Permission CODES held in this organization, resolved through
    -- member_roles -> roles -> role_permissions -> permissions. The same
    -- chain `core.principal_for_subject` (033) walks to build the server-side
    -- `Principal.permissions`, so the browser is now told exactly what the
    -- API will enforce rather than a role list it has to interpret.
    permissions       TEXT[]
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
           o.name,
           o.code,
           COALESCE(array_agg(DISTINCT r.code)
                    FILTER (WHERE r.code IS NOT NULL), '{}'),
           COALESCE(array_agg(DISTINCT p.code)
                    FILTER (WHERE p.code IS NOT NULL), '{}')
    FROM core.users u
    JOIN core.organization_members om
      ON om.user_id = u.id
     AND om.status  = 'active'
    JOIN core.organizations o
      ON o.id = om.organization_id
     -- An inactive or archived organization is not a place anyone may
     -- act. Omitting this would offer a tenant that every subsequent
     -- request then refuses, which reads as a broken sign-in.
     AND o.status = 'active'
    LEFT JOIN core.member_roles     mr ON mr.member_id = om.id
    LEFT JOIN core.roles            r  ON r.id = mr.role_id
    -- 🔴 THE TWO NEW JOINS, AND THE REASON THE AGGREGATES ARE `DISTINCT`.
    --
    -- Joining role_permissions multiplies each (member, role) row by the
    -- number of permissions that role carries, so without DISTINCT the
    -- `roles` array would repeat every role once per permission -- a
    -- chemist holding 30 permissions would be reported as 30 chemists.
    -- Both aggregates were already DISTINCT; this records WHY that now
    -- matters, because before these joins it was merely tidy.
    LEFT JOIN core.role_permissions rp ON rp.role_id = r.id
    LEFT JOIN core.permissions      p  ON p.id = rp.permission_id
    WHERE u.keycloak_sub = p_sub
      AND u.status = 'active'
    GROUP BY u.id, u.email, u.display_name, om.organization_id, o.name, o.code
    ORDER BY o.name
$$;

COMMENT ON FUNCTION core.memberships_for_subject(TEXT) IS
    'Organizations a verified Keycloak subject may act in, with the roles AND '
    'permissions held in each. SECURITY DEFINER because it must answer BEFORE '
    'an organization has been chosen, when no RLS GUC is set. Scoped strictly '
    'to the subject argument; takes no organization argument and therefore '
    'cannot be pointed at another tenant. Permissions are resolved from '
    'core.role_permissions so the browser and the API read ONE definition '
    '(I79); the browser copy stays cosmetic -- §6 re-enforces every control '
    'server-side.';

-- Ownership, exactly as 024 set it, because the DROP above removed it.
ALTER FUNCTION core.memberships_for_subject(TEXT) OWNER TO evercoat_owner;

-- 🔴 EXECUTE IS NOT PUBLIC, AND THE DROP RESET THAT TOO.
--
-- PostgreSQL grants EXECUTE on new functions to PUBLIC by default, so a
-- SECURITY DEFINER function is callable by every role in the database unless
-- that default is revoked. Revoked first, then granted to exactly the ONE
-- role that serves the one route that calls it -- not `evercoat_report`
-- (a reporting role has no business enumerating identities) and not
-- `evercoat_worker` (an RLS-bypassing lookup for an ARBITRARY subject is an
-- identity-enumeration primitive, and the worker never serves /api/me).
REVOKE ALL ON FUNCTION core.memberships_for_subject(TEXT) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION core.memberships_for_subject(TEXT) TO evercoat_app;

COMMIT;
