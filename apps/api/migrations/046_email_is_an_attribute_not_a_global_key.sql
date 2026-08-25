-- =====================================================================
-- 046 — an email address is an attribute, not a global key
--
-- Closes I83, the cross-tenant email existence oracle.
--
-- ---------------------------------------------------------------------
-- WHAT WAS WRONG — MEASURED, NOT ASSUMED
-- ---------------------------------------------------------------------
--
-- `core.users.email` is CITEXT carrying `users_email_key`, a GLOBALLY
-- unique constraint. Unique constraints are enforced OUTSIDE row-level
-- security: the index is consulted whatever the reader may see.
--
-- Measured 2026-08-25 as `evercoat_app` scoped to organization A, against
-- an address belonging to a member of organization B:
--
--     INSERT INTO core.users (keycloak_sub, email, display_name)
--     VALUES ('throwaway', 'victim@competitor.example', 'throwaway');
--       -->  REFUSED by "users_email_key"
--
--     ... the same statement with an address nobody holds:
--       -->  ACCEPTED
--
-- `POST /api/admin/members` turns the first into 409 and the second into
-- 201. So a holder of `admin.users` in ANY tenant — including a
-- self-service one — reads platform-wide existence from a status code,
-- with a throwaway subject and no row left behind. It repeats without
-- limit. Emails are guessable where a subject UUID is not:
-- `firstname.lastname@competitor.com`, or a whole domain swept, discloses
-- which named individuals and which companies are on this platform.
--
-- And measured in the same run, the squatting half:
--
--     A pre-inserts a junk identity holding 'target@competitor.example'
--       -->  ACCEPTED — organization B can now NEVER onboard that person
--
-- ---------------------------------------------------------------------
-- 🔴 WHY THE FIX IS TO DROP THE CONSTRAINT, NOT TO DISGUISE ITS REFUSAL
-- ---------------------------------------------------------------------
--
-- The alternative on the table was to keep `users_email_key`, resolve the
-- address through a SECURITY DEFINER, and answer one indistinguishable
-- 409 for every outcome. It does not work, and the reason is already in
-- the record rather than in an argument: **migration 044 ALREADY made
-- that refusal generic** (the route answers "the user record could not be
-- created" and never names a constraint), **and the oracle survived**.
--
-- It survived because the attacker does not read the message. They read
-- **201 against 409**, and no wording closes that gap while a globally
-- enforced constraint decides which one they get. A creating endpoint
-- cannot make "created" indistinguishable from "not created".
--
-- So: a GLOBAL unique constraint on an attribute is a cross-tenant
-- channel BY CONSTRUCTION, not by accident. The only fix that removes the
-- channel is to stop enforcing that invariant globally.
--
-- 🔴 AND IT COSTS LESS THAN THE PLAN CLAIMED, WHICH WAS ALSO MEASURED.
--
-- `TODO.md` recorded that dropping the constraint "reaches
-- messaging/service.py's @mention resolution, which matches on the local
-- part of core.users.email". It does not. That query is
--
--     WHERE split_part(u.email, '@', 1) = :handle
--
-- and the constraint is on the WHOLE ADDRESS. Those are not the same
-- invariant, so the constraint never protected that query. Measured with
-- two members of ONE organization, `jane@one.example` and
-- `jane@two.example` — both permitted by `users_email_key` today:
--
--     SELECT ... WHERE split_part(u.email,'@',1) = 'jane'  -->  2 rows
--
-- and `messaging/service.py` calls `.one_or_none()` on it, which raises
-- `MultipleResultsFound`. That is a pre-existing 500 on posting a
-- message, independent of this migration, and it is fixed in the same
-- commit rather than left to look like a consequence of this change.
--
-- ---------------------------------------------------------------------
-- WHAT REPLACES IT
-- ---------------------------------------------------------------------
--
-- Identity is `keycloak_sub`, and `users_keycloak_sub_key` is untouched.
-- Email is an ATTRIBUTE mirrored from the identity provider, and the
-- realm is where address uniqueness belongs.
--
-- What this platform does need is that one organization's member list
-- does not contain the same address twice. That is enforced HERE, per
-- organization, on `core.organization_members`:
--
--   * its refusal discloses only what `list_members` already shows that
--     caller — the members of their own organization — so it cannot be
--     an oracle;
--   * it is scoped to ACTIVE members, so deactivating somebody does not
--     block re-adding them or onboarding their replacement.
--
-- 🔴 THE GUARD IS DELIBERATELY *NOT* A SECURITY DEFINER.
--
-- A definer would read across tenants, and a check that reads across
-- tenants and refuses is exactly the shape being removed above — it would
-- rebuild the oracle in a trigger. As an INVOKER function it sees only
-- what the writing role may see. Within one organization that is every
-- member (044's read policy admits them), so it does not miss; and if RLS
-- ever hides a row from it, the guard silently passes rather than
-- silently leaking. **Prefer a guard that can miss inside your own tenant
-- over one that can answer across tenants.**
--
-- Measured before writing this: 0 organizations currently hold a
-- duplicate address, and 0 hold a duplicate local part, across 782 users
-- and 157 organizations — so nothing has to be cleaned up first. That
-- zero also means the live population CANNOT exercise this guard, so it
-- is proven below on rows built for the purpose, not on what happens to
-- be in the table.
-- =====================================================================

BEGIN;

-- ---------------------------------------------------------------------
-- 1. The global constraint goes.
-- ---------------------------------------------------------------------
ALTER TABLE core.users DROP CONSTRAINT IF EXISTS users_email_key;

COMMENT ON COLUMN core.users.email IS
    'The address mirrored from the identity provider. NOT unique, and '
    'deliberately so: a globally unique constraint on this column is '
    'enforced outside RLS, which made it a cross-tenant existence oracle '
    'and a squatting channel (I83, migration 046). Identity is '
    'keycloak_sub. Uniqueness within one organization is enforced by '
    'core.organization_members_one_address_per_organization.';

-- ---------------------------------------------------------------------
-- 2. Per-organization uniqueness, enforced where it cannot leak.
-- ---------------------------------------------------------------------
CREATE OR REPLACE FUNCTION core.deny_duplicate_address_in_organization()
RETURNS TRIGGER
LANGUAGE plpgsql
-- SECURITY INVOKER (the default, stated because it is load-bearing): a
-- DEFINER here would read every tenant and refuse on what it found, which
-- is the oracle this migration exists to remove.
SECURITY INVOKER
AS $fn$
DECLARE
    v_email CITEXT;
BEGIN
    -- The address of the member being added or reactivated.
    SELECT u.email INTO v_email
      FROM core.users u
     WHERE u.id = NEW.user_id;

    -- Not visible to this role: say nothing rather than guess. See the
    -- header — missing inside your own tenant beats answering across one.
    IF v_email IS NULL THEN
        RETURN NEW;
    END IF;

    IF EXISTS (
        SELECT 1
          FROM core.organization_members om
          JOIN core.users u ON u.id = om.user_id
         WHERE om.organization_id = NEW.organization_id
           AND om.id <> NEW.id
           AND om.status = 'active'
           AND u.email = v_email
    ) THEN
        RAISE EXCEPTION
            'address already belongs to an active member of this organization'
            USING ERRCODE = 'unique_violation',
                  CONSTRAINT = 'organization_members_one_address_per_organization';
    END IF;

    RETURN NEW;
END $fn$;

ALTER FUNCTION core.deny_duplicate_address_in_organization() OWNER TO evercoat_owner;

COMMENT ON FUNCTION core.deny_duplicate_address_in_organization() IS
    'Refuses a second ACTIVE member of one organization holding the same '
    'email address. Replaces the global users_email_key dropped in 046, '
    'at the only scope where a refusal discloses nothing the caller '
    'cannot already read. SECURITY INVOKER on purpose (I83).';

-- A CONSTRAINT TRIGGER, deferrable and fired at the END of the statement:
-- `invite_member` inserts the membership and the guard must see the row it
-- is judging, and a reactivation that swaps two members' status in one
-- statement must be judged on the final state, not on an intermediate one.
DROP TRIGGER IF EXISTS organization_members_one_address_per_organization
    ON core.organization_members;
CREATE CONSTRAINT TRIGGER organization_members_one_address_per_organization
    AFTER INSERT OR UPDATE OF user_id, status, organization_id
    ON core.organization_members
    DEFERRABLE INITIALLY IMMEDIATE
    FOR EACH ROW
    WHEN (NEW.status = 'active')
    EXECUTE FUNCTION core.deny_duplicate_address_in_organization();

COMMENT ON TRIGGER organization_members_one_address_per_organization
    ON core.organization_members IS
    'One active member per address, per organization. The tenant-scoped '
    'replacement for users_email_key (I83, migration 046).';

COMMIT;


-- ---------------------------------------------------------------------
-- PROVE BOTH HALVES, ON ROWS BUILT FOR THE PURPOSE.
--
-- The live population holds no duplicate address in any organization, so
-- it cannot exercise this guard at all -- a measurement over a population
-- that cannot exercise the risk is not evidence, however large it is.
-- Everything below is rolled back.
-- ---------------------------------------------------------------------
DO $probe$
DECLARE
    v_org_a  UUID;
    v_org_b  UUID;
    v_u1     UUID;
    v_u2     UUID;
    v_u3     UUID;
    v_sfx    TEXT := replace(gen_random_uuid()::TEXT, '-', '');
    v_addr   TEXT;
    v_caught BOOLEAN := FALSE;
BEGIN
    v_addr := 'probe046-' || left(v_sfx, 8) || '@example.test';

    INSERT INTO core.organizations (code, name)
    VALUES ('P046A-' || left(v_sfx, 8), '046 probe A') RETURNING id INTO v_org_a;
    INSERT INTO core.organizations (code, name)
    VALUES ('P046B-' || left(v_sfx, 8), '046 probe B') RETURNING id INTO v_org_b;

    -- (1) THE ORACLE IS GONE: two DIFFERENT subjects may now hold the same
    --     address, which is what made the global constraint answerable.
    INSERT INTO core.users (keycloak_sub, email, display_name)
    VALUES ('p046-1-' || v_sfx, v_addr, '046 one') RETURNING id INTO v_u1;
    INSERT INTO core.users (keycloak_sub, email, display_name)
    VALUES ('p046-2-' || v_sfx, v_addr, '046 two') RETURNING id INTO v_u2;

    RAISE NOTICE '046: two identities share one address -- users_email_key is gone';

    -- (2) IDENTITY IS STILL UNIQUE. Dropping the email key must not have
    --     made it possible to create the same SUBJECT twice.
    BEGIN
        INSERT INTO core.users (keycloak_sub, email, display_name)
        VALUES ('p046-1-' || v_sfx, 'other-' || v_addr, '046 duplicate subject')
        RETURNING id INTO v_u3;
        RAISE EXCEPTION
            '046 FAILED: keycloak_sub is no longer unique. Identity is not '
            'protected and this migration has broken more than it fixed.';
    EXCEPTION WHEN unique_violation THEN
        RAISE NOTICE '046: keycloak_sub is still unique -- identity intact';
    END;

    -- (3) THE PER-ORGANIZATION GUARD REFUSES the second active member.
    INSERT INTO core.organization_members (organization_id, user_id)
    VALUES (v_org_a, v_u1);

    BEGIN
        INSERT INTO core.organization_members (organization_id, user_id)
        VALUES (v_org_a, v_u2);
        RAISE EXCEPTION
            '046 FAILED: two active members of one organization hold %. The '
            'replacement guard did not fire, so dropping users_email_key '
            'removed a rule and put nothing in its place.', v_addr;
    EXCEPTION WHEN unique_violation THEN
        v_caught := TRUE;
    END;

    IF NOT v_caught THEN
        RAISE EXCEPTION '046 FAILED: the guard did not raise unique_violation';
    END IF;
    RAISE NOTICE '046: a second active member with the same address is refused';

    -- (4) AND IT IS SCOPED TO ONE ORGANIZATION. The same address in a
    --     DIFFERENT organization must be accepted -- otherwise the guard is
    --     the global constraint again, wearing a trigger, and I83 is not
    --     closed at all.
    --
    --     Caught and re-raised with a diagnosis on purpose. Falsified by
    --     deleting `om.organization_id = NEW.organization_id` from the
    --     function: without this handler the run aborts on the trigger's own
    --     message, which reads like the guard WORKING rather than like the
    --     scope being wrong.
    BEGIN
        INSERT INTO core.organization_members (organization_id, user_id)
        VALUES (v_org_b, v_u2);
    EXCEPTION WHEN unique_violation THEN
        RAISE EXCEPTION
            '046 FAILED: the guard refused % in a DIFFERENT organization. It '
            'is not scoped to one tenant, so it is users_email_key wearing a '
            'trigger and the cross-tenant oracle of I83 is still open.', v_addr;
    END;
    RAISE NOTICE '046: the same address in another organization is accepted';

    RAISE EXCEPTION 'probe complete, rolling back' USING ERRCODE = 'raise_exception';
EXCEPTION
    WHEN raise_exception THEN
        IF SQLERRM <> 'probe complete, rolling back' THEN
            RAISE;
        END IF;
        RAISE NOTICE '046: probe rolled back';
END $probe$;
