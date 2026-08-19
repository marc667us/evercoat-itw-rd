"""Every hand-written migration must actually be applied by something.

🔴 WHAT THIS CATCHES

`migrations/023_deny_mutation_names_its_own_table.sql` was written,
reviewed, committed and pushed in the previous session -- and **had never
run against any database.** No Alembic revision was ever created for it.

CI applies migrations with `alembic upgrade head`, deliberately, rather
than looping over `migrations/*.sql`: a glob applies files in glob order
with no record of what has already run, which is fine on a throwaway
database and useless anywhere the schema persists. The consequence is
that adding a `.sql` file to `migrations/` **does nothing at all** unless
a revision calls it.

Nothing failed, which is what makes it worth a test. Migration 023 only
corrects the text of an exception, so its absence is invisible until
somebody reads a refusal naming `audit.events` while deleting from
`ai.msd_evidence` -- the exact confusion it was written to end, and one
that had already cost a CI round trip.

A green pipeline proved nothing here, because the pipeline never knew the
file was supposed to exist. This test is the thing that knows.

It needs no database and no network.
"""

from __future__ import annotations

import re
from pathlib import Path

API_ROOT = Path(__file__).resolve().parents[1]
SQL_DIR = API_ROOT / "migrations"
VERSIONS_DIR = API_ROOT / "migrations_alembic" / "versions"

_APPLY_SQL = re.compile(r"""apply_sql\(\s*["']([^"']+)["']\s*\)""")


def _sql_migrations() -> set[str]:
    found = {path.name for path in SQL_DIR.glob("*.sql")}
    assert found, f"no .sql migrations found under {SQL_DIR}"
    return found


def _applied_by_alembic() -> list[str]:
    applied: list[str] = []
    for revision in VERSIONS_DIR.glob("*.py"):
        applied.extend(_APPLY_SQL.findall(revision.read_text(encoding="utf-8")))
    return applied


def test_every_sql_migration_is_applied_by_a_revision() -> None:
    """A .sql file nothing calls is a fix that has never been applied."""
    orphans = sorted(_sql_migrations() - set(_applied_by_alembic()))
    assert not orphans, (
        "these migrations exist as files and are applied by NO Alembic "
        "revision, so they have never run against any database:\n  "
        + "\n  ".join(orphans)
        + "\n\nAdd a revision in migrations_alembic/versions/ that calls "
        "apply_sql() for each. Being committed is not being applied."
    )


def test_every_revision_points_at_a_file_that_exists() -> None:
    """The mirror image: a revision naming a file that is not there.

    `_sql.py` raises FileNotFoundError at migration time, which means the
    failure surfaces during a deploy rather than during a test run. A
    renamed or deleted .sql file should break here instead.
    """
    missing = sorted(name for name in _applied_by_alembic() if not (SQL_DIR / name).is_file())
    assert not missing, (
        "these Alembic revisions call apply_sql() for files that do not exist, "
        "so `alembic upgrade head` will fail mid-deploy:\n  " + "\n  ".join(missing)
    )


def test_no_sql_migration_is_applied_twice() -> None:
    """Two revisions applying one file is a re-run nobody intended.

    Most of these files are not idempotent -- they create tables, add
    constraints and insert seed rows. Applying one twice fails the second
    time, in the middle of a deploy, on a database that is by then half
    migrated.
    """
    applied = _applied_by_alembic()
    duplicates = sorted({name for name in applied if applied.count(name) > 1})
    assert not duplicates, (
        "these .sql files are applied by more than one Alembic revision:\n  "
        + "\n  ".join(duplicates)
    )


def test_the_revision_chain_has_exactly_one_head() -> None:
    """Two heads mean `alembic upgrade head` is ambiguous and fails.

    Checked by reading the files rather than by asking Alembic, so it
    runs with no database configured -- the point is to fail in the unit
    suite, not at deploy time.
    """
    revisions: dict[str, str | None] = {}
    for path in VERSIONS_DIR.glob("*.py"):
        text = path.read_text(encoding="utf-8")
        rev = re.search(r'^revision:\s*str\s*=\s*["\']([^"\']+)["\']', text, re.M)
        down = re.search(r'^down_revision:\s*str\s*\|\s*None\s*=\s*(.+)$', text, re.M)
        if rev is None or down is None:
            continue
        raw_down = down.group(1).strip()
        parent = None if raw_down.startswith("None") else raw_down.strip("\"'")
        revisions[rev.group(1)] = parent

    assert revisions, f"no Alembic revisions parsed from {VERSIONS_DIR}"
    parents = {parent for parent in revisions.values() if parent is not None}
    heads = sorted(set(revisions) - parents)
    assert len(heads) == 1, f"expected exactly one head, found {heads}"

    orphan_parents = sorted(parents - set(revisions))
    assert not orphan_parents, (
        f"these revisions are named as down_revision but do not exist: {orphan_parents}"
    )
