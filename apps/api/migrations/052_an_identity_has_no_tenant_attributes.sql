-- =====================================================================
-- 052 — an identity has no tenant attributes; a MEMBERSHIP does
--
-- Closes I106, and I108 found while measuring it.
--
-- Depends on 051 (j1000).
--
-- ---------------------------------------------------------------------
-- I106 — MEASURED FIRST, THEN BELIEVED
-- ---------------------------------------------------------------------
--
-- 051 stopped the bind returning an identity identifier, and said in its
-- own header what it did NOT close. This is that. As a legitimate
-- administrator of organization A, against a subject whose identity
-- exists only in organization B:
--
--     BEGIN;
--     SELECT member_id FROM core.bind_subject_to_organization(S, e, n);
--     SELECT u.email, u.display_name
--       FROM core.organization_members om
--       JOIN core.users u ON u.id = om.user_id
--      WHERE om.id = <member_id>;
--     ROLLBACK;
--
--     submitted  : 'whatever@attacker.example'   / 'Whatever I Typed'
--     read back  : 'secret.person@competitor.example' / 'Confidential B Person'
--     org B holds: 'secret.person@competitor.example' / 'Confidential B Person'
--     memberships left behind: 0
--
-- The bind resolves an existing subject to the GLOBAL `core.users` row and
-- does not touch its attributes -- correctly, because writing them would be
-- the cross-tenant WRITE that 049 was rejected for. So the membership points
-- at another tenant's data, 044's read policy admits it for as long as the
-- membership exists, and the whole thing rolls back without a trace.
--
-- ---------------------------------------------------------------------
-- 🔴 I108 — AND THE BIND IS NOT EVEN NEEDED. MEASURED WHILE FIXING I106.
-- ---------------------------------------------------------------------
--
-- `evercoat_app` holds table-level INSERT on `core.organization_members`,
-- and `org_member_isolation` constrains only `organization_id`. `user_id`
-- is a plain FK to a GLOBAL table, so it accepts any identity in the
-- system. Measured as an ORDINARY member of A -- no `admin.users`, no
-- EXECUTE on the bind, no `keycloak_sub`:
--
--     foreign identity visible BEFORE            : 0 rows
--     INSERT INTO core.organization_members (organization_id, user_id)
--       VALUES (<my org>, <a foreign user id>);
--     read AFTER                                  : ('secret...@competitor.example',
--                                                    'Confidential B Person')
--     ROLLBACK
--
-- So I106's real shape is not "the bind leaks". It is **any membership row
-- turns a global identity into a readable one**, and the bind is one of two
-- ways to make one. NOTHING IN `app/` INSERTS THAT TABLE DIRECTLY -- the
-- only writer is the SECURITY DEFINER bind, which runs as the owner. The
-- grant is a capability nothing calls, and it is a disclosure primitive.
--
-- ---------------------------------------------------------------------
-- WHAT THIS MIGRATION DOES, AND WHICH PART IS LOAD-BEARING
-- ---------------------------------------------------------------------
--
--   1. `core.organization_members` carries its own `email` and
--      `display_name`. They are what the CALLER SUBMITTED, so they answer
--      nothing about any other tenant.
--   2. 🔴 `core.users.email` and `core.users.display_name` stop being
--      readable by the runtime roles. **THIS IS THE MECHANISM.** Step 1
--      is what keeps the application working once the global attributes
--      are gone; it is not, by itself, a closure -- I108 shows the raw
--      read survives every change to the bind.
--   3. INSERT on `core.organization_members` is revoked from
--      `evercoat_app`. Nothing calls it and it is I108's vector.
--
-- `core.users` keeps both columns as the identity provider's mirror. The
-- owner-owned SECURITY DEFINER sign-in lookups still read them -- but they
-- now return the MEMBERSHIP's values, because the address one organization
-- knows a person by is that organization's fact, not a global one. A person
-- in two tenants may legitimately appear under two addresses; before this,
-- whichever tenant onboarded them first decided what the other one saw.
--
-- ⚠️ WHY THE COLUMNS ARE NOT DROPPED. `keycloak_sub` was revoked rather
-- than dropped by 047 for the same reason: the sign-in definers need the
-- mirror, and an identity with no membership anywhere still has to have
-- come from somewhere. Dropping them would also make the bind unable to
-- record what it was given when it creates a NEW identity, which is the
-- only honest source for a first membership's attributes.
--
-- ---------------------------------------------------------------------
-- 046's TWO TRIGGER GUARDS ARE REPLACED BY A REAL UNIQUE INDEX
-- ---------------------------------------------------------------------
--
-- 046 could not use an index. The rule is "one active member per address
-- per organization", the address lived on the GLOBAL `core.users`, and no
-- index spans two tables -- so it was a pair of trigger functions holding
-- `pg_advisory_xact_lock` to stop two concurrent writers forking the
-- invariant, plus a second trigger on `core.users` because the address
-- could be changed in place without any membership row moving.
--
-- With the address ON the membership row, `(organization_id, email) WHERE
-- status = 'active'` is a single partial unique index. It covers INSERT,
-- UPDATE of the address, and a reactivation, in one mechanism, with no
-- advisory lock and no window in which two writers both pass.
--
-- 🔴 AND IT IS NOT I83's ORACLE COMING BACK. That is the question this
-- change has to answer, because 046 exists precisely because a unique
-- index is enforced OUTSIDE row-level security. The difference is the
-- KEY: `users_email_key` was `(email)` platform-wide, so its refusal
-- answered "does this address exist ANYWHERE". This key leads with
-- `organization_id`, so a refusal can only ever concern a row in the
-- organization the writer named -- and after this migration the only
-- writer is the definer, which takes the organization from
-- `core.current_org_id()` after proving the caller administers it. Every
-- refusal therefore describes a member `list_members` already shows that
-- caller. That is exactly 046's own stated criterion for where a
-- uniqueness rule may be enforced.
--
-- ⚠️ The index is NAMED `organization_members_one_address_per_organization`,
-- the same name 046's trigger used, because `app/api/admin.py` classifies
-- the 409 by constraint name and a rename would silently turn that into
-- "the membership could not be created" (500). Verified below.
-- =====================================================================

