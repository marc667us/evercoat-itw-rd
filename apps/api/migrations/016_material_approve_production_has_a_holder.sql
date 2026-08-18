-- 016_material_approve_production_has_a_holder.sql
-- =====================================================================
-- `material.approve_production` existed and NO ROLE HELD IT.
--
-- Found while wiring the Slice 3 status endpoint, by asking this
-- project's standing question of a permission rather than of a role:
-- WHICH PRODUCTION PATH USES IT? Migration 002 defines the code --
--
--     ('material.approve_production','material',
--      'Promote a material to production_approved')
--
-- -- and then grants it to none of the ten seeded roles. Chemist has
-- create/edit, Lead has approve_lab, QA has restrict, Procurement has
-- create/edit/supplier.manage. Nobody has approve_production.
--
-- So `preferred`, one of the five material statuses the web already
-- renders, was a state NO USER OF THIS SYSTEM COULD EVER SET. Not
-- hidden, not permission-denied for most people -- unreachable, for
-- everyone, permanently.
--
-- This is the sixth instance of that defect class on this platform. The
-- other five were roles with no write path (`customer`, `supplier_owner`,
-- `fleet_administrator`, `insurance_assessor`/`towing_operator`,
-- `platform_administrator`). This one is its mirror image: a write path
-- with no holder. The question that catches both is the same one.
--
-- WHY QA, AND NOT PROCUREMENT OR THE LEAD
-- ---------------------------------------
-- `qa_compliance_officer` already holds `material.restrict` -- the
-- NEGATIVE control over whether a material may be used. Splitting the
-- positive and negative halves of one judgement between two roles means
-- one person can bless a material for commercial products and a different
-- one must withdraw it, with neither able to see the other's reasoning as
-- part of their own authority.
--
-- Procurement was the other candidate and is wrong for a reason worth
-- writing down: `procurement_specialist` holds `material.create` and
-- `material.edit`, so granting it approve_production would let the same
-- person enter a material's data AND declare it fit for commercial
-- production. That is precisely the segregation of duties CLAUDE.md
-- section 9 requires at release authority, and a raw material entering a
-- released product is inside that boundary.
--
-- The Lead was the third candidate and is also wrong: the Lead holds
-- `material.approve_lab`, and the two approvals exist as separate
-- permissions specifically so that laboratory use and commercial
-- production use are separate decisions. One role holding both collapses
-- the distinction the schema went to the trouble of making.
--
-- WHAT STOPS THIS RECURRING
-- -------------------------
-- `tests/db/test_002_roles_permissions.py`, which migration 002's own
-- closing comment has claimed exists since Slice 1 and which DOES NOT
-- EXIST. That comment lists five properties it says are "verified by"
-- that file, including "every permission here is referenced somewhere in
-- source (guards against inert controls that read as real in an audit)".
-- A comment claiming a rule the code does not implement is this
-- codebase's most-repeated defect, and it had been sitting in the file
-- that defines the authorization model.
--
-- The file is written in this change, with a SIXTH property the original
-- comment did not claim and which is the one that would have caught this:
-- every permission must have at least one holder.
-- =====================================================================

BEGIN;

INSERT INTO core.role_permissions (role_id, permission_id)
SELECT r.id, p.id
FROM core.roles r
CROSS JOIN core.permissions p
WHERE r.code = 'qa_compliance_officer'
  AND p.code = 'material.approve_production'
ON CONFLICT DO NOTHING;

-- Refuse to commit if the grant did not land. A migration whose only
-- effect is an INSERT that silently matched zero rows -- because a role
-- code changed, or the permission was renamed -- would report success and
-- leave the hole exactly where it was. That is the "step gated on a
-- condition that has never been true" shape already recorded against this
-- platform.
DO $verify$
DECLARE holders INT;
BEGIN
    SELECT count(*) INTO holders
    FROM core.role_permissions rp
    JOIN core.permissions p ON p.id = rp.permission_id
    WHERE p.code = 'material.approve_production';

    IF holders = 0 THEN
        RAISE EXCEPTION
            'material.approve_production still has no holder after 016; '
            'check that the role code qa_compliance_officer and the permission '
            'code both still exist in core.roles / core.permissions';
    END IF;
END
$verify$;

COMMIT;
