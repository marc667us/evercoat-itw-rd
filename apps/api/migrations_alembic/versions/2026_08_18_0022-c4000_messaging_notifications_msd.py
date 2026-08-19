"""messaging, notifications, and MSD with an auditable authorization boundary

Revision ID: c4000
Revises: c3000
Created: 2026-08-18
"""

from __future__ import annotations

from collections.abc import Sequence

from migrations_alembic._sql import apply_sql

revision: str = "c4000"
down_revision: str | None = "c3000"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    apply_sql("022_messaging_notifications_msd.sql")


def downgrade() -> None:
    """Not implemented.

    `ai.msd_evidence` is what makes §7's authorization boundary auditable
    rather than merely asserted: it records exactly which rows MSD
    retrieved to produce each answer, so an answer built on a record the
    asker could not read is DETECTABLE after the fact. Dropping it
    removes the only evidence that the boundary held.

    `messaging.messages` is a record of what people said to each other
    about controlled technical work, and several of those conversations
    are the reasoning behind decisions recorded elsewhere.
    """
    raise NotImplementedError(
        "msd_evidence is the proof the authorization boundary held; "
        "see 022_messaging_notifications_msd.sql"
    )
