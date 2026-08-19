"""failures, hypotheses, evidence, corrective actions and why a version exists

Revision ID: c3000
Revises: c2000
Created: 2026-08-18
"""

from __future__ import annotations

from collections.abc import Sequence

from migrations_alembic._sql import apply_sql

revision: str = "c3000"
down_revision: str | None = "c2000"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    apply_sql("021_failures_hypotheses_evidence.sql")


def downgrade() -> None:
    """Not implemented.

    A failure investigation is the reasoning behind every reformulation
    that followed it. `formula_version_drivers` exists so the system can
    answer "why was F008 created?" -- §29 -- and dropping it makes that
    question permanently unanswerable for every version already recorded.

    `failure_hypotheses` carries the distinction §7 draws between an AI
    suggestion and a root cause a named human accepted. That attribution
    cannot be reconstructed from anything else once removed.
    """
    raise NotImplementedError(
        "an investigation is the reasoning behind the reformulations that "
        "followed it; see 021_failures_hypotheses_evidence.sql"
    )
