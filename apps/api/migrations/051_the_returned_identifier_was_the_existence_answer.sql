-- 051 — the returned identifier WAS the existence answer
--
-- Depends on 050 (i1000).
--
-- ============================================================================
-- 🔴 050 REMOVED THE FLAG AND KEPT THE BIT
-- ============================================================================
--
-- 050 deleted `identity_created` because it answered "does this subject exist
-- somewhere on this platform" for free. Codex, reviewing 050, pointed out that
-- the answer never left: `user_id` carries it. MEASURED, not accepted:
--
--     as a legitimate administrator OF THEIR OWN organization A:
--       BEGIN; SELECT user_id FROM core.bind_subject_to_organization(S,...);
--       ROLLBACK;                                      -- twice
--
--     subject that exists in organization B : e55fea29  e55fea29   SAME
--     subject that exists nowhere           : 6e0e24e8  22231d7c   DIFFER
--
--     memberships left behind by the probing: 0
--
-- An identity that already exists is SELECTed, so its uuid repeats across
-- attempts. A new one is minted per attempt, so it does not. Same question,
-- same price — nothing — under a different column name. **I83 was closed by
-- DROPPING the oracle rather than disguising it, and 050 disguised this one.**
--
-- The fix is that the function stops returning the identity. `member_id` comes
-- from `INSERT ... RETURNING` on a row created by this call, so it is fresh in
-- both branches and distinguishes nothing. `app/api/admin.py` resolves the
-- user through that membership instead — a read that 044's policy governs,
-- rather than one handed out by a definer.
--
-- ============================================================================
-- ⚠️ WHAT THIS DOES *NOT* CLOSE, STATED PLAINLY
-- ============================================================================
--
-- A caller who can roll back can still bind a subject, read the resulting
-- member's stored email and display name through the membership, and roll
-- back. If the subject existed in another tenant those attributes are that
-- tenant's, not the ones submitted. Closing that requires tenant-scoped
-- attributes on `core.organization_members` — 046's per-organization address
-- guard already reads the global identity, so it moves with them. That is a
-- schema change with its own migration and tests, filed as **I106**.
--
-- Two things bound it, and neither is a reason to leave it: the probe needs
-- `admin.users` in an organization the caller genuinely administers, and it
-- needs an EXACT `keycloak_sub` — an opaque Keycloak uuid, not the guessable
-- address that made I83 cheap. Over HTTP the route commits, so the same bit
-- costs a real, audited membership. The SQL-level probe is free, and the
-- SQL level is the framing under which 049's cross-tenant write was accepted
-- as a defect. It gets the same standard.

BEGIN;

DROP FUNCTION IF EXISTS core.bind_subject_to_organization(TEXT, TEXT, TEXT);

CREATE FUNCTION core.bind_subject_to_organization(
    p_subject      TEXT,
    p_email        TEXT,
    p_display_name TEXT
)
    -- 🔴 NO `identity_created`. See the header: it was a cross-tenant
    -- existence bit with no consumer, and the "cost" that supposedly excused
    -- it could be rolled away.
    -- 🔴 NO `user_id` EITHER (051). Removing `identity_created` in 050 did
    -- not remove the answer it carried; it moved it into this column. See the
    -- migration header: measured, free, and traceless.
    RETURNS TABLE (member_id UUID)
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

    -- The membership id is a fresh uuid on EVERY call, in both branches,
    -- so nothing about it distinguishes a subject that already existed from
    -- one that did not. The caller resolves the user THROUGH this membership,
    -- under RLS, where 044's policy is the thing that decides.
    RETURN QUERY SELECT v_member;
END
$fn$;

ALTER FUNCTION core.bind_subject_to_organization(TEXT, TEXT, TEXT)
    OWNER TO evercoat_owner;
REVOKE ALL ON FUNCTION core.bind_subject_to_organization(TEXT, TEXT, TEXT) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION core.bind_subject_to_organization(TEXT, TEXT, TEXT) TO evercoat_app;

COMMENT ON FUNCTION core.bind_subject_to_organization(TEXT, TEXT, TEXT) IS
    'Resolve a Keycloak subject and bind it to the CURRENT SESSION''s '
    'organization, atomically, returning ONLY the membership id (051). '
    'It PROVES the caller''s standing before writing: the session''s user must '
    'hold admin.users in the session''s organization according to '
    'core.authorization_for_current_session(). Without that check a caller '
    'could forge app.current_org and have this definer create a membership in '
    'another tenant, RLS-free -- measured, and the reason 050 exists. '
    'It returns no identity identifier: a uuid that repeats across rolled-back '
    'attempts answers "does this subject already exist somewhere" for free, '
    'which is the oracle 050 believed it had removed with identity_created.';

COMMIT;
