"""domain events

Revision ID: v1000
Revises: u1000
Created: 2026-08-31

Spec §22, "Event integration": cross-module facts announced rather than
hard-coded.

🔴 THE PROBE ASSERTS THE PROPERTIES, NOT THAT THE FILE RAN.

`CREATE TABLE IF NOT EXISTS` succeeds against a table that already exists with
the wrong shape, and `ALTER TABLE ... FORCE ROW LEVEL SECURITY` on a table with
no policy locks everyone out in a way that surfaces later as an empty result
rather than an error. So this checks what the migration was FOR: the table is
FORCE RLS, it carries both policies, the append-only trigger exists, and
`evercoat_app` can INSERT and cannot UPDATE.

⚠️ AND IT ASSERTS THE PRIVILEGE, NEVER THE GRANT STATEMENT. This project has a
standing note that a REVOKE against a broader GRANT does nothing; the only
trustworthy question is what `has_table_privilege` answers afterwards.
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op
from sqlalchemy import text

from migrations_alembic._sql import apply_sql

revision: str = "v1000"
down_revision: str | None = "u1000"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    apply_sql("063_domain_events.sql")

    bind = op.get_bind()

    forced = bind.execute(
        text(
            "SELECT relforcerowsecurity FROM pg_class "
            "WHERE oid = 'workflow.domain_events'::regclass"
        )
    ).scalar_one()
    if not forced:
        raise RuntimeError(
            "workflow.domain_events is not FORCE RLS. Without it the owner "
            "bypasses the tenant predicate and every test written as owner "
            "passes over a boundary that is not there."
        )

    policies = {
        row[0]
        for row in bind.execute(
            text(
                "SELECT policyname FROM pg_policies "
                "WHERE schemaname = 'workflow' AND tablename = 'domain_events'"
            )
        ).all()
    }
    missing = {"domain_events_scope", "domain_events_insert"} - policies
    if missing:
        raise RuntimeError(
            f"workflow.domain_events is missing policies {sorted(missing)}. "
            "FORCE RLS with no policy denies everything silently."
        )

    trigger = bind.execute(
        text(
            "SELECT count(*) FROM pg_trigger "
            "WHERE tgrelid = 'workflow.domain_events'::regclass "
            "AND tgname = 'domain_events_no_update' AND NOT tgisinternal"
        )
    ).scalar_one()
    if trigger != 1:
        raise RuntimeError(
            "the append-only trigger is absent. A revoked UPDATE stops "
            "evercoat_app and stops nothing else -- a migration or a future "
            "role would be able to rewrite the log."
        )

    # 🔴 OWNERSHIP, BECAUSE THE MIGRATION RUNS AS THE SUPERUSER.
    # Without an explicit ALTER the table is owned by `postgres` while every
    # other table in `workflow` is owned by `evercoat_owner`, and the symptom
    # arrives much later as "permission denied" from the owner role. Commit
    # 0108d7d is the previous instance.
    owner = bind.execute(
        text(
            "SELECT pg_get_userbyid(relowner) FROM pg_class "
            "WHERE oid = 'workflow.domain_events'::regclass"
        )
    ).scalar_one()
    if owner != "evercoat_owner":
        raise RuntimeError(
            f"workflow.domain_events is owned by {owner!r}, not evercoat_owner. "
            "The migration runs as the superuser, so the ALTER TABLE ... OWNER TO "
            "is load-bearing and is not optional."
        )

    may_insert, may_update, may_delete = bind.execute(
        text(
            "SELECT has_table_privilege('evercoat_app','workflow.domain_events','INSERT'),"
            "       has_table_privilege('evercoat_app','workflow.domain_events','UPDATE'),"
            "       has_table_privilege('evercoat_app','workflow.domain_events','DELETE')"
        )
    ).one()
    if not may_insert:
        raise RuntimeError("evercoat_app cannot INSERT: nothing could ever be announced.")
    if may_update or may_delete:
        raise RuntimeError(
            f"evercoat_app holds UPDATE={may_update} DELETE={may_delete} on an "
            "append-only log. The GRANT ran; the REVOKE did not take."
        )


def downgrade() -> None:
    # The table is dropped whole. Nothing else references it -- announcing a
    # fact creates no foreign key back into the log, which is the property that
    # makes an event log safe to remove and a hard-coded write not.
    op.execute("DROP TRIGGER IF EXISTS domain_events_no_update ON workflow.domain_events")
    op.execute("DROP FUNCTION IF EXISTS workflow.domain_events_append_only()")
    op.execute("DROP TABLE IF EXISTS workflow.domain_events")
