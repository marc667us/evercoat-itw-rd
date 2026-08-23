-- =====================================================================
-- 044 — the user directory is not a global directory
--
-- Closes I55, and closes a cross-tenant WRITE found while measuring it
-- (raised here as I80).
--
-- ---------------------------------------------------------------------
-- WHAT WAS WRONG — MEASURED, NOT ASSUMED
-- ---------------------------------------------------------------------
--
-- Migration 032 closed I19: `core.rls_permissive()` became FALSE, so every
-- policy collapsed to its real predicate and the database began to fail
-- closed with no tenant context. Measured today as `evercoat_app` with no
-- GUC set, that held:
--
--     SELECT count(*) FROM core.organization_members;   -->    0
--
-- But `core.users` had never had RLS enabled at all, so 032 did nothing for
-- it. Measured on the same connection, same absent GUC:
--
--     SELECT count(*) FROM core.users;                  -->  571
--     SELECT email FROM core.users LIMIT 3;
--         00cb698e@example.test
--         admin.demo@example.test
--         author00a99900@example.test
--
-- 571 rows. Every tenant. Email addresses and display names — personal data
-- belonging to organizations the connection had no context for. Tenant
-- *records* fail closed; the user *directory* did not, which qualifies the
-- claim 032's header makes and `SECURITY.md` §1 states.
--
-- 🔴 AND IT WAS NOT ONLY A READ. `app/api/admin.py`'s `invite_member` ran:
--
--     INSERT INTO core.users (keycloak_sub, email, display_name)
--     VALUES (:sub, :email, :name)
--     ON CONFLICT (keycloak_sub) DO UPDATE
--         SET display_name = EXCLUDED.display_name
--     RETURNING id
--
-- Executed as `evercoat_app` with organization A's GUC set, against a
-- `keycloak_sub` belonging to a user who is a member ONLY of organization B,
-- it returned:
--
--     id            54648e11-dcdc-4a05-84db-c928a4bee28c
--     email         owner-08f856f3@example.test      <-- B's real address
--     display_name  PWNED BY ORG A                   <-- overwritten
--
-- So an `admin.users` holder in any organization could rename a user in any
-- other organization, and the RETURNING handed back that user's real email
-- address even though the caller had supplied a different one. A read hole
-- and a write hole through the same statement. The write half is not fixed
-- by RLS alone — see the UPDATE policy and the route change below.
--
-- ---------------------------------------------------------------------
-- THE POLICY, AND THE THREE JUDGEMENTS INSIDE IT
-- ---------------------------------------------------------------------
--
-- A user is not owned by one organization. `core.users` has no
-- `organization_id` and must not grow one: the same human legitimately holds
-- membership in several organizations, and `core.principal_for_subject`
-- depends on that. So the predicate cannot be `organization_id = current`.
-- It is instead: **you may see a user if you share an organization with
-- them, or if they are you.**
--
-- 1. 🔴 THE MEMBERSHIP IS NOT FILTERED BY `status`, AND THAT IS DELIBERATE.
--    `core.organization_members.status` exists and is 'active' by default.
--    Requiring it here would mean that deactivating a member erases their
--    name from every record they ever touched: 21 queries in this codebase
--    join `core.users` to resolve an actor —
--    `projects/dashboard.py` (lead, director, assignee, transitioned_by),
--    `opportunities/service.py` (created_by, decided_by),
--    `messaging/service.py` (author), `tasks/service.py` (assignee),
--    `pipeline/service.py`, `projects/members.py` — and eleven of them are
--    INNER joins, so the *record itself* would disappear from the list, not
--    merely the name. A leaver would silently delete their own history.
--    That is the empty-panel failure this project has now shipped twice.
--    Visibility of a person's name is not the same control as their ability
--    to sign in, which is `status` and Keycloak's job.
--
-- 2. 🔴 THE `rls_permissive()` PREFIX IS NOT USED HERE, AND THAT IS ALSO
--    DELIBERATE. Every policy written before 032 carries
--    `(core.rls_permissive() AND core.current_org_id() IS NULL) OR ...`.
--    032 made that function FALSE, so the prefix is now dead weight that
--    remains only because rewriting 20+ policies by hand is a worse risk
--    than leaving them. Adding it to a NEW policy would re-create an
--    escape hatch this table never had, and one `CREATE OR REPLACE` back to
--    TRUE would re-open all 571 rows. It is omitted.
--
-- 3. THE SELF CLAUSE (`id = core.current_user_id()`) IS NOT REDUNDANT.
--    A signed-in caller always holds a membership in the organization they
--    selected, so in the ordinary case the EXISTS already admits them. The
--    clause matters at the edges the ordinary case does not cover: a caller
--    whose membership row is being changed in the same transaction, and any
--    future path that sets `app.current_user_id` before an organization is
--    chosen. A user being unable to read their own row is an outage, and it
--    would present as a 404 on `/api/me`, which is exactly how the
--    2026-08-19 sign-in defect presented.
--
-- ---------------------------------------------------------------------
-- WHY FORCE IS STILL NOT SET HERE
-- ---------------------------------------------------------------------
--
-- Same reasoning as 032, unchanged: `relforcerowsecurity` is FALSE on all
-- 59 tables and two tripwire tests assert it stays FALSE until the I58
-- cutover. `core.memberships_for_subject` and `core.principal_for_subject`
-- are SECURITY DEFINER owned by `evercoat_owner`, they read `core.users`,
-- and they run BEFORE an organization is chosen — by definition with no GUC.
-- They keep working here only because the owner is exempt from its own
-- policies while FORCE is off. Setting FORCE in this migration would return
-- zero rows from both and stop sign-in dead. I58 owns that cutover, and
-- `core.users` is now part of its scope.
--
-- ⚠️ `evercoat_worker` and `evercoat_report` hold SELECT on this table and
-- are not owners. From this migration on, either role reading `core.users`
-- without setting `app.current_org` sees ZERO rows rather than 571. That is
-- the intended direction — it fails closed — but it is a behaviour change
-- for any future job that assumed a global directory, and it will present
-- as an empty result, not an error.
-- =====================================================================

