-- 050 — the bind proves the caller administers the tenant, and stops
--       answering "did this subject exist"
--
-- Fixes two defects migration 049 introduced. Depends on 049 (h1000).
--
-- ============================================================================
-- 🔴 049 GRANTED A CROSS-TENANT WRITE WHILE REMOVING A CROSS-TENANT READ
-- ============================================================================
--
-- Raised by Codex, and CONFIRMED BY MEASUREMENT rather than accepted:
--
--     attacker is an active member of organization A ONLY
--     attacker sets app.current_org to organization B and calls the bind
--     -> ACCEPTED. A membership was created in organization B.
--
-- `core.bind_subject_to_organization` is SECURITY DEFINER, so its INSERT runs
-- as `evercoat_owner` and RLS does not apply. Before 049 the route performed
-- that INSERT itself as `evercoat_app`, where `org_member_isolation` refused
-- it. 049 therefore took a write that RLS was guarding and moved it somewhere
-- RLS is not.
--
-- 🔴 049's OWN HEADER QUOTES THE LESSON IT THEN BROKE: *"a cross-tenant WRITE,
-- granted by accident, inside the migration removing a cross-tenant READ"* —
-- ADR-029's mistake, described accurately, and repeated one level down. Not
-- taking an organization ARGUMENT was necessary and was never sufficient,
-- because a GUC is caller-settable and `evercoat_app` may set it.
--
-- **THE FIX IS THAT THE FUNCTION PROVES THE CALLER'S STANDING RATHER THAN
-- ASSUMING IT.** It asks `core.authorization_for_current_session()` — 048's
-- function, keyed on the same GUCs — whether this session's user actually
-- holds `admin.users` in this session's organization. A forged pair now fails
-- on the forgery: the attacker is not a member of B, so B grants them nothing.
--
-- ⚠️ THAT IS NOT PROOF OF THE KEYCLOAK PRINCIPAL, and this migration does not
-- claim it is. Anything that can execute arbitrary SQL as `evercoat_app` can
-- set both GUCs to a real administrator's pair and act as them — but that is
-- true of RLS itself, and of every policy in this database. What changed is
-- that the definer no longer accepts a pair the DATABASE does not agree with,
-- so it is exactly as strong as RLS instead of weaker than it.
--
-- ============================================================================
-- 🔴 AND THE "COST" WAS ROLLBACK-ABLE, SO THE ORACLE WAS NEVER PRICED
-- ============================================================================
--
-- 049's header claimed the existence answer now "requires creating a real
-- membership row and writes an audit record", a reduction rather than an
-- elimination. Codex showed that is false and the measurement agrees:
--
--     BEGIN;
--     SELECT * FROM core.bind_subject_to_organization(...);  -- identity_created
--     ROLLBACK;
--     -> zero memberships remain, no audit row, and the answer was returned
--
-- No function result can be made to depend on a commit. The claim was a
-- property I asserted and had not tested — the exact defect this repository
-- catalogues, written into the file that congratulated itself on avoiding it.
--
-- 🔴 SO THE ANSWER IS NO LONGER RETURNED. `identity_created` is removed.
-- It had NO consumer: `app/api/admin.py` destructured `user_id` and
-- `member_id` and dropped it, and `MemberRead` never carried it. A value
-- computed, carried, and never read — disclosing something — which is the
-- same shape as the analytics `rows` leak found earlier the same day.
--
-- ⚠️ WHAT REMAINS INFERABLE, STATED EXACTLY. A caller can still learn that a
-- subject is ALREADY IN THEIR OWN ORGANIZATION, because the bind is refused
-- by `organization_members_unique`. They are entitled to that: `list_members`
-- shows it. A subject that exists only in ANOTHER organization and one that
-- does not exist at all now produce the SAME observable outcome — a
-- successful bind returning a uuid the caller cannot correlate to anything.
-- That is the cross-tenant existence disclosure I82 was about, and it is
-- closed rather than priced.
-- ============================================================================

