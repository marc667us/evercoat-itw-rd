-- =====================================================================
-- 053 — signing in is not something the runtime role may do
--
-- Closes I109.
--
-- Depends on 052 (k1000).
--
-- ---------------------------------------------------------------------
-- WHAT WAS WRONG — MEASURED, NOT ASSUMED
-- ---------------------------------------------------------------------
--
-- Raised by Codex reviewing 052, which claimed a foreign identity's
-- attributes were no longer readable. That was true of the TABLE and not
-- of every path. Measured as an ORDINARY member of organization A,
-- holding no permission at all:
--
--     direct read of B's memberships          : 0 rows
--     core.memberships_for_subject(<B's sub>) : org  ='...B'
--                                               code ='...'
--                                               email='secret.person@competitor.example'
--                                               name ='Confidential B Person'
--
-- ⚠️ AND IT DISCLOSES MORE THAN THE ADDRESS: the NAME and CODE of every
-- organization that subject belongs to, which is a larger fact than the
-- email 052 was about. `principal_for_subject` answers the same way for
-- any (subject, organization) pair the caller can name.
--
-- ---------------------------------------------------------------------
-- 🔴 WHY NEITHER FUNCTION CAN SIMPLY CHECK ITS CALLER
-- ---------------------------------------------------------------------
--
-- Both take a subject as an ARGUMENT and neither can bind it to whoever
-- is asking, because both exist to answer BEFORE a session has an
-- organization -- there is nothing yet to compare against. That is not an
-- oversight in 024/033/045; it is the whole reason they are definers.
--
-- Three fixes were considered and two are decoration:
--
--   * "Require a GUC naming the verified subject." `evercoat_app` can SET
--     any GUC it likes, so an injected statement sets it too.
--   * "SET ROLE to a privileged role for the lookup." Anything that can
--     run SQL as `evercoat_app` can run the same SET ROLE. A misuse
--     barrier, not a boundary -- this repository already has that
--     distinction recorded about `AgentPrincipal`.
--   * A SEPARATE LOGIN ROLE, reachable only over a SEPARATE CONNECTION
--     whose credentials the application keeps apart from the runtime
--     pool. An injected statement on the runtime connection cannot reach
--     it, because privilege follows the connection and not the code.
--
-- Only the third is a mechanism. It is what this migration installs.
--
-- ---------------------------------------------------------------------
-- WHAT `evercoat_auth` MAY DO, WHICH IS ALMOST NOTHING
-- ---------------------------------------------------------------------
--
-- CONNECT, USAGE on `core`, and EXECUTE on exactly two functions. It
-- holds NO table privileges whatsoever -- it does not need any, because
-- both functions are SECURITY DEFINER owned by `evercoat_owner` and run
-- as that owner. A role that could also read tables would be a second
-- application role, which is the failure this migration would look like
-- if it were done carelessly. The probe below asserts the emptiness.
--
-- ⚠️ THE ROLE IS CREATED **NOLOGIN**, exactly as 001 creates the other
-- five. Granting LOGIN and a password is the deployment's job and differs
-- per environment (CI does it with `ALTER ROLE`, compose from `.env`).
-- A migration that baked in a password would put a credential in the
-- repository, and this project's history already has a rule about that.
--
-- ---------------------------------------------------------------------
-- 🔴 THIS MIGRATION FAILS CLOSED, AND THAT IS DELIBERATE
-- ---------------------------------------------------------------------
--
-- `evercoat_app` loses EXECUTE here. An environment that applies this
-- migration without configuring the auth connection cannot sign anybody
-- in -- it does not silently keep working with the old privilege, so
-- there is no half-applied state in which the fix reads as done and is
-- not. `/health/ready` reports the auth connection for the same reason,
-- so the failure surfaces as "not ready" rather than as 403 for every
-- user.
--
-- ⚠️ `authorization_for_current_session()` and
-- `bind_subject_to_organization()` STAY with `evercoat_app`, and that is
-- not an oversight. The first takes ZERO arguments and derives everything
-- from the session's own GUCs (ADR-030 chose that shape precisely so it
-- could not be aimed); the second proves the caller's standing before it
-- writes (050). Neither answers a question about a subject the caller
-- names. The probe asserts they are untouched, so a future revoke that
-- went too wide would be caught here rather than in production.
-- =====================================================================

