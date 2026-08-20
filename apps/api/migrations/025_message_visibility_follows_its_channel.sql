-- ---------------------------------------------------------------------
-- 025 — A message is exactly as private as the channel it was posted in
-- ---------------------------------------------------------------------
--
-- 🔴 THE DEFECT THIS CLOSES
--
-- Migration 022 gave `messaging.channels` a policy that carries the
-- PROJECT predicate:
--
--     project_id IS NULL
--     OR EXISTS (SELECT 1 FROM projects.projects p
--                WHERE p.id = channels.project_id
--                  AND (p.confidentiality = 'normal'
--                       OR core.is_project_member(p.id)))
--
-- and then gave `messaging.messages` — in the same file, in a DO-block
-- loop over six tables — a policy carrying only `organization_id`.
--
-- So the words were less protected than the room they were said in. Any
-- authenticated member of the organization holding a channel id could
-- read:
--
--   * every message in a RESTRICTED project's channel they are not a
--     member of. The CHANNEL row was correctly invisible to them; the
--     MESSAGE rows were not, and `list_messages` selected messages
--     without ever joining channels, so the channel's protection was
--     never consulted at all.
--
--   * every message in a DIRECT conversation between two other people.
--     022's own comment says direct messages "are governed by channel
--     membership instead" — and that governance existed in exactly ONE
--     place, the `list_channels` LISTING query. Nothing enforced it on
--     the path that returns the actual text.
--
-- This is the shape this repository keeps meeting: a rule stated in a
-- comment, implemented in one query, and absent from the layer that is
-- supposed to be the independent backstop. `SECURITY.md` §1 requires
-- that any ONE layer failing must not expose data. Here the application
-- layer WAS the only layer, and it was failing.
--
-- The service functions were fixed in the same change
-- (`app/domains/messaging/service.py`). This migration is the *other*
-- layer, so that a future route, worker, report or psql session reaching
-- `messaging.messages` directly inherits the rule instead of having to
-- remember it.
--
-- 🔴 WHY `core.can_read_channel` IS SECURITY **INVOKER**
--
-- Every other helper reached from a policy in this database is SECURITY
-- DEFINER, for a reason that does not apply here: they must see rows the
-- caller cannot, or they would find nothing and pass vacuously.
--
-- This one is the opposite. Its whole job is to ask "is this channel
-- visible to the person asking?", and the answer must be produced *by*
-- the caller's own RLS view of `messaging.channels`. As DEFINER it would
-- read every channel regardless of the project predicate and return TRUE
-- for a restricted project's channel — reintroducing the exact defect it
-- exists to close, while looking correct.
--
-- Invoker rights also keep it off `test_object_ownership.py`'s
-- `DEFINER_OWNED_BY_DESIGN` list, which is a security decision register
-- and should only grow when a definer is genuinely required.
--
-- 🔴 FAIL-CLOSED BEHAVIOUR
--
-- The membership half reads `core.current_user_id()`, the same GUC the
-- policies read. With no request context set that returns NULL, the
-- EXISTS is false, and a `direct` channel yields nothing. A caller with
-- no identity gets no private conversations rather than all of them.
--
-- Note the standing limitation, which this migration does NOT change:
-- `core.rls_permissive()` is still `SELECT TRUE`, so the first branch of
-- every policy in this database — including the two below — goes fully
-- permissive when `core.current_org_id()` is NULL. That scaffold is what
-- lets the seeder and the migrations write at all today. It is recorded
-- as an open gap in `SECURITY.md` §4 rather than flipped here, because
-- flipping it is the FORCE-RLS cutover and belongs in its own migration
-- with its own review.

BEGIN;

CREATE OR REPLACE FUNCTION core.can_read_channel(p_channel UUID) RETURNS BOOLEAN
    LANGUAGE sql STABLE
    -- SECURITY INVOKER (the default, stated here because it is a
    -- decision rather than an omission). See the header.
    SECURITY INVOKER
    SET search_path = messaging, core, pg_temp
