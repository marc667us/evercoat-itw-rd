-- 007_audit_canonical_json.sql
-- =====================================================================
-- Fix: the audit hash chain broke on every row carrying a JSON payload.
--
-- THE BUG. `audit.canonical_content()` serialised the JSONB states with
-- `::TEXT`, and `app/core/audit.py` serialised the same dicts with
-- `json.dumps(sort_keys=True, separators=(",", ":"))`. Those two
-- renderings disagree in TWO independent ways:
--
--   separators   PostgreSQL: {"stage": "REQUIREMENTS", "rework": false}
--                Python:     {"rework":false,"stage":"REQUIREMENTS"}
--
--   key order    PostgreSQL orders jsonb keys by LENGTH, then bytewise:
--                  '{"zz":1,"a":2,"mmm":3}'::jsonb -> {"a":2,"zz":1,"mmm":3}
--                Python sorts alphabetically:
--                  -> {"a":2,"mmm":3,"zz":1}
--
-- The second cannot be reconciled by adjusting separators. They are
-- different orderings, so the two sides could never agree on any object
-- with more than one key.
--
-- WHY IT HID FOR SO LONG. Every audit row written before Slice 2 had
-- NULL previous_state and new_state, and NULL renders as '' on both
-- sides. `test_python_and_sql_agree_on_the_hash` used exactly such a
-- fixture row and passed honestly while the defect sat underneath it.
-- The moment real domain events started writing payloads -- stage
-- transitions, requirement approvals -- every one of those rows failed
-- verification, and the chain reported tampering that had not happened.
--
-- A tamper-evidence mechanism that cries wolf is worse than none: the
-- first response to a real break would be "the hash thing is flaky
-- again".
--
-- THE FIX. `audit.jsonb_canonical()` renders JSONB the way Python does
-- -- alphabetically sorted keys, compact separators -- recursively, so
-- nested objects and arrays match too. Both sides keep computing the
-- hash independently, which is the point of having two.
--
-- EXISTING ROWS. Rows written before this migration used the old SQL
-- rendering and will not verify against the new one. They are dev data
-- here. In a deployed environment this migration is a DELIBERATE,
-- RECORDED CHAIN BREAK: verify the chain before applying, note the last
-- good id, and treat the discontinuity as expected rather than as
-- evidence of tampering.
-- =====================================================================

BEGIN;

CREATE OR REPLACE FUNCTION audit.jsonb_canonical(doc JSONB)
    RETURNS TEXT
    LANGUAGE plpgsql
    IMMUTABLE
AS $$
DECLARE
    result TEXT;
BEGIN
    IF doc IS NULL THEN
        RETURN '';
    END IF;

    CASE jsonb_typeof(doc)
        WHEN 'object' THEN
            -- Keys sorted ALPHABETICALLY (not by length, which is what
            -- jsonb::text does) and joined without spaces, matching
            -- json.dumps(sort_keys=True, separators=(",", ":")).
            SELECT COALESCE(
                '{' || string_agg(
                    to_json(kv.key)::text || ':' || audit.jsonb_canonical(kv.value),
                    ',' ORDER BY kv.key
                ) || '}',
                '{}'
            )
            INTO result
            FROM jsonb_each(doc) AS kv;

        WHEN 'array' THEN
            -- Array order is meaningful and preserved.
            SELECT COALESCE(
                '[' || string_agg(audit.jsonb_canonical(e.value), ','
                                  ORDER BY e.ordinality) || ']',
                '[]'
            )
            INTO result
            FROM jsonb_array_elements(doc) WITH ORDINALITY AS e(value, ordinality);

        ELSE
            -- Scalars: jsonb's own rendering already matches Python for
            -- strings, numbers, booleans and null.
            result := doc::text;
    END CASE;

    RETURN result;
END
$$;


-- Rebuild canonical_content to use it. Field order is unchanged --
-- that half of the contract was always correct.
CREATE OR REPLACE FUNCTION audit.canonical_content(
    p_organization_id UUID, p_user_id UUID, p_role_code TEXT,
    p_action TEXT, p_entity_type TEXT, p_entity_id TEXT,
    p_previous_state JSONB, p_new_state JSONB, p_reason TEXT,
    p_occurred_at TIMESTAMPTZ
) RETURNS TEXT LANGUAGE sql IMMUTABLE AS $$
    SELECT concat_ws('|',
        COALESCE(p_organization_id::TEXT, ''),
        COALESCE(p_user_id::TEXT, ''),
        COALESCE(p_role_code, ''),
        COALESCE(p_action, ''),
        COALESCE(p_entity_type, ''),
        COALESCE(p_entity_id, ''),
        audit.jsonb_canonical(p_previous_state),
        audit.jsonb_canonical(p_new_state),
        COALESCE(p_reason, ''),
        COALESCE(to_char(p_occurred_at AT TIME ZONE 'UTC',
                         'YYYY-MM-DD"T"HH24:MI:SS.US'), '')
    )
$$;

COMMIT;