ALTER TABLE core.users ENABLE ROW LEVEL SECURITY;


-- ---------------------------------------------------------------------
-- READ
-- ---------------------------------------------------------------------
CREATE POLICY users_visible_within_a_shared_organization ON core.users
    FOR SELECT
    USING (
        id = core.current_user_id()
        OR EXISTS (
            SELECT 1
              FROM core.organization_members om
             WHERE om.user_id = core.users.id
               AND om.organization_id = core.current_org_id()
        )
    );

COMMENT ON POLICY users_visible_within_a_shared_organization ON core.users IS
    'I55. A user row is readable by the runtime role only if the reader '
    'shares an organization with that user, or is that user. Membership '
    'status is deliberately NOT consulted: a deactivated member must keep '
    'resolving as the actor on the records they created, or eleven INNER '
    'joins drop those records entirely.';


-- ---------------------------------------------------------------------
-- WRITE — and this half is what closes I80
-- ---------------------------------------------------------------------
--
-- INSERT admits any row. That is not an oversight and it is not a
-- disclosure: creating an identity row reveals nothing about any existing
-- one, and there is no tenant-shaped predicate available to check against
-- because the membership that would make the user visible is created by the
-- NEXT statement. What it does permit is an `admin.users` holder writing a
-- junk identity row. That is a directory-hygiene concern, not a
-- confidentiality one, and it is reachable only behind that permission.
--
-- ⚠️ The `keycloak_sub` UNIQUE constraint is enforced outside RLS, as all
-- unique constraints are. So an INSERT of a subject that already exists in
-- another organization raises a unique violation rather than succeeding —
-- which tells the caller that subject exists. That channel is inherent to a
-- globally-unique identifier and is not closed here; it is named so nobody
-- later mistakes it for a leak this migration introduced. It discloses
-- existence of a subject the caller already had to name exactly, and no
-- attribute of it.
CREATE POLICY users_identity_may_be_created ON core.users
    FOR INSERT
    WITH CHECK (true);

