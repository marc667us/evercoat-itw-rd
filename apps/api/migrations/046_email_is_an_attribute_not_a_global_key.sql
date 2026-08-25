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

    -- 🔴 WITHOUT THIS LOCK THE CHECK IS NOT A CONSTRAINT, AND THAT WAS
    --    MEASURED RATHER THAN REASONED ABOUT.
    --
    -- A trigger that decides by SELECT is not a unique index. Under READ
    -- COMMITTED neither of two concurrent transactions sees the other's
    -- uncommitted row, so both EXISTS come back empty, both pass, and both
    -- commit. Measured on two real connections before this line existed:
    --
    --     session 1 inserted (uncommitted)
    --     session 2 inserted (uncommitted) -- the trigger did NOT see session 1
    --     session 1 committed
    --     session 2 committed
    --     ACTIVE members of one organization holding the address: 2
    --
    -- The comment above this function claimed it "refuses" a duplicate. That
    -- was true serially and false under concurrency -- a comment asserting a
    -- rule the code did not implement, which is this repository's most
    -- repeated defect.
    --
    -- The lock is the MECHANISM that makes the claim true. The second writer
    -- blocks here until the first transaction ends; its SELECT below then
    -- takes a fresh READ COMMITTED snapshot which includes the committed row,
    -- and refuses. Same shape as `audit.chain_row()` in 013, and for the same
    -- reason: concurrent writers must not fork an invariant.
    --
    -- Keyed on (organization, address) so it serialises only writers who
    -- could actually collide. A hash collision costs an unnecessary wait and
    -- never a wrong answer, because the EXISTS still compares real values.
    PERFORM pg_advisory_xact_lock(
        hashtext(NEW.organization_id::TEXT),
        hashtext(v_email::TEXT)
    );

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
    'replacement for users_email_key (I83, migration 046). Half of the rule '
    'only -- the other half is users_address_stays_unique_in_organization, '
    'because the ADDRESS lives on core.users and can be changed there.';

-- ---------------------------------------------------------------------
-- 3. 🔴 THE OTHER HALF: THE ADDRESS CAN BE CHANGED WITHOUT TOUCHING
--    THE TABLE THE TRIGGER ABOVE IS ON.
--
-- Raised by Codex and MEASURED. `evercoat_app` holds UPDATE on
-- `core.users`, and 044's UPDATE policy admits a user who shares an
-- organization with the writer. So:
--
--     UPDATE core.users SET email = <another active member's address>
--      WHERE id = <a colleague's id>;
--       -->  ACCEPTED, rows affected = 1
--       -->  ACTIVE members of one organization holding it: 2
--
-- The membership trigger never fires, because no membership row moved.
-- Without this second trigger the rule above is decorative on the exact
-- path an administrator is most likely to take, and -- worse -- the
-- schema would be WEAKER than before 046, since `users_email_key`
-- covered updates as well as inserts. A guard that covers INSERT and
-- nothing after it is a shape this repository has already shipped once.
-- ---------------------------------------------------------------------
CREATE OR REPLACE FUNCTION core.deny_address_collision_on_rename()
RETURNS TRIGGER
LANGUAGE plpgsql
-- SECURITY INVOKER for the same reason as the function above, and with a
-- sharper consequence here: the updated user may be an active member of
-- organizations the writer cannot see. As an INVOKER the RLS predicate on
-- `core.organization_members` restricts both sides of the join below to
-- the writer's own organization, so this can neither read nor answer for
-- another tenant. It therefore MISSES a collision in an organization the
-- writer is not in -- which is the trade this migration makes everywhere:
-- missing inside your own tenant beats answering across one.
SECURITY INVOKER
AS $fn$
BEGIN
    PERFORM pg_advisory_xact_lock(
        hashtext(COALESCE(core.current_org_id()::TEXT, '<none>')),
        hashtext(NEW.email::TEXT)
    );

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
    'ACTIVE member of an organization they both belong to. The UPDATE half '
    'of the rule whose INSERT half is enforced on '
    'core.organization_members. SECURITY INVOKER on purpose (I83).';

DROP TRIGGER IF EXISTS users_address_stays_unique_in_organization ON core.users;
CREATE CONSTRAINT TRIGGER users_address_stays_unique_in_organization
    AFTER UPDATE OF email ON core.users
    DEFERRABLE INITIALLY IMMEDIATE
    FOR EACH ROW
    WHEN (NEW.email IS DISTINCT FROM OLD.email)
    EXECUTE FUNCTION core.deny_address_collision_on_rename();

COMMENT ON TRIGGER users_address_stays_unique_in_organization ON core.users IS
    'The UPDATE half of one-address-per-organization (I83, migration 046). '
    'Without it the membership trigger is bypassed by changing the address '
    'in place, which is the path an administrator actually takes.';

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

    -- (5) AND THE RENAME PATH IS COVERED TOO. Without the second trigger the
    --     rule above is bypassed by changing the address in place -- measured
    --     as `evercoat_app`: UPDATE accepted, 2 active members holding it.
    INSERT INTO core.users (keycloak_sub, email, display_name)
    VALUES ('p046-3-' || v_sfx, 'renamer-' || v_addr, '046 renamer')
    RETURNING id INTO v_u3;
    INSERT INTO core.organization_members (organization_id, user_id)
    VALUES (v_org_a, v_u3);

    v_caught := FALSE;
    BEGIN
        UPDATE core.users SET email = v_addr WHERE id = v_u3;
    EXCEPTION WHEN unique_violation THEN
        v_caught := TRUE;
    END;

    IF NOT v_caught THEN
        RAISE EXCEPTION
            '046 FAILED: renaming a member onto %, already held by another '
            'active member of the same organization, was ACCEPTED. The '
            'membership trigger is bypassed by an in-place address change, '
            'which is the path an administrator actually takes.', v_addr;
    END IF;
    RAISE NOTICE '046: renaming onto a colleague''s address is refused';

    RAISE EXCEPTION 'probe complete, rolling back' USING ERRCODE = 'raise_exception';
EXCEPTION
    WHEN raise_exception THEN
        IF SQLERRM <> 'probe complete, rolling back' THEN
            RAISE;
        END IF;
        RAISE NOTICE '046: probe rolled back';
END $probe$;