AS $$
    SELECT EXISTS (
        SELECT 1
        FROM messaging.channels c
        WHERE c.id = p_channel
          -- A non-direct channel is governed by the `channels` policy
          -- alone: reaching this row at all means the project predicate
          -- already admitted the caller.
          AND (
                c.channel_type <> 'direct'
                OR EXISTS (
                    SELECT 1
                    FROM messaging.channel_members cm
                    WHERE cm.channel_id = c.id
                      AND cm.user_id = core.current_user_id()
                )
              )
    )
$$;

COMMENT ON FUNCTION core.can_read_channel(UUID) IS
    'May the current caller read this channel? SECURITY INVOKER on '
    'purpose: the answer must come from the caller''s own RLS view of '
    'messaging.channels, so a restricted project''s channel is refused. '
    'Adds the channel-membership rule for direct messages, which have no '
    'project to be governed by. See migration 025.';

-- ---------------------------------------------------------------------
-- The messages themselves
-- ---------------------------------------------------------------------
-- `org_scope` came from 022's DO-block loop. Replaced rather than added
-- to: two permissive policies on one table are OR-ed together, so
-- leaving `org_scope` in place would make this one decorative — the
-- classic way a tightening migration ships and changes nothing.
DROP POLICY IF EXISTS org_scope ON messaging.messages;
DROP POLICY IF EXISTS channel_scope ON messaging.messages;
CREATE POLICY channel_scope ON messaging.messages
    USING (
        core.rls_permissive() AND core.current_org_id() IS NULL
        OR (
            organization_id = core.current_org_id()
            AND core.can_read_channel(channel_id)
        )
    )
    WITH CHECK (
        core.rls_permissive() AND core.current_org_id() IS NULL
        OR (
            organization_id = core.current_org_id()
            AND core.can_read_channel(channel_id)
        )
    );

-- ---------------------------------------------------------------------
-- The links hanging off them
-- ---------------------------------------------------------------------
-- `message_links` carries no `channel_id`, so it inherits the rule
-- through its parent message. Its own policy would otherwise still be
-- organization-only, and the links are not innocuous: a `record` link
-- names a formula, batch, test or failure by code and label, so the row
-- discloses WHAT a conversation is about even to someone who cannot read
-- a word of it.
DROP POLICY IF EXISTS org_scope ON messaging.message_links;
DROP POLICY IF EXISTS parent_message_scope ON messaging.message_links;
CREATE POLICY parent_message_scope ON messaging.message_links
    USING (
        core.rls_permissive() AND core.current_org_id() IS NULL
        OR (
            organization_id = core.current_org_id()
            AND EXISTS (
                SELECT 1
                FROM messaging.messages m
                WHERE m.id = message_links.message_id
                  AND m.organization_id = message_links.organization_id
            )
        )
    )
    WITH CHECK (
        core.rls_permissive() AND core.current_org_id() IS NULL
        OR (
            organization_id = core.current_org_id()
            AND EXISTS (
                SELECT 1
                FROM messaging.messages m
                WHERE m.id = message_links.message_id
                  AND m.organization_id = message_links.organization_id
            )
        )
    );

-- ---------------------------------------------------------------------
-- 🔴 THE TWO INPUTS THE PREDICATE TRUSTS
-- ---------------------------------------------------------------------
-- Everything above tightens the `USING` side of `messaging.messages`
-- while leaving the `WITH CHECK` side of the tables `can_read_channel`
-- READS at organization-only. An adversarial review of this migration
-- found that this is not a backstop at all for the direct-message half:
-- both of its inputs are writable by `evercoat_app`, which holds
-- `GRANT SELECT, INSERT, UPDATE ON ALL TABLES IN SCHEMA messaging`
-- (022:511).
--
-- H1 — SELF-ENROLMENT. `messaging.channel_members` kept 022's org-only
--      policy, so a caller could simply insert their own membership row
--      for somebody else's direct channel and `can_read_channel` would
--      then answer TRUE. Channel ids are not secret: the `channels`
--      policy deliberately shows every `direct` row to the whole
--      organization, on the stated grounds that membership governs them.
--
-- H2 — RETYPING THE CHANNEL. Nothing made `channel_type` immutable, and
--      the `channels` policy's WITH CHECK is organization-only, so one
--      `UPDATE messaging.channels SET channel_type = 'announcement'`
--      took the `c.channel_type <> 'direct'` branch and exposed the
--      whole conversation to every member of the organization.
--
-- Neither is reachable over HTTP — `create_channel` is the only writer
-- of `channel_members` and inserts only for a channel id it generated
-- itself, and no route updates `channels` at all. But "not reachable
-- over HTTP" is precisely the assurance this layer exists to stop
-- depending on. §1 of SECURITY.md asks what happens when the
-- application layer fails.

