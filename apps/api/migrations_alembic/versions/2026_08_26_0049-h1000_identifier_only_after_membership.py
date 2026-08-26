"""an identifier is returned only after the membership exists

Revision ID: h1000
Revises: g1000
Created: 2026-08-26

Closes I82.

`core.user_id_for_subject(TEXT)` answered, for an exact Keycloak subject in ANY
organization, with that user's uuid and their existence — on a SELECT, leaving
no row behind. `core.bind_subject_to_organization` replaces it: resolution and
membership creation in one statement, so the identifier is returned only after
the membership exists, and the organization comes from `app.current_org`
rather than from an argument.

🔴 ADR-029 RECORDED THIS DESIGN AS REJECTED, AND THE REJECTION HAS EXPIRED.
Its mechanism was that a definer's WRITE fires ADR-028's address guards, which
inside a definer run as the table owner and reopen I83's disclosure. ADR-029's
own hardening — migration 047 — then made both guards scope themselves by
their own predicate, which is the step that chain depended on. Re-measured
with ADR-029's own probes against this schema: the DEFINER path is ACCEPTED
where it was REFUSED before 047. *Re-measure a settled conclusion before
paying for it.*

The measurement is kept as a test rather than a note, because this function IS
the writing definer ADR-029 warned about:
`tests/db/test_049_atomic_bind.py::test_a_definer_write_does_not_widen_the_address_guards`.

⚠️ EXISTENCE IS STILL LEARNABLE. What changed is the cost: the answer now
requires creating a real membership and writes an audit record, instead of a
silent traceless SELECT. A reduction, not an elimination — full reasoning in
`migrations/049_an_identifier_is_returned_only_after_the_membership_exists.sql`.
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op
from sqlalchemy import text

from migrations_alembic._sql import apply_sql

revision: str = "h1000"
down_revision: str | None = "g1000"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    apply_sql("049_an_identifier_is_returned_only_after_the_membership_exists.sql")


def downgrade() -> None:
    """Drop the atomic bind and restore 044's resolver.

    ⚠️ THE DOWNGRADE RE-OPENS I82 BY DESIGN, and that is what a downgrade
    means: `e8000..g1000` describes a schema in which the oracle existed, and a
    downgrade that quietly kept the improvement would make that description
    false. The application must be rolled back with it — `app/api/admin.py`
    calls the new function and will fail loudly if it is absent, which is the
    correct direction to fail.

    Restored to 044's exact text, owner pin included: an unpinned recreation
    would be owned by whoever runs the downgrade, and on this project that is
    `postgres` — a superuser, permanently outside RLS. That is I56's shape and
    it must not be reintroduced by a rollback path nobody reads.
    """
    op.execute(text("DROP FUNCTION IF EXISTS core.bind_subject_to_organization(TEXT, TEXT, TEXT)"))
    op.execute(
        text(
            """
            CREATE OR REPLACE FUNCTION core.user_id_for_subject(p_subject TEXT)
                RETURNS UUID
                LANGUAGE sql
                STABLE
                SECURITY DEFINER
                SET search_path = core, pg_temp
            AS $$
                SELECT id FROM core.users WHERE keycloak_sub = p_subject
            $$
            """
        )
    )
    # ⚠️ AND REVERT 049's TWO `ALTER FUNCTION ... SET search_path` PINS.
    # Raised by the Supervisor: without this, a database downgraded to g1000
    # keeps 049's pins and comments, so the schema no longer matches what
    # g1000 describes -- which is the argument this docstring already makes
    # about the function itself, not honoured for these two objects. The pin
    # is strictly safer, and that is not a reason for a downgrade to lie.
    op.execute(
        text("ALTER FUNCTION core.deny_duplicate_address_in_organization() RESET search_path")
    )
    op.execute(text("ALTER FUNCTION core.deny_address_collision_on_rename() RESET search_path"))
    op.execute(text("ALTER FUNCTION core.user_id_for_subject(TEXT) OWNER TO evercoat_owner"))
    op.execute(text("REVOKE ALL ON FUNCTION core.user_id_for_subject(TEXT) FROM PUBLIC"))
    op.execute(text("GRANT EXECUTE ON FUNCTION core.user_id_for_subject(TEXT) TO evercoat_app"))