BEGIN;

DO $drop$
DECLARE
    fn RECORD;
BEGIN
    FOR fn IN
        SELECT p.oid::regprocedure AS sig
        FROM pg_proc p
        JOIN pg_namespace n ON n.oid = p.pronamespace
        WHERE n.nspname = 'core' AND p.proname = 'bind_subject_to_organization'
    LOOP
        EXECUTE format('DROP FUNCTION %s', fn.sig);
    END LOOP;
END
$drop$;

CREATE FUNCTION core.bind_subject_to_organization(
    p_subject      TEXT,
    p_email        TEXT,
    p_display_name TEXT
)
    -- 🔴 NO `identity_created`. See the header: it was a cross-tenant
    -- existence bit with no consumer, and the "cost" that supposedly excused
    -- it could be rolled away.
    RETURNS TABLE (user_id UUID, member_id UUID)
    LANGUAGE plpgsql
    VOLATILE
    SECURITY DEFINER
    SET search_path = core, pg_temp
AS $fn$
DECLARE
    v_org     UUID := core.current_org_id();
    v_actor   UUID := core.current_user_id();
    v_perms   TEXT[];
    v_user    UUID;
    v_member  UUID;
BEGIN
    IF v_org IS NULL OR v_actor IS NULL THEN
        RAISE EXCEPTION 'no session context'
            USING ERRCODE = 'insufficient_privilege';
    END IF;

    -- 🔴 PROVE THE CALLER ADMINISTERS *THIS* TENANT (050).
    --
    -- 048's function derives roles and permissions from the same two GUCs RLS
    -- reads, and returns nothing at all for a user who is not an active
    -- member of that organization. So a caller who forges `app.current_org`
    -- to a tenant they do not belong to gets an empty permission set and is
    -- refused HERE, before the definer's RLS-free INSERT.
    --
    -- ⚠️ THE PERMISSION IS CHECKED IN THE DATABASE, NOT ONLY AT THE ROUTE.
    -- `require_permission("admin.users")` already guards the HTTP path. This
    -- is the same rule on the path that has no route — the argument
    -- `app/agents/boundary.py` makes for the agent tier, applied to a
    -- privileged write.
    SELECT permissions INTO v_perms FROM core.authorization_for_current_session();

    IF v_perms IS NULL OR NOT ('admin.users' = ANY(v_perms)) THEN
        -- Deliberately does not say WHICH is missing -- membership or
        -- permission -- because "you are not a member of that organization"
        -- and "you are, but may not administer it" are different facts and
        -- only one of them is the caller's business.
        RAISE EXCEPTION 'not permitted to bind members in this organization'
            USING ERRCODE = 'insufficient_privilege';
    END IF;

    SELECT id INTO v_user FROM core.users WHERE keycloak_sub = p_subject;

    IF v_user IS NULL THEN
        -- 🔴 THE ID IS CHOSEN HERE, NOT READ BACK -- AND THAT IS ABOUT THE
        -- I56/I58 FORCE CUTOVER. Raised by the Supervisor.
        --
        -- `INSERT ... RETURNING id` is subject to the SELECT policy, and 044's
        -- makes a freshly created identity invisible until it has a
        -- membership. It works today only because `evercoat_owner` is exempt
        -- while RLS is ENABLED and not FORCED. Under the cutover the ONLY
        -- user-creation path in the application would start returning
        -- nothing -- and `test_046_email_is_an_attribute.py` already
        -- documents that hazard as measured, which is why `_new_identity`
        -- exists there to avoid `RETURNING`.
        --
        -- Generating the uuid removes the read entirely. `gen_random_uuid()`
        -- is in `pg_catalog`, so the pinned search_path reaches it.
        --
        -- ⚠️ THE LOOKUP ABOVE IS STILL FORCE-SENSITIVE, and this migration
        -- does not pretend otherwise: under FORCE, `SELECT id FROM core.users
        -- WHERE keycloak_sub = ...` would stop seeing subjects in other
        -- tenants, which is the entire reason this function is a definer.
        -- That belongs to the cutover and is recorded in TODO.md.
        v_user := gen_random_uuid();
        INSERT INTO core.users (id, keycloak_sub, email, display_name)
        VALUES (v_user, p_subject, p_email::public.citext, p_display_name);
    END IF;

    -- If this cannot be created -- already a member, or 046's per-organization
    -- address guard -- the exception propagates, the function rolls back, and
    -- no identifier is returned.
    INSERT INTO core.organization_members (organization_id, user_id)
    VALUES (v_org, v_user)
    RETURNING id INTO v_member;

    RETURN QUERY SELECT v_user, v_member;
