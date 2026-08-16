"""Alembic environment.

Two decisions worth stating, because both are deliberate departures from
the default template.

**The hand-written SQL stays.** `001_core_tenancy.sql` and
`002_seed_roles_permissions.sql` contain RLS policies, `SECURITY DEFINER`
functions, trigger-enforced append-only audit, a SHA-256 hash chain,
composite tenant keys and phased parallel-run logic. `--autogenerate`
produces none of that — it compares table structure and would silently
drop every security control on the first regeneration. So Alembic
provides *version tracking and ordering*; the SQL files remain the
authoritative definition, and each revision applies one.

**Migrations run as the owner role, not the runtime role.** ADR-017
separates them: the runtime role deliberately has no DDL privilege. An
earlier draft of the plan required migrations to run as the app role,
which Codex correctly flagged as unworkable (F19) — that would mean
granting DDL to the role the application connects with, defeating the
separation entirely.
"""

from __future__ import annotations

import os
import sys
from logging.config import fileConfig
from pathlib import Path

from alembic import context
from sqlalchemy import engine_from_config, pool

# Make `app` importable without installing the package, so `alembic
# upgrade head` works from a checkout.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)


def _database_url() -> str:
    """Resolve the URL, preferring an explicit migration credential.

    ``MIGRATION_DATABASE_URL`` should carry the *owner* role. It falls
    back to ``DATABASE_URL`` only so a developer's first run works; in CI
    and production the two are different roles by design, and running
    migrations as the app role is a configuration error rather than a
    convenience.
    """
    url = os.getenv("MIGRATION_DATABASE_URL") or os.getenv("DATABASE_URL")
    if not url:
        raise RuntimeError(
            "set MIGRATION_DATABASE_URL (owner role) or DATABASE_URL before running alembic"
        )
    return url


def run_migrations_offline() -> None:
    """Emit SQL to stdout without connecting.

    Useful for review before applying to production: a migration that
    touches RLS policies deserves to be read by a human first.
    """
    context.configure(
        url=_database_url(),
        target_metadata=None,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        # Matches the online path -- see the note there.
        version_table_schema=None,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    section = config.get_section(config.config_ini_section, {})
    section["sqlalchemy.url"] = _database_url()

    connectable = engine_from_config(
        section,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=None,
            # The version table stays in `public`, deliberately.
            #
            # Putting it in `audit` looked tidier and does not work.
            # Alembic creates the version table BEFORE running any
            # migration, but `audit` — and the `evercoat_owner` role that
            # should own it — are both created BY migration 001.
            #
            # Pre-creating the schema in this file "fixed" the error and
            # introduced a worse bug: the schema was then owned by the
            # migration user, so migration 001's
            # `CREATE SCHEMA ... AUTHORIZATION evercoat_owner` silently
            # became a no-op and evercoat_owner ended up without USAGE.
            # That surfaced only as three fixture errors in the tenancy
            # suite — a permissions defect introduced by a convenience.
            #
            # `public` has no such ordering dependency. Alembic's version
            # table is deployment metadata, not an R&D record, so it does
            # not belong in the controlled schemas anyway.
            version_table_schema=None,
            # Wrap each migration in its own transaction so a failure
            # leaves a defined state rather than a half-applied schema.
            transaction_per_migration=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
