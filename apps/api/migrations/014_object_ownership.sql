-- 014_object_ownership.sql
-- =====================================================================
-- Every table and sequence in the application schemas is owned by
-- `evercoat_owner`, as ADR-017 already says they are.
--
-- HOW THIS WAS FOUND. The first CI run that ever executed reported
-- `37 failed, 65 passed, 50 errors`, every one of them
-- `permission denied for table tasks|opportunities|stage_definitions`,
-- against a suite that passes 152/0/0 on the developer machine. The
-- interesting part is not the failure; it is that both databases were
-- built from the same thirteen migrations and ended up with different
-- ownership.
--
--   local  every table and sequence in core/innovation/projects/workflow
--          and audit is owned by evercoat_owner
--   CI     tables are owned by `postgres`, and `evercoat_owner` -- which
--          the tenancy tests connect AS, so that RLS is actually
--          exercised instead of being bypassed by a superuser -- holds no
--          privilege on innovation or workflow at all
--
-- Neither state was produced by a migration. Migration 001 declares
-- `CREATE SCHEMA ... AUTHORIZATION evercoat_owner` for all sixteen
-- schemas and `migrations_alembic/env.py` states that migrations run as
-- the owner role -- but 001 must CREATE ROLE, which needs a superuser, so
-- in practice alembic is run as `postgres` everywhere. Tables therefore
-- belong to `postgres` and the declared ownership model was never true of
-- a single object.
--
-- The local database looked correct because it had been repaired by hand
-- at some point. CI repaired a DIFFERENT SUBSET in its own workflow file
-- (`core, projects, audit` -- not `innovation`, not `workflow`). Two
-- hand-maintained lists, in two files, that nothing can check against each
-- other: the same shape as this platform's recurring nav-vs-router and
-- release-vs-deploy defects. So the fix is not to extend the CI list. It
-- is to make the migration the single thing that decides ownership, and
-- to assert the result in a test.
--
-- WHY TABLES AND SEQUENCES, AND NOT FUNCTIONS
-- -------------------------------------------
-- Measured, not assumed. On the reference database exactly one function
-- is owned by evercoat_owner -- `audit.chain_row`, which migration 013
-- moved there deliberately, because a SECURITY DEFINER function executes
-- with the privileges of ITS OWNER and that is the whole mechanism by
-- which the audit chain can read its own tail. The remaining functions,
-- including the other SECURITY DEFINER one (`core.is_project_member`),
-- are owned by `postgres`.
--
-- Sweeping functions would therefore silently re-point the privileges of
-- every SECURITY DEFINER function in the schema -- a change to what the
-- audit trigger and the RLS helper are ALLOWED to do, disguised as
-- tidying. Ownership of a definer function is a security decision and
-- belongs in the migration that reasons about it. This one does not touch
-- functions.
--
-- `public` is excluded as well: it holds `alembic_version`, which belongs
-- to whoever runs the migrations and must keep belonging to them.
--
-- IDEMPOTENT AND RE-RUNNABLE. On a database that is already correct this
-- changes nothing, which is the case on the developer machine.
--
-- LOCKING -- read before running this against a database with traffic.
-- `ALTER TABLE ... OWNER TO` takes an ACCESS EXCLUSIVE lock, and this
-- sweep takes one per object inside a single transaction, holding them all
-- until COMMIT. On an idle or pre-launch database that is instant. On a
-- live one it blocks every reader and writer for the duration and will
-- queue behind any long-running query, so run it in a maintenance window
-- with a `lock_timeout` set. Nothing is deployed today, which is why it is
-- written as one transaction: partial ownership is worse than none.
-- =====================================================================

BEGIN;

-- WHAT THIS DOES TO RLS, STATED PLAINLY
-- -------------------------------------
-- An earlier draft of this file claimed the owner "remains subject to the
-- policies under FORCE RLS". That was measured and it is FALSE today:
-- `relforcerowsecurity` is `f` on all eighteen tables. Migration 001 defers
-- FORCE deliberately (see its header) until a cutover migration, so a table
-- OWNER is currently EXEMPT from every policy on it.
--
-- So this migration does hand `evercoat_owner` an RLS bypass. Three things
-- make that the right trade rather than a hole:
--
--   * The RUNTIME role is unaffected. `evercoat_app` does not own these
--     tables and is fully subject to the policies. Production connects as
--     `evercoat_app`; nothing about what the application can see changes.
--   * It is not a regression. The reference development database has had
--     evercoat_owner as table owner all along -- that is the state this
--     migration reproduces. CI's alternative was not "RLS enforced for the
--     owner", it was `permission denied` and fifty errors.
--   * The suite already accounts for it. `tests/db/conftest.py` requires
--     isolation assertions to run on `app_session`; `owner_session` builds
--     fixtures and deliberately plays the attacker with direct database
--     access.
--
-- When the FORCE cutover lands, ownership stops conferring exemption and
-- this becomes moot. `tests/db/test_011_audit_chain_scope.py` holds the
-- tripwire that fires when that happens.

