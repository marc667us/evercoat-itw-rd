"""Migration 034 — an unscoped session reads the system audit chain, and only it.

🔴 THIS FILE EXISTS BECAUSE THE MIGRATION MAY NOT PERFORM THIS CHECK ITSELF.

034's first version verified its own effect by inserting two probe rows and
reading them back under `SET LOCAL ROLE evercoat_app`. Codex refused it, and
was right: `audit.events` is append-only by trigger, so those rows can never be
removed -- confirmed, `DELETE` raises *"audit.events is append-only"*. A
security migration was writing permanent fake history into the one table whose
whole purpose is to be trustworthy about who did what, including a row bearing
an organization id that exists nowhere.

Two of those rows are in the local development database permanently and cannot
be deleted. Nothing is deployed, and CI rebuilds from empty, so the blast
radius stopped there. The migration now performs a **catalog** assertion only;
the behavioural proof lives here, where the fixture rolls back.

**A migration against an immutable ledger may inspect, never write.**
"""

from __future__ import annotations

import uuid

from sqlalchemy import text


def _insert(session, org: uuid.UUID | None, label: str) -> int:
    return int(
        session.execute(
            text(
                """
                INSERT INTO audit.events
                    (organization_id, action, entity_type, entity_id,
                     prev_hash, row_hash)
                VALUES (:org, 'test.034_scope', 'fixture', :label, '', '')
                RETURNING id
                """
            ),
            {"org": org, "label": label},
        ).scalar_one()
    )


def _scope(session, org: uuid.UUID | None) -> None:
    session.execute(
        text("SELECT set_config('app.current_org', :v, true)"),
        {"v": "" if org is None else str(org)},
    )


def test_an_unscoped_session_reads_the_system_chain(app_session) -> None:
    """The platform's own writer must be able to read what it wrote.

    Before 034 this failed on the RETURNING rather than the INSERT: the WITH
    CHECK policy permitted the write and the USING policy refused the read
    back. `INSERT ... RETURNING` is a READ -- the lesson this platform logged
    on 2026-08-19, resurfacing one layer down.
    """
    _scope(app_session, None)
    row_id = _insert(app_session, None, "SYSTEM")

    seen = app_session.execute(
        text("SELECT count(*) FROM audit.events WHERE id = :i"), {"i": row_id}
    ).scalar_one()

    assert seen == 1, (
        "an unscoped session cannot read the system-chain row it just wrote. "
        "Migrations, maintenance scripts and the bootstrap path all write here "
        "with RETURNING, so this is a write failure, not only a read failure."
    )


def test_an_unscoped_session_reads_only_the_system_chain(app_session) -> None:
    """🔴 The assertion that stops 034 being a reopening of the 032 hole.

    Before 032, an unscoped session saw **every tenant's** audit rows. 034
    widened the policy again, so the load-bearing question is precisely how
    far: it must admit the NULL-organization system chain and nothing else.
    """
    org = uuid.uuid4()

    _scope(app_session, org)
    tenant_row = _insert(app_session, org, "TENANT")

    _scope(app_session, None)
    visible = app_session.execute(
        text("SELECT count(*) FROM audit.events WHERE id = :i"), {"i": tenant_row}
    ).scalar_one()

    assert visible == 0, (
        "an unscoped session can read a TENANT-owned audit row. 034 was meant "
        "to admit only the system chain; this is the cross-tenant hole 032 "
        "closed, reopened."
    )


def test_a_scoped_session_does_not_see_the_system_chain(app_session) -> None:
    """The other direction, which NULL-safe equality could plausibly break.

    `IS NOT DISTINCT FROM` is symmetric, so it is worth proving it does not
    also hand the system chain to every tenant -- platform history is not a
    tenant's to read.
    """
    _scope(app_session, None)
    system_row = _insert(app_session, None, "SYSTEM_FOR_SCOPED_TEST")

    _scope(app_session, uuid.uuid4())
    visible = app_session.execute(
        text("SELECT count(*) FROM audit.events WHERE id = :i"), {"i": system_row}
    ).scalar_one()

    assert visible == 0, (
        "a tenant-scoped session can read the SYSTEM audit chain. Platform "
        "history is not tenant-readable."
    )


def test_the_policy_kept_no_permissive_branch(owner_session) -> None:
    """034 must have REPLACED the escape hatch, not preserved it.

    A policy still naming `core.rls_permissive()` would mean 034 quietly
    carried forward the construct 032 exists to remove.
    """
    qual = owner_session.execute(
        text(
            "SELECT pg_get_expr(polqual, polrelid) FROM pg_policy "
            "WHERE polrelid = 'audit.events'::regclass "
            "AND polname = 'audit_org_isolation'"
        )
    ).scalar_one()

    assert "rls_permissive" not in qual.lower(), (
        f"audit_org_isolation still references core.rls_permissive(): {qual}"
    )
    # PostgreSQL normalises `a IS NOT DISTINCT FROM b` to
    # `NOT (a IS DISTINCT FROM b)` before storing it, so the stored expression
    # never contains the text written in the migration. Assert the normalised
    # shape -- both halves, since `IS DISTINCT FROM` WITHOUT the negation would
    # be the exact inverse of the intended policy.
    lowered = qual.lower()
    assert "is distinct from" in lowered, (
        f"audit_org_isolation does not use DISTINCT FROM at all: {qual}"
    )
    assert "not" in lowered, (
        "audit_org_isolation uses IS DISTINCT FROM WITHOUT the negation, which "
        f"is the exact inverse of the intended policy: {qual}"
    )
