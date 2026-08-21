-- 028 — a conversation has ONE order, and it is the order it was written in
--
-- ─────────────────────────────────────────────────────────────────────────
-- WHAT WAS WRONG
-- ─────────────────────────────────────────────────────────────────────────
--
-- `messaging.messages.posted_at` defaulted to `now()`, and `list_messages`
-- ordered by `posted_at` alone with no tiebreaker.
--
-- 🔴 `now()` IS TRANSACTION-START TIME, NOT WALL-CLOCK TIME. It is constant
-- for the whole transaction — `SELECT now() = now()` inside a transaction is
-- TRUE. So every message written in a single transaction receives the
-- IDENTICAL timestamp, `ORDER BY posted_at` has nothing left to order them
-- by, and PostgreSQL is free to return them in any order it likes. The order
-- can differ between two runs of the same query on the same rows.
--
-- A conversation that renders in a different order each time it is opened is
-- not a conversation. A reply can appear above the message it answers, and a
-- withdrawal notice above the message it withdrew — which is exactly how this
-- was found: `test_a_withdrawn_message_leaves_the_conversation_readable`
-- failed against a local PostgreSQL while passing in CI, because the two
-- environments happened to return the same two rows in a different order.
-- CI had been passing on heap luck.
--
-- ─────────────────────────────────────────────────────────────────────────
-- THE FIX, IN TWO PARTS — BOTH ARE NECESSARY
-- ─────────────────────────────────────────────────────────────────────────
--
-- 1. `clock_timestamp()` instead of `now()`. This reads the actual clock at
--    the moment the row is inserted, so two messages written in one
--    transaction get two DIFFERENT and correctly ordered timestamps. This is
--    the part that makes the order right rather than merely repeatable.
--
-- 2. A tiebreaker on `id` in the query (see `list_messages`). Two rows can
--    still collide at the microsecond, and an ORDER BY that is not total is
--    not deterministic. This is the part that makes the order repeatable.
--
-- Neither alone is sufficient: (1) without (2) is almost always right and
-- occasionally arbitrary; (2) without (1) is always repeatable and, for
-- messages written in one transaction, repeatably WRONG.
--
-- ─────────────────────────────────────────────────────────────────────────
-- WHY THIS IS SAFE
-- ─────────────────────────────────────────────────────────────────────────
--
-- Changing a column DEFAULT affects only rows inserted afterwards. It does
-- not rewrite the table, does not take a lengthy lock, and does not touch a
-- single existing message. Existing rows keep the `now()` timestamps they
-- were written with; they are not made worse, and the ordering tiebreaker
-- gives them a stable order they did not have before.
--
-- The append-only trigger on `messaging.messages` refuses any UPDATE that
-- changes `posted_at` ("a message cannot be re-attributed or moved"). That
-- trigger is unaffected: a DEFAULT applies at INSERT, and no INSERT is
-- an UPDATE. Verified rather than assumed — see migration 022's
-- `messages_are_append_only` guard.
--
-- `notifications.created_at` and `channels.created_at` default to `now()`
-- and are ordered by DESC with no tiebreaker too. They are NOT changed here.
-- Both are ordered newest-first for display and neither has a test or a user
-- expectation of intra-transaction ordering; changing them would be an
-- unmeasured edit made on the strength of a nearby bug. Recorded in TODO.md
-- rather than done silently.

ALTER TABLE messaging.messages
    ALTER COLUMN posted_at SET DEFAULT clock_timestamp();

COMMENT ON COLUMN messaging.messages.posted_at IS
    'Wall-clock insert time from clock_timestamp(), NOT now(). now() is '
    'transaction-start time and is identical for every row written in one '
    'transaction, which left a conversation with no defined order. Always '
    'order by (posted_at, id) - the tiebreaker is required because two '
    'inserts can still share a microsecond.';
