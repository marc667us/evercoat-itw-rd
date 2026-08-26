"""an identity has no tenant attributes; a membership does

Revision ID: k1000
Revises: j1000
Created: 2026-08-26

Closes I106 — the channel 051 named in its own header and left open — and
I108, found while measuring it.

🔴 THE MEMBERSHIP COLUMNS ARE NOT THE CLOSURE. The revoke is.

I106 is a rolled-back bind reading a foreign identity's stored email and
display name through the membership it just created. The obvious fix is
tenant-scoped attributes on `core.organization_members`, and this migration
adds them — but measuring the defect turned up I108: `evercoat_app` holds
table-level INSERT on that table, `org_member_isolation` constrains only
`organization_id`, and `user_id` is a plain FK to a global table. So an
ORDINARY member — no `admin.users`, no EXECUTE on the bind, no
`keycloak_sub` — can manufacture a membership naming any identity in the
system, read it, and roll back. Measured.

That reframes it. The defect is not "the bind leaks"; it is **a membership
row turns a global identity into a readable one**, and the bind is one of
two ways to make one. What actually closes both is that
`core.users.email` and `core.users.display_name` stop being readable by the
runtime roles at all. The membership columns are what keeps the application
working once they are gone.
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op
from sqlalchemy import text

from migrations_alembic._sql import apply_sql

revision: str = "k1000"
down_revision: str | None = "j1000"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    apply_sql("052_an_identity_has_no_tenant_attributes.sql")


# ---------------------------------------------------------------------------
# The downgrade
# ---------------------------------------------------------------------------
# `j1000` describes a schema in which I106 and I108 were both open, so this
# reopens them. A downgrade that quietly kept the fix would make that
# description false — the same argument 049, 050 and 051 each make.

_RESTORE_DUPLICATE_GUARD = """
CREATE OR REPLACE FUNCTION core.deny_duplicate_address_in_organization()
RETURNS TRIGGER
LANGUAGE plpgsql
SECURITY INVOKER
AS $fn$
DECLARE
    v_email public.citext;
BEGIN
    SELECT u.email INTO v_email
      FROM core.users u
     WHERE u.id = NEW.user_id;

    IF v_email IS NULL THEN
        RETURN NEW;
    END IF;

    PERFORM pg_advisory_xact_lock(
        hashtext(NEW.organization_id::TEXT),
        hashtext(v_email::TEXT)
    );

    IF EXISTS (
        SELECT 1
          FROM core.organization_members om
          JOIN core.users u ON u.id = om.user_id
         WHERE om.organization_id = NEW.organization_id
           AND om.id <> NEW.id
           AND om.status = 'active'
           AND u.email = v_email
    ) THEN
        RAISE EXCEPTION
            'address already belongs to an active member of this organization'
            USING ERRCODE = 'unique_violation',
                  CONSTRAINT = 'organization_members_one_address_per_organization';
    END IF;

    RETURN NEW;
END $fn$;
"""

_RESTORE_RENAME_GUARD = """
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

    IF core.current_org_id() IS NULL THEN
        RETURN NEW;
    END IF;

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
           AND mine.organization_id = core.current_org_id()
           AND u.email = NEW.email
    ) THEN
        RAISE EXCEPTION
            'address already belongs to an active member of this organization'
            USING ERRCODE = 'unique_violation',
                  CONSTRAINT = 'users_address_stays_unique_in_organization';
    END IF;

    RETURN NEW;
END $fn$;
"""

_RESTORE_PRINCIPAL = """
CREATE OR REPLACE FUNCTION core.principal_for_subject(p_sub TEXT, p_org UUID)
RETURNS TABLE (
    user_id         UUID,
    email           TEXT,
    display_name    TEXT,
    organization_id UUID,
    roles           TEXT[],
    permissions     TEXT[]
)
    LANGUAGE sql
    STABLE
    SECURITY DEFINER
    SET search_path = core, pg_temp
