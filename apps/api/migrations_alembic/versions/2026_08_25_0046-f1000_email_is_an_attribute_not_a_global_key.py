"""an email address is an attribute, not a global key

Revision ID: f1000
Revises: e9000
Created: 2026-08-25

Closes I83, the cross-tenant email existence oracle.

`core.users.email` carried `users_email_key`, a GLOBALLY unique constraint, and
unique constraints are enforced OUTSIDE row-level security. Measured as
`evercoat_app` scoped to organization A: inserting an address held by a member
of organization B was refused by that constraint, and an unused address was
accepted. `POST /api/admin/members` turns those into 409 and 201, so a holder
of `admin.users` in any tenant read platform-wide existence from a status code
with a throwaway subject and no row left behind.

Migration 044 had already made that refusal generic, and the oracle survived --
because the attacker reads 201 against 409, not the message. A creating
endpoint cannot make "created" indistinguishable from "not created", so the
only fix that removes the channel is to stop enforcing the invariant globally.

Identity remains `keycloak_sub`. One-address-per-organization is enforced by a
SECURITY INVOKER constraint trigger, at the only scope where a refusal
discloses nothing the caller cannot already read.

Full reasoning in `migrations/046_email_is_an_attribute_not_a_global_key.sql`.
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op
from sqlalchemy import text

from migrations_alembic._sql import apply_sql

revision: str = "f1000"
down_revision: str | None = "e9000"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    apply_sql("046_email_is_an_attribute_not_a_global_key.sql")


def downgrade() -> None:
    """Restore the global constraint -- and REFUSE rather than delete rows.

    🔴 THIS DOWNGRADE CAN LEGITIMATELY FAIL, AND THAT IS THE CORRECT
    BEHAVIOUR.

    Once 046 has been in use, two identities may hold the same address --
    that is the whole point of it. Re-adding `users_email_key` over such
    data is impossible without deciding which row survives, and a
    downgrade that silently deleted user records to make a constraint fit
    would destroy identities and their audit trail to satisfy a schema.

    So it raises, and it NAMES the addresses. The operator resolves them
    and re-runs. A downgrade that cannot run is recoverable; one that
    quietly removed rows is not.

    ⚠️ The trigger and its function are dropped FIRST. Leaving them behind
    would mean a database that is nominally at e9000 while still carrying
    046's guard -- the schema disagreeing with the version table, which is
    how "the database in front of you is not the schema" happens.
    """
    op.execute(
        text(
            "DROP TRIGGER IF EXISTS organization_members_one_address_per_organization"
            " ON core.organization_members"
        )
    )
    op.execute(text("DROP FUNCTION IF EXISTS core.deny_duplicate_address_in_organization()"))

    duplicates = (
        op.get_bind()
        .execute(
            text(
                """
                SELECT email::text AS email, count(*) AS n
                  FROM core.users
                 GROUP BY email
                HAVING count(*) > 1
                 ORDER BY n DESC, email
                 LIMIT 20
                """
            )
        )
        .all()
    )
    if duplicates:
        listed = ", ".join(f"{row.email} ({row.n} identities)" for row in duplicates)
        raise RuntimeError(
            "cannot restore users_email_key: core.users holds addresses shared "
            f"by more than one identity -- {listed}. Migration 046 permits this "
            "deliberately (I83). Resolve the duplicates by hand and re-run this "
            "downgrade; this step will not delete user records to make the "
            "constraint fit."
        )

    op.execute(text("ALTER TABLE core.users ADD CONSTRAINT users_email_key UNIQUE (email)"))
    # 024 set no comment on this column; 046 added one. Remove it rather than
    # leave a comment describing a rule that no longer holds -- a comment
    # asserting a rule the schema does not implement is this repository's most
    # repeated defect, and a downgrade is exactly where one gets left behind.
    op.execute(text("COMMENT ON COLUMN core.users.email IS NULL"))
