"""the bind proves the caller administers the tenant

Revision ID: i1000
Revises: h1000
Created: 2026-08-26

Fixes two defects migration 049 introduced, both raised by Codex and both
CONFIRMED BY MEASUREMENT before being accepted.

🔴 049 GRANTED A CROSS-TENANT WRITE WHILE REMOVING A CROSS-TENANT READ. The
bind is SECURITY DEFINER, so its INSERT runs as `evercoat_owner` and RLS does
not apply; the organization came from a GUC, and a GUC is caller-settable.
Measured: an attacker who is an active member of organization A only, setting
`app.current_org` to organization B, successfully created a membership in B.
Before 049 the route did that INSERT itself as `evercoat_app`, where
`org_member_isolation` refused it.

The function now PROVES the caller's standing instead of assuming it: it asks
`core.authorization_for_current_session()` (048) whether this session's user
holds `admin.users` in this session's organization. A forged pair fails on the
forgery.

🔴 AND THE "COST" WAS ROLLBACK-ABLE. 049 claimed the existence answer now cost
a membership row and an audit record. `BEGIN; SELECT ...; ROLLBACK;` returns
the answer and leaves nothing — measured. No function result can be made to
depend on a commit. `identity_created` is removed; it had no consumer.

⚠️ Codex also asked for the trigger guards' `search_path` to be narrowed back.
That change is DEFERRED and the reason is in the migration header: doing it
requires retyping the guard's whole body, and my draft silently dropped the
`pg_advisory_xact_lock` that makes it a constraint rather than a check two
writers walk past. Recorded in TODO.md.
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op
from sqlalchemy import text

from migrations_alembic._sql import apply_sql

revision: str = "i1000"
down_revision: str | None = "h1000"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    apply_sql("050_the_bind_proves_the_caller_administers_the_tenant.sql")


def downgrade() -> None:
    """Restore 049's function — WITH ITS DEFECTS, which is what a downgrade is.

    ⚠️ THIS REINSTATES A CROSS-TENANT WRITE AND AN EXISTENCE ORACLE. `h1000`
    describes a schema in which both existed, and a downgrade that quietly
    kept the fixes would make that description false. Do not run it as a way
    of "getting back to a working state"; it is strictly less safe.
    """
    op.execute(text("DROP FUNCTION IF EXISTS core.bind_subject_to_organization(TEXT, TEXT, TEXT)"))
    op.execute(
        text(
            """
            CREATE FUNCTION core.bind_subject_to_organization(
                p_subject TEXT, p_email TEXT, p_display_name TEXT
            )
                RETURNS TABLE (user_id UUID, member_id UUID, identity_created BOOLEAN)
                LANGUAGE plpgsql VOLATILE SECURITY DEFINER
                SET search_path = core, pg_temp
            AS $fn$
            DECLARE
                v_org     UUID := core.current_org_id();
                v_user    UUID;
                v_member  UUID;
                v_created BOOLEAN := FALSE;
            BEGIN
                IF v_org IS NULL THEN
                    RAISE EXCEPTION 'no organization in the session context'
                        USING ERRCODE = 'insufficient_privilege';
                END IF;
                SELECT id INTO v_user FROM core.users WHERE keycloak_sub = p_subject;
                IF v_user IS NULL THEN
                    INSERT INTO core.users (keycloak_sub, email, display_name)
                    VALUES (p_subject, p_email::public.citext, p_display_name)
                    RETURNING id INTO v_user;
                    v_created := TRUE;
                END IF;
                INSERT INTO core.organization_members (organization_id, user_id)
                VALUES (v_org, v_user)
                RETURNING id INTO v_member;
                RETURN QUERY SELECT v_user, v_member, v_created;
            END
            $fn$
            """
        )
    )
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
    # ⚠️ `DROP FUNCTION` DISCARDS THE COMMENT. `h1000` describes a schema in
    # which this function carries 049's, so restoring the body without it
    # leaves the description false in a way nothing would notice. Raised by the
    # Supervisor, which also pointed out this diff had just made the same
    # argument about `RESET search_path` and stopped one step short.
    op.execute(
        text(
            "COMMENT ON FUNCTION core.bind_subject_to_organization(TEXT, TEXT, TEXT) IS "
            "'Resolve a Keycloak subject and bind it to the CURRENT SESSION''s "
            "organization, atomically, returning the identifiers only after the "
            "membership exists (I82). ⚠️ THIS REVISION''s VERSION PROVES NOTHING "
            "ABOUT THE CALLER: a forged app.current_org drives an RLS-free "
            "membership write into another tenant, and identity_created answers "
            "a cross-tenant existence question for free. Both measured -- see "
            "i1000, which is why you should not be here.'"
        )
    )