BEGIN;

-- ---------------------------------------------------------------------
-- 1. The membership carries the organization's own view of the person.
-- ---------------------------------------------------------------------
ALTER TABLE core.organization_members
    ADD COLUMN email        public.citext,
    ADD COLUMN display_name TEXT;

-- Backfill from the global row, which is what every existing membership
-- was displaying anyway. Measured before writing this: 153 memberships,
-- 0 with a NULL email or display name, so NOT NULL below cannot fail on
-- the live population -- and if it ever does, it fails loudly rather than
-- leaving a nullable column nobody notices.
UPDATE core.organization_members om
   SET email        = u.email,
       display_name = u.display_name
  FROM core.users u
 WHERE u.id = om.user_id;

ALTER TABLE core.organization_members
    ALTER COLUMN email        SET NOT NULL,
    ALTER COLUMN display_name SET NOT NULL;

COMMENT ON COLUMN core.organization_members.email IS
    'The address THIS organization knows this member by, submitted by the '
    'administrator who bound them (migration 052, I106). Deliberately not '
    'read from core.users: for an identity that already existed in another '
    'tenant that row holds the OTHER tenant''s address, and a rolled-back '
    'bind made it readable for free.';

COMMENT ON COLUMN core.organization_members.display_name IS
    'The name THIS organization knows this member by (migration 052, I106). '
    'See core.organization_members.email.';

-- ---------------------------------------------------------------------
-- 2. One active member per address per organization -- as an INDEX now.
-- ---------------------------------------------------------------------
DROP TRIGGER IF EXISTS organization_members_one_address_per_organization
    ON core.organization_members;