-- --- H1 -------------------------------------------------------------
-- 🔴 WHY THE `created_by` BRANCH IS NOT A HOLE, AND WHY IT IS NEEDED.
--
-- The obvious rule — "you may only add a member to a channel you can
-- already read" — CANNOT BOOTSTRAP A DIRECT CHANNEL. `WITH CHECK`
-- subqueries do not see the row the same command is inserting, so the
-- creator's own first membership row would be refused: at that instant
-- nobody is a member, so `can_read_channel` is false, and
-- `create_channel` would fail outright for every direct message. That
-- version of the fix was proposed and rejected here because it breaks
-- the feature it is meant to protect.
--
-- `created_by` is the bootstrap, and it is exactly as narrow as it needs
-- to be: it is set by the INSERT in `create_channel` from the
-- authenticated actor, it is never updatable (the trigger below), and an
-- attacker looking at somebody else's direct channel is not its creator.
-- So the creator may populate the conversation, a participant may add
-- others, and a stranger can do neither.
DROP POLICY IF EXISTS org_scope ON messaging.channel_members;
DROP POLICY IF EXISTS channel_scope ON messaging.channel_members;
CREATE POLICY channel_scope ON messaging.channel_members
    USING (
        core.rls_permissive() AND core.current_org_id() IS NULL
        OR (
            organization_id = core.current_org_id()
            -- Deliberately NOT `can_read_channel` here. That function
            -- reads this table, and putting it in this table's USING
            -- clause is the one arrangement that would recurse.
            AND EXISTS (
                SELECT 1 FROM messaging.channels c
                WHERE c.id = channel_members.channel_id
            )
        )
    )
    WITH CHECK (
        core.rls_permissive() AND core.current_org_id() IS NULL
        OR (
            organization_id = core.current_org_id()
            AND (
                core.can_read_channel(channel_id)
                OR EXISTS (
                    SELECT 1 FROM messaging.channels c
                    WHERE c.id = channel_members.channel_id
                      AND c.created_by = core.current_user_id()
                )
            )
        )
    );

-- --- H2 -------------------------------------------------------------
-- `channel_type` is a CONFIDENTIALITY CONTROL, not an attribute: it is
-- what decides whether membership or the project predicate governs the
-- conversation. `project_id` is the same thing for project channels, and
-- `organization_id` is the tenant. None of the three may ever change,
-- and `created_by` joins them because the policy above now depends on it.
--
-- Nothing in the application updates this table at all, so this trigger
-- costs nothing and forbids only what no legitimate path does.
CREATE OR REPLACE FUNCTION messaging.deny_channel_retyping() RETURNS TRIGGER
    LANGUAGE plpgsql AS $fn$
BEGIN
    IF NEW.channel_type    IS DISTINCT FROM OLD.channel_type
       OR NEW.project_id      IS DISTINCT FROM OLD.project_id
       OR NEW.organization_id IS DISTINCT FROM OLD.organization_id
       OR NEW.created_by      IS DISTINCT FROM OLD.created_by
    THEN
        RAISE EXCEPTION
            'a channel cannot be retyped, re-tenanted, moved between projects '
            'or re-attributed; these decide who may read the conversation'
            USING ERRCODE = 'insufficient_privilege';
    END IF;
    RETURN NEW;
END
$fn$;

DROP TRIGGER IF EXISTS channels_keep_their_scope ON messaging.channels;
CREATE TRIGGER channels_keep_their_scope
    BEFORE UPDATE ON messaging.channels
    FOR EACH ROW EXECUTE FUNCTION messaging.deny_channel_retyping();

COMMIT;
