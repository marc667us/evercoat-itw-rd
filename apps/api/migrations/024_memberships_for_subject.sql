-- ---------------------------------------------------------------------
-- 024 — How a browser learns which organization it may ask for
-- ---------------------------------------------------------------------
--
-- 🔴 THE PROBLEM THIS SOLVES, AND WHY NOTHING ELSE COULD
--
-- `get_principal` requires the `X-Organization-Id` header and refuses
-- without it. That is correct: defaulting to "the user's only
-- organization" silently picks one for a user who belongs to several and
-- writes records into whichever tenant happened to sort first. Every
-- authenticated route depends on it, directly or through
-- `require_permission`.
--
-- So a browser that has just signed in holds a valid token and has NO
-- WAY to discover a tenant to ask for. Every request it can make returns
-- 400 demanding a header whose value nothing will tell it.
-- Authentication completes and the application is still unusable.
--
-- This is this project's most-repeated lesson wearing a new face. It has
-- been asked six times of roles — *which production path WRITES this?* —
-- and never once of the organization id: **which production path TELLS
-- THE BROWSER its organization?** None did. The CI auth suite could not
-- catch it, because the workflow computes TEST_ORGANIZATION_ID from the
-- seeder and injects it as an environment variable. The tests were handed
-- the answer a real browser has no way to obtain.
--
-- 🔴 WHY THIS CANNOT BE AN ORDINARY QUERY
--
-- `core.organizations` and `core.organization_members` are both RLS-
-- enabled, and both policies are keyed on `core.current_org_id()`. A
-- request that has not yet chosen an organization has no GUC set, so:
--
--   * TODAY it would appear to work, because `core.rls_permissive()` is
--     still a `SELECT TRUE` stub and the policies go permissive when the
--     GUC is absent;
--   * AFTER THE FORCE RLS CUTOVER it would return ZERO ROWS and 404 for
--     every legitimate user.
--
-- `unscoped_session_scope()`'s own docstring states that end state
-- plainly: "this session sees nothing in tenant-scoped tables anyway,
-- because the policies stop being permissive when the GUC is absent."
--
-- Relying on the permissive stub would therefore have shipped a route
-- that works in every environment we have and breaks in the one we are
-- deliberately moving towards — while, in the meantime, being the FIRST
-- route in the application to query tenant tables with no organization
-- context at all. That is a cross-tenant read path opened by accident.
-- This platform has already recorded the shape of that mistake:
-- *LOCAL IS SUPERUSER, RENDER IS NOT.*
--
-- 🔴 WHY SECURITY DEFINER IS SAFE **HERE** SPECIFICALLY
--
-- The function bypasses RLS, so the argument for it has to be that it
-- CANNOT return a row the caller should not see — not that it is
-- convenient.
--
--   * It is scoped to `p_sub`, which is the `sub` claim of a token whose
--     signature, issuer, audience and expiry the API has already
--     verified. A caller cannot ask about another subject without first
--     forging a token the realm's JWKS would have to sign.
--   * It takes NO organization argument, and there is deliberately no
--     overload that does. A tenant filter here would be a filter the
--     caller controls, on the one query whose entire purpose is to
--     report what the caller is a member of.
--   * It returns ONLY membership facts that `core.organization_members`
--     already asserts. It grants nothing, and it is `STABLE` — it cannot
--     write.
--   * `SET search_path` is pinned, so a caller cannot shadow `core` with
--     a schema of their own and have the body resolve to their tables.
--
-- Same reasoning already applied to `core.is_project_member` (001) and
-- `audit.chain_row` (011).

BEGIN;

CREATE OR REPLACE FUNCTION core.memberships_for_subject(p_sub TEXT)
RETURNS TABLE (
    user_id           UUID,
    email             TEXT,
    display_name      TEXT,
    organization_id   UUID,
    organization_name TEXT,
    organization_code TEXT,
    roles             TEXT[]
)
    LANGUAGE sql
    STABLE
    SECURITY DEFINER
    SET search_path = core, pg_temp
