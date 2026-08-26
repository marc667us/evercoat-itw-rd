-- 049 — an identifier is returned only after the membership exists
--
-- Closes I82. Depends on 048 (g1000).
--
-- ============================================================================
-- 🔴 THE ORACLE, AND WHY REPLACING IT NEEDED PERMISSION FROM A MEASUREMENT
-- ============================================================================
--
-- `core.user_id_for_subject(TEXT)` answers, for an exact Keycloak subject, in
-- ANY organization on the platform:
--
--   * the user's UUID — which matters because `project_members.user_id`,
--     `tasks.assigned_user_id` and others are plain `REFERENCES core.users(id)`
--     and referential integrity bypasses RLS. `app/core/tenancy.py` guards that
--     hole in PYTHON.
--   * EXISTENCE, on a SELECT, leaving no row behind — where the constraint it
--     replaced answered only on an INSERT.
--
-- Reachable only with `admin.users` and the exact subject string, and the
-- route's next act binds that user anyway. It is a narrow oracle. It is still
-- an oracle, and it is the shape 048 deliberately avoided by taking no
-- arguments at all.
--
-- ============================================================================
-- 🔴 ADR-029 REJECTED THIS FIX. THE REJECTION HAS EXPIRED, AND THAT IS
--    MEASURED, NOT ARGUED.
-- ============================================================================
--
-- ADR-029 recorded the atomic-bind design as **rejected on evidence**:
--
--     I82 proposes folding subject resolution into "a single atomic bind so
--     the id is returned only after the membership exists". The obvious
--     implementation is a SECURITY DEFINER. Measured before building it, and
--     it would have re-opened I83.
--
-- The mechanism was precise: a definer WRITES, the write fires ADR-028's
-- address-collision triggers, and a trigger inside a definer owned by the
-- table owner runs as that owner — bypassing RLS while FORCE is off. The
-- guard then refused on another tenant's row, and the refusal itself
-- disclosed that the address exists somewhere.
--
-- 🔴 BUT 047 THEN FIXED THAT, AND NOBODY WENT BACK TO CHECK. ADR-029's own
-- hardening made `deny_address_collision_on_rename` scope itself by its own
-- predicate instead of relying on the caller's RLS. That is the exact step
-- the chain depended on. Re-measured today with ADR-029's own probes, against
-- this schema:
--
--     definer_rename.py       INVOKER: ACCEPTED   DEFINER: ACCEPTED
--     definer_composition.py  INVOKER: ACCEPTED   DEFINER: ACCEPTED
--
-- Before 047 the DEFINER row read REFUSED — the disclosure. Both guards now
-- stay tenant-scoped inside a definer, so the chain has no second step.
--
-- ⚠️ *RE-MEASURE A SETTLED CONCLUSION BEFORE PAYING FOR IT.* A recorded
-- rejection is evidence about the code as it was. This one outlived its cause
-- by one migration, and designing around it would have meant accepting a
-- worse shape to respect a constraint that no longer existed.
--
-- 🔴 AND THE MEASUREMENT IS NOW A TEST, not a note in a header:
-- `tests/db/test_049_atomic_bind.py::test_a_definer_write_does_not_widen_the_address_guards`
-- fails the moment a future migration un-does 047's explicit scoping, because
-- THIS FUNCTION IS THE WRITING DEFINER ADR-029 warned about. The warning was
-- right; it simply no longer applies, and the way to keep that true is to
-- watch it.
--
-- ============================================================================
-- WHAT THIS CHANGES, AND WHAT IT HONESTLY DOES NOT
-- ============================================================================
--
-- The uuid is no longer obtainable without a membership. Resolution and bind
-- happen in one statement, so a caller who learns an id has, in the same
-- breath, created a membership in their OWN organization — after which 044's
-- read policy admits that user to them anyway, because they now share an
-- organization. Nothing is disclosed that the caller was not entitled to.
--
-- ⚠️ EXISTENCE IS STILL LEARNABLE, AND SAYING SO IS THE POINT. A caller may
-- still discover that a subject had an account elsewhere — `identity_created`
-- says which happened, and an administrator needs it, since creating a
-- duplicate identity for a human who already has one is the failure 044's
-- design exists to prevent.
--
-- What changed is the COST. The answer is no longer a silent, traceless
-- SELECT: it requires creating a real membership row and it writes an audit
-- record. A probe that leaves evidence is a different object from one that
-- does not, and this is a reduction rather than an elimination. Any claim
-- here broader than that would be false.
--
-- ============================================================================
-- 🔴 THE ORGANIZATION IS NOT A PARAMETER
-- ============================================================================
--
-- The obvious signature takes `p_org`, mirroring the route's
-- `principal.organization_id`. That would be a SECURITY DEFINER that creates
-- a membership in ANY organization the caller cares to name — a cross-tenant
-- WRITE, granted by accident, inside the migration removing a cross-tenant
-- READ. ADR-029 caught exactly that shape in its own first draft (`UPDATE
-- status` on a GLOBAL row) and it is the second time the same reflex has
-- appeared.
--
-- So the organization comes from `core.current_org_id()` — the GUC the
-- caller's own RLS context already carries, which they cannot set to another
-- tenant without also losing their ability to read their own rows. Same rule
-- as 048: no parameter means nothing to aim.
-- ============================================================================

