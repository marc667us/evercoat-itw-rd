"""an agent may draft, but never publish

Revision ID: s1000
Revises: r1000
Created: 2026-08-30

The agent tier that maintains the public competitor catalogue, and the
boundary that keeps it from putting invented claims in front of anonymous
readers.

🔴 THE PROBE BELOW IS THE POINT OF THIS MIGRATION.

Asserting that a trigger EXISTS would pass for a trigger that returns NEW
unconditionally. So the migration assumes the agent's identity with
`SET ROLE` and tries the write the boundary is supposed to refuse — then
tries the one it is supposed to allow, because a trigger that refused
everything would also pass the first half.
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op
from sqlalchemy import text

from migrations_alembic._sql import apply_sql

revision: str = "s1000"
down_revision: str | None = "r1000"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    apply_sql("060_an_agent_may_draft_but_never_publish.sql")

    bind = op.get_bind()

    # -----------------------------------------------------------------
    # 1. The role is what this migration assumes.
    # -----------------------------------------------------------------
    attrs = bind.execute(
        text(
            """
            SELECT rolsuper, rolcreatedb, rolcreaterole, rolbypassrls,
                   rolreplication, rolinherit
              FROM pg_roles WHERE rolname = 'evercoat_agent'
            """
        )
    ).one_or_none()
    if attrs is None:
        raise RuntimeError("evercoat_agent was not created")
    if any(
        [
            attrs.rolsuper,
            attrs.rolcreatedb,
            attrs.rolcreaterole,
            attrs.rolbypassrls,
            attrs.rolreplication,
            attrs.rolinherit,
        ]
    ):
        raise RuntimeError(
            "evercoat_agent has privileges it must not have. NOINHERIT and "
            "NOBYPASSRLS are load-bearing: with either missing the agent "
            "connection can reach rows the boundary assumes it cannot."
        )

    # It must belong to no group. `NOINHERIT` stops privileges arriving
    # automatically; a membership would still let it `SET ROLE` deliberately,
    # and `current_user` would then no longer be 'evercoat_agent'.
    memberships = bind.execute(
        text(
            """
            SELECT g.rolname
              FROM pg_auth_members m
              JOIN pg_roles r ON r.oid = m.member
              JOIN pg_roles g ON g.oid = m.roleid
             WHERE r.rolname = 'evercoat_agent'
            """
        )
    ).all()
    if memberships:
        raise RuntimeError(
            f"evercoat_agent is a member of {[m.rolname for m in memberships]}; "
            "it could SET ROLE to one of them and step outside the draft-only "
            "trigger, which reads current_user."
        )

    # -----------------------------------------------------------------
    # 2. It cannot reach what it has no business reading.
    # -----------------------------------------------------------------
    for privilege in ("SELECT", "INSERT", "UPDATE", "DELETE"):
        if bind.execute(
            text(
                "SELECT has_table_privilege('evercoat_agent', 'public_intel.access_requests', :p)"
            ),
            {"p": privilege},
        ).scalar_one():
            raise RuntimeError(
                f"evercoat_agent holds {privilege} on access_requests. Those "
                "rows are names and work addresses submitted by members of "
                "the public."
            )

    for table in ("manufacturers", "products", "news_items", "product_documents"):
        # ⚠️ THE TABLE NAME IS A BIND PARAMETER, NOT AN f-STRING.
        # `has_table_privilege` takes the relation name as a VALUE, so there is
        # no reason to build SQL here -- and Semgrep's `avoid-sqlalchemy-text`
        # blocked the f-string version, correctly. The tuple above is hardcoded
        # today; it is one edit away from not being, and by then nobody
        # re-reads the loop.
        if bind.execute(
            text("SELECT has_table_privilege('evercoat_agent', :rel, 'DELETE')"),
            {"rel": f"public_intel.{table}"},
        ).scalar_one():
            raise RuntimeError(
                f"evercoat_agent holds DELETE on {table}; it could erase the "
                "record of what it previously proposed."
            )

    reachable = bind.execute(
        text(
            """
            SELECT n.nspname, c.relname
              FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
             WHERE c.relkind IN ('r', 'v', 'm', 'p', 'f')
               AND n.nspname NOT IN ('pg_catalog', 'information_schema')
               AND n.nspname <> 'public_intel'
               AND (has_table_privilege('evercoat_agent', c.oid, 'SELECT')
                 OR has_table_privilege('evercoat_agent', c.oid, 'INSERT')
                 OR has_table_privilege('evercoat_agent', c.oid, 'UPDATE')
                 OR has_table_privilege('evercoat_agent', c.oid, 'DELETE'))
            """
        )
    ).all()
    if reachable:
        raise RuntimeError(
            "evercoat_agent can reach tables outside public_intel: "
            f"{[(r.nspname, r.relname) for r in reachable]}. The agent tier "
            "curates a public catalogue and has no tenant."
        )

    # -----------------------------------------------------------------
    # 3. 🔴 THE BOUNDARY REFUSES, AND ALLOWS. Both halves.
    #
    # Run under `SET ROLE evercoat_agent` so `current_user` is the agent —
    # which is why the trigger reads `current_user` as well as
    # `session_user`. A probe that could not assume the identity could only
    # assert the trigger exists, and a trigger that returns NEW
    # unconditionally exists too.
    # -----------------------------------------------------------------
    published_refused = False
    try:
        with bind.begin_nested():
            bind.execute(text("SET LOCAL ROLE evercoat_agent"))
            bind.execute(
                text(
                    """
                    INSERT INTO public_intel.manufacturers
                        (name, content_origin, publication_status,
                         is_demonstration_data)
                    VALUES ('__agent_probe_published__', 'synthetic',
                            'published', true)
                    """
                )
            )
    except Exception:  # noqa: BLE001 - the probe asks WHETHER it refuses
        published_refused = True
    if not published_refused:
        raise RuntimeError(
            "an agent PUBLISHED a row. The draft-only boundary does not hold, "
            "which means generated content can reach anonymous readers as fact."
        )

    review_refused = False
    try:
        with bind.begin_nested():
            bind.execute(text("SET LOCAL ROLE evercoat_agent"))
            bind.execute(
                text(
                    """
                    INSERT INTO public_intel.manufacturers
                        (name, content_origin, publication_status,
                         reviewed_at)
                    VALUES ('__agent_probe_review__', 'synthetic', 'draft',
                            clock_timestamp())
                    """
                )
            )
    except Exception:  # noqa: BLE001
        review_refused = True
    if not review_refused:
        raise RuntimeError(
            "an agent recorded a review. `reviewed_by`/`reviewed_at` is what "
            "the publication invariant reads to accept a 'verified' row, so an "
            "agent that can set it can manufacture its own evidence."
        )

    # And the write it IS for. Without this, a trigger that refused every
    # agent write would pass both probes above and the agent tier would be
    # unable to do its job.
    with bind.begin_nested() as allowed:
        bind.execute(text("SET LOCAL ROLE evercoat_agent"))
        bind.execute(
            text(
                """
                INSERT INTO public_intel.manufacturers
                    (name, content_origin, publication_status)
                VALUES ('__agent_probe_draft__', 'source_derived', 'draft')
                """
            )
        )
        allowed.rollback()


def downgrade() -> None:
    raise NotImplementedError(
        "060 is not reversible: dropping the draft-only trigger would leave an "
        "agent role able to publish."
    )
