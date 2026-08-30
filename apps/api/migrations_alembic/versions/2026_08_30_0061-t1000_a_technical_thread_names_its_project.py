"""a technical thread names its project (I21)

Revision ID: t1000
Revises: s1000
Created: 2026-08-30

A `technical_thread` channel could carry `project_id IS NULL`, and
`project_scope` treats a NULL project as organization-wide — so a discussion
of a restricted formulation was readable by everyone in the organization.

🔴 THE PROBE ASSERTS THE CONSTRAINT REFUSES, NOT THAT IT EXISTS.

`pg_constraint` would show a constraint that could not fail just as happily as
one that can. This attempts the insert the constraint is for, and then the one
it must still allow — because a constraint refusing every technical thread
would pass the first half and break messaging.
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence

from alembic import op
from sqlalchemy import text

from migrations_alembic._sql import apply_sql

revision: str = "t1000"
down_revision: str | None = "s1000"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    apply_sql("061_a_technical_thread_names_its_project.sql")

    bind = op.get_bind()

    # A tenant and a project to hang the probes on. Rolled back either way —
    # a migration that leaves probe rows behind has written data nobody asked
    # for into a real database.
    with bind.begin_nested() as probe:
        org = bind.execute(
            text(
                "INSERT INTO core.organizations (name, code) "
                "VALUES ('__probe_061__', '__P061__') RETURNING id"
            )
        ).scalar_one()
        user = bind.execute(text("SELECT id FROM core.users LIMIT 1")).scalar_one_or_none()
        if user is None:
            # No users yet (a fresh database mid-bootstrap). The constraint is
            # still asserted below against the catalogue; the behavioural probe
            # needs a creator and is skipped rather than faked.
            probe.rollback()
            _assert_constraint_exists(bind)
            return

        project = bind.execute(
            text(
                """
                INSERT INTO projects.projects
                    (organization_id, project_code, name, lead_user_id)
                VALUES (:org, '__P061__', '__probe_061__', :u)
                RETURNING id
                """
            ),
            {"org": org, "u": user},
        ).scalar_one()

        # 1. The write the constraint exists to refuse.
        refused = False
        try:
            with bind.begin_nested():
                bind.execute(
                    text(
                        """
                        INSERT INTO messaging.channels
                            (organization_id, channel_type, name, entity_type,
                             entity_id, created_by)
                        VALUES (:org, 'technical_thread', 'probe',
                                'formula_version', :eid, :u)
                        """
                    ),
                    {"org": org, "eid": str(uuid.uuid4()), "u": user},
                )
        except Exception:  # noqa: BLE001 - the probe asks WHETHER it refuses
            refused = True
        if not refused:
            probe.rollback()
            raise RuntimeError(
                "a technical_thread was created with no project. It is "
                "readable organization-wide, so a discussion of a restricted "
                "record would be too."
            )

        # 2. The write it must still allow, without which messaging is broken
        #    and every probe above passes anyway.
        with bind.begin_nested():
            bind.execute(
                text(
                    """
                    INSERT INTO messaging.channels
                        (organization_id, project_id, channel_type, name,
                         entity_type, entity_id, created_by)
                    VALUES (:org, :pid, 'technical_thread', 'probe',
                            'formula_version', :eid, :u)
                    """
                ),
                {"org": org, "pid": project, "eid": str(uuid.uuid4()), "u": user},
            )

        # 3. And a direct message still needs no project — 022 says those are
        #    governed by channel membership, and a constraint that broke them
        #    would be this fix overreaching.
        with bind.begin_nested():
            bind.execute(
                text(
                    """
                    INSERT INTO messaging.channels
                        (organization_id, channel_type, name, created_by)
                    VALUES (:org, 'direct', 'probe', :u)
                    """
                ),
                {"org": org, "u": user},
            )

        probe.rollback()

    _assert_constraint_exists(bind)


def _assert_constraint_exists(bind) -> None:  # type: ignore[no-untyped-def]
    present = bind.execute(
        text(
            """
            SELECT 1 FROM pg_constraint c
              JOIN pg_class t ON t.oid = c.conrelid
              JOIN pg_namespace n ON n.oid = t.relnamespace
             WHERE n.nspname = 'messaging' AND t.relname = 'channels'
               AND c.conname = 'channels_thread_channel_has_a_project'
            """
        )
    ).scalar_one_or_none()
    if present is None:
        raise RuntimeError(
            "channels_thread_channel_has_a_project is absent after this migration ran"
        )


def downgrade() -> None:
    raise NotImplementedError(
        "061 is not reversible: dropping the constraint would re-open an "
        "organization-wide read path for discussions of restricted records."
    )