BEGIN;

-- ---------------------------------------------------------------------
-- 1. The role. NOLOGIN, like every other role 001 creates.
-- ---------------------------------------------------------------------
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'evercoat_auth') THEN
        CREATE ROLE evercoat_auth NOLOGIN;
    END IF;
END
$$;

-- 🔴 NORMALISE THE ATTRIBUTES, BECAUSE `IF NOT EXISTS` MEANS THE ROLE MAY
--    ALREADY EXIST AND NOT BE WHAT THIS MIGRATION ASSUMES.
--
-- Raised by Codex. The block above is idempotent about EXISTENCE and said
-- nothing about CAPABILITY, so a role somebody had already created -- or one
-- left behind by an earlier downgrade -- kept whatever it had. This runs
-- unconditionally, so the end state is the same whether the role was created
-- here or found. `NOINHERIT` is the load-bearing one: without it a membership
-- in some group grants this role that group's privileges automatically, on a
-- connection that never sets a tenant GUC.
ALTER ROLE evercoat_auth
    NOSUPERUSER NOCREATEDB NOCREATEROLE NOBYPASSRLS NOREPLICATION NOINHERIT;

COMMENT ON ROLE evercoat_auth IS
    'Sign-in only (I109, migration 053). Holds EXECUTE on '
    'core.principal_for_subject and core.memberships_for_subject and '
    'NOTHING else -- no table privileges, because both functions are '
    'SECURITY DEFINER owned by evercoat_owner. It exists so that the two '
    'lookups which take a SUBJECT AS AN ARGUMENT, and therefore cannot '
    'check their caller, are unreachable from the runtime connection.';

-- CONNECT is per-database and the database name is not knowable at
-- authoring time, so it is formatted from `current_database()` rather
-- than hardcoded -- CI, compose and Render all use different names.
DO $$
BEGIN
    EXECUTE format(
        'GRANT CONNECT ON DATABASE %I TO evercoat_auth', current_database()
    );
END
$$;

GRANT USAGE ON SCHEMA core TO evercoat_auth;

-- ---------------------------------------------------------------------
-- 2. The two lookups move to it.
-- ---------------------------------------------------------------------
GRANT EXECUTE ON FUNCTION core.principal_for_subject(TEXT, UUID) TO evercoat_auth;
GRANT EXECUTE ON FUNCTION core.memberships_for_subject(TEXT)     TO evercoat_auth;

-- 🔴 AND THE RUNTIME ROLE LOSES THEM. This line is the migration.
--
-- Everything above is scaffolding; without this the capability is merely
-- duplicated. Measured before writing: `proacl` on both functions is
-- {evercoat_owner=X, evercoat_app=X} -- PUBLIC does NOT hold EXECUTE, so
-- this revoke is decisive rather than cosmetic. Had PUBLIC held it (the
-- DEFAULT for a new function, and the reason 045 revokes it explicitly)
-- this migration would have changed nothing at all while reading exactly
-- as it does now.
REVOKE EXECUTE ON FUNCTION core.principal_for_subject(TEXT, UUID) FROM evercoat_app;
REVOKE EXECUTE ON FUNCTION core.memberships_for_subject(TEXT)     FROM evercoat_app;

-- Belt and braces on the default, for both: a later `CREATE OR REPLACE`
-- keeps the ACL, but a `DROP` + `CREATE` resets it to PUBLIC EXECUTE, and
-- 045's header records that exact reset happening.
REVOKE ALL ON FUNCTION core.principal_for_subject(TEXT, UUID) FROM PUBLIC;
REVOKE ALL ON FUNCTION core.memberships_for_subject(TEXT)     FROM PUBLIC;