DO $$
DECLARE
    r RECORD;
    moved INT := 0;
BEGIN
    -- If the role does not exist the reassignment cannot be meaningful,
    -- and a bare ALTER would fail with a message about a missing role
    -- rather than about a broken migration order. 001 creates it.
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'evercoat_owner') THEN
        RAISE EXCEPTION
            'evercoat_owner does not exist; migration 001 must run before 014';
    END IF;

    -- PREFLIGHT: can this role actually give objects away?
    --
    -- `ALTER ... OWNER TO` requires the caller to be a superuser, or to be
    -- a member of the target role AND own the object. On a managed host the
    -- migration role is typically NEITHER a superuser NOR a member of
    -- evercoat_owner, and the sweep would then die partway through with
    -- "must be owner of table X" -- a message that describes the symptom
    -- and not the cause.
    --
    -- Failing here instead names the requirement. This is the same class of
    -- deployment constraint already recorded for migration 011 in TODO.md:
    -- a non-superuser deployment needs an owner-capable migration role.
    IF NOT (SELECT rolsuper FROM pg_roles WHERE rolname = current_user)
       AND NOT pg_has_role(current_user, 'evercoat_owner', 'MEMBER') THEN
        RAISE EXCEPTION
            'role % can neither bypass ownership checks nor act as evercoat_owner; '
            'run migrations as a superuser or GRANT evercoat_owner TO %',
            current_user, current_user;
    END IF;

    FOR r IN
        SELECT n.nspname AS schema_name,
               c.relname AS object_name,
               c.relkind AS kind
        FROM pg_class c
        JOIN pg_namespace n ON n.oid = c.relnamespace
        WHERE n.nspname IN (
                  'core', 'innovation', 'projects', 'materials',
                  'formulations', 'laboratory', 'testing', 'workflow',
                  'quality', 'products', 'knowledge', 'messaging',
                  'analytics', 'modeling', 'ai', 'audit'
              )
          -- r ordinary table, p partitioned table, S sequence,
          -- v view, m materialized view. Indexes ('i') follow their
          -- table's ownership automatically and cannot be altered
          -- independently; TOAST tables likewise.
          AND c.relkind IN ('r', 'p', 'S', 'v', 'm')
          AND pg_get_userbyid(c.relowner) <> 'evercoat_owner'
        ORDER BY n.nspname, c.relname
    LOOP
        IF r.kind = 'S' THEN
            EXECUTE format('ALTER SEQUENCE %I.%I OWNER TO evercoat_owner',
                           r.schema_name, r.object_name);
        ELSIF r.kind = 'v' THEN
            EXECUTE format('ALTER VIEW %I.%I OWNER TO evercoat_owner',
                           r.schema_name, r.object_name);
        ELSIF r.kind = 'm' THEN
            EXECUTE format('ALTER MATERIALIZED VIEW %I.%I OWNER TO evercoat_owner',
                           r.schema_name, r.object_name);
        ELSE
            EXECUTE format('ALTER TABLE %I.%I OWNER TO evercoat_owner',
                           r.schema_name, r.object_name);
        END IF;
        moved := moved + 1;
    END LOOP;

    RAISE NOTICE '014: reassigned % object(s) to evercoat_owner', moved;
END
$$;


-- ---------------------------------------------------------------------
-- The runtime role's grants, restated
-- ---------------------------------------------------------------------
-- Changing an object's owner rewrites its ACL: PostgreSQL re-attributes
-- the grantor of existing entries, so the grants made in 001 and 003
-- survive this. They are restated anyway, for two reasons.
--
-- First, `GRANT ... ON ALL TABLES IN SCHEMA` only ever covered the tables
-- that existed at the moment it ran, and 011-013 have run since.
--
-- Second, the DEFAULT PRIVILEGES declared in 001 and 003 are recorded
-- `FOR ROLE evercoat_owner` -- they apply to objects that evercoat_owner
-- CREATES. Since alembic actually runs as postgres, no object has ever
-- been created by evercoat_owner and those defaults have never once
-- applied. That is why they are not load-bearing here and the grants are
-- explicit.
--
-- DELETE is deliberately absent: the runtime role does not delete rows in
-- these schemas, and the audit tables refuse mutation by trigger.
GRANT USAGE ON SCHEMA core, innovation, projects, workflow, audit
    TO evercoat_app, evercoat_worker, evercoat_report;

GRANT SELECT, INSERT, UPDATE ON ALL TABLES IN SCHEMA core, innovation, projects, workflow
    TO evercoat_app;
GRANT SELECT ON ALL TABLES IN SCHEMA core, innovation, projects, workflow
    TO evercoat_worker, evercoat_report;

GRANT INSERT, SELECT ON audit.events TO evercoat_app, evercoat_worker;
GRANT SELECT ON audit.events TO evercoat_report;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA audit
    TO evercoat_app, evercoat_worker;

COMMIT;