DROP TRIGGER IF EXISTS users_address_stays_unique_in_organization
    ON core.users;
DROP FUNCTION IF EXISTS core.deny_duplicate_address_in_organization();
DROP FUNCTION IF EXISTS core.deny_address_collision_on_rename();

CREATE UNIQUE INDEX organization_members_one_address_per_organization
    ON core.organization_members (organization_id, email)
    WHERE status = 'active';

COMMENT ON INDEX core.organization_members_one_address_per_organization IS
    'One ACTIVE member per address, per organization (I83, restated by '
    'migration 052). Replaces the two trigger functions 046 needed while '
    'the address lived on the global core.users table. Leading with '
    'organization_id is what keeps it from being users_email_key again: a '
    'refusal can only describe a member of the organization the writer '
    'named, which list_members already shows them.';

-- ---------------------------------------------------------------------
-- 3. The bind records what it was GIVEN, on the membership.
-- ---------------------------------------------------------------------
DROP FUNCTION IF EXISTS core.bind_subject_to_organization(TEXT, TEXT, TEXT);

CREATE FUNCTION core.bind_subject_to_organization(
    p_subject      TEXT,
    p_email        TEXT,
    p_display_name TEXT
)
    -- Still only `member_id`, for 051's reason: any value that repeats
    -- across two rolled-back attempts answers "does this subject already
    -- exist somewhere on this platform".
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

    -- PROVE THE CALLER ADMINISTERS *THIS* TENANT (050). 048's function
    -- derives roles and permissions from the same two GUCs RLS reads and
    -- returns nothing for a user who is not an active member of that
    -- organization, so a forged `app.current_org` fails on itself here,
    -- before the definer's RLS-free INSERT.
    SELECT permissions INTO v_perms FROM core.authorization_for_current_session();

    IF v_perms IS NULL OR NOT ('admin.users' = ANY(v_perms)) THEN
        -- Deliberately does not say WHICH is missing -- membership or
        -- permission -- because only one of those is the caller's business.
        RAISE EXCEPTION 'not permitted to bind members in this organization'
            USING ERRCODE = 'insufficient_privilege';
    END IF;

    SELECT id INTO v_user FROM core.users WHERE keycloak_sub = p_subject;

    IF v_user IS NULL THEN
        -- The id is chosen here rather than read back: `INSERT ... RETURNING
        -- id` is subject to the SELECT policy, and 044's makes a freshly
        -- created identity invisible until it has a membership. That works
        -- today only because `evercoat_owner` is exempt while RLS is ENABLED
        -- and not FORCED, so under the I56/I58 cutover the only
        -- user-creation path in the application would start returning
        -- nothing. `gen_random_uuid()` is in `pg_catalog`, which the pinned
        -- search_path reaches.
        --
        -- ⚠️ The lookup above is still FORCE-sensitive and this migration
        -- does not pretend otherwise -- see TODO.md.
        v_user := gen_random_uuid();
        INSERT INTO core.users (id, keycloak_sub, email, display_name)
        VALUES (v_user, p_subject, p_email::public.citext, p_display_name);
    END IF;

    -- 🔴 THE SUBMITTED ATTRIBUTES, ON THE MEMBERSHIP, ALWAYS (052).
    --
    -- Not read from `core.users`, and not written TO it either. For a
    -- pre-existing identity the global row belongs to whichever tenant
    -- created it: reading it is I106, and writing it would be the
    -- cross-tenant WRITE that got 049's first design rejected. The only
    -- honest thing this call knows about the person is what the caller
    -- submitted, so that is what this organization records.
    --
    -- If this cannot be created -- already a member, or the address is
    -- already held by an active member here -- the exception propagates,
    -- the function rolls back, and no identifier is returned.
    INSERT INTO core.organization_members
        (organization_id, user_id, email, display_name)
    VALUES (v_org, v_user, p_email::public.citext, p_display_name)
    RETURNING id INTO v_member;

    -- Fresh on EVERY call in BOTH branches, so it distinguishes nothing.
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
    'It PROVES the caller''s standing first: the session''s user must hold '
    'admin.users in the session''s organization according to '
    'core.authorization_for_current_session(). The membership records the '
    'SUBMITTED email and display name (052, I106) -- never the global '
    'identity''s, which for a subject that already exists belongs to '
    'another tenant, and never onto the global identity either, which '
    'would be a cross-tenant write.';

