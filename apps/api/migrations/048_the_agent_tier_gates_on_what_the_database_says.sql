-- 048 — the agent tier gates on what the database says, not on what it was told
--
-- Closes I105. Depends on 047 (f2000).
--
-- ============================================================================
-- 🔴 WHAT I104 CLOSED, AND WHAT IT DID NOT
-- ============================================================================
--
-- I104 replaced the orchestrator's loose `permissions` / `user_id` arguments
-- with an `AgentPrincipal` that cannot be assembled from values, and added a
-- session check: `bind()` asks PostgreSQL whether `app.current_org` and
-- `app.current_user_id` agree with the caller.
--
-- Codex named the half that left open, exactly:
--
--     bind() validates only organization and user; it never validates roles
--     or permissions. A forged principal using the real session identity
--     therefore passes bind() while claiming arbitrary authorization.
--
-- That is true, and it is the whole of the remaining hole. The conductor gate
-- consults `caller.permissions`, and until this migration that set arrived
-- from Python and nothing outside Python had ever agreed to it.
--
-- ============================================================================
-- 🔴 WHY THIS IS NOT THE DESIGN ADR-029 REJECTED
-- ============================================================================
--
-- ADR-029 recorded a SECURITY DEFINER approach as **rejected on measured
-- evidence** for I82, and that record must be answered rather than stepped
-- around. What it rejected was precise:
--
--     I82 proposes folding subject resolution into "a single atomic bind so
--     the id is returned only after the membership exists". The obvious
--     implementation is a SECURITY DEFINER. Measured before building it, and
--     it would have re-opened I83.
--
-- The mechanism was that a definer **WRITES**, the write fires ADR-028's
-- address-collision triggers, and a trigger inside a definer owned by the
-- table owner runs as that owner — bypassing RLS while FORCE is off, so the
-- guard refuses on another tenant's row and the refusal discloses that the
-- address exists somewhere.
--
-- Every step of that chain begins with a write. This function:
--
--   * WRITES NOTHING. It is `STABLE` and its body is a single SELECT. No
--     trigger on `core.users` or `core.organization_members` can fire, so the
--     chain ADR-029 measured has no first step here.
--   * TAKES NO PARAMETERS. This is the difference between a lookup and an
--     ORACLE, and it is the one that matters. `core.user_id_for_subject(TEXT)`
--     answers a question about somebody the caller names — which is I82. This
--     function can only ever answer about the session's own GUC, so there is
--     no input with which to ask about a victim. A caller who could set that
--     GUC to another user could already read that user's rows through RLS,
--     which is a strictly larger hole and not one this creates.
--
-- ⚠️ SO THE PERMISSION SET BECOMES EXACTLY AS STRONG AS RLS, WHICH IS THE
-- POINT. Both are now derived from the same two GUCs. There is no longer a
-- state in which the database shows one person's rows while the gate answers
-- for another — which was precisely the state I105 describes.
--
-- ============================================================================
-- ⚠️ THE OWNER IS PINNED, BECAUSE NOT PINNING IT IS A FOUR-TIME DEFECT HERE
-- ============================================================================
--
-- SECURITY DEFINER means "run as the owner", and the owner is whoever executed
-- CREATE FUNCTION unless it is set. This database's migrations are applied as
-- `postgres` (`rolsuper`, `rolbypassrls`), so an unpinned function runs as a
-- superuser: permanently outside RLS, including after the I56/I58 FORCE
-- cutover. Migration 044 created the fourth instance of that while its own
-- comment claimed it had not, and it was found by reading `pg_proc` rather
-- than by either reviewer.
--
-- `tests/db/test_048_session_permissions.py` asserts the owner from `pg_proc`,
-- not from this comment.
-- ============================================================================

BEGIN;

CREATE OR REPLACE FUNCTION core.permissions_for_current_session()
    RETURNS TEXT[]
    LANGUAGE sql
    STABLE
    SECURITY DEFINER
    -- A SECURITY DEFINER without a fixed search_path can be redirected by a
    -- caller-controlled search_path to shadowed objects.
    SET search_path = core, pg_temp
AS $$
    SELECT COALESCE(
               array_agg(DISTINCT p.code) FILTER (WHERE p.code IS NOT NULL),
               '{}'
           )
    FROM core.users u
    JOIN core.organization_members om
      ON om.user_id = u.id
     -- Immediate revocation. `get_principal` says a JWT "is not a current
     -- statement about authorization"; the same is true of a permission set
     -- computed at the start of a request. A membership suspended mid-request
     -- stops granting here on the next call.
     AND om.status = 'active'
    LEFT JOIN core.member_roles     mr ON mr.member_id = om.id
    LEFT JOIN core.roles            r  ON r.id = mr.role_id
    LEFT JOIN core.role_permissions rp ON rp.role_id = r.id
    LEFT JOIN core.permissions      p  ON p.id = rp.permission_id
    -- 🔴 THE SUBJECT IS THE SESSION'S OWN GUC AND THERE IS NO PARAMETER.
    -- `core.current_user_id()` and `core.current_org_id()` return NULL rather
    -- than raising when the GUC is unset (001), and `u.id = NULL` is never
    -- true — so an unscoped session gets `'{}'`, every gate refuses, and the
    -- failure is closed rather than open. That is a SECOND independent
    -- barrier: `AgentPrincipal.authorize()` already refuses an unscoped
    -- session in Python before reaching this.
    WHERE u.id = core.current_user_id()
      AND u.status = 'active'
      AND om.organization_id = core.current_org_id()
$$;

-- 🔴 PIN THE OWNER. See the header — unpinned means superuser here.
ALTER FUNCTION core.permissions_for_current_session() OWNER TO evercoat_owner;

REVOKE ALL ON FUNCTION core.permissions_for_current_session() FROM PUBLIC;
GRANT EXECUTE ON FUNCTION core.permissions_for_current_session() TO evercoat_app;

COMMENT ON FUNCTION core.permissions_for_current_session() IS
    'The permission codes held by the CURRENT SESSION''s user in the CURRENT '
    'SESSION''s organization, read from app.current_user_id / app.current_org. '
    'SECURITY DEFINER because role and permission rows are tenant-scoped and '
    'the caller must not need SELECT on them. '
    'It takes NO ARGUMENTS deliberately: a lookup a caller can aim at somebody '
    'else is an oracle (see core.user_id_for_subject and I82), and this one '
    'can only answer about the session it is called on. '
    'It is STABLE and writes nothing, so it fires no trigger and cannot '
    'reopen I83 the way ADR-029 measured a WRITING definer would. '
    'Returns an empty array on an unscoped session -- fail closed.';

COMMIT;
