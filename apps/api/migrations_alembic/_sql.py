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
    statement = "\n".join(lines)

    # Executed on the raw DBAPI cursor with NO parameters, which is the
    # only way to bypass BOTH parameter styles. Hand-written DDL is not a
    # parameterised query and must not be parsed as one; there are no
    # user inputs in these files to bind.
    #
    # Two real failures got us here:
    #
    #   op.execute(...)      wraps the string in sqlalchemy.text(), which
    #                        scans for ':name'. Migration 007 died on
    #                        "A value is required for bind parameter
    #                        'false'" because a COMMENT contained
    #                        {"rework":false}.
    #
    #   exec_driver_sql(...) hands it to psycopg with '%' placeholder
    #                        semantics. Migration 001 then died on
    #                        "incomplete placeholder: '%'" because its
    #                        DO block uses format('%I.%I', ...).
    #
    # psycopg only interpolates when parameters are supplied, so passing
    # none leaves the SQL untouched.
    connection = op.get_bind().connection
    with connection.cursor() as cursor:
        cursor.execute(statement)
