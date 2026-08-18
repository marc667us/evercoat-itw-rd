"""Celery worker — the Slice 1 ``WorkflowPort`` implementation.

Reused from Solar (ADR-022 / REUSE.md R9), running on Valkey rather than
Redis. Valkey is wire-compatible, so the proven pattern ports unchanged.

**What this is and is not.** Temporal takes over the *named durable*
workflows at Slice 11 — stability time points, escalation timers,
long-running qualification, announcement acknowledgement (ADR-008).
Everything else stays here permanently. That cutover is a migration, not
an adapter swap, because timers, signals, retries, idempotency and
compensation semantics leak into the domain no matter how the port is
drawn (Codex F41). So the tasks below are deliberately written as thin
shells around domain commands: the command is the stable thing, and
whichever engine invokes it is not.

**Tenancy.** A background task has no HTTP request and therefore no
principal, but it still touches tenant-scoped tables. Every task must
establish context explicitly via ``RequestContext``. There is no
"system" bypass — a task that cannot name the organization it is acting
for has no business reading the data.
"""

from __future__ import annotations

import uuid
from typing import Any

import structlog
from celery import Celery
from celery.signals import setup_logging

from app.core.config import settings
from app.core.db import RequestContext, session_scope
from app.core.logging import configure_logging, log_queue

__all__ = ["celery_app", "refresh_analytics", "verify_audit_chain"]

log = structlog.get_logger(__name__)

celery_app = Celery(
    "evercoat_itw_rd",
    broker=settings.valkey_url,
    backend=settings.valkey_url,
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    # Acknowledge only after the task finishes, so a worker killed
    # mid-task redelivers rather than silently dropping the work. The
    # trade-off is that tasks must be idempotent — which they must be
    # anyway to survive the Temporal migration.
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    # One task at a time per child. These tasks are database-bound, and
    # prefetching would hold rows locked while a worker sat on queued
    # work it had not started.
    worker_prefetch_multiplier=1,
    task_time_limit=600,
    task_soft_time_limit=540,
    broker_connection_retry_on_startup=True,
)


@setup_logging.connect
def _configure_worker_logging(**_: Any) -> None:
    """Use the application's structured logger, not Celery's default.

    Without this the worker emits unstructured text into a JSON log
    stream, and the one place you look during an incident is the one
    place that does not parse.
    """
    configure_logging()


@celery_app.task(
    name="analytics.refresh_materialized_views",
    bind=True,
    max_retries=3,
    default_retry_delay=60,
)
def refresh_analytics(self: Any, organization_id: str, scope: str = "hourly") -> dict[str, Any]:
    """Refresh analytics materialized views for one organization.

    Scoped per organization rather than globally, because materialized
    views carry their own ``organization_id`` and RLS policies (Codex
    F20) — a global refresh would need a role that can see every tenant,
    which is exactly the cross-tenant aggregate the design avoids.

    Views arrive with the modules that populate them; Slice 1 has none
    yet, so this is the shape and the wiring, doing no work.
    """
    org = uuid.UUID(organization_id)
    ctx = RequestContext(organization_id=org, user_id=_SYSTEM_ACTOR)

    try:
        with session_scope(ctx) as session:
            # Slice 11+ populates this list. Deliberately empty rather
            # than refreshing "everything found in the catalogue": an
            # unbounded refresh is how a nightly job quietly becomes a
            # four-hour one.
            refreshed: list[str] = []
            _ = session
        log_queue(
            "analytics_refreshed",
            organization_id=organization_id,
            scope=scope,
            views=len(refreshed),
        )
        return {"organization_id": organization_id, "refreshed": refreshed}
    except Exception as exc:
        log_queue(
            "analytics_refresh_failed", organization_id=organization_id, scope=scope, error=str(exc)
        )
        raise self.retry(exc=exc) from exc


@celery_app.task(name="audit.verify_chain", bind=True)
def verify_audit_chain(self: Any, organization_id: str) -> dict[str, Any]:
    """Walk the audit hash chain and report the first break.

    Scheduled rather than on-demand because tamper *evidence* is only
    useful if someone looks. A chain nobody verifies is a chain that
    detects nothing.

    The organization is passed to `verify_chain` explicitly rather than
    left to RLS. Both scoped the walk to the same rows before migration
    011, so the previous call was not wrong -- but it was correct by
    coincidence, and a verifier whose scope is implicit reports a
    different answer when the role or the policy changes underneath it.
    """
    from app.core.audit import verify_chain

    org = uuid.UUID(organization_id)
    ctx = RequestContext(organization_id=org, user_id=_SYSTEM_ACTOR)

    with session_scope(ctx) as session:
        result = verify_chain(session, organization_id=org)

    if result is None:
        log_queue("audit_chain_verified", organization_id=organization_id, status="intact")
        return {"status": "intact"}

    # Loud on purpose. This is either tampering or a canonical-form drift
    # between audit.py and audit.canonical_content() — both need a human
    # the same day.
    log.error(
        "audit_chain_broken",
        organization_id=organization_id,
        event_id=result.event_id,
        reason=result.reason,
    )
    return {
        "status": "broken",
        "event_id": result.event_id,
        "reason": result.reason,
    }


# A fixed, reserved UUID identifying the platform itself as an actor.
# Background work is attributable rather than anonymous: an audit row
# reading "who: null" is indistinguishable from a bug that failed to
# record the user.
_SYSTEM_ACTOR = uuid.UUID("00000000-0000-0000-0000-000000000001")