AS $$
    SELECT u.id,
           u.email::TEXT,
           u.display_name,
           om.organization_id,
           COALESCE(array_agg(DISTINCT r.code)
                    FILTER (WHERE r.code IS NOT NULL), '{}'),
           COALESCE(array_agg(DISTINCT p.code)
                    FILTER (WHERE p.code IS NOT NULL), '{}')
    FROM core.users u
    JOIN core.organization_members om
      ON om.user_id = u.id
     AND om.status  = 'active'
    LEFT JOIN core.member_roles     mr ON mr.member_id = om.id
    LEFT JOIN core.roles            r  ON r.id = mr.role_id
    LEFT JOIN core.role_permissions rp ON rp.role_id = r.id
    LEFT JOIN core.permissions      p  ON p.id = rp.permission_id
    WHERE u.keycloak_sub = p_sub
      AND u.status = 'active'
      AND om.organization_id = p_org
    GROUP BY u.id, u.email, u.display_name, om.organization_id
$$;
"""

_RESTORE_MEMBERSHIPS = """
CREATE OR REPLACE FUNCTION core.memberships_for_subject(p_sub TEXT)
RETURNS TABLE (
    user_id           UUID,
    email             TEXT,
    display_name      TEXT,
    organization_id   UUID,
    organization_name TEXT,
    organization_code TEXT,
    roles             TEXT[],
    permissions       TEXT[]
)
    LANGUAGE sql
    STABLE
    SECURITY DEFINER
    SET search_path = core, pg_temp
AS $$
    SELECT u.id,
           u.email::TEXT,
           u.display_name,
           om.organization_id,
           o.name,
           o.code,
           COALESCE(array_agg(DISTINCT r.code ORDER BY r.code)
                    FILTER (WHERE r.code IS NOT NULL), '{}'),
           COALESCE(array_agg(DISTINCT p.code ORDER BY p.code)
                    FILTER (WHERE p.code IS NOT NULL), '{}')
    FROM core.users u
    JOIN core.organization_members om
      ON om.user_id = u.id
     AND om.status  = 'active'
    JOIN core.organizations o
      ON o.id = om.organization_id
     AND o.status = 'active'
    LEFT JOIN core.member_roles     mr ON mr.member_id = om.id
    LEFT JOIN core.roles            r  ON r.id = mr.role_id
    LEFT JOIN core.role_permissions rp ON rp.role_id = r.id
    LEFT JOIN core.permissions      p  ON p.id = rp.permission_id
    WHERE u.keycloak_sub = p_sub
      AND u.status = 'active'
    GROUP BY u.id, u.email, u.display_name, om.organization_id, o.name, o.code
    ORDER BY o.name
