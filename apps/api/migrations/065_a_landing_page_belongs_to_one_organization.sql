-- =====================================================================
-- 065 — AN ORGANIZATION OPTS IN TO RECEIVING PUBLIC ACCESS REQUESTS
-- =====================================================================
--
-- ---------------------------------------------------------------------
-- 🔴 064 GAVE THE ROW AN OWNER AND LET THE PUBLIC ROLE CHOOSE IT.
-- ---------------------------------------------------------------------
--
-- 064's public INSERT policy is `WITH CHECK (organization_id IS NOT NULL)`.
-- Codex, on the second review pass:
--
--   *"Because permissive RLS policies are ORed, this bypasses the tenant
--   policy's current_org_id() check for public inserts. Anyone obtaining the
--   deliberately narrow public database credential can plant applicant
--   records into any known organization, undermining the new database-level
--   ownership boundary."*
--
-- That is correct. 064 closed the cross-tenant READ and left the cross-tenant
-- WRITE open — which is the same half-a-boundary shape this project has
-- closed before: a `USING` clause without a `WITH CHECK` filters reads and
-- permits writes the writer cannot then see.
--
-- ---------------------------------------------------------------------
-- WHAT THE DATABASE CAN ACTUALLY CHECK HERE
-- ---------------------------------------------------------------------
--
-- `evercoat_public` is not a tenant and never will be: it serves callers with
-- no identity, so it has no `app.current_org` to be checked against, and any
-- GUC it could set it could also lie about. So the predicate cannot ask "is
-- this the caller's organization". It can ask something better:
--
--   **is this an organization that has said it accepts public access requests?**
--
-- That is a property of the ORGANIZATION, set by a migration or an
-- administrator, and nothing the anonymous caller controls. With one opted-in
-- organization the public role can write to exactly one place; with none it
-- can write nowhere.
--
-- ⚠️ IT IS A NARROWING, NOT A PROOF OF IDENTITY. A credential holder can still
-- write into an opted-in organization's queue — that is what a public sign-up
-- form IS. What they can no longer do is reach an organization that never
-- offered a landing page. Stated plainly rather than overclaimed.
--
-- ---------------------------------------------------------------------
-- WHY A SECURITY DEFINER FUNCTION AND NOT A JOIN IN THE POLICY
-- ---------------------------------------------------------------------
--
-- A policy predicate is evaluated with the CALLER's privileges, so a direct
-- `EXISTS (SELECT 1 FROM core.organizations ...)` would require granting
-- `evercoat_public` SELECT on `core.organizations` — handing the anonymous
-- role a readable list of every tenant in order to stop it writing to them.
-- The definer function answers one boolean about one id and grants nothing.
--
-- ⚠️ POSTGRES GRANTS EXECUTE TO `PUBLIC` ON NEW FUNCTIONS BY DEFAULT, which
-- this repository treats as a live vulnerability (027:110, 053:148). The
-- REVOKE below is therefore not decoration, and the probe asserts the
-- resulting privilege rather than the statement.
-- =====================================================================

BEGIN;

ALTER TABLE core.organizations
    ADD COLUMN IF NOT EXISTS accepts_public_access_requests BOOLEAN NOT NULL DEFAULT false;

COMMENT ON COLUMN core.organizations.accepts_public_access_requests IS
    'Whether this organization publishes a public landing page that may take '
    'access requests. Read by the RLS policy on '
    'public_intel.access_requests; false by default, so a new organization is '
    'not reachable by the anonymous role until somebody says so.';

CREATE OR REPLACE FUNCTION core.accepts_public_access_requests(org UUID)
RETURNS BOOLEAN
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path = pg_catalog, core
AS $$
    SELECT EXISTS (
        SELECT 1 FROM core.organizations o
         WHERE o.id = org
           AND o.accepts_public_access_requests
    );
$$;

COMMENT ON FUNCTION core.accepts_public_access_requests(UUID) IS
    'Answers one boolean about one organization so the public INSERT policy '
    'can be written without granting evercoat_public SELECT on '
    'core.organizations.';

ALTER FUNCTION core.accepts_public_access_requests(UUID) OWNER TO evercoat_owner;
REVOKE ALL ON FUNCTION core.accepts_public_access_requests(UUID) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION core.accepts_public_access_requests(UUID) TO evercoat_public;
GRANT EXECUTE ON FUNCTION core.accepts_public_access_requests(UUID) TO evercoat_app;

-- The narrowed public write.
DROP POLICY IF EXISTS access_requests_public_insert ON public_intel.access_requests;
CREATE POLICY access_requests_public_insert ON public_intel.access_requests
    FOR INSERT
    TO evercoat_public
    WITH CHECK (
        organization_id IS NOT NULL
        AND core.accepts_public_access_requests(organization_id)
    );

COMMIT;