COMMENT ON POLICY users_identity_may_be_created ON core.users IS
    'Creating an identity row discloses nothing and has no tenant predicate '
    'available -- the membership that would satisfy one is written by the '
    'following statement. Reachable only behind admin.users.';


-- 🔴 WHAT THIS POLICY DOES AND DOES NOT DO — MEASURED, BECAUSE THE FIRST
-- VERSION OF THIS COMMENT CLAIMED A BOUNDARY IT DOES NOT HOLD.
--
-- It first read: *"UPDATE is where the measured cross-tenant write is closed
-- ... both are required."* That is FALSE. The full matrix was measured on
-- 2026-08-23 by replaying the exact `invite_member` upsert as `evercoat_app`
-- under organization A's GUC against organization B's subject:
--
--     SELECT policy | UPDATE policy | result
--     --------------+---------------+---------------------------------------
--     restrictive   | restrictive   | refused                (shipped state)
--     restrictive   | permissive    | refused
--     permissive    | restrictive   | refused (USING expression)
--     permissive    | permissive    | 'PWNED BY ORG A'       (the pre-044 hole)
--
-- Either policy alone refuses it, so neither is "required" — and with the
-- SELECT policy in place the UPDATE predicate is **not an independent
-- boundary at all**. A direct `UPDATE ... WHERE keycloak_sub = ...` was also
-- measured with the UPDATE policy made permissive: it still changed **0
-- rows**, silently, because PostgreSQL applies the SELECT policy to the rows
-- an UPDATE reads through its WHERE clause. The read policy is doing this
-- work.
--
-- So the honest statement of why this policy exists is narrower, and it is
-- two things:
--
--   1. WITHOUT ANY UPDATE POLICY, RLS DENIES EVERY UPDATE. `core.users` rows
--      must remain editable within an organization — display names change.
--      A table with RLS on and no UPDATE policy is not hardened, it is
--      read-only, and that is an outage rather than a control.
--   2. It carries the SAME predicate as the read policy so that it does not
--      silently become the weak link if the read policy is ever widened —
--      a directory search, an admin "find any user" screen, a reporting view.
--      The moment SELECT opens, this is the only thing standing between an
--      `admin.users` holder and another tenant's rows, and the measured
--      matrix row `permissive | restrictive` is exactly that case refusing.
--
-- That is defence in depth, stated as defence in depth. It is not the control
-- that closes I80 today; the read policy is.
CREATE POLICY users_updatable_within_a_shared_organization ON core.users
    FOR UPDATE
    USING (
        id = core.current_user_id()
        OR EXISTS (
            SELECT 1
              FROM core.organization_members om
             WHERE om.user_id = core.users.id
               AND om.organization_id = core.current_org_id()
        )
    )
    WITH CHECK (
        id = core.current_user_id()
        OR EXISTS (
            SELECT 1
              FROM core.organization_members om
             WHERE om.user_id = core.users.id
               AND om.organization_id = core.current_org_id()
        )
    );

COMMENT ON POLICY users_updatable_within_a_shared_organization ON core.users IS
    'Permits UPDATE within a shared organization -- without an UPDATE policy '
    'RLS denies every update and the directory becomes read-only. Its '
    'predicate is defence in depth, NOT the control that closes I80: measured '
    '2026-08-23, the read policy alone refuses the cross-tenant rename, and '
    'this predicate made permissive changes nothing. It matters only if the '
    'read policy is ever widened.';


-- ---------------------------------------------------------------------
-- THE BINDING LOOKUP — so multi-organization membership still works
-- ---------------------------------------------------------------------
--
-- With the read policy in place, an administrator inviting a human who
-- already has an account under a DIFFERENT organization can no longer see
-- that row, and cannot insert a duplicate because `keycloak_sub` is unique.
-- Without this function, `044` would silently make multi-organization
-- membership impossible — and multi-organization membership is the reason
-- `core.users` has no `organization_id` in the first place. Removing a
-- disclosure by removing a feature is not a fix.
--
-- So: one narrow lookup that resolves an EXACT subject to an id and returns
-- nothing else. No email, no display name, no status, no enumeration — the
-- caller must already know the exact subject string, and the unique
-- constraint already tells them whether it exists.
--
-- SECURITY DEFINER owned by `evercoat_owner`, matching the three definers
-- that already exist (`memberships_for_subject`, `principal_for_subject`,
-- `project_lead`). ⚠️ That ownership is I56/I58's subject, not this
-- migration's: I58's specification re-owners every definer to a dedicated
-- NOLOGIN role, and this one joins that list rather than inventing a fourth
-- ownership convention here.
CREATE OR REPLACE FUNCTION core.user_id_for_subject(p_subject TEXT)
    RETURNS UUID
    LANGUAGE sql
    STABLE
    SECURITY DEFINER
    SET search_path = core, pg_temp
