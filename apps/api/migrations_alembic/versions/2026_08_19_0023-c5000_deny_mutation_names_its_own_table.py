"""the append-only guard must name the table it actually guarded

Revision ID: c5000
Revises: c4000
Created: 2026-08-19

🔴 THIS FILE IS WHY 023 HAD NEVER RUN.

`migrations/023_deny_mutation_names_its_own_table.sql` was written in the
previous session and no Alembic revision was ever created for it. CI
applies migrations with `alembic upgrade head`, NOT with a loop over
`migrations/*.sql` -- deliberately, because a glob has no record of what
has already run. So the file sat in the repository, reviewed and
committed, and was applied to no database anywhere.

Nothing failed. The migration only corrects the text of an exception, so
its absence is invisible until somebody reads a refusal that names
`audit.events` while deleting from `ai.msd_evidence` -- which is the
exact confusion it was written to end, and which cost a CI round trip
once already.

**A migration is not applied because a file exists.** Adding a .sql file
to `migrations/` does nothing on its own; the revision here is the thing
that runs it.
"""

from __future__ import annotations

from collections.abc import Sequence

from migrations_alembic._sql import apply_sql

revision: str = "c5000"
down_revision: str | None = "c4000"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    apply_sql("023_deny_mutation_names_its_own_table.sql")


def downgrade() -> None:
    """Deliberately not implemented.

    Reverting would restore a guard that names the wrong table in its
    refusal. The behaviour is identical either way -- only the message
    differs -- so a downgrade buys nothing and reintroduces a documented
    source of misdiagnosis.
    """
    raise NotImplementedError(
        "reverting would restore an exception message that names the wrong table"
    )
