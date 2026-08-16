# -*- coding: utf-8 -*-
"""Structured JSON logging with typed channels.

Reused in shape from Solar's ``logging_config/structured_logger.py``
(REUSE.md R5), with the channels remapped to this domain. Typed channels
matter because "find every authorization failure last week" and "find
every formula approval last week" are different questions, and grepping
one undifferentiated stream answers neither well.

**What must never appear in a log line:** formula compositions, component
percentages, secrets, tokens, or full request bodies from formulation
endpoints (SECURITY.md §11). Log identifiers and outcomes, not payloads.
A log aggregator is not access-controlled the way the database is, so a
formula that leaks into Loki has left the protected boundary.
"""

from __future__ import annotations

import logging
import sys
from typing import Any, Literal

import structlog

from app.core.config import settings

__all__ = [
    "configure_logging",
    "log_audit",
    "log_security",
    "log_formulation",
    "log_laboratory",
    "log_testing",
    "log_ai",
    "log_queue",
]

Channel = Literal[
    "app", "audit", "security", "formulation",
    "laboratory", "testing", "ai", "queue", "error",
]

# Keys that must never be emitted, whatever a caller passes.
_REDACT = frozenset(
    {
        "password", "secret", "token", "access_token", "refresh_token",
        "authorization", "api_key", "client_secret", "private_key",
        "components", "composition", "weight_percent", "formula_components",
    }
)


def _redact(_logger: Any, _method: str, event: dict[str, Any]) -> dict[str, Any]:
    """Drop forbidden keys rather than masking them.

    Masking still confirms the field was present and hints at its length.
    For a formulation percentage that is already a meaningful leak, so the
    key is removed entirely and replaced with a marker.
    """
    for key in list(event):
        if key.lower() in _REDACT:
            event[key] = "<redacted>"
    return event


def configure_logging() -> None:
    # structlog's NATIVE processors, not the .stdlib ones.
    #
    # `structlog.stdlib.add_logger_name` reads `logger.name`, which only
    # exists on a stdlib logger. Paired with PrintLoggerFactory below it
    # raises AttributeError on the very first log line — which meant the
    # application aborted during startup, before binding a port, with the
    # failure buried in a structlog traceback rather than anything that
    # looked like a logging problem.
    #
    # PrintLoggerFactory is kept deliberately: it needs no stdlib logging
    # configuration, writes straight to stdout for the container runtime
    # to collect, and is faster. So the processors match the factory
    # instead of the factory matching the processors.
    processors: list[Any] = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        _redact,
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]
    processors.append(
        structlog.processors.JSONRenderer()
        if settings.log_format == "json"
        else structlog.dev.ConsoleRenderer(colors=True)
    )

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(
            logging.getLevelNamesMapping().get(settings.log_level.upper(), logging.INFO)
        ),
        logger_factory=structlog.PrintLoggerFactory(file=sys.stdout),
        cache_logger_on_first_use=True,
    )


def _emit(channel: Channel, event: str, **kwargs: Any) -> None:
    # channel is bound as a FIELD, not as a logger name. PrintLogger
    # has no name, so a name would simply vanish -- and a typed channel
    # that silently disappears is worse than none, because the queries
    # written against it return empty rather than failing.
    structlog.get_logger().info(event, channel=channel, **kwargs)


def log_audit(action: str, **kwargs: Any) -> None:
    """User actions on controlled records.

    This is the *operational* log of an action. It is not the audit trail
    -- ``audit.events`` is, and it is hash-chained and append-only. A log
    line can be lost, rotated or tampered with; the chain cannot, silently.
    Never treat this as evidence.
    """
    _emit("audit", action, **kwargs)


def log_security(event: str, **kwargs: Any) -> None:
    """Auth failures, tenant violations, permission denials."""
    _emit("security", event, **kwargs)


def log_formulation(event: str, **kwargs: Any) -> None:
    """Formula lifecycle. Identifiers and outcomes only -- never composition."""
    _emit("formulation", event, **kwargs)


def log_laboratory(event: str, **kwargs: Any) -> None:
    _emit("laboratory", event, **kwargs)


def log_testing(event: str, **kwargs: Any) -> None:
    _emit("testing", event, **kwargs)


def log_ai(event: str, **kwargs: Any) -> None:
    """MSD runs. Record which records were retrieved, not their contents."""
    _emit("ai", event, **kwargs)


def log_queue(event: str, **kwargs: Any) -> None:
    _emit("queue", event, **kwargs)
