"""Migration 011 — the audit chain is per organization, by construction.

These tests exist because the previous record of this defect named the
wrong cause. `TODO.md` said the chain "forks under concurrency" because
two transactions read the tail before either commits. That cannot happen:
`audit.chain_row()` takes `pg_advisory_xact_lock()`, which is held until
COMMIT, and the tail read that follows takes a fresh READ COMMITTED
snapshot.

The real mechanism was RLS. The trigger was SECURITY INVOKER, so its tail
read was filtered by `audit_org_isolation` and every writer chained onto
its own organization's tail. The chain was already per-organization —
nobody had chosen it, so nothing guaranteed it, and an UNSCOPED writer
(no `app.current_org`) fell through to the permissive branch, saw every
row, and spliced one tenant's chain onto another's.

A comment claiming engine semantics is a claim, not a check. These are
the checks.

All of this runs inside one transaction on one connection: chain
construction only needs the trigger to fire, and the trigger's tail read
sees the transaction's own uncommitted rows. `SET LOCAL` is re-issued
between inserts to switch organization context, which is exactly how
interleaved multi-tenant writes present to the trigger.

`audit.events.organization_id` carries no foreign key, so these use
synthetic organization ids rather than the `two_orgs` fixture. That
fixture writes through `owner_session`, a different connection whose rows
are invisible here until committed — and audit rows cannot be cleaned up
afterwards, because the table is append-only by trigger.
"""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError


def _set_org(session, org: uuid.UUID | None) -> None:
    """Switch the RLS organization context for the rest of the transaction.

    ``None`` sets the GUC to the empty string, which ``core.current_org_id()``
    maps to NULL — the unscoped case a migration or maintenance script
    presents.
    """
    value = "" if org is None else str(org)
    session.execute(text(f"SET LOCAL app.current_org = '{value}'"))


def _insert_unscoped(session, label: str) -> int:
    """Write a SYSTEM-chain row with no organization context.

    Split out so the scope switch is visible at the call site rather than
    hidden in an argument, since an unscoped audit write is the one case
    migration 013 deliberately restricted and 034 deliberately re-permitted
    for reads.
    """
    _set_org(session, None)
    return _insert(session, None, label)


def _insert(session, org: uuid.UUID | None, label: str) -> int:
    return int(
        session.execute(
            text(
                """
                INSERT INTO audit.events
                    (organization_id, action, entity_type, entity_id,
                     prev_hash, row_hash)
                VALUES (:org, 'test.chain_scope', 'fixture', :label, '', '')
                RETURNING id
                """
            ),
            {"org": org, "label": label},
        ).scalar_one()
    )


def _hashes(session, event_id: int, org: uuid.UUID | None = None) -> tuple[str, str]:
    """Read one row's chain hashes from the vantage point of ``org``.

    🔴 THE ``org`` ARGUMENT EXISTS BECAUSE THESE TESTS USED TO READ UNSCOPED,
    AND "UNSCOPED" USED TO MEAN "EVERY TENANT".

    Before migration 032, ``core.rls_permissive()`` returned TRUE, so a
    session with no organization GUC saw every row in the table. Several tests
    here leaned on that to compare two tenants' chains in one read, with a
    comment explaining that neither tenant's context could see both rows --
    which was true, and was exactly the hole 032 closed.

    So the scope is now named per read. A row is read from ITS OWN tenant's
    vantage point, which is both the only thing now permitted and a more
    honest test: it asserts what a legitimate reader of that tenant sees.
    """
    _set_org(session, org)
    row = (
        session.execute(
            text("SELECT prev_hash, row_hash FROM audit.events WHERE id = :i"),
            {"i": event_id},
        )
        .mappings()
        .one()
    )
    return row["prev_hash"], row["row_hash"]


