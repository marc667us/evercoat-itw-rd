"""the returned identifier was the existence answer

Revision ID: j1000
Revises: i1000
Created: 2026-08-26

🔴 050 REMOVED THE FLAG AND KEPT THE BIT. It deleted `identity_created`
because that column answered "does this subject exist somewhere on this
platform" for free — and left `user_id`, which answers the same question the
same way. Raised by Codex reviewing 050, and MEASURED before being accepted:
two rolled-back binds return the SAME uuid for a subject that exists in
another tenant and DIFFERENT uuids for one that does not, leaving nothing
behind either way.

I83 was closed by dropping its oracle rather than disguising it. 050
disguised this one. The function now returns only `member_id`, which is minted
by the call itself and therefore distinguishes nothing; `app/api/admin.py`
resolves the user through that membership, under 044's read policy.

⚠️ What this does NOT close is stated in the SQL header and filed as I106:
the stored email and display name of a pre-existing foreign identity are still
readable through the membership before a rollback. Closing it needs
tenant-scoped attributes on `core.organization_members`, which is a schema
change with its own tests.
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op
from sqlalchemy import text

from migrations_alembic._sql import apply_sql

revision: str = "j1000"
down_revision: str | None = "i1000"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    apply_sql("051_the_returned_identifier_was_the_existence_answer.sql")


def downgrade() -> None:
    """Restore 050's signature — WITH the existence oracle, which is the point.

    ⚠️ THIS REINSTATES A FREE, TRACELESS CROSS-TENANT EXISTENCE ORACLE.
    `i1000` describes a schema in which it existed. A downgrade that quietly
    kept the fix would make that description false.

    The body is re-read from `pg_get_functiondef` and only the two lines that
    051 changed are put back, so this cannot silently drop the standing check
    the way a hand-retyped body dropped an advisory lock in 049.
    """
    body = (
        op.get_bind()
        .execute(
            text(
                "SELECT pg_get_functiondef(p.oid) FROM pg_proc p"
                " JOIN pg_namespace n ON n.oid = p.pronamespace"
                " WHERE n.nspname = 'core' AND p.proname = 'bind_subject_to_organization'"
            )
        )
        .scalar_one()
    )
    restored = body.replace(
        "RETURNS TABLE(member_id uuid)", "RETURNS TABLE(user_id uuid, member_id uuid)"
    ).replace("RETURN QUERY SELECT v_member;", "RETURN QUERY SELECT v_user, v_member;")
    if "user_id uuid" not in restored or "v_user, v_member" not in restored:
        raise RuntimeError(
            "the downgrade could not find the two lines 051 changed; refusing "
            "to install a function it did not fully rewrite"
        )
    op.execute(text("DROP FUNCTION IF EXISTS core.bind_subject_to_organization(TEXT, TEXT, TEXT)"))
    # 🔴 THE RAW CURSOR, NOT `op.execute(text(...))`.
    #
    # `op.execute` wraps its argument in `text()`, which scans for `:name` bind
    # parameters. This string is a whole plpgsql body including every inline
    # comment, and `_sql.py` records migration 007 dying on *"A value is
    # required for bind parameter 'false'"* because a COMMENT contained
    # `{"rework":false}`. It is safe today only because SQLAlchemy's regex
    # excludes `:=` and `::`; one future comment containing `:word` inside this
    # function would break the downgrade with an error that reads like a typo.
    # Raised by the Supervisor. `_sql.apply_sql` avoids this the same way.
    op.get_bind().exec_driver_sql(restored)
    op.execute(
        text(
            "ALTER FUNCTION core.bind_subject_to_organization(TEXT, TEXT, TEXT)"
            " OWNER TO evercoat_owner"
        )
    )
    op.execute(
        text(
            "REVOKE ALL ON FUNCTION core.bind_subject_to_organization(TEXT, TEXT, TEXT) FROM PUBLIC"
        )
    )
    op.execute(
        text(
            "GRANT EXECUTE ON FUNCTION core.bind_subject_to_organization(TEXT, TEXT, TEXT)"
            " TO evercoat_app"
        )
    )
    # ⚠️ `DROP FUNCTION` DISCARDS THE COMMENT -- `CREATE OR REPLACE` would have
    # kept it. Without this the downgraded function carries no comment at all,
    # while `i1000` describes a schema in which it carries 050's. That is the
    # same argument this file's own header makes about the downgrade being an
    # honest description of the target revision, applied to the comment
    # instead of only to the behaviour. Raised by the Supervisor.
    op.execute(
        text(
            "COMMENT ON FUNCTION core.bind_subject_to_organization(TEXT, TEXT, TEXT) IS "
            "'Resolve a Keycloak subject and bind it to the CURRENT SESSION''s "
            "organization, atomically, returning the identifiers only after the "
            "membership exists (I82). It PROVES the caller''s standing before "
            "writing: the session''s user must hold admin.users in the session''s "
            "organization according to core.authorization_for_current_session(). "
            "It does not report whether the identity already existed. "
            "⚠️ RETURNS user_id, which IS that answer -- see j1000.'"
        )
    )
