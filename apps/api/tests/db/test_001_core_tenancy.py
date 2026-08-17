"""Tenancy and audit invariants.

These are the gate for the riskiest decision in the project. Both
reviewers named the authorization and tenancy model as the thing most
likely to force an expensive rewrite if it is wrong (Codex Q3), so it
gets asserted rather than assumed.

Every test here runs under ``SET ROLE evercoat_app``. A migration or a
query that only works as superuser is a latent production failure:
superuser bypasses RLS entirely, so a suite that runs as one would pass
against a schema with no isolation at all.
"""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError, IntegrityError, ProgrammingError

from app.core.db import set_local

pytestmark = [pytest.mark.db, pytest.mark.rls]


# ---------------------------------------------------------------------------
# Structural invariants
# ---------------------------------------------------------------------------


def test_every_tenant_table_has_composite_candidate_key(owner_session):
    """UNIQUE (id, organization_id) on every tenant-scoped table.

    Not a style rule. PostgreSQL requires a unique index on the referenced
    columns, so without this a composite foreign key is impossible and the
    migration fails with "there is no unique constraint matching given
    keys for referenced table" (Supervisor S7).

    The predictable reaction to that error under time pressure is to drop
    the composite FK and fall back to a single-column one — which silently
    reintroduces the cross-tenant reference this whole design prevents.
    This test exists so that never becomes a judgement call.
    """
    missing = owner_session.execute(
        text(
            """
            SELECT c.table_schema, c.table_name
            FROM information_schema.columns c
            WHERE c.column_name = 'organization_id'
              AND c.table_schema NOT IN ('pg_catalog', 'information_schema')
              AND NOT EXISTS (
                  SELECT 1
                  FROM information_schema.table_constraints tc
                  JOIN information_schema.key_column_usage k
                    ON k.constraint_name = tc.constraint_name
                   AND k.table_schema    = tc.table_schema
                  WHERE tc.table_schema   = c.table_schema
                    AND tc.table_name     = c.table_name
                    AND tc.constraint_type = 'UNIQUE'
                  GROUP BY tc.constraint_name
                  HAVING array_agg(k.column_name::text ORDER BY k.column_name::text)
                         = ARRAY['id', 'organization_id']::text[]
              )
            ORDER BY 1, 2
            """
        )
    ).all()

    assert not missing, (
        "tenant-scoped tables missing UNIQUE (id, organization_id): "
        f"{[f'{s}.{t}' for s, t in missing]}"
    )


def test_rls_enabled_on_every_tenant_table(owner_session):
    """A table with organization_id and no RLS is an open door."""
    unprotected = owner_session.execute(
        text(
            """
            SELECT n.nspname, c.relname
            FROM pg_class c
            JOIN pg_namespace n ON n.oid = c.relnamespace
            WHERE c.relkind = 'r'
              AND NOT c.relrowsecurity
              AND EXISTS (
                  SELECT 1 FROM information_schema.columns col
                  WHERE col.table_schema = n.nspname
                    AND col.table_name   = c.relname
                    AND col.column_name  = 'organization_id'
              )
            ORDER BY 1, 2
            """
        )
    ).all()

    assert not unprotected, f"tenant tables without RLS: {[f'{s}.{t}' for s, t in unprotected]}"


def test_no_cascade_delete_on_rnd_history(owner_session):
    """R&D history is retired by status, never deleted.

    A CASCADE anywhere in the thread means deleting a project silently
    destroys the test results that justified a released product.
    """
    cascades = owner_session.execute(
        text(
            """
            SELECT n.nspname, c.conname, t.relname
            FROM pg_constraint c
            JOIN pg_class t     ON t.oid = c.conrelid
            JOIN pg_namespace n ON n.oid = t.relnamespace
            WHERE c.contype = 'f'
              AND c.confdeltype = 'c'
              AND n.nspname IN ('core','projects','materials','formulations',
                                'laboratory','testing','quality','products')
            """
        )
    ).all()

    assert not cascades, f"ON DELETE CASCADE found on R&D history: {cascades}"


# ---------------------------------------------------------------------------
# Cross-tenant references
# ---------------------------------------------------------------------------