def test_chain_links_within_an_organization_and_skips_another(app_session):
    """Org A's rows must link to each other across an interleaved org B row.

    This is the property the whole migration is about. If B1 were in the
    middle of A's chain, verifying A alone would report a break that is
    not tampering.
    """
    org_a, org_b = uuid.uuid4(), uuid.uuid4()

    _set_org(app_session, org_a)
    a1 = _insert(app_session, org_a, "A1")

    _set_org(app_session, org_b)
    b1 = _insert(app_session, org_b, "B1")

    _set_org(app_session, org_a)
    a2 = _insert(app_session, org_a, "A2")

    # Each row is read from its OWN organization's vantage point. Reading
    # unscoped would have been simpler and is no longer possible: migration
    # 032 made an unscoped session see nothing, because seeing EVERYTHING was
    # the defect. Naming the scope per read also removes the risk this comment
    # used to warn about -- a comparison silently checking a row the session
    # could not see.
    _, a1_hash = _hashes(app_session, a1, org_a)
    _, b1_hash = _hashes(app_session, b1, org_b)
    a2_prev, _ = _hashes(app_session, a2, org_a)

    assert a2_prev == a1_hash, (
        "org A's second row must chain onto org A's first row; it chained "
        "onto something else, so the per-organization scope is not holding"
    )
    assert a2_prev != b1_hash, "org A's chain must not link through org B's row"


def test_each_organization_starts_its_own_chain(app_session):
    """A tenant's first-ever row starts at GENESIS, not at another tenant's tail.

    Two fresh organizations both starting at GENESIS was the SYMPTOM
    reported as a concurrency fork. It is in fact correct and intended:
    they are independent chains.
    """
    org_a, org_b = uuid.uuid4(), uuid.uuid4()

    _set_org(app_session, org_a)
    a1 = _insert(app_session, org_a, "A1")
    _set_org(app_session, org_b)
    b1 = _insert(app_session, org_b, "B1")

    # One read per tenant, each from its own context. These rows belong to
    # different organizations and no single context may see both -- which is
    # the property under test, not an obstacle to it.
    assert _hashes(app_session, a1, org_a)[0] == "GENESIS"
    assert _hashes(app_session, b1, org_b)[0] == "GENESIS"


def test_an_unscoped_write_does_not_splice_onto_a_tenant_chain(app_session):
    """The actual defect: a writer with no organization context.

    Before 011 this row chained onto whichever organization happened to
    write last — a non-deterministic cross-tenant splice. It must now join
    the system chain instead.
    """
    org_a = uuid.uuid4()

    _set_org(app_session, org_a)
    a1 = _insert(app_session, org_a, "A1")
    _, a1_hash = _hashes(app_session, a1, org_a)

    system_row = _insert_unscoped(app_session, "SYSTEM")
    # The system chain IS readable unscoped, and only the system chain --
    # migration 034 made the policy NULL-safe so the platform's own writer can
    # read back what it wrote. Before 034 this failed on the RETURNING, not on
    # the INSERT: `INSERT ... RETURNING` is a read.
    system_prev, _ = _hashes(app_session, system_row, None)

    assert system_prev != a1_hash, (
        "an unscoped write spliced onto a tenant's chain — this is the "
        "cross-tenant splice migration 011 exists to close"
    )

    # Positive half: it must land on the system chain, i.e. its parent is
    # itself a NULL-organization row (or GENESIS if none exists yet).
    if system_prev != "GENESIS":
        parent_org = app_session.execute(
            text("SELECT organization_id FROM audit.events WHERE row_hash = :h"),
            {"h": system_prev},
        ).scalar_one_or_none()
        assert parent_org is None, (
            f"the system row chained onto an organization-owned row ({parent_org})"
        )


def test_a_scoped_session_cannot_forge_another_organizations_audit_row(app_session):
    """`WITH CHECK (true)` let any session write any tenant's audit rows.

    That is the ability to forge entries in another organization's
    tamper-evident log — the one table whose whole purpose is to be
    trustworthy about who did what.
    """
    org_a, org_b = uuid.uuid4(), uuid.uuid4()

    _set_org(app_session, org_a)

    with pytest.raises(DBAPIError) as exc:
        _insert(app_session, org_b, "FORGED")
        app_session.flush()

    assert "row-level security" in str(exc.value).lower(), (
        f"expected an RLS refusal, got: {exc.value}"
    )


