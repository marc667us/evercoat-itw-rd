"""an authentication identifier is not a readable column

Revision ID: f2000
Revises: f1000
Created: 2026-08-25

Closes I81, and hardens 046 against a defect found while measuring I82.

I81: 044's read policy hands over the whole `core.users` row where its
justification — attribution in eleven joins — needs only the name. Measured
before acting: `display_name` has eleven readers, `email` has two production
paths that deliberately return it, and `keycloak_sub` has **none**. RLS cannot
express "the name but not the identifier"; column privileges can.

046 hardening: `core.deny_address_collision_on_rename` was scoped by the RLS
policy on `core.organization_members` rather than by its own predicate. A
trigger runs as the current user, and inside a SECURITY DEFINER owned by the
table owner that user bypasses RLS — measured, the guard then refused on
another tenant's row, and the refusal discloses that the address exists. The
scope is now explicit, which also survives the FORCE RLS cutover of I56/I58.

Full reasoning in
`migrations/047_an_authentication_identifier_is_not_a_readable_column.sql`.
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op
from sqlalchemy import text

from migrations_alembic._sql import apply_sql

revision: str = "f2000"
down_revision: str | None = "f1000"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    apply_sql("047_an_authentication_identifier_is_not_a_readable_column.sql")


def downgrade() -> None:
    """Restore the table-wide grants and 046's RLS-scoped rename guard.

    ⚠️ THE COLUMN GRANTS MUST BE REVOKED BEFORE THE TABLE GRANT IS RESTORED.

    PostgreSQL keeps column-level grants and table-level grants as separate
    entries. Adding `GRANT SELECT ON core.users` back while the explicit
    column list is still in place leaves both recorded, so a later attempt to
    narrow the column again looks like it worked and does not — the same trap
    the upgrade documents, in the other direction.

    The rename guard is restored to 046's exact text, RLS-scoped and all. A
    downgrade that quietly kept the improvement would mean e9000..f1000 no
    longer describes what f1000 actually was.
    """
    op.execute(
        text(
            "REVOKE SELECT (id, email, display_name, status, created_at, updated_at)"
            " ON core.users FROM evercoat_app, evercoat_report, evercoat_worker"
        )
    )
    op.execute(text("REVOKE UPDATE (email, display_name) ON core.users FROM evercoat_app"))
    op.execute(text("GRANT SELECT ON core.users TO evercoat_app, evercoat_report, evercoat_worker"))
    op.execute(text("GRANT UPDATE ON core.users TO evercoat_app"))
    op.execute(text("COMMENT ON COLUMN core.users.keycloak_sub IS NULL"))

    op.execute(
        text(
            """
            CREATE OR REPLACE FUNCTION core.deny_address_collision_on_rename()
            RETURNS TRIGGER
            LANGUAGE plpgsql
            SECURITY INVOKER
            AS $fn$
            BEGIN
                PERFORM pg_advisory_xact_lock(
                    hashtext(COALESCE(core.current_org_id()::TEXT, '<none>')),
                    hashtext(NEW.email::TEXT)
                );

                IF EXISTS (
                    SELECT 1
                      FROM core.organization_members mine
                      JOIN core.organization_members other
                        ON other.organization_id = mine.organization_id
                       AND other.user_id <> NEW.id
                       AND other.status = 'active'
                      JOIN core.users u ON u.id = other.user_id
                     WHERE mine.user_id = NEW.id
                       AND mine.status = 'active'
                       AND u.email = NEW.email
                ) THEN
                    RAISE EXCEPTION
                        'address already belongs to an active member of this organization'
                        USING ERRCODE = 'unique_violation',
                              CONSTRAINT = 'users_address_stays_unique_in_organization';
                END IF;

                RETURN NEW;
            END $fn$
            """
        )
    )
    op.execute(
        text("ALTER FUNCTION core.deny_address_collision_on_rename() OWNER TO evercoat_owner")
    )
    # 🔴 THE COMMENT MUST GO BACK TOO. Raised by Codex.
    #
    # `CREATE OR REPLACE FUNCTION` keeps the existing COMMENT, so a downgrade
    # that only replaced the body left 047's comment -- "scoped by its own
    # predicate" -- describing f1000's RLS-dependent code. A comment asserting
    # a rule the body does not implement is this repository's most repeated
    # defect, and a downgrade is exactly where one gets left behind.
    op.execute(
        text(
            "COMMENT ON FUNCTION core.deny_address_collision_on_rename() IS "
            "'Refuses renaming a user onto an address already held by another "
            "ACTIVE member of an organization they both belong to. The UPDATE "
            "half of the rule whose INSERT half is enforced on "
            "core.organization_members. SECURITY INVOKER on purpose (I83).'"
        )
    )
