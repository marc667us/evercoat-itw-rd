# -*- coding: utf-8 -*-
"""Database session and tenant/user context.

This module is where Row Level Security either works or silently fails.

The tenancy model (ADR-016) enforces BOTH organization isolation and
project membership in PostgreSQL, via two GUCs read by
``core.current_org_id()`` and ``core.current_user_id()``. Those GUCs must
be set correctly on every request, and unset correctly afterwards.

The classic failure mode (Codex F34) is a plain ``SET``, which persists
for the life of a pooled connection. Request A sets its organization,
finishes, returns the connection to the pool, and request B — belonging
to a different organization — inherits it. RLS then dutifully enforces
the *wrong* tenant, and every query looks perfectly normal. Nothing
errors. The data is simply wrong, quietly, in production.

Three defences here:

1.  ``SET LOCAL`` only, always inside an explicit transaction, so the
    setting dies with the transaction rather than the connection.
2.  Connections are reset on checkin, so a leaked setting cannot outlive
    a transaction even if a code path escapes the helper.
3.  **Fail closed.** A request that reaches the database without context
    raises rather than proceeding. During Slice 1 the SQL policies are
    permissive when the GUC is absent (so the stack is usable before
    every path sets context), which means an unset GUC would otherwise
    read as "no restriction" — the most dangerous default there is. This
    guard is what makes the permissive parallel-run window safe.
"""

from __future__ import annotations

import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass

from sqlalchemy import create_engine, event, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings

__all__ = [
    "RequestContext",
    "MissingContextError",
    "get_engine",
    "SessionLocal",
    "session_scope",
    "unscoped_session_scope",
    "apply_context",
    "set_local",
]


class MissingContextError(RuntimeError):
    """Raised when a database session is used without tenant/user context.

    Deliberately not an HTTP error: reaching the database with no identity
    is a programming fault, not a client fault, and it must be loud.
    """


@dataclass(frozen=True, slots=True)
class RequestContext:
    """Who is asking, and on whose behalf.

    Both values come from the verified JWT — never from a header, query
    parameter or request body. A client-supplied organization id would
    make the entire tenancy model advisory.
    """

    organization_id: uuid.UUID
    user_id: uuid.UUID

    def __post_init__(self) -> None:
        # UUIDs are interpolated into a SET LOCAL statement below, because
        # PostgreSQL does not accept bind parameters in SET. Typing them as
        # uuid.UUID and validating here is what makes that interpolation
        # safe -- a str would be an injection surface.
        if not isinstance(self.organization_id, uuid.UUID):
            raise TypeError("organization_id must be uuid.UUID")
        if not isinstance(self.user_id, uuid.UUID):
            raise TypeError("user_id must be uuid.UUID")


_engine: Engine | None = None
_session_factory: sessionmaker[Session] | None = None


def get_engine() -> Engine:
    """Create the engine on first use, not at import.

    Building it at module scope made ``import app.core.db`` require a full
    valid configuration, which meant a test that only wanted to assert
    ``session_scope(None)`` raises could not import the module at all.
    That is a smell worth fixing rather than working around: a module that
    cannot be imported without a live database is one that cannot be unit
    tested, and it would fail at collection time in CI for the same reason.
    """
    global _engine, _session_factory
    if _engine is not None:
        return _engine

    _engine = create_engine(
        settings.database_url,
        pool_pre_ping=True,
        pool_size=settings.db_pool_size,
        max_overflow=settings.db_max_overflow,
        # Defence 2. DISCARD ALL clears GUCs, prepared statements, temp
        # tables and cursors, so nothing survives a checkin even if a code
        # path escapes session_scope(). Slightly more expensive than the
        # default rollback; the cost of the alternative is cross-tenant
        # disclosure.
        pool_reset_on_return="rollback",
        echo=settings.db_echo,
    )

    @event.listens_for(_engine, "checkin")
    def _scrub_connection(dbapi_connection, connection_record) -> None:  # type: ignore[no-untyped-def]
        """Belt and braces: explicitly discard session state on checkin."""
        try:
            with dbapi_connection.cursor() as cur:
                cur.execute("DISCARD ALL")
        except Exception:  # noqa: BLE001
            # A connection we cannot scrub must not be reused. Invalidating
            # it costs one reconnect; keeping it risks leaking context.
            connection_record.invalidate()

    _session_factory = sessionmaker(
        bind=_engine, expire_on_commit=False, class_=Session
    )
    return _engine


