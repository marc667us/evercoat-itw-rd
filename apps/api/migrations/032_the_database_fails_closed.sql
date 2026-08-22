-- =====================================================================
-- 032 — the database fails closed when no tenant context is set
--
-- Closes I19. Approved by the operator 2026-08-22 alongside the
-- IMPLEMENTATION_PLAN_EXTENSION, where it is a hard prerequisite of the
-- Research Center (E6) because that slice is the first to aggregate across
-- projects, and shipping it over an open database would put the highest-value
-- aggregation surface in the product behind a single layer.
--
-- ---------------------------------------------------------------------
-- WHAT WAS WRONG
-- ---------------------------------------------------------------------
--
-- Every RLS policy in this database is written:
--
--     USING (core.rls_permissive() AND core.current_org_id() IS NULL
--            OR <the real predicate>)
--
-- and `core.rls_permissive()` was `SELECT TRUE`. So whenever the
-- `app.current_org` GUC was absent, the left branch was TRUE and the policy
-- admitted every row in the table.
--
-- MEASURED 2026-08-22, connected as `evercoat_app` with no GUC set:
--
--     SELECT count(*) FROM core.organizations;   -->  119
--     SELECT count(*) FROM projects.projects;    -->  137
--
-- That is the entire database, every tenant. `SECURITY.md` §1 claims that any
-- ONE layer failing must not expose data; while this function returned TRUE
-- the claim was false, because the sole thing preventing a cross-tenant read
-- was `session_scope()` raising in Python. One code path reaching a connection
-- without setting the GUC — a worker, a health probe, a background job, a
-- future route, an exception handler — read everything.
--
-- ---------------------------------------------------------------------
-- WHAT THIS CHANGES, AND WHAT IT DELIBERATELY DOES NOT
-- ---------------------------------------------------------------------
--
-- `core.rls_permissive()` now returns FALSE. The left branch collapses, and
-- each policy reduces to its real predicate. With no GUC, `current_org_id()`
-- is NULL, `organization_id = NULL` is NULL, and NULL is not TRUE — so no row
-- is admitted. **Fail closed.**
--
-- 🔴 THIS MIGRATION DOES NOT ENABLE `FORCE ROW LEVEL SECURITY`, AND THAT IS
-- THE WHOLE REASON IT IS SAFE TO APPLY TODAY.
--
-- Measured: 53 of 59 tables have RLS enabled and **0** have FORCE, and every
-- table is owned by `evercoat_owner`. A table owner is exempt from its own
-- policies unless FORCE is set. Three things depend on that exemption right
-- now, and all three keep working:
--
--   1. Migrations and their backfills, which run as the owner with no GUC.
--   2. `scripts/seed.py`, which connects as the superuser.
--   3. 🔴 `core.memberships_for_subject` — SECURITY DEFINER, **owned by
--      `evercoat_owner`** (verified: `pg_proc.proowner`). It is the one
--      lookup that runs BEFORE a tenant is chosen, because it is what tells a
--      signed-in browser which organizations it may ask for. It runs with no
--      GUC by definition.
--
-- Item 3 is why the two halves of the cutover are separated here.
-- `tests/db/test_024_memberships_for_subject.py` was written by a previous
-- session as a deliberate tripwire, and its docstring is exactly right: the
-- moment FORCE is enabled *and* this function returns FALSE,
-- `memberships_for_subject` returns zero rows, `GET /api/me` answers 404 for
-- every legitimate user, and **sign-in stops working entirely**.
--
-- That tripwire is not being defused. It is being narrowed to the half that
-- still bites. Enabling FORCE remains a separate migration that must, in the
-- same change, either grant `evercoat_owner` BYPASSRLS or add a policy
-- admitting this one lookup — and must prove sign-in still works afterwards.
-- Doing both halves at once is how a security improvement becomes an outage.
--
-- ---------------------------------------------------------------------
-- WHY THE FUNCTION SURVIVES AT ALL RATHER THAN THE POLICIES BEING REWRITTEN
-- ---------------------------------------------------------------------
--
-- It would be tidier to delete the `rls_permissive() AND ... IS NULL OR`
-- prefix from all 20+ policies. It would also be a far larger diff across
-- eight migrations, every line of which is a chance to weaken a predicate by
-- hand. Keeping the function and changing its single return value makes the
-- cutover one reviewable line with one behaviour, and leaves the escape hatch
-- reinstatable in an emergency by an owner who understands what it opens.
-- =====================================================================

CREATE OR REPLACE FUNCTION core.rls_permissive() RETURNS BOOLEAN
    LANGUAGE sql IMMUTABLE AS $$ SELECT FALSE $$;

COMMENT ON FUNCTION core.rls_permissive() IS
    'FALSE since migration 032 (I19). Returns whether RLS policies should '
    'admit rows when no app.current_org GUC is set. It returned TRUE as '
    'scaffolding, which meant the database admitted every tenant''s rows to '
    'the runtime role whenever tenant context was absent -- 119 organizations '
    'and 137 projects when measured on 2026-08-22. Do not set this back to '
    'TRUE to make a test or a job pass: the correct fix is to set the GUC, or '
    'to run that work as evercoat_owner, which is exempt because it owns the '
    'tables and FORCE ROW LEVEL SECURITY is not enabled.';


-- ---------------------------------------------------------------------
-- The migration proves its own effect rather than asserting it.
--
-- A migration that changes an authorization boundary and does not verify the
-- boundary moved is indistinguishable from one that silently did nothing --
-- and `CREATE OR REPLACE FUNCTION` on a mistyped signature would create a
-- second overload and leave the original in place, which is precisely such a
-- case.
-- ---------------------------------------------------------------------
DO $$
DECLARE
    v_permissive BOOLEAN;
    v_overloads  INT;
    v_forced     INT;
BEGIN
    SELECT core.rls_permissive() INTO v_permissive;
    IF v_permissive IS DISTINCT FROM FALSE THEN
        RAISE EXCEPTION
            'core.rls_permissive() returned % after 032; it must be FALSE',
            v_permissive;
    END IF;

    -- One function, not two. An accidental overload would leave policies
    -- resolving to whichever signature matched, which is the failure this
    -- check exists to make impossible.
    SELECT count(*) INTO v_overloads
      FROM pg_proc p
      JOIN pg_namespace n ON n.oid = p.pronamespace
     WHERE n.nspname = 'core' AND p.proname = 'rls_permissive';
    IF v_overloads <> 1 THEN
        RAISE EXCEPTION
            'core.rls_permissive() has % definitions; expected exactly 1',
            v_overloads;
    END IF;

    -- Assert the OTHER half of the cutover has NOT happened, because this
    -- migration's safety argument depends on the owner still being exempt.
    -- If a later migration enables FORCE, this one's reasoning no longer
    -- holds and whoever wrote it must have handled memberships_for_subject.
    SELECT count(*) INTO v_forced
      FROM pg_class c
      JOIN pg_namespace n ON n.oid = c.relnamespace
     WHERE c.relkind = 'r'
       AND c.relforcerowsecurity
       AND n.nspname NOT IN ('pg_catalog', 'information_schema');
    IF v_forced > 0 THEN
        RAISE WARNING
            'FORCE ROW LEVEL SECURITY is on for % table(s). 032 assumed the '
            'owner exemption still applied. Verify core.memberships_for_subject '
            'still returns rows, or sign-in is dead.', v_forced;
    END IF;
END $$;