AS $$
    SELECT u.id,
           u.email::TEXT,
           u.display_name,
           om.organization_id,
           o.name,
           o.code,
           COALESCE(array_agg(DISTINCT r.code)
                    FILTER (WHERE r.code IS NOT NULL), '{}')
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
    LEFT JOIN core.member_roles mr ON mr.member_id = om.id
    LEFT JOIN core.roles       r   ON r.id = mr.role_id
    WHERE u.keycloak_sub = p_sub
      AND u.status = 'active'
    GROUP BY u.id, u.email, u.display_name, om.organization_id, o.name, o.code
    ORDER BY o.name
$$;

COMMENT ON FUNCTION core.memberships_for_subject(TEXT) IS
    'Organizations a verified Keycloak subject may act in. SECURITY DEFINER '
    'because it must answer BEFORE an organization has been chosen, when no '
    'RLS GUC is set. Scoped strictly to the subject argument; takes no '
    'organization parameter, by design. See migration 024.';

-- 🔴 THE DEFINER IS PINNED. WITHOUT THIS THE FUNCTION'S BEHAVIOUR DEPENDS
-- ON WHO RAN THE MIGRATION.
--
-- SECURITY DEFINER means "run as the OWNER", and the owner is whichever
-- account executed CREATE FUNCTION unless it is set. CI applies
-- migrations as `postgres`, a superuser, which bypasses RLS entirely.
-- Another deployment applies them as `evercoat_owner`. After the FORCE
-- RLS cutover those two owners behave DIFFERENTLY: the superuser-owned
-- function keeps returning rows, and the `evercoat_owner`-owned one
-- returns none unless that role holds BYPASSRLS.
--
-- The failure that produces is the worst kind: CI green, production
-- answering 404 to `/api/me` for every user, and nothing in the diff to
-- explain it. This platform has recorded the shape already --
-- *LOCAL IS SUPERUSER, RENDER IS NOT.* Codex caught the omission; the
-- pattern was already established by `audit.chain_row` (011, 013) and
-- `formulations.deny_component_mutation` (015).
--
-- 🔴 AND PINNING THE OWNER DOES NOT SURVIVE THE FORCE RLS CUTOVER.
--
-- Be clear about what this ALTER does and does not buy. It makes the
-- behaviour DETERMINISTIC. It does not make it correct forever.
--
-- `evercoat_owner` is NOLOGIN and holds no BYPASSRLS anywhere in this
-- repository. Today it is exempt from these policies only because RLS is
-- ENABLED and not FORCED, and an owner is exempt from a non-forced
-- policy. The moment the cutover forces RLS and flips
-- `core.rls_permissive()` to FALSE, this function runs subject to
-- policies keyed on `core.current_org_id()` -- with no GUC set, because
-- it is called BEFORE an organization is chosen. It will return zero
-- rows, `/api/me` will 404 for everyone, and sign-in will be dead.
--
-- The Supervisor caught that: the header above argues this function
-- exists to avoid exactly that outcome, and pinning the owner made it
-- deterministically wrong rather than unpredictably wrong.
--
-- It is left as a BLOCKER rather than pre-solved, because the fix --
-- granting `evercoat_owner` BYPASSRLS, or writing a policy that admits
-- this one lookup -- belongs in the cutover migration where it can be
-- reviewed alongside every other FORCE-RLS consequence, not smuggled in
-- ahead of it. `tests/db/test_024_memberships_for_subject.py` fails the
-- moment the cutover lands and says what to do.
ALTER FUNCTION core.memberships_for_subject(TEXT) OWNER TO evercoat_owner;

-- 🔴 EXECUTE IS NOT PUBLIC.
--
-- PostgreSQL grants EXECUTE on new functions to PUBLIC by default, so a
-- SECURITY DEFINER function is callable by every role in the database
-- unless that default is revoked. Revoked first, then granted to exactly
-- the ONE role that serves the one route that calls it.
--
-- `evercoat_report` is not granted: a reporting role has no business
-- enumerating identities. `evercoat_worker` is not granted EITHER -- it
-- was, and Codex was right that it should not be. The worker never
-- serves `/api/me`, and an RLS-bypassing lookup that any worker code can
-- call for an ARBITRARY subject is an identity-enumeration primitive
-- sitting in a process that does not need it. A grant is a write path;
-- ask who actually uses it.
REVOKE ALL ON FUNCTION core.memberships_for_subject(TEXT) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION core.memberships_for_subject(TEXT) TO evercoat_app;

COMMIT;
