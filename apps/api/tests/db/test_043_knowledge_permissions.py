"""Migration 043 — the knowledge tier's permissions, and who holds them.

🔴 THE DEFECT THIS WHOLE FILE IS ABOUT.

Migration 042 built the knowledge tier and NOTHING WROTE TO IT.
`ingest_document` was reachable only from a test file: no route, no CLI, no
job. On a deployed instance the table was permanently empty, MSD's knowledge
branch always fell through to its refusal, and the only observable effect of
the whole slice was one extra round-trip per question (I74).

That is the seventh instance of the class on this platform, and the question
that catches every one of them is the same: **which production path writes
it?** These tests are that question, asked of the permissions in a form that
runs.
"""

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.orm import Session

INGEST_HOLDERS = {
    "product_development_lead",
    "product_development_director",
    "qa_compliance_officer",
    "administrator",
}

VIEW_HOLDERS = INGEST_HOLDERS | {
    "product_development_chemist",
    "product_development_engineer",
    "laboratory_technician",
    "production_engineer",
    "executive_viewer",
}


def _holders(session: Session, code: str) -> set[str]:
    return set(
        session.execute(
            text(
                """
                SELECT r.code
                FROM core.role_permissions rp
                JOIN core.permissions p ON p.id = rp.permission_id
                JOIN core.roles r       ON r.id = rp.role_id
                WHERE p.code = :code
                """
            ),
            {"code": code},
        ).scalars()
    )


def test_both_knowledge_permissions_exist(owner_session: Session) -> None:
    """🔴 AND THEY PREDATE MIGRATION 043.

    This test first asserted the `knowledge` domain contained EXACTLY these
    two, and it failed on `knowledge.promote` -- which has been in migration
    002 since the beginning, along with both codes below. 043's own header
    said it "adds the two permissions", and that was simply wrong.

    Written as a subset for the honest reason: 043 does not own this domain,
    it fills in the holders. An exact-set assertion here would fail the next
    time somebody adds a knowledge permission for an unrelated feature, which
    is not a defect this file is entitled to have an opinion about.
    """
    codes = set(
        owner_session.execute(
            text("SELECT code FROM core.permissions WHERE domain = 'knowledge'")
        ).scalars()
    )
    assert {"knowledge.view", "knowledge.ingest"} <= codes, codes


def test_every_knowledge_permission_has_a_holder(owner_session: Session) -> None:
    """Migration 016's defect, asked of the new permissions.

    `material.approve_production` was defined in 002 and granted to nobody, and
    nothing noticed for fourteen migrations — so one of the five material
    statuses the web already rendered was a state NO USER could ever set. Not
    permission-denied for most people: unreachable, for everyone, permanently.
    """
    for code in ("knowledge.view", "knowledge.ingest"):
        assert _holders(owner_session, code), (
            f"{code} is held by no role, so every path behind it is unreachable "
            f"for everyone -- the defect migration 016 exists to document"
        )


def test_the_roles_holding_each_permission_are_the_intended_ones(
    owner_session: Session,
) -> None:
    """Stated as an exact set, so a widening is a failure and not a shrug.

    `ON CONFLICT DO NOTHING` makes `core._grant` idempotent, which also makes
    an accidental extra grant completely silent. An assertion on the exact set
    is the only thing that turns "somebody added chemist to ingest" into a red
    test rather than a quiet change in who decides what is CONFIDENTIAL.
    """
    assert _holders(owner_session, "knowledge.ingest") == INGEST_HOLDERS
    assert _holders(owner_session, "knowledge.view") == VIEW_HOLDERS


def test_the_largest_population_cannot_classify_a_document(
    owner_session: Session,
) -> None:
    """🔴 THE PROPERTY 043 ARGUES FOR, ASSERTED SEPARATELY FROM THE SET.

    Chemist and Engineer are the biggest group and the people most likely to
    paste in a supplier PDF mid-experiment. Ingestion is not "uploading a
    file" — it SETS the classification of text MSD will quote to whoever can
    retrieve it, and a mistaken `PUBLIC` on a competitor-sensitive note cannot
    be recalled once it has been quoted into somebody's answer.

    Written as its own test because the exact-set assertion above would also
    fail for a dozen unrelated reasons; this one fails for exactly this.
    """
    holders = _holders(owner_session, "knowledge.ingest")
    for role in ("product_development_chemist", "product_development_engineer"):
        assert role not in holders, (
            f"{role} can now set a document's classification. That is a "
            f"deliberate decision if intended -- update migration 043's "
            f"reasoning and this test together, not just this test."
        )
    # And the same roles CAN read, or the exclusion above would be a
    # capability they simply do not have rather than a boundary.
    view = _holders(owner_session, "knowledge.view")
    assert {"product_development_chemist", "product_development_engineer"} <= view


def test_the_grant_helper_did_not_survive_the_migration(
    owner_session: Session,
) -> None:
    """`core._grant` is scaffolding, created and dropped inside each migration.

    Left behind, it is a permission-granting function sitting in the schema
    with nothing owning it -- and the next migration's `CREATE OR REPLACE`
    would silently inherit whatever the last one left.
    """
    surviving = owner_session.execute(
        text("SELECT count(*) FROM pg_proc WHERE proname = '_grant'")
    ).scalar_one()
    assert surviving == 0, "core._grant outlived the migration that created it"
