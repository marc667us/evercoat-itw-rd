"""Apply a hand-written .sql file from an Alembic revision.

The security-critical DDL lives in `migrations/*.sql` rather than in
Python, because Alembic's autogenerate cannot express RLS policies,
SECURITY DEFINER functions, trigger-enforced append-only tables or a hash
chain -- and would quietly drop all of them on the first regeneration.
Alembic supplies ordering and version tracking; the SQL stays canonical.
"""

from __future__ import annotations

from pathlib import Path

from alembic import op

_MIGRATIONS = Path(__file__).resolve().parents[1] / "migrations"


def apply_sql(filename: str) -> None:
    """Execute one migration file.

    Read as UTF-8 explicitly. On this host PowerShell writes UTF-16 with
    a BOM by default, and a BOM at the head of a .sql file makes the
    first statement a syntax error in a way that reads like a typo.
    """
    path = _MIGRATIONS / filename
    if not path.exists():
        raise FileNotFoundError(f"migration not found: {path}")

    sql = path.read_text(encoding="utf-8")

    # The .sql files manage their own BEGIN/COMMIT so they can be applied
    # standalone with psql. Alembic already opens a transaction per
    # migration, so nested control statements are stripped rather than
    # fighting over transaction boundaries.
    lines = [line for line in sql.splitlines() if line.strip().upper() not in {"BEGIN;", "COMMIT;"}]
    op.execute("\n".join(lines))
