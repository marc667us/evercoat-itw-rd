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
-- Verify by INSPECTING THE POLICY, never by writing.
--
-- 🔴 THIS BLOCK USED TO SEED TWO PROBE ROWS AND READ THEM BACK UNDER
-- `SET LOCAL ROLE evercoat_app`. Codex refused it, and was right: `audit.events`
-- is append-only by trigger, so those rows COULD NOT BE DELETED -- verified,
-- `DELETE` raises *"audit.events is append-only"*. A security migration was
-- writing permanent fake history into the one table whose entire purpose is to
-- be trustworthy about who did what, including a tenant row bearing an
-- organization id that exists nowhere.
--
-- The behavioural check now lives in
-- `tests/db/test_034_system_audit_chain_readable.py`, where the transaction
-- rolls back and nothing survives. What remains here is a catalog assertion,
-- which is the only kind of verification a migration against an immutable
-- ledger may safely perform.
-- ---------------------------------------------------------------------
DO $$
DECLARE
    v_qual TEXT;
BEGIN
    SELECT pg_get_expr(polqual, polrelid) INTO v_qual
      FROM pg_policy
     WHERE polrelid = 'audit.events'::regclass
       AND polname  = 'audit_org_isolation';

    IF v_qual IS NULL THEN
        RAISE EXCEPTION 'audit_org_isolation policy is missing after 034';
    END IF;

    -- The NULL-safe operator is the whole point of this migration. `=` would
    -- leave the platform's own writer unable to read the system chain, which
    -- breaks the WRITE, because INSERT ... RETURNING is a read.
    --
    -- ⚠️ MATCH THE NORMALISED FORM. PostgreSQL rewrites `a IS NOT DISTINCT
    -- FROM b` as `NOT (a IS DISTINCT FROM b)` before storing it, so searching
    -- pg_get_expr() for the literal source text finds nothing and this check
    -- would fail on every fresh database while the policy was perfectly
    -- correct. Caught by running it; the first version of this block searched
    -- for the text as written in the CREATE POLICY above.
    IF v_qual NOT ILIKE '%IS DISTINCT FROM%' THEN
        RAISE EXCEPTION
            'audit_org_isolation is not NULL-safe (%). An unscoped session '
            'cannot read the system chain, so INSERT ... RETURNING fails for '
            'migrations and maintenance scripts.', v_qual;
    END IF;

    -- And it must NOT have kept the permissive escape hatch, or 034 would
    -- have quietly reopened what 032 closed.
    IF v_qual ILIKE '%rls_permissive%' THEN
        RAISE EXCEPTION
            'audit_org_isolation still references core.rls_permissive() (%). '
            '034 was meant to REPLACE the permissive branch, not keep it.',
            v_qual;
    END IF;
END $$;
