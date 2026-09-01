-- =====================================================================
-- 064 — AN ACCESS REQUEST BELONGS TO AN ORGANIZATION
-- =====================================================================
--
-- ---------------------------------------------------------------------
-- 🔴 WHY THIS EXISTS: A NAMED RISK IS NOT AN ENFORCED BOUNDARY.
-- ---------------------------------------------------------------------
--
-- Migration 059 created `public_intel.access_requests` with no
-- `organization_id`, no RLS and no tenant predicate, because an applicant
-- names no tenant — they do not know which organization they would be
-- joining. On 2026-09-01 the queue finally got its reader
-- (`GET /api/admin/access-requests`), and the first version of that route
-- gated on `admin.users` and wrote the exposure down as issue I113.
--
-- Codex refused it, correctly and in one sentence: *"the comment
-- acknowledges the breach but does not enforce a rule."* Every rule in this
-- system about cross-tenant reads is enforced twice — once in the query and
-- once by RLS — and a comment is neither. In a multi-organization
-- deployment an administrator of A could read the name, work address and
-- company of somebody who meant to apply to B.
--
-- So the request is given an owner at birth, and I113 is closed rather than
-- carried.
--
-- ---------------------------------------------------------------------
-- ⚠️ THE OWNER COMES FROM THE DEPLOYMENT, NOT FROM THE APPLICANT.
-- ---------------------------------------------------------------------
--
-- A public landing page belongs to one deployment, and that deployment
-- belongs to one organization. `Settings.public_landing_organization_id`
-- is how a deployment says so, and `POST /api/public/access-requests`
-- REFUSES with 503 when it is unset — because a form that accepts a
-- submission into a row nobody may ever read is worse than a form that says
-- it is unavailable. That is the same fail-closed rule ADR-032 applied to
-- the sign-in connection.
--
-- The column stays NULLABLE for exactly one reason: rows written before
-- this migration cannot be attributed to anyone. They are NOT readable by
-- any tenant — that is the point.
--
-- ⚠️ AND THERE IS NO ROUTE THAT COUNTS THEM. An earlier draft of this header
-- said "the route reports how many exist"; that route was written, found to
-- return 0 for every caller because the policy filters the rows before
-- `count(*)` sees them, and deleted before it shipped. Counting them is a
-- SUPERUSER query, and `TODO.md` carries it. Measured on this database at the
-- time of writing: **zero** such rows exist, so the case is theoretical here.
--
-- ---------------------------------------------------------------------
-- 🔴 RLS IS THE BACKSTOP, AND `evercoat_public` KEEPS INSERT AND ONLY INSERT.
-- ---------------------------------------------------------------------
--
-- The tenant predicate is in the route's SQL *and* in a policy, because
-- `CLAUDE.md` §6 requires the database to be an independent barrier and this
-- repository has twice found the application layer to be the only one that
-- was actually holding.
--
-- `evercoat_public` holds INSERT and no SELECT (059), so an anonymous caller
-- still cannot read the queue under any policy. Its INSERT policy is written
-- separately from the tenant SELECT policy precisely because the public role
-- has no organization GUC to satisfy — it is not a tenant, it is the public.
-- =====================================================================

BEGIN;

ALTER TABLE public_intel.access_requests
    ADD COLUMN IF NOT EXISTS organization_id UUID
        REFERENCES core.organizations (id) ON DELETE RESTRICT;

COMMENT ON COLUMN public_intel.access_requests.organization_id IS
    'The organization whose landing page took this request, from '
    'Settings.public_landing_organization_id. NULL only for rows written '
    'before migration 064; those are readable by nobody, deliberately.';

-- The reader asks "my organization''s undecided requests, newest first".
CREATE INDEX IF NOT EXISTS access_requests_org_status_idx
    ON public_intel.access_requests (organization_id, status, created_at DESC);

