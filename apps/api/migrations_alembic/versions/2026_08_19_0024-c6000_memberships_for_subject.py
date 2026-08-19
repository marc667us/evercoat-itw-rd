"""how a browser learns which organization it may ask for

Revision ID: c6000
Revises: c5000
Created: 2026-08-19

`get_principal` requires `X-Organization-Id`, and every authenticated
route depends on it. So a browser that had just signed in held a valid
token and no way to discover a tenant to ask for -- authentication
completed and the application was still unusable.

`core.memberships_for_subject` answers that one question, before any
organization has been chosen. It is SECURITY DEFINER because it must run
with no RLS GUC set; it is scoped strictly to the verified token subject
and takes no organization argument, by design.

Full reasoning, including why an ordinary query would have worked today
and returned zero rows after the FORCE RLS cutover, is in
`migrations/024_memberships_for_subject.sql`. See also ADR-025.
"""

from __future__ import annotations

from collections.abc import Sequence

from migrations_alembic._sql import apply_sql

revision: str = "c6000"
down_revision: str | None = "c5000"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    apply_sql("024_memberships_for_subject.sql")


def downgrade() -> None:
    """Drop the function and the grants that go with it.

    Safe to reverse, unlike most migrations here: it creates no table and
    stores no data, so nothing is lost. Dropping it does break sign-in --
    `GET /api/me` is the only caller and has no fallback - which is
    stated here so that is a decision rather than a surprise.
    """
    from alembic import op

    op.execute("DROP FUNCTION IF EXISTS core.memberships_for_subject(TEXT)")