END
$fn$;

ALTER FUNCTION core.bind_subject_to_organization(TEXT, TEXT, TEXT)
    OWNER TO evercoat_owner;
REVOKE ALL ON FUNCTION core.bind_subject_to_organization(TEXT, TEXT, TEXT) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION core.bind_subject_to_organization(TEXT, TEXT, TEXT) TO evercoat_app;

COMMENT ON FUNCTION core.bind_subject_to_organization(TEXT, TEXT, TEXT) IS
    'Resolve a Keycloak subject and bind it to the CURRENT SESSION''s '
    'organization, atomically, returning the identifiers only after the '
    'membership exists (I82). '
    'It PROVES the caller''s standing before writing: the session''s user must '
    'hold admin.users in the session''s organization according to '
    'core.authorization_for_current_session(). Without that check a caller '
    'could forge app.current_org and have this definer create a membership in '
    'another tenant, RLS-free -- measured, and the reason 050 exists. '
    'It does not report whether the identity already existed: that answer was '
    'a cross-tenant existence oracle whose supposed cost could be rolled back.';

-- ============================================================================
-- ⚠️ THE TRIGGER GUARDS KEEP 049's WIDER search_path, AND HERE IS WHY
-- ============================================================================
--
-- Codex, correctly: 049 added `public` to both ADR-028 guards so they could
-- resolve the CITEXT they declare, and migration 013 records that this
-- database never revoked CREATE on `public`. A writable schema in a guard's
-- resolution path turns any FUTURE unqualified name in those triggers into
-- owner-context resolution through a schema unprivileged roles can write to.
-- The proposed fix is to declare `v_email public.citext` and restore
-- `core, pg_temp`.
--
-- 🔴 I WROTE THAT FIX AND WITHDREW IT, AND THE REASON IS THE POINT.
--
-- Changing a DECLARE requires `CREATE OR REPLACE` with the WHOLE body. I
-- drafted that body by hand and then read the real one out of
-- `pg_get_functiondef` — and my draft had silently dropped
--
--     PERFORM pg_advisory_xact_lock(hashtext(...), hashtext(...))
--
-- which is the line that makes the guard a CONSTRAINT rather than a check two
-- concurrent writers walk past. 046 added it after measuring exactly that
-- race on two real connections. Shipping my draft would have reopened it,
-- inside a migration whose subject is not weakening guards.
--
-- ⚠️ SO THE NARROWING IS DEFERRED, NOT DECLINED. Codex assessed the current
-- risk as theoretical — *"I do not see an immediate exploitable shadow of the
-- current statements"* — because `core` precedes `public` and the existing
-- type cannot be replaced by an unprivileged role. Trading a theoretical
-- shadowing risk for a measured concurrency defect is a bad trade, and doing
-- it by retyping a security guard from memory is a worse method.
--
-- The right change copies the body VERBATIM from `pg_get_functiondef` and
-- alters only the declaration, or revokes CREATE on `public` database-wide.
-- Both are their own migration with their own tests. Recorded in `TODO.md`.

COMMIT;