-- 🔴 `UNIQUE (id, organization_id)` — THE MANDATORY COLUMN OF THE TABLE-CREATION
-- CHECKLIST, AND THIS MIGRATION FORGOT IT.
--
-- `CLAUDE.md` §5: *"Every tenant-scoped table also declares
-- UNIQUE (id, organization_id). This is mandatory, not an optimisation."*
-- PostgreSQL requires a unique index on the REFERENCED columns, so without it
-- no future table can carry a composite `(access_request_id, organization_id)`
-- foreign key back to this one — and the documented reaction to that error
-- under time pressure is to drop the composite FK for a single-column one,
-- which silently reintroduces the cross-tenant reference the whole design
-- exists to prevent.
--
-- Adding `organization_id` to a table is what makes it tenant-scoped, so the
-- rule attached itself the moment this migration ran.
-- `test_every_tenant_table_has_composite_candidate_key` caught it — the guard
-- doing exactly its job on the first table to need it since 063.
--
-- ⚠️ NULLS ARE FINE HERE. A unique index treats NULLs as distinct, so the
-- pre-064 rows (organization_id IS NULL) do not collide with each other. The
-- key still does its job for every row that has an owner.
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
         WHERE conrelid = 'public_intel.access_requests'::regclass
           AND conname  = 'access_requests_id_org_key'
    ) THEN
        ALTER TABLE public_intel.access_requests
            ADD CONSTRAINT access_requests_id_org_key UNIQUE (id, organization_id);
    END IF;
END $$;

-- ---------------------------------------------------------------------
-- RLS
-- ---------------------------------------------------------------------
--
-- FORCE, so the owner is subject to it too. Every table born since 058 is
-- FORCE and mixing the two has already cost this project twice.
ALTER TABLE public_intel.access_requests ENABLE ROW LEVEL SECURITY;
ALTER TABLE public_intel.access_requests FORCE ROW LEVEL SECURITY;

-- 🔴 NO `TO <role>` ON THE TENANT POLICY, AND THE FIRST DRAFT HAD ONE.
--
-- It said `TO evercoat_app`, which under FORCE RLS locks `evercoat_owner` out
-- of the table completely: the owner is `NOBYPASSRLS` (001) and matches no
-- policy, so every SELECT returns nothing and every INSERT is refused. Both
-- reviewers found it independently — Codex's phrase for the class is exact,
-- and the Supervisor named the precedent: 032 and 033 already warn that *"a
-- migration that forces RLS must grant `evercoat_owner` BYPASSRLS or add a
-- policy that admits it"*.
--
-- It is also the 2026-08-31 lesson repeating, verbatim: *"A STRICTER POLICY IS
-- NOT A SAFER ONE. Mine omitted the branch every other tenant table carries,
-- and broke two suites."* Measured this time by the test suite before it
-- shipped, which is the only reason it is a paragraph rather than an incident.
--
-- Every other tenant policy in this schema is written with no `TO` clause, so
-- the PREDICATE governs every role: the owner acts by setting `app.current_org`
-- exactly as production does at `db.py:514` and as the fixtures now do.
--
-- ⚠️ A NULL `organization_id` MATCHES NOTHING. `NULL = anything` is NULL, which
-- a policy treats as false, so an unattributable row is refused to every tenant
-- by the predicate itself rather than by a second rule somebody must remember.
-- Reading those rows is a SUPERUSER act, not an owner one.
DROP POLICY IF EXISTS access_requests_org_scope ON public_intel.access_requests;
CREATE POLICY access_requests_org_scope ON public_intel.access_requests
    FOR ALL
    USING (organization_id = core.current_org_id())
    WITH CHECK (organization_id = core.current_org_id());

-- 🔴 THE PUBLIC ROLE IS THE ONE DELIBERATE `TO`, AND IT HAS TO BE.
--
-- `evercoat_public` is not a tenant: it never sets `app.current_org`, because
-- it has none. So it can never satisfy the predicate above, and admitting it
-- requires naming it. Permissive policies are OR-ed, so this adds an INSERT
-- path for the public role without widening anybody else's.
--
-- It carries a WITH CHECK and no USING, because there is no SELECT to govern —
-- 059 granted INSERT alone, and this policy must not be the thing that quietly
-- restores a read. The Alembic probe asserts that it did not.
DROP POLICY IF EXISTS access_requests_public_insert ON public_intel.access_requests;
CREATE POLICY access_requests_public_insert ON public_intel.access_requests
    FOR INSERT
    TO evercoat_public
    WITH CHECK (organization_id IS NOT NULL);

COMMIT;