COMMENT ON FUNCTION core.principal_for_subject(TEXT, UUID) IS
    'Identity, roles and permissions for a verified Keycloak subject within '
    'one organization. SECURITY DEFINER because it must answer BEFORE the '
    'tenant GUC can be set. The email and display name come from the '
    'MEMBERSHIP (052). 🔴 EXECUTE belongs to evercoat_auth ONLY (053, I109): '
    'it takes a subject as an ARGUMENT and cannot check its caller, so on '
    'the runtime connection it was an identity-enumeration primitive.';

COMMENT ON FUNCTION core.memberships_for_subject(TEXT) IS
    'Organizations a verified Keycloak subject may act in, with the roles '
    'AND permissions held in each, and the MEMBERSHIP''s email and display '
    'name (052). SECURITY DEFINER because it must answer BEFORE an '
    'organization has been chosen. 🔴 EXECUTE belongs to evercoat_auth ONLY '
    '(053, I109): it discloses the NAME and CODE of every organization a '
    'named subject belongs to, and it cannot check its caller.';

COMMIT;


-- ---------------------------------------------------------------------
-- PROVE IT. Privileges, both directions, plus the emptiness of the role.
--
-- ⚠️ THIS PROBE SITS AFTER `COMMIT`, AND WHAT THAT MEANS DEPENDS ON HOW THE
-- FILE IS RUN. Raised by Codex as a partial-application risk, and MEASURED
-- rather than argued:
--
--   Under alembic -- the only path any environment actually uses --
--   `migrations_alembic/_sql.py` STRIPS every bare `BEGIN;`/`COMMIT;` line
--   and runs what is left inside alembic's own per-migration transaction.
--   So a probe failure rolls the whole migration back. Forced, by granting
--   `evercoat_auth` to `evercoat_app` so the first assertion had to fail:
--
--       alembic_version                     : k1000   (not stamped)
--       proacl on principal_for_subject     : {evercoat_owner=X, evercoat_app=X}
--
--   -- neither the GRANT to evercoat_auth nor the REVOKE from evercoat_app
--   survived. Atomic.
--
--   Applied standalone with `psql -f`, the COMMIT is real and a probe failure
--   would leave the privilege changes in place. That is true of every probe
--   in this directory (046, 052) and is the price of files that can also be
--   read and run by hand. **Apply migrations with alembic.**
-- ---------------------------------------------------------------------
DO $probe$
DECLARE
    v_tbl TEXT;
    v_priv TEXT;
