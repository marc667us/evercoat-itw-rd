-- ---------------------------------------------------------------------
-- 026 — An MSD conversation is exactly as private as its thread
-- ---------------------------------------------------------------------
--
-- 🔴 THE DEFECT, AND IT IS MIGRATION 025's TWIN
--
-- Migration 022 gave `ai.msd_threads` an OWNER-scoped policy and stated
-- the intent in its own comment:
--
--     "An MSD thread is visible to its OWNER and to nobody else, even
--      inside the same project. A conversation in which somebody explored
--      their own half-formed ideas is not a shared record, and §7's
--      boundary is per-user rather than per-project."
--
-- Then, in the same file, a DO-block loop gave `ai.msd_turns` and
-- `ai.msd_evidence` policies carrying only `organization_id`.
--
-- So the ROOM was private to its owner and the WORDS SAID IN IT were
-- readable by every member of the organization holding a thread id. The
-- comment describes a boundary the schema did not implement — exactly
-- the shape migration 025 closed for `messaging.messages`, in the file
-- that closed it, on the tables immediately below it in the same loop.
--
-- 🔴 `ai.msd_evidence` IS THE SHARPER HALF.
--
-- It is not merely a record of which rows were cited: it stores an
-- `excerpt`, up to 500 characters of the cited record's own content
-- (`app/domains/msd/retrieval.py`). Those excerpts are retrieved inside
-- the ASKER's authorization boundary — which is correct — and were then
-- readable organization-wide, so a colleague outside a restricted
-- project could read extracts of its formulations by reading somebody
-- else's evidence rows.
--
-- That is precisely what `IMPLEMENTATION_PLAN.md` §J item 5 warns about:
-- *"MSD authorization provenance (F33) across chunks, embeddings,
-- caches, conversation memory, tool outputs and model datasets."*
-- Retrieval was filtered before the model saw anything, and the RECORD OF
-- WHAT IT SAW was not.
--
-- Found while building the MSD routes — the leak would have shipped with
-- the first conversation.

BEGIN;

-- ---------------------------------------------------------------------
-- The predicate
-- ---------------------------------------------------------------------
-- SECURITY INVOKER, for the same reason `core.can_read_channel` is: the
-- answer must be produced BY the caller's own RLS view of
-- `ai.msd_threads`. As DEFINER it would see every thread regardless of
-- `owner_scope` and return TRUE for exactly the rows it exists to refuse.
CREATE OR REPLACE FUNCTION core.can_read_msd_thread(p_thread UUID) RETURNS BOOLEAN
    LANGUAGE sql STABLE
    SECURITY INVOKER
    SET search_path = ai, core, pg_temp
AS $$
    SELECT EXISTS (
        SELECT 1 FROM ai.msd_threads t WHERE t.id = p_thread
    )
$$;

COMMENT ON FUNCTION core.can_read_msd_thread(UUID) IS
    'May the current caller read this MSD thread? SECURITY INVOKER on '
    'purpose: the answer comes from the caller''s own RLS view of '
    'ai.msd_threads, whose owner_scope policy admits the owner alone. '
    'See migration 026.';

-- ---------------------------------------------------------------------
-- The turns
-- ---------------------------------------------------------------------
-- Replaced, not added to: two permissive policies on one table are OR-ed
-- together, so leaving `org_scope` in place would make this decorative.
DROP POLICY IF EXISTS org_scope ON ai.msd_turns;
DROP POLICY IF EXISTS thread_scope ON ai.msd_turns;
CREATE POLICY thread_scope ON ai.msd_turns
    USING (
        core.rls_permissive() AND core.current_org_id() IS NULL
        OR (
            organization_id = core.current_org_id()
            AND core.can_read_msd_thread(thread_id)
        )
    )
    WITH CHECK (
        core.rls_permissive() AND core.current_org_id() IS NULL
        OR (
            organization_id = core.current_org_id()
            AND core.can_read_msd_thread(thread_id)
        )
    );

-- ---------------------------------------------------------------------
-- The evidence
-- ---------------------------------------------------------------------
-- `msd_evidence` carries no `thread_id`, so it inherits through its turn
-- — which now inherits through its thread. The excerpt is the reason
-- this matters: it is content, not just a pointer.
DROP POLICY IF EXISTS org_scope ON ai.msd_evidence;
DROP POLICY IF EXISTS turn_scope ON ai.msd_evidence;
CREATE POLICY turn_scope ON ai.msd_evidence
    USING (
        core.rls_permissive() AND core.current_org_id() IS NULL
        OR (
            organization_id = core.current_org_id()
            AND EXISTS (
                SELECT 1 FROM ai.msd_turns t
                WHERE t.id = msd_evidence.turn_id
                  AND t.organization_id = msd_evidence.organization_id
            )
        )
    )
    WITH CHECK (
        core.rls_permissive() AND core.current_org_id() IS NULL
        OR (
            organization_id = core.current_org_id()
            AND EXISTS (
                SELECT 1 FROM ai.msd_turns t
                WHERE t.id = msd_evidence.turn_id
                  AND t.organization_id = msd_evidence.organization_id
            )
        )
    );

COMMIT;