def SessionLocal() -> Session:  # noqa: N802 - kept as a callable factory name
    """Session factory. Initialises the engine on first call."""
    if _session_factory is None:
        get_engine()
    assert _session_factory is not None  # noqa: S101 - narrowed by get_engine
    return _session_factory()


def set_local(session: Session, guc: str, value: uuid.UUID) -> None:
    """Issue ``SET LOCAL <guc> = '<uuid>'``.

    PostgreSQL does **not** accept bind parameters in SET — a placeholder
    there is a syntax error, not a slower query. So the value is
    interpolated, and the ``uuid.UUID`` type is what makes that safe: a
    UUID has no representation that can carry SQL. Passing a ``str`` here
    would be an injection surface, which is why the signature refuses one.

    The GUC name is validated against an allow-list for the same reason.
    """
    if guc not in _ALLOWED_GUCS:
        raise ValueError(f"refusing to set unknown GUC {guc!r}")
    if not isinstance(value, uuid.UUID):
        raise TypeError("GUC values must be uuid.UUID, never str")
    session.execute(text(f"SET LOCAL {guc} = '{value}'"))


_ALLOWED_GUCS = frozenset({"app.current_org", "app.current_user_id"})


def apply_context(session: Session, ctx: RequestContext) -> None:
    """Set the RLS GUCs for the current transaction.

    ``SET LOCAL`` is scoped to the transaction, so it is discarded on
    COMMIT or ROLLBACK. Using ``SET`` here instead would reintroduce the
    pooled-connection leak this whole module exists to prevent.
    """
    if not session.in_transaction():
        # SET LOCAL outside a transaction is silently a no-op with a
        # warning -- the GUC would never be set and RLS would fall through
        # to the permissive branch. Refuse rather than half-work.
        raise MissingContextError(
            "apply_context requires an open transaction; SET LOCAL is a "
            "no-op outside one"
        )

    set_local(session, "app.current_org", ctx.organization_id)
    set_local(session, "app.current_user_id", ctx.user_id)


@contextmanager
def session_scope(ctx: RequestContext | None) -> Iterator[Session]:
    """Transactional session with tenant/user context applied.

    Every database access in the application goes through here. There is
    no supported path that reaches PostgreSQL without context.

    Args:
        ctx: The verified caller. ``None`` is permitted only for the
            handful of genuinely context-free operations -- health checks,
            JWKS refresh, migration bootstrap -- and those must pass
            ``allow_unscoped=True`` via :func:`unscoped_session_scope`.

    Raises:
        MissingContextError: if called without context (defence 3).
    """
    if ctx is None:
        raise MissingContextError(
            "database access attempted without RequestContext. If this is a "
            "genuinely context-free operation (health, JWKS, migrations), "
            "use unscoped_session_scope() and justify it in review."
        )

    session = SessionLocal()
    try:
        session.begin()
        apply_context(session, ctx)
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


@contextmanager
def unscoped_session_scope() -> Iterator[Session]:
    """Session with NO tenant context. Rare, audited, and deliberately ugly.

    Legitimate uses are narrow: liveness/readiness probes, Keycloak JWKS
    caching, and migration bootstrap. It is named awkwardly on purpose --
    a reviewer should notice every call site.

    Once the FORCE RLS cutover migration lands, this session sees nothing
    in tenant-scoped tables anyway, because the policies stop being
    permissive when the GUC is absent. That is the intended end state:
    the guard above catches the mistake in development, and the database
    catches it in production.
    """
    session = SessionLocal()
    try:
        session.begin()
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