BEGIN
    -- (1) The runtime role can no longer sign anybody in.
    IF has_function_privilege('evercoat_app', 'core.principal_for_subject(TEXT, UUID)', 'EXECUTE')
       OR has_function_privilege('evercoat_app', 'core.memberships_for_subject(TEXT)', 'EXECUTE')
    THEN
        RAISE EXCEPTION
            '053 FAILED: evercoat_app can still execute a sign-in lookup. '
            'Both take a subject as an argument and neither can check its '
            'caller, so on the runtime connection they enumerate identities '
            'and disclose every organization a subject belongs to (I109).';
    END IF;
    RAISE NOTICE '053: evercoat_app cannot execute either sign-in lookup';

    -- (2) ...and neither can PUBLIC, which is the DEFAULT for a function
    --     and would make (1) meaningless.
    IF has_function_privilege('public', 'core.principal_for_subject(TEXT, UUID)', 'EXECUTE')
       OR has_function_privilege('public', 'core.memberships_for_subject(TEXT)', 'EXECUTE')
    THEN
        RAISE EXCEPTION
            '053 FAILED: PUBLIC holds EXECUTE on a sign-in lookup, so '
            'revoking it from evercoat_app changed nothing.';
    END IF;
    RAISE NOTICE '053: PUBLIC holds no EXECUTE on either lookup';

    -- (3) THE CONTROL. Without it every assertion above is satisfied by a
    --     database in which nobody can sign in at all.
    IF NOT has_function_privilege('evercoat_auth', 'core.principal_for_subject(TEXT, UUID)', 'EXECUTE')
       OR NOT has_function_privilege('evercoat_auth', 'core.memberships_for_subject(TEXT)', 'EXECUTE')
    THEN
        RAISE EXCEPTION
            '053 FAILED: evercoat_auth cannot execute the sign-in lookups, '
            'so the capability was removed rather than moved and NOBODY can '
            'authenticate.';
    END IF;
    RAISE NOTICE '053: evercoat_auth can execute both lookups';

    -- (4) THE SECOND CONTROL, AND THE ONE A TOO-WIDE REVOKE WOULD TRIP.
    --     `authorization_for_current_session` takes zero arguments and
    --     `bind_subject_to_organization` proves standing, so neither is
    --     an enumeration primitive and both stay with the runtime role.
    IF NOT has_function_privilege(
              'evercoat_app', 'core.authorization_for_current_session()', 'EXECUTE')
       OR NOT has_function_privilege(
              'evercoat_app', 'core.bind_subject_to_organization(TEXT, TEXT, TEXT)', 'EXECUTE')
    THEN
        RAISE EXCEPTION
            '053 FAILED: evercoat_app lost EXECUTE on a function it must '
            'keep. The revoke was too wide: every permission check and '
            'every member invitation is now broken.';
    END IF;
    RAISE NOTICE '053: the session-scoped functions are untouched';

    -- (5) `evercoat_auth` IS NOT A SECOND APPLICATION ROLE.
    --     It needs no table privileges at all -- both functions run as
    --     their owner. Granting any would quietly turn a sign-in role
    --     into one that reads tenant data on an unscoped connection,
    --     which is a bigger hole than the one being closed.
    -- ⚠️ EVERY APPLICATION SCHEMA, NOT JUST `core`. The first version looked
    -- only at `core`, and Codex pointed out the hole: a pre-existing
    -- `evercoat_auth` that was a member of some group with SELECT on
    -- `projects` or `materials` would pass a core-only check and still read
    -- those tables on an unscoped connection. `NOINHERIT` above closes the
    -- membership route; this closes the direct-grant one, and asserts rather
    -- than trusting either.
    FOR v_tbl IN
        SELECT format('%I.%I', n.nspname, c.relname)
          FROM pg_class c
          JOIN pg_namespace n ON n.oid = c.relnamespace
         WHERE n.nspname NOT IN ('pg_catalog', 'information_schema')
           AND n.nspname NOT LIKE 'pg_toast%'
           AND c.relkind IN ('r', 'v', 'm', 'p')
    LOOP
        FOREACH v_priv IN ARRAY ARRAY['SELECT', 'INSERT', 'UPDATE', 'DELETE']
        LOOP
            IF has_table_privilege('evercoat_auth', v_tbl, v_priv) THEN
                RAISE EXCEPTION
                    '053 FAILED: evercoat_auth holds % on % -- it is a second '
                    'application role on a connection that never sets a tenant '
                    'GUC. It must hold EXECUTE on two functions and nothing '
                    'else.', v_priv, v_tbl;
            END IF;
        END LOOP;
    END LOOP;
    RAISE NOTICE '053: evercoat_auth holds no table privilege in any schema';

    -- (6) And it cannot log in until a deployment says so.
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'evercoat_auth' AND rolsuper) THEN
        RAISE EXCEPTION '053 FAILED: evercoat_auth is a SUPERUSER';
    END IF;
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'evercoat_auth' AND rolbypassrls) THEN
        RAISE EXCEPTION '053 FAILED: evercoat_auth has BYPASSRLS';
    END IF;
    RAISE NOTICE '053: evercoat_auth is neither superuser nor BYPASSRLS';
END $probe$;
