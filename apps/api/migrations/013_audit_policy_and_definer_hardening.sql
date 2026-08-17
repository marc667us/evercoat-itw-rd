-- 013_audit_policy_and_definer_hardening.sql
-- =====================================================================
-- Three corrections to migration 011, from the Codex review of it.
-- Written as a new migration rather than by editing 011, because 011 has
-- been applied: rewriting an applied migration makes the file disagree
-- with every database that already ran it.
--
-- 1. THE INSERT POLICY WAS STILL FAIL-OPEN IN ONE DIRECTION.
--
--    011 replaced `WITH CHECK (true)` with:
--
--        organization_id IS NULL
--        OR core.current_org_id() IS NULL
--        OR organization_id = core.current_org_id()
--
--    That closed the case it set out to close -- a session scoped to org
--    A can no longer write a row attributed to org B. It left two open:
--
--      * `organization_id IS NULL` was unconditional, so ANY scoped
--        tenant session could write SYSTEM-chain rows. The system chain
--        is where platform actions are recorded; a tenant able to append
--        to it can manufacture platform history.
--
--      * `core.current_org_id() IS NULL` made any accidentally unscoped
--        connection trusted for EVERY organization. The whole point of
--        `MissingContextError` in app/core/db.py is that a request
--        reaching the database with no identity is a fault, not a
--        credential.
--
--    Tightened below to the two combinations that are actually
--    legitimate:
--
--      * unscoped session  -> system rows only (organization_id IS NULL)
--      * scoped session    -> its own organization's rows only
--
--    Verified safe before tightening, not after: every `write_audit()`
--    call site in app/ runs inside `session_scope()` with a principal, and
--    `unscoped_session_scope()` is used in exactly three places -- the
--    liveness probe, the readiness probe and principal resolution -- none
--    of which write audit rows. Migrations write as a superuser, which
--    bypasses RLS entirely and is unaffected.
--
-- 2. THE COMMENT ON chain_row() OVERCLAIMED.
--
--    011's comment said SECURITY DEFINER means the tail read "does not
--    depend on the caller's RLS context". That is true TODAY and only
--    because `audit.events` has RLS ENABLED but not FORCED, so the table
--    owner is exempt. Under `FORCE ROW LEVEL SECURITY` the owner is
--    subject to its own policies unless the role has BYPASSRLS.
--
--    A comment claiming a safety net that does not exist is worse than no
--    comment, because the next reader stops checking. Corrected below,
--    and the condition is already covered by a failing test:
--    tests/db/test_011_audit_chain_scope.py
--      ::test_the_force_rls_cutover_must_revisit_the_chain_trigger
--
-- 3. THE DEFINER search_path DID NOT NAME pg_temp.
--
--    PostgreSQL's own guidance for SECURITY DEFINER functions is to name
--    every schema explicitly and put `pg_temp` LAST, so a caller cannot
--    pre-create a temporary object that shadows a referenced one. No
--    exploit is available on a fresh PostgreSQL 16 database, where
--    `public` is not writable by default -- but this repository never
--    revokes CREATE on `public`, and a database upgraded from an older
--    major version keeps the old writable default.
--
--    `public` must stay in the path: pgcrypto installs `digest()` there,
--    and the hash chain stops working without it. Verified in the live
--    catalogue rather than assumed.
-- =====================================================================

BEGIN;

-- ---------------------------------------------------------------------
-- PART 1 — Fail-closed audit insert policy
-- ---------------------------------------------------------------------

DROP POLICY IF EXISTS audit_insert ON audit.events;
CREATE POLICY audit_insert ON audit.events
    FOR INSERT WITH CHECK (
        -- An unscoped writer -- a migration, a maintenance script, the
        -- bootstrap path -- may write SYSTEM rows and nothing else. It
        -- can no longer attribute an event to a tenant it has not
        -- identified itself as.
        (core.current_org_id() IS NULL AND organization_id IS NULL)
        -- A scoped session may write its own organization's rows, and
        -- may NOT write system rows: appending to the platform chain is
        -- not a tenant action.
        OR organization_id = core.current_org_id()
    );

COMMENT ON POLICY audit_insert ON audit.events IS
    'Fail-closed. Unscoped sessions may write only system rows '
    '(organization_id IS NULL); scoped sessions may write only their own '
    'organization''s rows and may not append to the system chain. '
    'Superusers bypass RLS and are unaffected.';

-- ---------------------------------------------------------------------
-- PART 2 — search_path hardening, and an honest comment
-- ---------------------------------------------------------------------
-- The body is unchanged from 011. Only the search_path and the comment
-- differ; it is restated in full because CREATE OR REPLACE FUNCTION
-- replaces the whole definition.

CREATE OR REPLACE FUNCTION audit.chain_row() RETURNS TRIGGER
    LANGUAGE plpgsql
    SECURITY DEFINER
    -- Every schema named explicitly, pg_temp LAST. `public` is required:
    -- pgcrypto's digest() lives there.
    SET search_path = pg_catalog, audit, public, pg_temp
    AS $$
DECLARE
    v_prev TEXT;
BEGIN
    PERFORM pg_advisory_xact_lock(
        hashtext('audit.events.chain'),
        hashtext(COALESCE(NEW.organization_id::TEXT, '<system>'))
    );

    SELECT row_hash INTO v_prev
    FROM audit.events
    WHERE organization_id IS NOT DISTINCT FROM NEW.organization_id
    ORDER BY id DESC
    LIMIT 1;

    NEW.prev_hash := COALESCE(v_prev, 'GENESIS');
    NEW.row_hash := encode(
        digest(
            NEW.prev_hash || '|' || audit.canonical_content(
                NEW.organization_id, NEW.user_id, NEW.role_code,
                NEW.action, NEW.entity_type, NEW.entity_id,
                NEW.previous_state, NEW.new_state, NEW.reason,
                NEW.occurred_at),
            'sha256'),
        'hex');
    RETURN NEW;
END
$$;

ALTER FUNCTION audit.chain_row() OWNER TO evercoat_owner;

COMMENT ON FUNCTION audit.chain_row() IS
    'BEFORE INSERT trigger for audit.events. Chains PER ORGANIZATION: '
    'prev_hash resolves against the last row with the same '
    'organization_id (NULL forming its own system chain). '
    'SECURITY DEFINER, owned by evercoat_owner. '
    'IMPORTANT: that makes the tail read independent of the caller ONLY '
    'while audit.events has RLS ENABLED but NOT FORCED, because an owner '
    'is exempt from a non-forced policy. Under FORCE ROW LEVEL SECURITY '
    'the owner becomes subject to its own policies and the tail read is '
    'filtered again, unless the owning role is granted BYPASSRLS. The '
    'FORCE cutover MUST revisit this function -- see '
    'tests/db/test_011_audit_chain_scope.py::'
    'test_the_force_rls_cutover_must_revisit_the_chain_trigger, which '
    'fails the moment the cutover lands.';

COMMIT;