def test_cross_organization_reference_is_rejected(owner_session, two_orgs):
    """The composite FK must refuse a child pointing at another tenant.

    This is the case RLS cannot catch. Referential integrity bypasses RLS
    even under FORCE, so without the composite key this insert succeeds
    and one organization's membership row silently references another
    organization's project (Codex F14).
    """
    org_a, org_b = two_orgs

    project_a = owner_session.execute(
        text(
            """
            INSERT INTO projects.projects (organization_id, project_code, name)
            VALUES (:org, 'RDP-2026-001', 'Org A project')
            RETURNING id
            """
        ),
        {"org": org_a},
    ).scalar_one()

    user_id = owner_session.execute(
        text(
            """
            INSERT INTO core.users (keycloak_sub, email, display_name)
            VALUES (:sub, :email, 'Cross Tenant Probe')
            RETURNING id
            """
        ),
        {"sub": str(uuid.uuid4()), "email": f"{uuid.uuid4()}@example.test"},
    ).scalar_one()

    # org_b claiming org_a's project. The FK is (project_id, organization_id)
    # against projects (id, organization_id), so this pair does not exist.
    with pytest.raises((IntegrityError, DBAPIError)):
        owner_session.execute(
            text(
                """
                INSERT INTO projects.project_members
                    (organization_id, project_id, user_id, project_role)
                VALUES (:org_b, :project_a, :user, 'chemist')
                """
            ),
            {"org_b": org_b, "project_a": project_a, "user": user_id},
        )
        owner_session.flush()


# ---------------------------------------------------------------------------
# Row visibility
# ---------------------------------------------------------------------------


def test_restricted_project_hidden_from_non_member(app_session, seeded_projects):
    """Resource scope, enforced by the database and not only by FastAPI.

    This is the assertion that makes the three-layer claim true. Before
    ADR-016 a colleague inside the same organization was kept out of
    another team's formulations by application code alone, so one missing
    dependency on one route was a disclosure (Codex F32).
    """
    org_id, normal_project, restricted_project, non_member_id = seeded_projects

    set_local(app_session, "app.current_org", org_id)
    set_local(app_session, "app.current_user_id", non_member_id)

    visible = {r[0] for r in app_session.execute(text("SELECT id FROM projects.projects")).all()}

    assert normal_project in visible, "a normal project should be visible org-wide"
    assert restricted_project not in visible, (
        "a restricted project must be invisible to a non-member — "
        "organization-level RLS alone is not sufficient"
    )


def test_other_organization_is_invisible(app_session, two_orgs):
    org_a, org_b = two_orgs

    set_local(app_session, "app.current_org", org_a)
    set_local(app_session, "app.current_user_id", uuid.uuid4())

    leaked = app_session.execute(
        text("SELECT count(*) FROM projects.projects WHERE organization_id = :b"),
        {"b": org_b},
    ).scalar_one()

    assert leaked == 0, "rows from another organization are visible"


# ---------------------------------------------------------------------------
# Audit
# ---------------------------------------------------------------------------


def test_audit_update_and_delete_are_refused(app_session, one_audit_row):
    """Append-only, enforced by the database rather than by convention.

    An application-level convention is bypassable by direct SQL, scripts,
    failed code paths and compromised credentials (Codex F22).
    """
    event_id = one_audit_row

    with pytest.raises((ProgrammingError, DBAPIError)):
        app_session.execute(
            text("UPDATE audit.events SET reason = 'tampered' WHERE id = :i"),
            {"i": event_id},
        )
        app_session.flush()

    app_session.rollback()

    with pytest.raises((ProgrammingError, DBAPIError)):
        app_session.execute(text("DELETE FROM audit.events WHERE id = :i"), {"i": event_id})
        app_session.flush()


