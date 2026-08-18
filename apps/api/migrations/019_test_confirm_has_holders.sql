-- 019_test_confirm_has_holders.sql
-- =====================================================================
-- `test.confirm` was defined in migration 002 and held by NO ROLE.
--
-- It was found on the first run of `tests/db/test_002_roles_permissions.py`
-- -- the file that migration 002 had claimed existed since Slice 1 and
-- which did not -- alongside `knowledge.ingest`. Both were allowlisted in
-- `ORPHANED_UNTIL_THEIR_SLICE`, each with the slice that would assign it:
--
--     "test.confirm": "Slice 5 -- Testing, with the approval route templates"
--
-- This is Slice 5. The debt comes due, and the allowlist entry is removed
-- in the same change -- that test asserts in BOTH directions, so a
-- permission that gains a holder while still listed fails just as loudly
-- as a new orphan. That was deliberate when the allowlist was written,
-- precisely so it could not become the place orphans go to be forgotten.
--
-- WHO CONFIRMS, AND WHY THOSE THREE
-- ---------------------------------
-- `DATA_MODEL.md` §3.5 states the transition and its holders:
--
--     final_confirmed | false -> true | L / QA / D (`test.confirm`)
--                     | only from `approved`; never from
--                     | `conditionally_approved`
--
-- Lead, QA/Compliance and Director. Confirmation is the act that turns an
-- approved result into evidence the product may be released on, so it
-- sits with the three roles that carry release-side accountability.
--
-- 🔴 THE ADMINISTRATOR IS DELIBERATELY EXCLUDED, AND THAT ABSENCE IS
-- TESTED. Migration 002's own comment says it: "Administrator manages
-- configuration. It does NOT get product.release, test.confirm or
-- failure.accept_root_cause: administering the system is not the same
-- authority as making a technical decision, and an admin account that can
-- silently release a product is a governance hole."
-- `test_role_does_not_hold_permission` asserts it, so adding the
-- administrator here would fail the suite rather than pass quietly.
--
-- The Chemist and Engineer are excluded too. They hold
-- `test.approve_development`, and confirmation must not be reachable by
-- the same development-side authority that supplied an approval -- which
-- is the segregation ADR-019 requires and the reason authorization is on
-- permissions rather than role names.
-- =====================================================================

BEGIN;

INSERT INTO core.role_permissions (role_id, permission_id)
SELECT r.id, p.id
FROM core.roles r
CROSS JOIN core.permissions p
WHERE r.code IN (
        'product_development_lead',
        'qa_compliance_officer',
        'product_development_director'
      )
  AND p.code = 'test.confirm'
ON CONFLICT DO NOTHING;

-- Refuse to commit if the grant did not land. An INSERT that silently
-- matched zero rows -- because a role code changed, or the permission was
-- renamed -- would report success and leave the hole exactly where it
-- was. The same guard migration 016 carries, for the same reason.
DO $verify$
DECLARE holders INT;
BEGIN
    SELECT count(*) INTO holders
    FROM core.role_permissions rp
    JOIN core.permissions p ON p.id = rp.permission_id
    WHERE p.code = 'test.confirm';

    IF holders < 3 THEN
        RAISE EXCEPTION
            'test.confirm has % holder(s) after 019; expected 3 (lead, QA, director). '
            'Check that those role codes still exist in core.roles.', holders;
    END IF;

    -- And the exclusion is verified here too, not only in the test suite:
    -- a migration that granted it to the administrator by a copy-paste
    -- error would otherwise commit and be caught later, somewhere else.
    IF EXISTS (
        SELECT 1
        FROM core.role_permissions rp
        JOIN core.roles r       ON r.id = rp.role_id
        JOIN core.permissions p ON p.id = rp.permission_id
        WHERE p.code = 'test.confirm' AND r.code = 'administrator'
    ) THEN
        RAISE EXCEPTION
            'the administrator must not hold test.confirm; administering the '
            'system is not the authority to make a technical decision';
    END IF;
END
$verify$;

COMMIT;
