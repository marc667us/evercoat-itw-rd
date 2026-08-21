-- 029 — "opens OR LINKS" becomes a constraint, and the conversation order
--       gets an index that can actually serve it
--
-- Both parts were raised by the Supervisor against migration 028 and the §10
-- wiring in `open_failure_for_failed_test`.
--
-- ─────────────────────────────────────────────────────────────────────────
-- PART 1 — AT MOST ONE INVESTIGATION MAY NAME A TEST
-- ─────────────────────────────────────────────────────────────────────────
--
-- `open_failure_for_failed_test` documents the rule as "opens OR LINKS —
-- returns the existing investigation rather than opening a second, because two
-- investigations of one failure is two half-answers". That rule lived only in
-- application code, and the public `POST /api/failures` route accepts an
-- arbitrary `test_id`, so two engineers could each legitimately open an
-- investigation naming the same test.
--
-- 🔴 THE CONSEQUENCE WAS A PERMANENT LOCKOUT, NOT A DUPLICATE ROW. The link
-- lookup used `.one_or_none()`. With two rows it raised `MultipleResultsFound`,
-- which nothing catches — so completing that test raised, and raised again on
-- every retry, because the condition never cleared. A safety-critical path
-- (recording that a confirmation test failed) became permanently unavailable
-- for that test, and the only recovery was a database edit.
--
-- The service no longer depends on this index — it uses `LIMIT 1` and an
-- explicit ORDER BY, so it is correct against a database migrated only to 028.
-- This index makes the documented invariant TRUE rather than merely intended.
--
-- PARTIAL, on `test_id IS NOT NULL`: an investigation need not concern a test
-- at all (a batch deviation, a customer complaint), and NULLs must not collide
-- with each other.
--
-- ⚠️ IT CAN REFUSE TO BUILD, AND THAT IS THE POINT. If a database already
-- holds two investigations for one test, this migration FAILS rather than
-- picking a winner. Which of two human investigations to keep is a decision
-- for the people who opened them, not for a migration. The DO block below
-- reports the offending rows by id so the refusal is actionable instead of a
-- bare constraint error.

DO $$
DECLARE
    offenders TEXT;
BEGIN
    SELECT string_agg(format('test_id=%s has %s investigations', test_id, n), '; ')
      INTO offenders
      FROM (
          SELECT test_id, count(*) AS n
            FROM quality.failures
           WHERE test_id IS NOT NULL
           GROUP BY organization_id, test_id
          HAVING count(*) > 1
      ) dupes;

    IF offenders IS NOT NULL THEN
        RAISE EXCEPTION
            'cannot enforce one investigation per test: %. Merge or re-point '
            'these by hand -- choosing which to keep is not a migration''s '
            'decision to make.', offenders;
    END IF;
END $$;

CREATE UNIQUE INDEX IF NOT EXISTS failures_one_per_test_uk
    ON quality.failures (organization_id, test_id)
    WHERE test_id IS NOT NULL;

COMMENT ON INDEX quality.failures_one_per_test_uk IS
    'CLAUDE.md §10 "opens OR LINKS": at most one Failure Investigation may '
    'name a given test. Partial because an investigation need not concern a '
    'test at all. Before this existed, two rows made the link lookup raise '
    'MultipleResultsFound and the test could never be completed again.';


-- ─────────────────────────────────────────────────────────────────────────
-- PART 2 — AN INDEX THAT MATCHES THE ORDER 028 INTRODUCED
-- ─────────────────────────────────────────────────────────────────────────
--
-- 022 created `messages (channel_id, posted_at DESC)`. PostgreSQL can scan a
-- btree in either direction, so that index served the old `ORDER BY posted_at`
-- perfectly well. 028 added the `id` tiebreaker that makes the order total —
-- and `id` is not in that index, so the planner can no longer satisfy the sort
-- from it. Every channel read became a full sort of the channel's messages
-- with no LIMIT pushdown.
--
-- Not a correctness bug and not urgent at current volumes, but 028's header
-- was scrupulous about stating costs and did not state this one. Raised by the
-- Supervisor.
--
-- DESC on both columns to match `list_messages`, which now reads the NEWEST
-- page (see part 3 of the same change) and reverses it for display.

CREATE INDEX IF NOT EXISTS messages_channel_posted_id_idx
    ON messaging.messages (channel_id, posted_at DESC, id DESC);

COMMENT ON INDEX messaging.messages_channel_posted_id_idx IS
    'Serves list_messages'' total order (posted_at, id). 022''s '
    '(channel_id, posted_at DESC) cannot, because 028 added the id '
    'tiebreaker and id is not in it.';
