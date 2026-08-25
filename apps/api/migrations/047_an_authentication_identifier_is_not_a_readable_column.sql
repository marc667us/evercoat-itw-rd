-- =====================================================================
-- 047 — an authentication identifier is not a readable column,
--       and a guard's tenant scope must be its own predicate
--
-- Closes I81. Hardens 046 against a defect found while measuring I82.
--
-- ---------------------------------------------------------------------
-- PART 1 — I81: THE ROW CARRIES MORE THAN THE JUSTIFICATION NEEDS
-- ---------------------------------------------------------------------
--
-- 044's read policy admits a user when the reader shares an organization
-- with them, with no `status` filter — deliberately, because eleven INNER
-- joins resolve an actor through `core.users` and filtering would drop
-- the RECORDS from every list rather than merely blanking a name.
--
-- The objection recorded against it was that those joins need only the
-- NAME while the policy hands over the whole row. Measured before acting,
-- because the objection deserves the same scrutiny as the defect:
--
--   * `display_name` — read by all eleven joins. Attribution. Correct.
--   * `email`        — read by TWO production paths that deliberately
--                      return it: `admin.list_members` and
--                      `projects.list_members` (which documents that it
--                      lists former members on purpose, because "who has
--                      ever had access" is the question asked after an
--                      incident). Messaging also matches on its local
--                      part for @mentions. So email has real consumers
--                      and removing it would break stated behaviour.
--   * `keycloak_sub` — read by **NO application query at all.**
--
-- 🔴 THAT LAST LINE IS THE WHOLE FINDING. `keycloak_sub` is an
-- authentication identifier, it is granted to three roles, and not one
-- read path in `app/` selects it. The only readers are
-- `core.principal_for_subject`, `core.memberships_for_subject` and
-- `core.user_id_for_subject` — all SECURITY DEFINER owned by
-- `evercoat_owner`, so they keep working when the column stops being
-- readable by the runtime roles.
--
-- RLS is row-level and cannot express "you may see the name but not the
-- identifier". Column privileges can, and that is what this does.
--
-- ⚠️ A COLUMN-LEVEL REVOKE AGAINST A TABLE-LEVEL GRANT DOES NOTHING.
-- PostgreSQL treats `GRANT SELECT ON core.users` as covering every
-- column, including ones added later, and `REVOKE SELECT (keycloak_sub)`
-- against it is silently ineffective. The table-level grant has to go and
-- be replaced by an explicit column list. Getting that wrong would leave
-- a migration that reads like a fix and changes nothing — the shape this
-- repository keeps finding.
--
-- UPDATE is narrowed on the same evidence: no production code updates
-- `core.users` at all, and an UPDATE on `keycloak_sub` would be an
-- identity swap — the subject a token is verified against, rewritten by
-- the runtime role. INSERT keeps `keycloak_sub`, because `invite_member`
-- creates identities and that is the one path that legitimately sets it.
--
-- ---------------------------------------------------------------------
-- PART 2 — 046's RENAME GUARD WAS SCOPED BY RLS, NOT BY ITSELF
-- ---------------------------------------------------------------------
--
-- Found while measuring whether I82's proposed "atomic bind inside a
-- SECURITY DEFINER" was safe. It is not, and the reason generalises.
--
-- `core.deny_duplicate_address_in_organization` scopes itself:
--
--     WHERE om.organization_id = NEW.organization_id
--
-- `core.deny_address_collision_on_rename` did not. Its `mine` side was
-- restricted only by the RLS policy on `core.organization_members`. A
-- trigger runs as whatever the current user is, and inside a SECURITY
-- DEFINER owned by `evercoat_owner` that is the TABLE OWNER, who bypasses
-- RLS while FORCE is off. Measured, both paths, same data:
--
--     INVOKER path  : ACCEPTED  <- tenant-scoped, correct
--     DEFINER path  : REFUSED   <- refused on organization B's row
--
-- The refusal itself then discloses that the address exists somewhere on
-- the platform — I83's oracle, rebuilt inside the guard that replaced it,
-- by any future definer that writes to `core.users`.
--
-- 🔴 CHECK WHICH MECHANISM IS LOAD-BEARING. RLS was doing the scoping and
-- the comment credited the INVOKER choice. Both were true, and only one
-- of them survives being wrapped. The predicate is now explicit, so the
-- scope travels with the function instead of with the caller's role —
-- and it is equally correct under the FORCE RLS cutover of I56/I58,
-- which would otherwise have changed this behaviour again.
-- =====================================================================

BEGIN;

-- ---------------------------------------------------------------------
-- 1. The identifier stops being readable by the runtime roles.
-- ---------------------------------------------------------------------
REVOKE SELECT ON core.users FROM evercoat_app, evercoat_report, evercoat_worker;

GRANT SELECT (id, email, display_name, status, created_at, updated_at)
    ON core.users TO evercoat_app, evercoat_report, evercoat_worker;

REVOKE UPDATE ON core.users FROM evercoat_app;
GRANT UPDATE (email, display_name, status) ON core.users TO evercoat_app;

COMMENT ON COLUMN core.users.keycloak_sub IS
    'The identity provider''s subject. NOT readable by evercoat_app, '
    'evercoat_report or evercoat_worker (migration 047, I81): no '
    'application query selects it, and the only readers are the '
    'owner-owned SECURITY DEFINER lookups. It stays INSERTable because '
    'invite_member creates identities.';