def test_chain_detects_tampering(owner_session, audit_chain):
    """Altering a row must break verification from that row onward.

    Uses the owner role to bypass the append-only triggers, simulating an
    attacker with direct database access — which is precisely the threat
    the chain exists to make detectable rather than merely difficult.
    """
    from app.core.audit import verify_chain

    # Verify only the rows this test created, not the whole table.
    #
    # This comment previously said the chain was GLOBAL and forked "when
    # two transactions each read the tail before either commits". That was
    # wrong, and it was wrong in a way worth recording: audit.chain_row()
    # takes pg_advisory_xact_lock(), which is transaction-scoped, so the
    # second writer blocks until the first commits and then reads a fresh
    # snapshot. Concurrency alone never forked this chain.
    #
    # What actually happened was RLS: the trigger's tail read was SECURITY
    # INVOKER and filtered by audit_org_isolation, so every writer chained
    # onto its own organization's tail. Two organizations therefore both
    # started at GENESIS -- the observed symptom -- for a reason that had
    # nothing to do with concurrency. Migration 011 makes the per-
    # organization scope explicit and stops unscoped writers splicing
    # across tenants.
    #
    # The fixture writes rows with no organization_id, so these belong to
    # the SYSTEM chain and organization_id=None is what selects them.
    start = audit_chain[0] - 1
    assert verify_chain(owner_session, organization_id=None, start_id=start) is None, (
        "the rows this test just wrote must verify"
    )

    target = audit_chain[1]
    owner_session.execute(text("ALTER TABLE audit.events DISABLE TRIGGER audit_events_no_update"))
    owner_session.execute(
        text("UPDATE audit.events SET reason = 'silently altered' WHERE id = :i"),
        {"i": target},
    )
    owner_session.execute(text("ALTER TABLE audit.events ENABLE TRIGGER audit_events_no_update"))

    break_found = verify_chain(owner_session, organization_id=None, start_id=start)
    assert break_found is not None, "tampering went undetected"
    assert break_found.event_id == target, (
        f"expected the break at the altered row {target}, got {break_found.event_id}"
    )


def test_python_and_sql_agree_on_the_hash(owner_session, one_audit_row):
    """Each side must reproduce the other's hash.

    If they diverge, either the trigger was altered or the canonical form
    drifted between SQL and Python — both of which are the tampering the
    chain exists to surface, so a silent divergence would defeat it.
    """
    from app.core.audit import AuditEvent, canonical_content, compute_row_hash

    row = (
        owner_session.execute(
            text(
                """
            SELECT organization_id, user_id, role_code, action, entity_type,
                   entity_id, previous_state, new_state, reason,
                   occurred_at, prev_hash, row_hash
            FROM audit.events WHERE id = :i
            """
            ),
            {"i": one_audit_row},
        )
        .mappings()
        .one()
    )

    recomputed = compute_row_hash(
        row["prev_hash"],
        canonical_content(
            AuditEvent(
                action=row["action"],
                entity_type=row["entity_type"],
                organization_id=row["organization_id"],
                user_id=row["user_id"],
                role_code=row["role_code"],
                entity_id=row["entity_id"],
                previous_state=row["previous_state"],
                new_state=row["new_state"],
                reason=row["reason"],
            ),
            row["occurred_at"],
        ),
    )

    assert recomputed == row["row_hash"], (
        "Python and PostgreSQL disagree on the canonical form — field "
        "order or timestamp format has drifted between audit.py and "
        "audit.canonical_content() in 001_core_tenancy.sql"
    )


# ---------------------------------------------------------------------------
# Session context
# ---------------------------------------------------------------------------


def test_context_does_not_survive_a_transaction(app_session):
    """SET LOCAL must die with the transaction.

    A plain SET persists for the life of a pooled connection, so the next
    request — possibly another organization's — inherits it and RLS
    enforces the wrong tenant with no error anywhere (Codex F34).
    """
    org = uuid.uuid4()

    set_local(app_session, "app.current_org", org)
    assert app_session.execute(text("SELECT core.current_org_id()")).scalar_one() == org

    app_session.commit()

    leaked = app_session.execute(text("SELECT core.current_org_id()")).scalar_one()
    assert leaked is None, (
        "tenant context survived the transaction — SET was used instead of "
        "SET LOCAL, or the connection was not reset on checkin"
    )


def test_malformed_context_denies_rather_than_permits(app_session):
    """A corrupt GUC must never read as 'no restriction'."""
    app_session.execute(text("SET LOCAL app.current_org = 'not-a-uuid'"))
    assert app_session.execute(text("SELECT core.current_org_id()")).scalar_one() is None, (
        "a malformed organization id must resolve to NULL, never to a value"
    )


def test_session_scope_refuses_missing_context():
    """Fail closed at the application boundary.

    While the SQL policies are permissive during the parallel-run window,
    an absent GUC would otherwise read as 'no restriction' — the most
    dangerous default available. This guard is what makes that window safe.
    """
    from app.core.db import MissingContextError, session_scope

    with pytest.raises(MissingContextError), session_scope(None):
        pass
