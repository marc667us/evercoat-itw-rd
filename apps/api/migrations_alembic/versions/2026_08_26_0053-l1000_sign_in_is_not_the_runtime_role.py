"""signing in is not something the runtime role may do

Revision ID: l1000
Revises: k1000
Created: 2026-08-26

Closes I109, raised by Codex reviewing 052 and measured before it was believed.

`core.principal_for_subject(TEXT, UUID)` and
`core.memberships_for_subject(TEXT)` take a subject as an ARGUMENT and cannot
bind it to whoever is asking, because both exist to answer BEFORE a session has
an organization. Granted to `evercoat_app`, they let an ordinary member read any
named subject's address AND the name and code of every organization that subject
belongs to.

Neither a GUC nor `SET ROLE` fixes that: anything able to run SQL as
`evercoat_app` can set the GUC or the role too. Privilege has to follow the
CONNECTION, so this creates `evercoat_auth` -- EXECUTE on exactly those two
functions, no table privileges at all -- and revokes them from `evercoat_app`.

🔴 IT FAILS CLOSED. An environment that applies this without configuring the
auth connection cannot sign anybody in. There is deliberately no state in which
the fix reads as applied and the old privilege quietly still works.
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op
from sqlalchemy import text

from migrations_alembic._sql import apply_sql

revision: str = "l1000"
down_revision: str | None = "k1000"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    apply_sql("053_sign_in_is_not_the_runtime_role.sql")


def downgrade() -> None:
    """Give the sign-in lookups back to the runtime role.

    ⚠️ THIS REOPENS I109 BY DESIGN. `k1000` describes a schema in which
    `evercoat_app` could enumerate identities through those two functions, and
    a downgrade that quietly kept the fix would make that description false --
    the same argument 049, 051 and 052 each make.

    ⚠️ THE ROLE IS NOT DROPPED, AND THAT IS A CHOICE RATHER THAN AN OMISSION.
    A deployment will have given `evercoat_auth` LOGIN and a password and put
    it in a running process's configuration. Dropping it out from under that
    process turns a schema rollback into an outage in a component the rollback
    was not about. Revoked to nothing and left in place, it is inert; the
    application must be rolled back with it either way, exactly as 049 records
    for its own downgrade.
    """
    op.execute(
        text("GRANT EXECUTE ON FUNCTION core.principal_for_subject(TEXT, UUID) TO evercoat_app")
    )
    op.execute(
        text("GRANT EXECUTE ON FUNCTION core.memberships_for_subject(TEXT) TO evercoat_app")
    )

    # The role keeps nothing. `REVOKE` before any future `DROP ROLE`, because
    # PostgreSQL refuses to drop a role that still holds a privilege anywhere
    # -- and the error names the database, not the object, which is a poor
    # clue to act on months later.
    op.execute(
        text("REVOKE EXECUTE ON FUNCTION core.principal_for_subject(TEXT, UUID) FROM evercoat_auth")
    )
    op.execute(
        text("REVOKE EXECUTE ON FUNCTION core.memberships_for_subject(TEXT) FROM evercoat_auth")
    )
    op.execute(text("REVOKE USAGE ON SCHEMA core FROM evercoat_auth"))

    # 🔴 ASSERT THE DOWNGRADE ACHIEVED ITS POINT, rather than assuming the
    # statements above did anything. A GRANT that silently failed to apply
    # would leave a database nobody can authenticate against, and the symptom
    # -- 403 on every request -- reads like an application bug.
    restored = (
        op.get_bind()
        .execute(
            text(
                "SELECT has_function_privilege("
                "'evercoat_app', 'core.principal_for_subject(TEXT, UUID)', 'EXECUTE')"
            )
        )
        .scalar_one()
    )
    if not restored:
        raise RuntimeError(
            "the downgrade did not restore EXECUTE on core.principal_for_subject "
            "to evercoat_app; nobody would be able to sign in against this schema"
        )