-- ---------------------------------------------------------------------
-- 4. Sign-in reports the organization's own view of the person.
-- ---------------------------------------------------------------------
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
    SET search_path = core, pg_temp
AS $$
    -- 🔴 `om.email`, NOT `u.email` (052). This function is scoped to ONE
    -- organization, so the address it reports must be that organization's.
    -- A person who belongs to two tenants had whichever one onboarded them
    -- first decide what the other one displayed.
    SELECT u.id,
           om.email::TEXT,
           om.display_name,
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
    GROUP BY u.id, om.email, om.display_name, om.organization_id
$$;

ALTER FUNCTION core.principal_for_subject(TEXT, UUID) OWNER TO evercoat_owner;
GRANT EXECUTE ON FUNCTION core.principal_for_subject(TEXT, UUID) TO evercoat_app;

COMMENT ON FUNCTION core.principal_for_subject(TEXT, UUID) IS
    'Identity, roles and permissions for a verified Keycloak subject within '
    'one organization. SECURITY DEFINER because it must answer BEFORE the '
    'tenant GUC can be set. Scoped strictly to (subject, organization); a '
    'subject who is not an active member of that organization gets zero '
    'rows. The email and display name come from the MEMBERSHIP (052), so '
    'each organization reports the person as it knows them.';

CREATE OR REPLACE FUNCTION core.memberships_for_subject(p_sub TEXT)
RETURNS TABLE (
    user_id           UUID,
    email             TEXT,
    display_name      TEXT,
    organization_id   UUID,
    organization_name TEXT,
    organization_code TEXT,
    roles             TEXT[],
    permissions       TEXT[]
)
    LANGUAGE sql
    STABLE
    SECURITY DEFINER
    SET search_path = core, pg_temp
AS $$
    -- 🔴 `om.email` / `om.display_name` (052). This function returns ONE
    -- ROW PER ORGANIZATION, so reading the global identity meant every
    -- tenant in the list was described by a single shared address. The
    -- membership makes each row report its own organization's view.
    SELECT u.id,
           om.email::TEXT,
           om.display_name,
           om.organization_id,
           o.name,
           o.code,
           -- The ORDER BY is explicit rather than inherited: `array_agg
           -- (DISTINCT x)` does come back sorted on 16.14, but that is an
           -- implementation behaviour and not a documented contract, and a
           -- guarantee must be a mechanism rather than an argument.
           COALESCE(array_agg(DISTINCT r.code ORDER BY r.code)
                    FILTER (WHERE r.code IS NOT NULL), '{}'),
           COALESCE(array_agg(DISTINCT p.code ORDER BY p.code)
                    FILTER (WHERE p.code IS NOT NULL), '{}')
    FROM core.users u
    JOIN core.organization_members om
      ON om.user_id = u.id
     AND om.status  = 'active'
    JOIN core.organizations o
      ON o.id = om.organization_id
     -- An inactive or archived organization is not a place anyone may act.
     AND o.status = 'active'
    LEFT JOIN core.member_roles     mr ON mr.member_id = om.id
    LEFT JOIN core.roles            r  ON r.id = mr.role_id
    -- DISTINCT matters because role_permissions multiplies each
    -- (member, role) row by the number of permissions that role carries.
    LEFT JOIN core.role_permissions rp ON rp.role_id = r.id
    LEFT JOIN core.permissions      p  ON p.id = rp.permission_id
    WHERE u.keycloak_sub = p_sub
      AND u.status = 'active'
    GROUP BY u.id, om.email, om.display_name, om.organization_id, o.name, o.code
    ORDER BY o.name