-- ---------------------------------------------------------------------
-- 2. The rename guard scopes itself.
-- ---------------------------------------------------------------------
CREATE OR REPLACE FUNCTION core.deny_address_collision_on_rename()
RETURNS TRIGGER
LANGUAGE plpgsql
SECURITY INVOKER
AS $fn$
BEGIN
    PERFORM pg_advisory_xact_lock(
        hashtext(COALESCE(core.current_org_id()::TEXT, '<none>')),
        hashtext(NEW.email::TEXT)
    );

    -- 🔴 `mine.organization_id = core.current_org_id()` IS THE SCOPE.
    --
    -- It used to be absent, and the RLS policy on
    -- `core.organization_members` did the work instead. That is correct
    -- for an invoker under RLS and WRONG the moment the same statement
    -- runs inside a SECURITY DEFINER owned by the table owner, who
    -- bypasses RLS: measured, the guard then refused on another tenant's
    -- row and the refusal disclosed that the address exists.
    --
    -- With the predicate here, the scope belongs to the function rather
    -- than to whoever happens to be calling it. A NULL GUC matches no
    -- organization and the guard passes — missing inside your own tenant
    -- beats answering about one you cannot see, which is the trade 046
    -- makes throughout.
    IF core.current_org_id() IS NULL THEN
        RETURN NEW;
    END IF;

    IF EXISTS (
        SELECT 1
          FROM core.organization_members mine
          JOIN core.organization_members other
            ON other.organization_id = mine.organization_id
           AND other.user_id <> NEW.id
           AND other.status = 'active'
          JOIN core.users u ON u.id = other.user_id
         WHERE mine.user_id = NEW.id
           AND mine.status = 'active'
           AND mine.organization_id = core.current_org_id()
           AND u.email = NEW.email
    ) THEN
        RAISE EXCEPTION
            'address already belongs to an active member of this organization'
            USING ERRCODE = 'unique_violation',
                  CONSTRAINT = 'users_address_stays_unique_in_organization';
    END IF;

    RETURN NEW;
END $fn$;

ALTER FUNCTION core.deny_address_collision_on_rename() OWNER TO evercoat_owner;

COMMENT ON FUNCTION core.deny_address_collision_on_rename() IS
    'Refuses renaming a user onto an address already held by another '
    'ACTIVE member of the SAME organization, scoped by its own predicate '
    'rather than by the caller''s RLS (migration 047). Under RLS alone it '
    'went global inside a SECURITY DEFINER and its refusal became a '
    'cross-tenant existence answer.';

COMMIT;


-- ---------------------------------------------------------------------
-- PROVE BOTH PARTS. Rolled back.
-- ---------------------------------------------------------------------
DO $probe$
DECLARE
    v_has_sub  BOOLEAN;
    v_has_mail BOOLEAN;
BEGIN
    -- (1) The identifier is gone for the runtime roles, and the columns
    --     the application actually reads are not.
    SELECT has_column_privilege('evercoat_app', 'core.users', 'keycloak_sub', 'SELECT')
      INTO v_has_sub;
    SELECT has_column_privilege('evercoat_app', 'core.users', 'email', 'SELECT')
      INTO v_has_mail;

    IF v_has_sub THEN
        RAISE EXCEPTION
            '047 FAILED: evercoat_app can still SELECT core.users.keycloak_sub. '
            'A column-level REVOKE against a table-level GRANT does nothing; '
            'the table-level grant must be replaced by a column list.';
    END IF;
    IF NOT v_has_mail THEN
        RAISE EXCEPTION
            '047 FAILED: evercoat_app can no longer SELECT core.users.email. '
            'admin.list_members and projects.list_members both return it.';
    END IF;
    RAISE NOTICE '047: keycloak_sub is unreadable by evercoat_app; email still readable';

    IF has_column_privilege('evercoat_app', 'core.users', 'keycloak_sub', 'UPDATE') THEN
        RAISE EXCEPTION
            '047 FAILED: evercoat_app can UPDATE keycloak_sub. Rewriting the '
            'subject a token is verified against is an identity swap.';
    END IF;
    IF NOT has_column_privilege('evercoat_app', 'core.users', 'keycloak_sub', 'INSERT') THEN
        RAISE EXCEPTION
            '047 FAILED: evercoat_app can no longer INSERT keycloak_sub, so '
            'invite_member cannot create an identity at all.';
    END IF;
    RAISE NOTICE '047: keycloak_sub is INSERTable and not UPDATEable';

    -- (2) The definers that DO read it still can. They run as their owner,
    --     so this must hold -- but "must" is an argument and this is the
    --     measurement. Sign-in dies if it is wrong.
    IF NOT has_column_privilege('evercoat_owner', 'core.users', 'keycloak_sub', 'SELECT') THEN
        RAISE EXCEPTION
            '047 FAILED: evercoat_owner cannot read keycloak_sub. '
            'principal_for_subject is a definer owned by it and sign-in is dead.';
    END IF;
    RAISE NOTICE '047: evercoat_owner still reads keycloak_sub -- sign-in intact';

    RAISE EXCEPTION 'probe complete, rolling back' USING ERRCODE = 'raise_exception';
EXCEPTION
    WHEN raise_exception THEN
        IF SQLERRM <> 'probe complete, rolling back' THEN
            RAISE;
        END IF;
        RAISE NOTICE '047: probe rolled back';
END $probe$;