BEGIN;

-- 🔴 DROP EVERY OVERLOAD BY NAME BEFORE CREATING. `CREATE OR REPLACE
-- FUNCTION` REPLACES ONLY AN EXACT SIGNATURE MATCH -- change a parameter TYPE
-- and it creates a SECOND function instead, silently.
--
-- Measured while writing this migration: an earlier draft took `p_email
-- CITEXT`, the pinned `search_path` could not resolve that type, and the
-- corrected `TEXT` version was created ALONGSIDE the citext one. Two
-- overloads, both callable, and `pg_proc` queries that expect one row start
-- failing in ways that read like the function is missing.
--
-- Same family as *a column-level REVOKE against a table-level GRANT does
-- nothing*: the statement succeeds and does not do what it looks like it did.
DO $drop$
DECLARE
    fn RECORD;
BEGIN
    FOR fn IN
        SELECT p.oid::regprocedure AS sig
        FROM pg_proc p
        JOIN pg_namespace n ON n.oid = p.pronamespace
        WHERE n.nspname = 'core' AND p.proname = 'bind_subject_to_organization'
    LOOP
        EXECUTE format('DROP FUNCTION %s', fn.sig);
    END LOOP;
END
$drop$;

CREATE FUNCTION core.bind_subject_to_organization(
    p_subject      TEXT,
    -- 🔴 TEXT, NOT CITEXT, AND THE PINNED search_path IS WHY.
    --
    -- `core.users.email` is `citext` and the obvious signature mirrors it.
    -- But the `citext` TYPE lives in `public`, which `SET search_path = core,
    -- pg_temp` deliberately excludes — so a caller resolving this signature
    -- got `type "citext" does not exist`. Measured, not predicted: the first
    -- version failed exactly that way.
    --
    -- Adding `public` to the search_path would fix it and reintroduce the
    -- shadowing risk the pin exists to prevent. Taking TEXT and letting the
    -- column's assignment cast do the work costs nothing: the value lands in
    -- a `citext` column and compares case-insensitively from then on, which
    -- is the whole reason the column has that type.
    p_email        TEXT,
    p_display_name TEXT
)
    RETURNS TABLE (user_id UUID, member_id UUID, identity_created BOOLEAN)
    LANGUAGE plpgsql
    -- VOLATILE: it writes. Stated rather than defaulted, because 048's
    -- counterpart is STABLE for exactly the opposite reason and the contrast
    -- is the whole of why one of them can fire a trigger and the other cannot.
    VOLATILE
    SECURITY DEFINER
    SET search_path = core, pg_temp