AS $$
    SELECT id FROM core.users WHERE keycloak_sub = p_subject
$$;

REVOKE ALL ON FUNCTION core.user_id_for_subject(TEXT) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION core.user_id_for_subject(TEXT) TO evercoat_app;

COMMENT ON FUNCTION core.user_id_for_subject(TEXT) IS
    'Resolves an EXACT keycloak_sub to a user id and returns nothing else, so '
    'an administrator can bind an existing human to a second organization '
    'after 044 made the directory org-scoped. Returns no personal data and '
    'cannot enumerate: the caller must already hold the exact subject, whose '
    'existence the UNIQUE constraint discloses regardless. Definer ownership '
    'is in I58''s scope along with the other three.';


-- ---------------------------------------------------------------------
-- The migration proves its own effect rather than asserting it.
--
-- A migration that moves an authorization boundary and does not verify the
-- boundary moved is indistinguishable from one that silently did nothing.
-- 032 established this shape; the specific failure it guards against here is
-- a policy created against the wrong table, or RLS enabled with no policy at
-- all (which denies everything and would take sign-in with it).
-- ---------------------------------------------------------------------
DO $$
DECLARE
    v_rls      BOOLEAN;
    v_force    BOOLEAN;
    v_policies INT;
    v_visible  INT;
    v_total    INT;
    v_org      UUID;
BEGIN
    SELECT c.relrowsecurity, c.relforcerowsecurity
      INTO v_rls, v_force
      FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
     WHERE n.nspname = 'core' AND c.relname = 'users';

    IF NOT v_rls THEN
        RAISE EXCEPTION 'core.users still has RLS disabled after 044';
    END IF;

    -- 044 must NOT set FORCE. If it somehow did, sign-in is dead: both
    -- subject lookups run as the owner with no GUC.
    IF v_force THEN
        RAISE EXCEPTION
            'core.users has FORCE ROW LEVEL SECURITY after 044. That is I58''s '
            'cutover, and memberships_for_subject returns zero rows under it.';
    END IF;

    SELECT count(*) INTO v_policies
      FROM pg_policy WHERE polrelid = 'core.users'::regclass;
    IF v_policies <> 3 THEN
        RAISE EXCEPTION
            'core.users carries % policies after 044; expected exactly 3 '
            '(select, insert, update)', v_policies;
    END IF;

    -- The boundary itself, measured through the policy rather than described.
    -- Run as the owner this block cannot observe the restriction directly
    -- (the owner is exempt), so it asserts the shape a non-owner will see:
    -- one organization's membership must not cover the whole directory.
    SELECT count(*) INTO v_total FROM core.users;
    SELECT id INTO v_org FROM core.organizations ORDER BY created_at LIMIT 1;

    IF v_org IS NOT NULL THEN
        SELECT count(*) INTO v_visible
          FROM core.users u
         WHERE EXISTS (SELECT 1 FROM core.organization_members om
                        WHERE om.user_id = u.id AND om.organization_id = v_org);

        IF v_total > 0 AND v_visible >= v_total THEN
            RAISE WARNING
                'Every one of the % users in this database is a member of the '
                'first organization, so this database cannot demonstrate the '
                '044 boundary. Verify it against tests/db/test_044 instead.',
                v_total;
        ELSE
            RAISE NOTICE
                '044: one organization now sees % of % users.', v_visible, v_total;
        END IF;
    END IF;
END $$;