$$;
"""


def downgrade() -> None:
    bind = op.get_bind()

    # 🔴 REFUSE RATHER THAN INSTALL A GUARD THE DATA ALREADY VIOLATES.
    #
    # 052 stops policing `core.users.email`, so two members of ONE
    # organization may since have acquired the same GLOBAL address while
    # holding different membership addresses. Restoring 046's triggers over
    # that data leaves a rule that is false the moment anyone touches those
    # rows — a guard installed against a population that violates it.
    # Same shape as 046's own downgrade, which refuses rather than deleting.
    colliding = bind.execute(
        text(
            """
            SELECT count(*) FROM (
                SELECT om.organization_id, u.email
                  FROM core.organization_members om
                  JOIN core.users u ON u.id = om.user_id
                 WHERE om.status = 'active'
                 GROUP BY 1, 2
                HAVING count(*) > 1
            ) x
            """
        )
    ).scalar_one()
    if colliding:
        raise RuntimeError(
            f"{colliding} organization(s) hold two active members whose GLOBAL "
            "core.users.email is the same. 046's trigger guards enforce that "
            "rule and this downgrade would install them against data that "
            "already breaks it. Reconcile core.users.email with "
            "core.organization_members.email first; refusing rather than "
            "deleting rows."
        )

    # 1. The definers stop reading the membership's attributes.
    for stmt in (_RESTORE_PRINCIPAL, _RESTORE_MEMBERSHIPS):
        # The raw cursor, not `op.execute(text(...))`: these bodies contain
        # `::TEXT` and `:=`-free SQL today, but `text()` scans for `:name`
        # and migration 007 died on exactly that. `_sql.apply_sql` avoids it
        # the same way.
        bind.exec_driver_sql(stmt)
    op.execute(
        text("ALTER FUNCTION core.principal_for_subject(TEXT, UUID) OWNER TO evercoat_owner")
    )
    op.execute(text("ALTER FUNCTION core.memberships_for_subject(TEXT) OWNER TO evercoat_owner"))

    # 2. The bind stops writing them. The body is re-read from the catalogue
    #    and only the lines 052 changed are put back, because a hand-retyped
    #    plpgsql body dropped a `pg_advisory_xact_lock` in 049 and the lesson
    #    is standing: copy a security body programmatically.
    body = bind.execute(
        text(
            "SELECT pg_get_functiondef(p.oid) FROM pg_proc p"
            " JOIN pg_namespace n ON n.oid = p.pronamespace"
            " WHERE n.nspname = 'core' AND p.proname = 'bind_subject_to_organization'"
        )
    ).scalar_one()
    restored = body.replace(
        "INSERT INTO core.organization_members\n"
        "        (organization_id, user_id, email, display_name)\n"
        "    VALUES (v_org, v_user, p_email::public.citext, p_display_name)",
        "INSERT INTO core.organization_members (organization_id, user_id)\n"
        "    VALUES (v_org, v_user)",
    )
    # 🔴 THE CHECK NAMES THE MEMBERSHIP INSERT, NOT THE WORDS IT CONTAINS.
    #
    # The first version asked whether `"email, display_name"` still appeared
    # anywhere in the body. It always does -- the `core.users` INSERT above
    # names both columns -- so the guard fired on a CORRECT rewrite and this
    # downgrade could never run. Found by actually running it, not by reading
    # it: a guard that cannot pass is the mirror of one that cannot fail, and
    # both look right until something exercises them.
    if restored == body:
        raise RuntimeError(
            "the downgrade found nothing to replace in "
            "core.bind_subject_to_organization; it is not the function 052 "
            "installed, and rewriting it blind could drop the standing check"
        )
    if (
        "(organization_id, user_id, email, display_name)" in restored
        or "VALUES (v_org, v_user)" not in restored
    ):
        raise RuntimeError(
            "the downgrade did not fully rewrite the membership INSERT in "
            "core.bind_subject_to_organization; refusing to install a bind it "
            "only half changed"
        )
    bind.exec_driver_sql(restored)

    # 3. The guards come back, and the retype is checked rather than trusted.
    for stmt in (_RESTORE_DUPLICATE_GUARD, _RESTORE_RENAME_GUARD):
        if "pg_advisory_xact_lock" not in stmt:
            raise RuntimeError(
                "a restored address guard has no advisory lock. Without it a "
                "trigger that decides by SELECT is not a constraint: two "
                "concurrent writers both pass and both commit (measured, 046)."
            )
        bind.exec_driver_sql(stmt)
    op.execute(
        text("ALTER FUNCTION core.deny_duplicate_address_in_organization() OWNER TO evercoat_owner")
    )
    op.execute(
        text("ALTER FUNCTION core.deny_address_collision_on_rename() OWNER TO evercoat_owner")
    )

    op.execute(text("DROP INDEX IF EXISTS core.organization_members_one_address_per_organization"))
    op.execute(
        text(
            """
            CREATE CONSTRAINT TRIGGER organization_members_one_address_per_organization
                AFTER INSERT OR UPDATE OF user_id, status, organization_id
                ON core.organization_members
                DEFERRABLE INITIALLY IMMEDIATE
                FOR EACH ROW
                WHEN (NEW.status = 'active')
                EXECUTE FUNCTION core.deny_duplicate_address_in_organization()
            """
        )
    )
    op.execute(
        text(
            """
            CREATE CONSTRAINT TRIGGER users_address_stays_unique_in_organization
                AFTER UPDATE OF email ON core.users
                DEFERRABLE INITIALLY IMMEDIATE
                FOR EACH ROW
                WHEN (NEW.email IS DISTINCT FROM OLD.email)
                EXECUTE FUNCTION core.deny_address_collision_on_rename()
            """
        )
    )

    # 4. The privileges 052 removed. ⚠️ REOPENS I106 AND I108 — by design.
    op.execute(
        text(
            "GRANT SELECT (email, display_name) ON core.users"
            " TO evercoat_app, evercoat_report, evercoat_worker"
        )
    )
    op.execute(text("GRANT UPDATE (email, display_name) ON core.users TO evercoat_app"))
    op.execute(text("GRANT INSERT ON core.organization_members TO evercoat_app"))

    # 5. The columns go last: everything above had to stop reading them first.
    op.execute(
        text("ALTER TABLE core.organization_members DROP COLUMN email, DROP COLUMN display_name")
    )