AS $fn$
DECLARE
    v_org     UUID := core.current_org_id();
    v_user    UUID;
    v_member  UUID;
    v_created BOOLEAN := FALSE;
BEGIN
    -- 🔴 FAIL CLOSED ON AN UNSCOPED SESSION. `core.current_org_id()` returns
    -- NULL rather than raising when the GUC is unset (001), and an unscoped
    -- session is the one `unscoped_session_scope()` opens. Binding into NULL
    -- would violate NOT NULL rather than doing something dangerous, but a
    -- named refusal is what tells the next reader this was considered.
    IF v_org IS NULL THEN
        RAISE EXCEPTION 'no organization in the session context'
            USING ERRCODE = 'insufficient_privilege';
    END IF;

    SELECT id INTO v_user FROM core.users WHERE keycloak_sub = p_subject;

    IF v_user IS NULL THEN
        -- 🔴 `public.citext`, SCHEMA-QUALIFIED, AND BOTH HALVES OF THAT WERE
        -- LEARNED THE HARD WAY.
        --
        -- `core.users.email` is `citext` and the type lives in `public`, which
        -- `SET search_path = core, pg_temp` deliberately excludes. Taking the
        -- parameter as TEXT fixed the SIGNATURE; the assignment cast in this
        -- INSERT then failed the same way, at runtime, inside the function --
        -- `type "citext" does not exist`.
        --
        -- Adding `public` to the search_path would fix both and reintroduce
        -- the shadowing a pinned path exists to prevent. Qualifying the cast
        -- keeps the pin and says exactly which type is meant.
        INSERT INTO core.users (keycloak_sub, email, display_name)
        VALUES (p_subject, p_email::public.citext, p_display_name)
        RETURNING id INTO v_user;
        v_created := TRUE;
    END IF;
    -- ⚠️ AN EXISTING IDENTITY IS NOT UPDATED. Its email and display name
    -- belong to whoever created it; overwriting them from another tenant's
    -- submission is I80, which 044 refused and the route already avoids.

    -- 🔴 THIS IS THE ATOMICITY. If the membership cannot be created --
    -- already a member, or 046's per-organization address guard -- the
    -- exception propagates, the whole function rolls back, and NO identifier
    -- is returned. That is the entire content of "the id is returned only
    -- after the membership exists".
    INSERT INTO core.organization_members (organization_id, user_id)
    VALUES (v_org, v_user)
    RETURNING id INTO v_member;

    RETURN QUERY SELECT v_user, v_member, v_created;
END
$fn$;

-- 🔴 PIN THE OWNER. Unpinned, a definer created by a migration applied as
-- `postgres` runs as a SUPERUSER with BYPASSRLS -- permanently outside RLS,
-- including after the I56/I58 cutover. Migration 044 did exactly that while
-- its own comment claimed otherwise, and it was found by reading `pg_proc`.
ALTER FUNCTION core.bind_subject_to_organization(TEXT, TEXT, TEXT)
    OWNER TO evercoat_owner;

REVOKE ALL ON FUNCTION core.bind_subject_to_organization(TEXT, TEXT, TEXT) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION core.bind_subject_to_organization(TEXT, TEXT, TEXT)
    TO evercoat_app;

COMMENT ON FUNCTION core.bind_subject_to_organization(TEXT, TEXT, TEXT) IS
    'Resolve a Keycloak subject to an identity and bind it to the CURRENT '
    'SESSION''s organization, atomically. Returns the user id only after the '
    'membership exists, which is what closes I82: the identifier is no longer '
    'obtainable by a silent SELECT that leaves no row behind. '
    'The organization is read from app.current_org, never taken as an '
    'argument -- a SECURITY DEFINER that accepted one would create memberships '
    'in any tenant the caller named. '
    'SECURITY DEFINER because 044 makes a user in another organization '
    'invisible, and a human legitimately belongs to several. '
    'It WRITES, so ADR-028''s address guards fire inside it -- safe only '
    'because 047 made both guards scope themselves by their own predicate; '
    'tests/db/test_049_atomic_bind.py measures that and fails if it regresses.';

