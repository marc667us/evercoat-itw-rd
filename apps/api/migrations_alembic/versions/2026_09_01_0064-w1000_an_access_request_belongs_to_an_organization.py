"""an access request belongs to an organization

Revision ID: w1000
Revises: v1000
Created: 2026-09-01

Migration 059 created `public_intel.access_requests` with no tenant column,
no RLS and no predicate. On 2026-09-01 the queue got its reader, and the first
version of that route gated on `admin.users` and wrote the cross-tenant
exposure down as an issue.

🔴 Codex refused it in one sentence: *"the comment acknowledges the breach but
does not enforce a rule."* This migration is the enforcement.

🔴 THE PROBE ASSERTS THE RESULTING BEHAVIOUR, NOT THAT THE STATEMENTS RAN.

`ADD COLUMN IF NOT EXISTS` succeeds against a column that already exists with a
different type, and `ENABLE ROW LEVEL SECURITY` on a table whose policy is
missing produces an empty result rather than an error — which is the failure
this project keeps paying for. So this checks what the migration was FOR: the
column exists and is nullable, RLS is enabled AND forced, both policies exist
with the roles they were written for, and `evercoat_public` still holds INSERT
and still holds no SELECT.
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op
from sqlalchemy import text

from migrations_alembic._sql import apply_sql

revision: str = "w1000"
down_revision: str | None = "v1000"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    apply_sql("064_an_access_request_belongs_to_an_organization.sql")

    bind = op.get_bind()

    column = bind.execute(
        text(
            """
            SELECT data_type, is_nullable
              FROM information_schema.columns
             WHERE table_schema = 'public_intel'
               AND table_name = 'access_requests'
               AND column_name = 'organization_id'
            """
        )
    ).one_or_none()
    if column is None:
        raise RuntimeError(
            "public_intel.access_requests has no organization_id column, so the "
            "queue is still platform-wide and the tenant predicate has nothing "
            "to read."
        )
    if column.data_type != "uuid":
        raise RuntimeError(
            f"organization_id is {column.data_type!r}, not uuid — the composite "
            "tenant convention of this schema is not satisfied."
        )
    # 🔴 NULLABLE ON PURPOSE, AND ASSERTED SO IT STAYS THAT WAY DELIBERATELY.
    # Rows written before this migration cannot be attributed to anyone. They
    # are readable by no tenant, which is the point; making the column NOT NULL
    # would require inventing an owner for them.
    if column.is_nullable != "YES":
        raise RuntimeError(
            "organization_id is NOT NULL, which means the pre-064 rows were "
            "given an invented owner rather than left unattributable."
        )

    # 🔴 THE COMPOSITE CANDIDATE KEY. Adding `organization_id` is what makes a
    # table tenant-scoped, and `CLAUDE.md` §5 calls
    # `UNIQUE (id, organization_id)` "mandatory, not an optimisation": without
    # it no future table can carry a composite FK back to this one, and the
    # documented reaction to that error is to drop the composite FK — which
    # reintroduces the cross-tenant reference the design exists to prevent.
    #
    # The first draft of this migration omitted it and
    # `test_every_tenant_table_has_composite_candidate_key` caught it.
    composite = bind.execute(
        text(
            "SELECT count(*) FROM pg_constraint "
            " WHERE conrelid = 'public_intel.access_requests'::regclass "
            "   AND contype = 'u' "
            "   AND conname = 'access_requests_id_org_key'"
        )
    ).scalar_one()
    if composite != 1:
        raise RuntimeError(
            "public_intel.access_requests has no UNIQUE (id, organization_id). "
            "A tenant-scoped table without it cannot be the target of a "
            "composite foreign key."
        )

    enabled, forced = bind.execute(
        text(
            "SELECT relrowsecurity, relforcerowsecurity "
            "FROM pg_class WHERE oid = 'public_intel.access_requests'::regclass"
        )
    ).one()
    if not enabled or not forced:
        raise RuntimeError(
            f"access_requests RLS enabled={enabled} forced={forced}. Every table "
            "since 058 is FORCE from birth, and mixing the two has cost this "
            "project twice."
        )

    policies = dict(
        bind.execute(
            text(
                "SELECT policyname, roles::text FROM pg_policies "
                "WHERE schemaname = 'public_intel' AND tablename = 'access_requests'"
            )
        ).all()
    )
    for expected in ("access_requests_org_scope", "access_requests_public_insert"):
        if expected not in policies:
            raise RuntimeError(
                f"policy {expected!r} is missing. FORCE RLS with a missing policy "
                "refuses everything and surfaces as an empty queue, not an error."
            )
    # 🔴 THE CHECK THAT WOULD HAVE CAUGHT THIS MIGRATION'S OWN FIRST DRAFT.
    #
    # That draft wrote the tenant policy as `TO evercoat_app`, which under FORCE
    # RLS locks `evercoat_owner` — NOBYPASSRLS since 001 — out of the table
    # entirely: no applicable policy means empty SELECTs and refused INSERTs,
    # and 032/033 already warn about exactly this. The probe above passed it,
    # because it asked whether the policy EXISTED and not whom it governs.
    #
    # `{public}` in `pg_policies.roles` means "no TO clause", i.e. the predicate
    # governs every role — which is how every other tenant policy in this
    # database is written. Asserting the ROLE SET rather than the statement is
    # the same discipline this project applies to grants.
    scope_roles = policies["access_requests_org_scope"]
    if scope_roles != "{public}":
        raise RuntimeError(
            f"the tenant policy is restricted to {scope_roles}. A `TO <role>` "
            "clause here locks evercoat_owner (NOBYPASSRLS) out of the table "
            "under FORCE RLS — every SELECT returns nothing and every INSERT is "
            "refused, and it surfaces as an empty queue rather than an error. "
            "Every other tenant policy in this database omits TO so the "
            "predicate governs every role."
        )
    if policies["access_requests_public_insert"] != "{evercoat_public}":
        raise RuntimeError(
            "the public INSERT policy does not name evercoat_public alone. It "
            "is the one deliberate TO clause here, because the public role has "
            "no tenant GUC and can never satisfy the predicate."
        )

    # ⚠️ THE PRIVILEGE, NEVER THE GRANT STATEMENT. 059 gave the public role
    # INSERT and nothing else; this migration must not have changed that.
    may_insert, may_select = bind.execute(
        text(
            "SELECT has_table_privilege('evercoat_public',"
            "         'public_intel.access_requests','INSERT'),"
            "       has_table_privilege('evercoat_public',"
            "         'public_intel.access_requests','SELECT')"
        )
    ).one()
    if not may_insert:
        raise RuntimeError("evercoat_public cannot INSERT: the landing page's Sign Up is dead.")
    if may_select:
        raise RuntimeError(
            "evercoat_public gained SELECT on the access-request queue. An "
            "anonymous caller must never be able to read other people's "
            "submissions."
        )


def downgrade() -> None:
    op.execute(
        "DROP POLICY IF EXISTS access_requests_public_insert ON public_intel.access_requests"
    )
    op.execute("DROP POLICY IF EXISTS access_requests_org_scope ON public_intel.access_requests")
    op.execute("ALTER TABLE public_intel.access_requests NO FORCE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE public_intel.access_requests DISABLE ROW LEVEL SECURITY")
    op.execute("DROP INDEX IF EXISTS public_intel.access_requests_org_status_idx")
    op.execute("ALTER TABLE public_intel.access_requests DROP COLUMN IF EXISTS organization_id")
