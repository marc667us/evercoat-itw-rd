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

from app.core.db import AuthConnectionNotConfiguredError, auth_session_scope, unscoped_session_scope

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


def _check_sign_in() -> tuple[bool, str]:
    """Confirm the sign-in connection exists and may do its one job.

    🔴 A DEPLOYMENT WITHOUT THIS IS NOT "DEGRADED", IT CANNOT AUTHENTICATE.

    Migration 053 moved EXECUTE on `core.principal_for_subject` and
    `core.memberships_for_subject` to `evercoat_auth` (I109), because both take
    a subject as an ARGUMENT and cannot check their caller. The application
    therefore needs a second connection. Without `AUTH_DATABASE_URL` every
    authenticated request fails at `get_principal` -- a 403 for every user,
    which reads like a broken realm or a bad token and sends whoever is on call
    to Keycloak.

    Readiness is the right place to say so: "can this serve traffic" is false
    for a deployment where nobody can sign in. `_check_migrations` makes the
    same argument about a database that answers `SELECT 1` with no RLS.

    ⚠️ IT ASKS THE PRIVILEGE, NOT JUST THE CONNECTION. A URL pointing at the
    runtime role would connect happily and then be refused at the first
    sign-in; `has_function_privilege` for the connected role turns that into a
    startup-time answer instead of a user-facing one.
    """
    try:
        with auth_session_scope() as session:
            allowed = session.execute(
                text(
                    "SELECT has_function_privilege("
                    "  current_user,"
                    "  'core.principal_for_subject(TEXT, UUID)',"
                    "  'EXECUTE')"
                )
            ).scalar_one()
        if not allowed:
            log.warning("health_sign_in_role_lacks_execute")
            return False, "sign-in role cannot execute the principal lookup"
        return True, "ok"
    except AuthConnectionNotConfiguredError:
        # Named separately from a connection failure: one is a missing
        # setting, the other is an unreachable database, and they are fixed
        # in different places.
        log.warning("health_sign_in_not_configured")
        return False, "not configured"
    except Exception as exc:  # noqa: BLE001
        log.warning("health_sign_in_unavailable", error=str(exc))
        return False, "unavailable"


@router.get("/ready", include_in_schema=False)
async def ready(response: Response) -> dict[str, Any]:
    checks: dict[str, str] = {}

    db_ok, checks["database"] = _check_database()
    mig_ok, checks["migrations"] = _check_migrations()
    auth_ok, checks["sign_in"] = _check_sign_in()

    healthy = db_ok and mig_ok and auth_ok
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