-- ============================================================================
-- 🔴 AND THE ORACLE IS DROPPED, NOT MERELY LEFT UNCALLED
-- ============================================================================
--
-- `core.user_id_for_subject` had exactly one caller, `app/api/admin.py`, which
-- this migration's companion change rewires. Leaving the function in place
-- with `GRANT EXECUTE ... TO evercoat_app` would leave I82 fully reachable and
-- merely unused -- a capability nothing calls is still a capability, which is
-- this repository's most-repeated finding pointed the other way round.
DROP FUNCTION IF EXISTS core.user_id_for_subject(TEXT);

-- ============================================================================
-- 🔴 AND A SECOND FINDING, FROM BUILDING THE FIRST: A DEFINER'S PINNED
--    search_path PROPAGATES INTO THE TRIGGERS ITS WRITES FIRE.
-- ============================================================================
--
-- ADR-028's two address guards declare `v_email CITEXT` and neither pins a
-- `search_path` — measured from `pg_proc.proconfig`, both `(none)`. A trigger
-- with no pinned path resolves names through whatever its CALLER has.
--
-- Ordinarily the caller is `app/api/admin.py` on an ordinary session, whose
-- path includes `public`, where the `citext` TYPE lives. So it worked, and
-- nothing said the dependency existed.
--
-- The moment the write came from a SECURITY DEFINER with the pinned
-- `search_path = core, pg_temp` that definer hardening REQUIRES, the trigger
-- inherited it and failed:
--
--     ERROR: type "citext" does not exist
--     LINE 3:     v_email CITEXT;
--     CONTEXT: PL/pgSQL function core.deny_duplicate_address_in_organization()
--
-- 🔴 THIS IS ADR-029's CONCERN WITH A DIFFERENT MECHANISM. ADR-029 found that
-- a definer changes the PRIVILEGE a guard runs with; this is that a definer
-- changes the NAMES a guard can resolve. Both are "the guard behaves
-- differently depending on who called it", and 047 already fixed the first by
-- making the tenant scope explicit. This makes the name resolution explicit,
-- for the same reason and in the same place.
--
-- ⚠️ THE FAILURE MODE IS THE DANGEROUS DIRECTION. A guard that RAISES is
-- loud. But `deny_duplicate_address_in_organization` is what stops a second
-- active member of one organization holding the same address, so any future
-- caller whose search_path happens not to reach `public` would have found the
-- write refused rather than silently admitted — loud, and still a guard that
-- answers differently by caller, which is what 047 set out to end.
--
-- `pg_temp` LAST, and `public` present because the guards genuinely need the
-- type. A shadowing object would have to be created in `core` to take effect
-- before it, and `evercoat_app` does not own that schema.

ALTER FUNCTION core.deny_duplicate_address_in_organization()
    SET search_path = core, public, pg_temp;

ALTER FUNCTION core.deny_address_collision_on_rename()
    SET search_path = core, public, pg_temp;

COMMENT ON FUNCTION core.deny_duplicate_address_in_organization() IS
    'ADR-028''s per-organization address guard. search_path pinned by 049: it '
    'declares CITEXT, whose type lives in public, and an unpinned trigger '
    'resolves names through its CALLER -- so a write from a SECURITY DEFINER '
    'with a narrow pinned path made it raise "type citext does not exist". '
    'A guard must not behave differently depending on who called it.';

COMMENT ON FUNCTION core.deny_address_collision_on_rename() IS
    'ADR-028''s rename guard, tenant-scoped explicitly by 047 and search_path '
    'pinned by 049 -- the same rule applied to privilege and then to name '
    'resolution.';

COMMIT;