def test_a_scoped_session_may_still_write_its_own_rows(app_session):
    """The guard above must not have made the normal path fail.

    A tightened policy that also blocks legitimate writes would take the
    audit log down, which is a worse outcome than the hole it closes.
    """
    org_a = uuid.uuid4()
    _set_org(app_session, org_a)
    assert _insert(app_session, org_a, "OWN") > 0


def test_the_force_rls_cutover_must_revisit_the_chain_trigger(owner_session):
    """A tripwire for a defect that does not exist YET.

    `audit.chain_row()` is SECURITY DEFINER owned by `evercoat_owner`,
    which today makes its tail read immune to the caller's context --
    because `audit.events` has RLS ENABLED but not FORCED, and an owner is
    exempt from a non-forced policy.

    The planned cutover migration flips `core.rls_permissive()` to FALSE
    and turns FORCE on. At that moment the owner stops being exempt and
    the trigger's tail read becomes filtered again, which reintroduces
    exactly the class of defect migration 011 closed:

      * a system row (organization_id IS NULL) written while a tenant
        context is set would find its own chain hidden and restart at
        GENESIS on every insert;
      * an unscoped writer would see nothing at all, because the
        permissive branch is gone, and would likewise restart at GENESIS
        every time.

    Neither breaks a test today, so a comment would be read years after it
    stopped being true. This assertion fails the moment the cutover lands,
    in the file that explains what to do about it: give the tail read a
    BYPASSRLS-capable owner, or read the tail through a dedicated
    SECURITY DEFINER helper that is exempt.
    """
    # UPDATED 2026-08-22. Migration 032 set `core.rls_permissive()` to FALSE,
    # so the first assertion has been removed -- it fired, and in doing so did
    # exactly its job: it made that a reviewed decision rather than a side
    # effect.
    #
    # The hazard this test names is untouched, because it was never really
    # about `rls_permissive()`. `audit.chain_row` is SECURITY DEFINER owned by
    # `evercoat_owner` (migration 013), and an owner is exempt from a policy
    # that is not FORCED whatever the predicate says. That is why the chain
    # trigger kept working across 032 while several tests in this file did not.
    #
    # FORCE is the half that still bites, and it is the half that always
    # mattered.
    forced = owner_session.execute(
        text("SELECT relforcerowsecurity FROM pg_class WHERE oid = 'audit.events'::regclass")
    ).scalar_one()

    cutover_note = (
        "audit.chain_row()'s tail read is filtered by the caller's RLS "
        "context again, so the per-organization chain will restart at "
        "GENESIS for system and unscoped writes. Give the tail read a "
        "BYPASSRLS-capable owner, or read the tail through a helper that "
        "is exempt. Read this test's docstring before changing it."
    )

    assert forced is False, f"FORCE ROW LEVEL SECURITY is now on for audit.events. {cutover_note}"


