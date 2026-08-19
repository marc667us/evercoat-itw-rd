-- 023 — the append-only guard must name the table it actually guarded.
--
-- `audit.deny_mutation()` was written in 001 for exactly one table and
-- hardcoded its name into the message. Migration 022 then reused it —
-- correctly, it is the right mechanism — on `ai.msd_turns` and
-- `ai.msd_evidence`. The result is a refusal that says:
--
--     audit.events is append-only; DELETE is not permitted
--
-- ...when the statement was `DELETE FROM ai.msd_evidence`.
--
-- 🔴 AN ERROR MESSAGE THAT NAMES THE WRONG TABLE SENDS THE READER TO THE
-- WRONG PLACE. This one cost a CI round trip: the failure was read as
-- "something is deleting audit rows", and the audit path was searched
-- before the real cause — a correctly-guarded MSD table — was found. A
-- guard reused across tables cannot describe itself with a literal.
--
-- The behaviour is unchanged. Only the message becomes true.

CREATE OR REPLACE FUNCTION audit.deny_mutation() RETURNS TRIGGER
    LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION
        '%.% is append-only; % is not permitted',
        TG_TABLE_SCHEMA, TG_TABLE_NAME, TG_OP
        USING ERRCODE = 'insufficient_privilege';
END
$$;
