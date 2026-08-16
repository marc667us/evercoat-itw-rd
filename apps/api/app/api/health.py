"""Health endpoints.

Three, because they answer three different questions and conflating them
causes real outages:

``/health/live``   Is the process running? Never touches a dependency, so
                   a database blip cannot get the container killed and
                   restarted into the same blip.
``/health/ready``  Can it serve traffic? Checks dependencies. This is what
                   compose and any load balancer should probe.
``/health/startup`` Has first-time initialisation finished? Distinguishes
                   "still booting" from "broken" during the ~2 minute
                   cold starts a free tier can produce -- a short timeout
                   against a cold start is not proof of an outage.

Deliberately unauthenticated, and deliberately thin: a health endpoint
that enumerates versions or connection strings is reconnaissance.
"""

from __future__ import annotations

import time
from typing import Any, Literal

import structlog
from fastapi import APIRouter, Response, status
from sqlalchemy import text

from app.core.db import unscoped_session_scope

router = APIRouter()
log = structlog.get_logger(__name__)

_STARTED_AT = time.monotonic()

__all__ = ["router"]


@router.get("/live", include_in_schema=False)
async def live() -> dict[str, str]:
    return {"status": "alive"}


def _check_database() -> tuple[bool, str]:
    try:
        with unscoped_session_scope() as session:
            session.execute(text("SELECT 1"))
        return True, "ok"
    except Exception as exc:  # noqa: BLE001
        # Log the reason; do not return it. The exception text can contain
        # host names, role names and connection details.
        log.warning("health_database_unavailable", error=str(exc))
        return False, "unavailable"


def _check_migrations() -> tuple[bool, str]:
    """Confirm the tenancy foundation is actually present.

    A database that answers SELECT 1 but has no RLS is *worse* than one
    that is down: it serves requests with no tenant isolation. Readiness
    therefore checks that the context helper exists, not merely that a
    connection can be made.
    """
    try:
        with unscoped_session_scope() as session:
            found = session.execute(
                text(
                    """
                    SELECT EXISTS (
                        SELECT 1 FROM pg_proc p
                        JOIN pg_namespace n ON n.oid = p.pronamespace
                        WHERE n.nspname = 'core' AND p.proname = 'current_org_id'
                    )
                    """
                )
            ).scalar_one()
        return bool(found), "ok" if found else "migrations not applied"
    except Exception as exc:  # noqa: BLE001
        log.warning("health_migration_check_failed", error=str(exc))
        return False, "unavailable"


@router.get("/ready", include_in_schema=False)
async def ready(response: Response) -> dict[str, Any]:
    checks: dict[str, str] = {}

    db_ok, checks["database"] = _check_database()
    mig_ok, checks["migrations"] = _check_migrations()

    healthy = db_ok and mig_ok
    if not healthy:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE

    return {"status": "ready" if healthy else "not_ready", "checks": checks}


@router.get("/startup", include_in_schema=False)
async def startup(response: Response) -> dict[str, Any]:
    db_ok, _ = _check_database()
    uptime = round(time.monotonic() - _STARTED_AT, 1)

    state: Literal["starting", "started"] = "started" if db_ok else "starting"
    if not db_ok:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE

    return {"status": state, "uptime_seconds": uptime}
