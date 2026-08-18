"""The authorization model's invariants -- the tests migration 002 said existed.

WHY THIS FILE EXISTS
--------------------
`migrations/002_seed_roles_permissions.sql` ends with this comment, and
has since Slice 1:

    -- Verified by tests/db/test_002_roles_permissions.py:
    --   * every permission code referenced in application source exists here
    --   * every permission here is referenced somewhere in source
    --   * no role holds both test.approve_development and test.approve_qa
    --   * product_development_chemist does NOT hold product.release
    --   * product_development_engineer does NOT hold formula.modify_draft
    --   * administrator does NOT hold product.release or test.confirm

**That file did not exist.** Not one of those six properties was checked
by anything. The comment sat at the bottom of the file that defines the
entire authorization model, describing a safety net made of prose.

This is the defect class this repository names most often -- a comment
asserting a guarantee the code does not provide -- and finding it inside
the RBAC seed is the worst place for it, because every other security
claim in the product is downstream of these grants.

Written while building Slice 3, after the missing net let a real defect
through: `material.approve_production` was defined and granted to NO ROLE,
so `preferred` -- one of the five material statuses the deployed site
already renders -- was a state no user could ever set. Migration 016
closes that; `test_every_permission_has_at_least_one_holder` is what makes
sure the next one cannot be introduced silently.

WHAT THIS FILE DOES AND DOES NOT CHECK -- stated exactly, because an
overclaim here is the very thing it was written to retire.

Implemented: every permission has a holder; every permission the
application CHECKS exists in the database; no role holds both development
and QA test approval; six load-bearing absences; the ten seeded roles.

**NOT implemented: the reverse direction** -- "every permission seeded here
is referenced somewhere in source". It would fail today and correctly so:
most of `batch.*`, `test.*`, `failure.*` and `product.release` belong to
Slices 4-7 and nothing checks them yet. Adding it with a large allowlist
would prove nothing, so it is named here as a gap rather than implemented
as theatre. Migration 002's closing comment still claims it and has been
amended to match.

WHICH SESSION AND WHY
---------------------
`owner_session`. These are assertions about the CONTENT of the RBAC
tables, not about tenant isolation, and `core.roles`, `core.permissions`
and `core.role_permissions` are global reference data with no
organization column. Isolation assertions must use `app_session`; this
file has none.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session

# apps/api/tests/db/this_file.py -> apps/api
API_ROOT = Path(__file__).resolve().parents[2]
APP_SOURCE = API_ROOT / "app"

# ONLY THE PLACES A PERMISSION IS ACTUALLY CHECKED.
#
# 🔴 THE OBVIOUS IMPLEMENTATION IS WRONG, AND WAS WRITTEN FIRST. Scanning
# for every `'domain.thing'` string literal in `app/` looks equivalent and
# is not: AUDIT ACTION NAMES HAVE THE SAME SHAPE. `material.created`,
# `formula.created`, `admin.role_granted`, `opportunity.decided` and 22
# others are audit actions, not permissions, and the naive scan reported
# every one of them as "a permission the application checks that migration
# 002 does not seed". Twenty-six false failures, in the test whose whole
# purpose is to be trusted about the authorization model.
#
# So this matches the CALL SITES instead. A permission is a string handed
# to `require_permission(...)` or to `.has(...)`; anything else with a dot
# in it is some other kind of name.
_CHECK_SITE = re.compile(r"(?:require_permission|\.has)\s*\(([^)]*)\)", re.DOTALL)
_QUOTED = re.compile(r"""["']([a-z_]+\.[a-z_]+)["']""")


def _permission_codes_checked_in_source() -> set[str]:
    """Every permission code the application actually gates on.

    Read from the source text rather than by importing and introspecting,
    because a route's dependency is evaluated at import time and a typo in
    a permission string is exactly the thing that must be caught without
    running the application.
    """
    found: set[str] = set()
    for path in APP_SOURCE.rglob("*.py"):
        if "__pycache__" in path.parts:
            continue
        text_content = path.read_text(encoding="utf-8")
        for call in _CHECK_SITE.finditer(text_content):
            found.update(_QUOTED.findall(call.group(1)))

    # `POST /materials/{id}/status` resolves its permission from a table
    # rather than naming it in the call, because the required authority
    # depends on the requested status. The table is imported rather than
    # pattern-matched: it IS the mapping, and a copy of it here would be
    # the second list that drifts from the first.
    from app.api.materials import STATUS_PERMISSION

    found.update(STATUS_PERMISSION.values())
    return found


# PERMISSIONS THAT DELIBERATELY HAVE NO HOLDER YET, and the slice that
# will give them one. Found by this test on its first run -- two more
# orphans beyond the one that prompted the file, both belonging to modules
# nothing has built.
#
# An allowlist weakens a check, so it is written to fail in BOTH
# directions: an entry that gains a holder must be removed, or the test
# fails as loudly as a new orphan would. That is what stops it becoming
# the place orphans go to be forgotten.
ORPHANED_UNTIL_THEIR_SLICE: dict[str, str] = {
    # Slice 5. Confirmation authority is the top of the test-approval
    # ladder and deliberately not folded into `test.approve_lead` or
    # `test.approve_qa`; which role holds it is a decision that belongs
    # with the approval-route templates, not with a guess made now.
    "test.confirm": "Slice 5 -- Testing, with the approval route templates",
    # Slice 8. Nothing can ingest into the Knowledge Library because the
    # Knowledge Library does not exist; `knowledge.promote` is granted
    # because promotion is referenced from Slice 7's messaging.
    "knowledge.ingest": "Slice 8 -- Knowledge Library and RAG",
}


@pytest.fixture(scope="module")
def seeded_permissions(owner_session: Session) -> set[str]:
    return {
        row[0] for row in owner_session.execute(text("SELECT code FROM core.permissions")).all()
    }


def test_every_permission_has_at_least_one_holder(owner_session: Session) -> None:
    """A permission no role holds is a control that can never be exercised.

    THE CHECK THAT WAS MISSING. `material.approve_production` was defined
    in migration 002 and granted to none of the ten seeded roles, which
    made the material status `preferred` unreachable by any production
    path -- not restricted, not permission-denied, unreachable. Migration
    016 grants it to `qa_compliance_officer`.

    The failure message names the orphans, because "0 != 0" tells whoever
    hits this nothing about which permission they have just orphaned.
    """
    orphans = [
        row[0]
        for row in owner_session.execute(
            text(
                """
                SELECT p.code
                FROM core.permissions p
                LEFT JOIN core.role_permissions rp ON rp.permission_id = p.id
                WHERE rp.permission_id IS NULL
                ORDER BY p.code
                """
            )
        ).all()
    ]
    unexpected = [code for code in orphans if code not in ORPHANED_UNTIL_THEIR_SLICE]
    assert unexpected == [], (
        "these permissions are held by no role, so no user can ever exercise "
        f"them: {', '.join(unexpected)}"
    )

    # The allowlist must not outlive its entries. A permission that HAS
    # been granted but is still listed here means the list is stale, and a
    # stale allowlist is how a real orphan hides behind a resolved one.
    stale = sorted(set(ORPHANED_UNTIL_THEIR_SLICE) - set(orphans))
    assert stale == [], (
        "ORPHANED_UNTIL_THEIR_SLICE lists permissions that now have holders; "
        f"remove them: {', '.join(stale)}"
    )


def test_every_permission_checked_in_source_exists_in_the_database(
    seeded_permissions: set[str],
) -> None:
    """A route guarding on a permission nobody can hold is a 403 forever.

    The direction that matters most: `require_permission("formula.aprove_lab")`
    with a typo denies every caller, and looks exactly like a correct
    authorization refusal in production.
    """
    # A final prefix filter, kept as a belt to the call-site braces: a
    # literal reaching a `.has(...)` on some object that is not a Principal
    # would otherwise be reported as a missing permission.
    domains = {code.split(".", 1)[0] for code in seeded_permissions}
    checked = {c for c in _permission_codes_checked_in_source() if c.split(".", 1)[0] in domains}

    unknown = sorted(checked - seeded_permissions)
    assert unknown == [], (
        "the application checks permissions that migration 002 does not seed, "
        f"so they can never be granted: {', '.join(unknown)}"
    )


def test_no_role_holds_both_development_and_qa_test_approval(owner_session: Session) -> None:
    """Independent QA review must be independent of development approval.

    Migration 002 states this and the source it came from is explicit that
    approval routes may demand DISTINCT persons. One role holding both
    turns a two-step route into a formality.
    """
    conflicted = [
        row[0]
        for row in owner_session.execute(
            text(
                """
                SELECT r.code
                FROM core.roles r
                WHERE EXISTS (
                        SELECT 1 FROM core.role_permissions rp
                        JOIN core.permissions p ON p.id = rp.permission_id
                        WHERE rp.role_id = r.id AND p.code = 'test.approve_development')
                  AND EXISTS (
                        SELECT 1 FROM core.role_permissions rp
                        JOIN core.permissions p ON p.id = rp.permission_id
                        WHERE rp.role_id = r.id AND p.code = 'test.approve_qa')
                ORDER BY r.code
                """
            )
        ).all()
    ]
    assert conflicted == [], (
        f"these roles hold both development and QA test approval: {', '.join(conflicted)}"
    )


@pytest.mark.parametrize(
    ("role_code", "forbidden", "why"),
    [
        (
            "product_development_chemist",
            "product.release",
            "a Chemist must not be able to release a commercial master formulation",
        ),
        (
            "product_development_engineer",
            "formula.modify_draft",
            "an Engineer triggers a revision through the Chemist rather than "
            "overwriting a composition",
        ),
        (
            "administrator",
            "product.release",
            "administering the system is not the authority to release a product",
        ),
        (
            "administrator",
            "test.confirm",
            "an admin account that can silently confirm a test is a governance hole",
        ),
        (
            "product_development_director",
            "formula.create",
            "the Director approves work and does not also perform it",
        ),
        (
            # Added by this file, not claimed by the original comment.
            # Migration 016 chose QA over Procurement precisely because
            # Procurement enters material data, and the same person must
            # not both enter it and declare it fit for production.
            "procurement_specialist",
            "material.approve_production",
            "whoever enters a material's data must not also approve it for "
            "commercial production (segregation of duties)",
        ),
    ],
)
def test_role_does_not_hold_permission(
    owner_session: Session, role_code: str, forbidden: str, why: str
) -> None:
    """Absences that are load-bearing.

    Each of these is enforced by NOT granting a permission, which is
    invisible in the migration -- there is nothing on the page to read.
    That is exactly why it needs a test: a future edit that adds the code
    to a role's list looks like a small convenience and silently removes a
    governance control.
    """
    held = owner_session.execute(
        text(
            """
            SELECT EXISTS (
                SELECT 1
                FROM core.role_permissions rp
                JOIN core.roles r       ON r.id = rp.role_id
                JOIN core.permissions p ON p.id = rp.permission_id
                WHERE r.code = :role AND p.code = :perm
            )
            """
        ),
        {"role": role_code, "perm": forbidden},
    ).scalar_one()

    assert held is False, f"{role_code} must not hold {forbidden}: {why}"


def test_all_ten_canonical_roles_are_seeded(owner_session: Session) -> None:
    """The ten roles the plan names, and no silent renaming of one.

    A role code is also a Keycloak realm role name. Renaming one here
    without renaming it there produces a token whose roles map to nothing,
    which presents as "this user has no permissions" rather than as a
    configuration error.
    """
    expected = {
        "product_development_chemist",
        "product_development_engineer",
        "product_development_lead",
        "product_development_director",
        "qa_compliance_officer",
        "laboratory_technician",
        "procurement_specialist",
        "production_engineer",
        "executive_viewer",
        "administrator",
    }
    actual = {
        row[0]
        for row in owner_session.execute(text("SELECT code FROM core.roles WHERE is_seeded")).all()
    }
    assert expected <= actual, f"missing seeded roles: {', '.join(sorted(expected - actual))}"
