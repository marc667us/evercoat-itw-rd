-- =====================================================================
-- 061 — A TECHNICAL THREAD MUST NAME ITS PROJECT (I21)
-- =====================================================================
--
-- 022 wrote the rule and applied it to one channel type:
--
--     "A PROJECT channel must name its project: it is the only thing that
--      lets RLS apply that project's confidentiality to the conversation.
--      Without it, a discussion of a restricted formulation would be
--      readable by the whole organization."
--
-- The constraint it wrote says `channel_type <> 'project' OR project_id IS
-- NOT NULL`, which leaves `technical_thread` free to carry a NULL project.
--
-- 🔴 AND THE POLICY TREATS A NULL PROJECT AS ORGANIZATION-WIDE.
--
-- `project_scope` on `messaging.channels` reads:
--
--     project_id IS NULL
--     OR EXISTS (... p.confidentiality = 'normal' OR is_project_member(p.id))
--
-- That is correct for `direct` and `announcement`, which 022 says are
-- governed by channel membership instead. For a technical thread it is the
-- exact hole the paragraph above was written to close: a thread ABOUT a
-- restricted formulation, carrying no project, is readable by everyone in
-- the organization.
--
-- ⚠️ AND `thread_for_record` IS FIND-OR-CREATE.
--
-- It keys on `(entity_type, entity_id)`. So somebody holding a restricted
-- record's UUID could pre-create an organization-visible thread for it, and
-- every later "discuss this" click would find that thread rather than make a
-- scoped one. The discussion of a record they cannot read would then accrue
-- in a channel they can.
--
-- The precondition — knowing a restricted record's UUID without being able
-- to read it — is what kept this below the fix-now bar when it was raised as
-- N1 by the Supervisor. It is still a hole, and the fix is one constraint.
--
-- ⚠️ MEASURED BEFORE WRITTEN: `technical_thread` rows with a NULL project in
-- this database: 0. There is no backfill because there is nothing to
-- backfill, and the migration asserts that rather than assuming it — on an
-- installation that DOES have such rows, this must fail loudly rather than
-- silently leave them.
-- =====================================================================

BEGIN;

-- The assertion first: adding a constraint to data that violates it fails
-- with PostgreSQL's own message, which names the constraint and not the
-- reason. This names the reason.
DO $$
DECLARE
    offenders BIGINT;
BEGIN
    SELECT count(*) INTO offenders
      FROM messaging.channels
     WHERE channel_type = 'technical_thread' AND project_id IS NULL;

    IF offenders > 0 THEN
        RAISE EXCEPTION
            '% technical_thread channels carry no project and are therefore '
            'readable organization-wide. Each needs its project set — or, if '
            'the record it discusses is gone, archiving — before this '
            'constraint can hold. They are not deleted here: a conversation '
            'is a record.', offenders;
    END IF;
END
$$;

ALTER TABLE messaging.channels
    DROP CONSTRAINT IF EXISTS channels_thread_channel_has_a_project;

-- 🔴 A SEPARATE CONSTRAINT, NOT A WIDENING OF THE EXISTING ONE.
--
-- Extending `channels_project_channel_has_a_project` to cover both types
-- would have been fewer lines and would have made the failure message say
-- "project channel" while refusing a technical thread. A constraint that
-- misnames what it refused sends the next reader to the wrong rule.
ALTER TABLE messaging.channels
    ADD CONSTRAINT channels_thread_channel_has_a_project CHECK (
        channel_type <> 'technical_thread' OR project_id IS NOT NULL
    );

COMMENT ON CONSTRAINT channels_thread_channel_has_a_project
    ON messaging.channels IS
    'I21: a technical thread with no project is visible organization-wide, '
    'because project_scope treats a NULL project as unscoped. A thread about '
    'a restricted record must inherit that record project''s confidentiality.';

COMMIT;