$$;

ALTER FUNCTION core.memberships_for_subject(TEXT) OWNER TO evercoat_owner;
REVOKE ALL ON FUNCTION core.memberships_for_subject(TEXT) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION core.memberships_for_subject(TEXT) TO evercoat_app;

COMMENT ON FUNCTION core.memberships_for_subject(TEXT) IS
    'Organizations a verified Keycloak subject may act in, with the roles '
    'AND permissions held in each. SECURITY DEFINER because it must answer '
    'BEFORE an organization has been chosen, when no RLS GUC is set. Scoped '
    'strictly to the subject argument; takes no organization argument and '
    'therefore cannot be pointed at another tenant. Permissions are '
    'resolved from core.role_permissions so the browser and the API read '
    'ONE definition (I79). Each row carries the MEMBERSHIP''s email and '
    'display name (052), not the global identity''s.';

-- ---------------------------------------------------------------------
-- 5. 🔴 THE LOAD-BEARING PART: the global attributes stop being readable.
-- ---------------------------------------------------------------------
--
-- Everything above keeps the application working. THIS is what closes
-- I106 and I108, because both of them are a raw read of `core.users` made
-- legal by a membership row that can be rolled away.
--
-- These are COLUMN-level grants already (047 replaced the table-level
-- SELECT with an explicit list), so a column-level REVOKE does bite here.
-- ⚠️ It would not against a table-level grant -- see 047's header. The
-- probe at the bottom of this file asserts the resulting privilege rather
-- than assuming this statement did anything.
REVOKE SELECT (email, display_name) ON core.users
    FROM evercoat_app, evercoat_report, evercoat_worker;

-- UPDATE goes with it. 047 kept `UPDATE (email, display_name)` on the
-- strength of 044's assertion that an administrator may correct a
-- colleague's name inside their own organization -- and the rename was
-- policed by `users_address_stays_unique_in_organization`, dropped above.
-- Leaving the grant while removing its guard would let one tenant rewrite
-- a person's GLOBAL address with nothing checking it: a cross-tenant
-- write, granted by omission, in the migration that removes a
-- cross-tenant read. That capability now lives on the membership, where
-- `org_member_isolation` scopes it and the unique index polices it.
REVOKE UPDATE (email, display_name) ON core.users FROM evercoat_app;

COMMENT ON COLUMN core.users.email IS
    'The address mirrored from the identity provider. NOT unique (I83, 046) '
    'and NOT readable by evercoat_app, evercoat_report or evercoat_worker '
    '(I106, 052): a membership row makes any global identity readable under '
    '044''s policy, and a membership can be created and rolled back without '
    'a trace. What an organization knows a member by lives on '
    'core.organization_members. The owner-owned sign-in definers still read '
    'this column, and the bind still writes it when it creates an identity.';

COMMENT ON COLUMN core.users.display_name IS
    'The name mirrored from the identity provider. NOT readable by the '
    'runtime roles (I106, 052) -- see core.users.email. Attribution reads '
    'core.organization_members.display_name.';

-- ---------------------------------------------------------------------
-- 6. I108's vector: a grant nothing calls.
-- ---------------------------------------------------------------------
--
-- No query in `app/` inserts this table. The only writer is the SECURITY
-- DEFINER bind above, which runs as `evercoat_owner`. The grant let any
-- authenticated session manufacture a membership naming an arbitrary
-- global `user_id` -- measured, and the reason the revoke in step 5 rather
-- than the columns in step 1 is what closes this.
--
-- UPDATE and SELECT stay: `set_member_status` updates, `list_members`
-- reads, and both are confined to the caller's organization by
-- `org_member_isolation`.
REVOKE INSERT ON core.organization_members FROM evercoat_app;

COMMIT;


