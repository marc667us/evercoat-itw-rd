-- =====================================================================
-- 034 — the system audit chain is readable by the session that writes it
--
-- Third and last companion to 032. Found by running the suite, not by
-- reading the code.
--
-- ---------------------------------------------------------------------
-- WHAT 032 BROKE
-- ---------------------------------------------------------------------
--
-- `audit.events` carries a legitimate SYSTEM chain: rows with
-- `organization_id IS NULL`, written by migrations, maintenance scripts and
-- the bootstrap path. Migration 013 deliberately protected it — a tenant
-- session may not append to it, or a tenant could manufacture platform
-- history.
--
-- The read policy was the standard shape:
--
--     USING (core.rls_permissive() AND core.current_org_id() IS NULL
--            OR organization_id = core.current_org_id())
--
-- With `rls_permissive()` now FALSE, an unscoped session evaluates
-- `organization_id = NULL`, which is NULL, which is not TRUE. **So the
-- platform's own writer can no longer read the system chain at all — not even
-- the row it just wrote.**
--
-- 🔴 AND THAT BREAKS THE WRITE, NOT ONLY THE READ, BECAUSE
-- `INSERT ... RETURNING` IS A READ.
--
-- This platform has logged that exact lesson before (2026-08-19: *"an
-- anonymous writer cannot SELECT its row back, so RETURNING fails"*). Here it
-- resurfaced one layer down: `test_an_unscoped_session_may_still_write_system
-- _rows` inserts with `RETURNING id`, and the INSERT is permitted by the
-- WITH CHECK policy while the RETURNING is refused by the USING policy. The
-- write succeeds and the statement fails.
--
-- ---------------------------------------------------------------------
-- THE FIX, AND WHY IT IS STRICTLY BETTER THAN WHAT CAME BEFORE
-- ---------------------------------------------------------------------
--
-- `organization_id IS NOT DISTINCT FROM core.current_org_id()`
--
-- `IS NOT DISTINCT FROM` is NULL-safe equality, so:
--
--   * scoped to org A  -> exactly org A's rows. NULL-organization system rows
--                         are NOT visible. (`=` behaved this way too.)
--   * unscoped         -> exactly the system rows. **Not every row.**
--
-- Compare the three states honestly:
--
--   before 032   unscoped saw EVERY tenant's audit rows        (the hole)
--   after 032    unscoped saw NOTHING, incl. rows it wrote     (the outage)
--   after 034    unscoped sees exactly the system chain        (correct)
--
-- So this does not reopen anything. An unscoped session gains access to
-- precisely the chain it is already permitted to WRITE by 013's WITH CHECK
-- policy, and to nothing else. Read and write authority now agree, which is
-- what they should always have done — a policy that lets a session write rows
-- it cannot read is a policy that will produce a confusing outage eventually.
--
-- ⚠️ SCOPE: this is applied to `audit.events` ONLY, because it is the only
-- table where a NULL organization is a MEANINGFUL, deliberately-supported
-- value rather than the absence of context. Do not sweep this pattern across
-- other tables: elsewhere `organization_id` is NOT NULL, so `IS NOT DISTINCT
-- FROM` and `=` are identical for real rows, and applying it would only add
-- noise and invite the belief that unscoped access is normal.
-- =====================================================================

BEGIN;

DROP POLICY IF EXISTS audit_org_isolation ON audit.events;
CREATE POLICY audit_org_isolation ON audit.events
    -- NULL-safe on purpose. See the header: a scoped session sees its own
    -- tenant; an unscoped session sees the system chain and nothing else.
    USING (organization_id IS NOT DISTINCT FROM core.current_org_id());

COMMIT;


-- ---------------------------------------------------------------------
-- Prove the boundary rather than assert it.
--
-- Written as a SET ROLE experiment because the property is about what the
-- RUNTIME role can see, and the migration runs as a role that is exempt.
-- ---------------------------------------------------------------------
DO $$
DECLARE
    v_org        UUID := gen_random_uuid();
    v_sys_seen   INT;
    v_other_seen INT;
BEGIN
    -- Seed one system row and one tenant row, as the exempt migration role.
    INSERT INTO audit.events (organization_id, action, entity_type, entity_id,
                              prev_hash, row_hash)
    VALUES (NULL,  'migration.034_probe', 'probe', 'system', '', ''),
           (v_org, 'migration.034_probe', 'probe', 'tenant', '', '');

    -- Unscoped runtime session: must see system rows, and no tenant row.
    SET LOCAL ROLE evercoat_app;
    PERFORM set_config('app.current_org', '', true);

    SELECT count(*) INTO v_sys_seen
      FROM audit.events
     WHERE action = 'migration.034_probe' AND organization_id IS NULL;

    SELECT count(*) INTO v_other_seen
      FROM audit.events
     WHERE action = 'migration.034_probe' AND organization_id IS NOT NULL;

    RESET ROLE;

    IF v_sys_seen = 0 THEN
        RAISE EXCEPTION
            'an unscoped runtime session still cannot read the system audit '
            'chain; INSERT ... RETURNING will keep failing for the platform''s '
            'own writer';
    END IF;

    IF v_other_seen > 0 THEN
        RAISE EXCEPTION
            'an unscoped runtime session can read % tenant-owned audit row(s). '
            '034 was meant to admit ONLY the system chain -- this is the hole '
            '032 closed, reopened.', v_other_seen;
    END IF;
END $$;