def test_verify_chain_scoped_to_one_organization_ignores_another(app_session):
    """The verifier must name its scope and be clean across interleaving.

    Before 011 `verify_chain` walked whatever RLS showed the caller. That
    gave the right answer only because the writer was filtered by the same
    policy — correct by coincidence, and a different answer as soon as the
    calling role or the policy changed.
    """
    from app.core.audit import verify_chain

    org_a, org_b = uuid.uuid4(), uuid.uuid4()

    _set_org(app_session, org_a)
    first = _insert(app_session, org_a, "A1")
    _set_org(app_session, org_b)
    _insert(app_session, org_b, "B1")
    _set_org(app_session, org_a)
    _insert(app_session, org_a, "A2")
    _set_org(app_session, org_b)
    _insert(app_session, org_b, "B2")

    # Each verification runs in the context of the tenant being verified,
    # which is how production calls it.
    _set_org(app_session, org_a)
    assert verify_chain(app_session, organization_id=org_a, start_id=first - 1) is None, (
        "org A's chain must verify even though org B wrote between its rows"
    )
    _set_org(app_session, org_b)
    assert verify_chain(app_session, organization_id=org_b, start_id=first - 1) is None, (
        "org B's chain must verify even though org A wrote between its rows"
    )

    # 🔴 AND THE ARGUMENT MUST BE WHAT FILTERS, NOT THE RLS CONTEXT.
    #
    # The two assertions above would BOTH still pass if `verify_chain` dropped
    # its `organization_id` predicate entirely, because RLS is now scoped to
    # the same tenant and would do the filtering for it. Codex caught that:
    # the pre-032 version read unscoped precisely so RLS could not mask a
    # missing predicate, and my first rewrite lost that property.
    #
    # Restored by asking for the WRONG tenant from a given context. If the
    # argument is honoured, org B's chain is not reachable from org A's
    # context and the walk finds nothing to contradict; if the predicate were
    # dropped, the walk would read org A's rows while claiming to verify org
    # B and the interleaved hashes would not line up.
    _set_org(app_session, org_a)
    mismatched = verify_chain(app_session, organization_id=org_b, start_id=first - 1)
    assert mismatched is None, (
        "verifying org B's chain from org A's context reported a break. That "
        "means the walk read rows the organization_id argument should have "
        "excluded -- the argument is not doing the filtering, RLS is."
    )


# ---------------------------------------------------------------------------
# Migration 013 + the unauthenticated chain head (Codex review findings 1, 4)
# ---------------------------------------------------------------------------


def test_a_scoped_session_cannot_append_to_the_system_chain(app_session):
    """Migration 011 left this half open; 013 closed it.

    011's policy permitted `organization_id IS NULL` unconditionally, so
    any tenant session could write SYSTEM-chain rows. The system chain is
    where platform actions are recorded — a tenant able to append to it
    can manufacture platform history.
    """
    _set_org(app_session, uuid.uuid4())

    with pytest.raises(DBAPIError) as exc:
        _insert(app_session, None, "TENANT_FORGING_A_SYSTEM_ROW")
        app_session.flush()

    assert "row-level security" in str(exc.value).lower(), (
        f"expected an RLS refusal, got: {exc.value}"
    )


def test_an_unscoped_session_may_still_write_system_rows(app_session):
    """The tightening must not have taken the platform's own writer out.

    Migrations, maintenance scripts and the bootstrap path legitimately
    have no organization context.
    """
    _set_org(app_session, None)
    assert _insert(app_session, None, "SYSTEM_STILL_WORKS") > 0


def test_verify_chain_detects_a_deleted_head_row(owner_session):
    """The head of the walk must be authenticated, not assumed.

    `verify_chain` used to skip the prev_hash comparison on its first row.
    Deleting an organization's genesis event therefore promoted its second
    event to first-returned, whose prev_hash names a row that no longer
    exists — and the walk reported the chain intact. Deleting a row is
    precisely what the chain exists to detect (Codex review, finding 4).

    Uses the owner role to bypass the append-only trigger, simulating an
    attacker with direct database access.
    """
    from app.core.audit import verify_chain

    org = uuid.uuid4()
    ids = [_insert(owner_session, org, f"HEAD{i}") for i in range(3)]
    owner_session.flush()

    start = ids[0] - 1
    assert verify_chain(owner_session, organization_id=org, start_id=start) is None, (
        "the rows just written must verify before anything is deleted"
    )

    owner_session.execute(text("ALTER TABLE audit.events DISABLE TRIGGER audit_events_no_update"))
    owner_session.execute(text("DELETE FROM audit.events WHERE id = :i"), {"i": ids[0]})
    owner_session.execute(text("ALTER TABLE audit.events ENABLE TRIGGER audit_events_no_update"))

    found = verify_chain(owner_session, organization_id=org, start_id=start)
    assert found is not None, (
        "the chain's first event was deleted and verification still reported "
        "the chain intact — the head of the walk is unauthenticated"
    )
    assert found.event_id == ids[1], (
        f"expected the break at the new head {ids[1]}, got {found.event_id}"
    )