-- ---------------------------------------------------------------------
-- PROVE IT, ON ROWS BUILT FOR THE PURPOSE, AND ROLL BACK.
--
-- The live population cannot exercise any of this: no organization holds
-- a duplicate address (measured: 0 groups across 153 memberships), and
-- nothing has ever bound a foreign subject. A measurement over a
-- population that cannot exercise the risk is not evidence.
-- ---------------------------------------------------------------------
DO $probe$
DECLARE
    v_org_a  UUID;
    v_org_b  UUID;
    v_u1     UUID;
    v_u2     UUID;
    v_sfx    TEXT := replace(gen_random_uuid()::TEXT, '-', '');
    v_addr   TEXT;
    v_caught BOOLEAN;
    v_priv   BOOLEAN;
BEGIN
    v_addr := 'probe052-' || left(v_sfx, 8) || '@example.test';

    -- (1) THE PRIVILEGE, NOT THE STATEMENT. A REVOKE that did nothing
    --     would leave this migration reading like a fix and changing
    --     nothing -- 047's header names that shape explicitly.
    FOR v_priv IN
        SELECT has_column_privilege(role_name, 'core.users', col, 'SELECT')
          FROM (VALUES ('evercoat_app'), ('evercoat_report'), ('evercoat_worker'))
                   AS r(role_name),
               (VALUES ('email'), ('display_name')) AS c(col)
    LOOP
        IF v_priv THEN
            RAISE EXCEPTION
                '052 FAILED: a runtime role can still SELECT the global '
                'identity attributes. I106 and I108 are both open -- the '
                'membership columns above are only what keeps the '
                'application working, not the closure.';
        END IF;
    END LOOP;
    RAISE NOTICE '052: core.users.email/display_name are unreadable by the runtime roles';

    -- ...and the control half: `id` must still be readable, or every
    -- join in the application is broken and the loop above would pass
    -- against a REVOKE SELECT on the whole table.
    IF NOT has_column_privilege('evercoat_app', 'core.users', 'id', 'SELECT') THEN
        RAISE EXCEPTION
            '052 FAILED: evercoat_app cannot read core.users.id. The revoke '
            'was too wide and every actor join in the application is broken.';
    END IF;
    RAISE NOTICE '052: core.users.id is still readable -- the revoke is scoped';

    -- (2) INSERT on the membership table is gone for the runtime role
    --     (I108), and SELECT/UPDATE are not.
    IF has_table_privilege('evercoat_app', 'core.organization_members', 'INSERT') THEN
        RAISE EXCEPTION
            '052 FAILED: evercoat_app can still INSERT memberships directly. '
            'That is I108''s vector: a membership naming an arbitrary global '
            'user_id, rolled back after reading the identity.';
    END IF;
    IF NOT has_table_privilege('evercoat_app', 'core.organization_members', 'SELECT')
       OR NOT has_table_privilege('evercoat_app', 'core.organization_members', 'UPDATE') THEN
        RAISE EXCEPTION
            '052 FAILED: evercoat_app lost SELECT or UPDATE on '
            'core.organization_members. list_members and set_member_status '
            'are both broken.';
    END IF;
    RAISE NOTICE '052: the membership table is readable and updatable, not insertable';

    -- (3) THE UNIQUE INDEX REFUSES A SECOND ACTIVE MEMBER ON ONE ADDRESS...
    INSERT INTO core.organizations (code, name)
    VALUES ('P052A-' || left(v_sfx, 8), '052 probe A') RETURNING id INTO v_org_a;
    INSERT INTO core.organizations (code, name)
    VALUES ('P052B-' || left(v_sfx, 8), '052 probe B') RETURNING id INTO v_org_b;

    INSERT INTO core.users (keycloak_sub, email, display_name)
    VALUES ('p052-1-' || v_sfx, v_addr, '052 one') RETURNING id INTO v_u1;
    INSERT INTO core.users (keycloak_sub, email, display_name)
    VALUES ('p052-2-' || v_sfx, 'other-' || v_addr, '052 two') RETURNING id INTO v_u2;

    INSERT INTO core.organization_members (organization_id, user_id, email, display_name)
    VALUES (v_org_a, v_u1, v_addr, '052 one');

    v_caught := FALSE;
    BEGIN
        INSERT INTO core.organization_members (organization_id, user_id, email, display_name)
        VALUES (v_org_a, v_u2, v_addr, '052 two');
    EXCEPTION WHEN unique_violation THEN
        v_caught := TRUE;
    END;
    IF NOT v_caught THEN
        RAISE EXCEPTION
            '052 FAILED: two active members of one organization hold %. The '
            'index did not replace 046''s trigger guard.', v_addr;
    END IF;
    RAISE NOTICE '052: a second active member on one address is refused';

    -- (4) ...AND IT IS SCOPED TO ONE ORGANIZATION. Without this half the
    --     index would be users_email_key again and I83 would be reopened.
    --     Caught and re-diagnosed on purpose: without the handler the run
    --     would abort on the index's own message, which reads like the
    --     guard WORKING rather than like its scope being wrong.
    BEGIN
        INSERT INTO core.organization_members (organization_id, user_id, email, display_name)
        VALUES (v_org_b, v_u2, v_addr, '052 two elsewhere');
    EXCEPTION WHEN unique_violation THEN
        RAISE EXCEPTION
            '052 FAILED: the index refused % in a DIFFERENT organization. It '
            'is not scoped to one tenant, so it is users_email_key wearing a '
            'partial index and I83''s cross-tenant oracle is open again.', v_addr;
    END;
    RAISE NOTICE '052: the same address in another organization is accepted';

    -- (5) AND THE UPDATE HALF, WHICH 046 NEEDED A SECOND TRIGGER FOR.
    --     Renaming a member onto a colleague's address must be refused by
    --     the same index -- this is where the old design was bypassed.
    v_caught := FALSE;
    BEGIN
        UPDATE core.organization_members
           SET email = v_addr
         WHERE organization_id = v_org_b AND user_id = v_u2;
        -- Not a collision yet: v_u2 is the only member of B. Make one.
        INSERT INTO core.organization_members (organization_id, user_id, email, display_name)
        VALUES (v_org_b, v_u1, 'third-' || v_addr, '052 one elsewhere');
        UPDATE core.organization_members
           SET email = v_addr
         WHERE organization_id = v_org_b AND user_id = v_u1;
    EXCEPTION WHEN unique_violation THEN
        v_caught := TRUE;
    END;
    IF NOT v_caught THEN
        RAISE EXCEPTION
            '052 FAILED: renaming a member onto %, already held by another '
            'active member of the same organization, was ACCEPTED. That is '
            'the bypass 046 needed a second trigger on core.users for, and '
            'the index is supposed to cover it.', v_addr;
    END IF;
    RAISE NOTICE '052: renaming onto a colleague''s address is refused';

    -- (6) THE CONSTRAINT NAME THE ROUTE CLASSIFIES ON.
    --     `app/api/admin.py` turns this exact name into a 409 explaining the
    --     address is taken; anything it cannot name becomes a 500. Renaming
    --     the index would silently downgrade a correct 409 into a server
    --     error, and nothing else in the suite reads the name.
    IF NOT EXISTS (
        SELECT 1 FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
         WHERE n.nspname = 'core'
           AND c.relname = 'organization_members_one_address_per_organization'
           AND c.relkind = 'i'
    ) THEN
        RAISE EXCEPTION
            '052 FAILED: the index is not named '
            'organization_members_one_address_per_organization, so '
            '_bind_conflict cannot classify it and a taken address answers '
            '500 instead of 409.';
    END IF;
    RAISE NOTICE '052: the index carries the name the route classifies on';

    RAISE EXCEPTION 'probe complete, rolling back' USING ERRCODE = 'raise_exception';
EXCEPTION
    WHEN raise_exception THEN
        IF SQLERRM <> 'probe complete, rolling back' THEN
            RAISE;
        END IF;
        RAISE NOTICE '052: probe rolled back';
END $probe$;
