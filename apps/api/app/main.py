"""EvercoatITWRD APP — FastAPI entrypoint.

Observability lands in Slice 1 rather than Slice 20 (Codex F43): the
slice gate requires every feature to be exercised on a *deployed*
instance from Slice 1 onward, and you cannot diagnose a deployed instance
that has no health endpoint, no structured logs and no metrics.
"""

from __future__ import annotations

import time
import uuid
from collections.abc import Awaitable, Callable
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest

from app.api.admin import router as admin_router
from app.api.admin_reference_data import router as admin_reference_data_router
from app.api.admin_stage_gates import router as admin_stage_gates_router
from app.api.analysis import router as analysis_router
from app.api.competitors import router as competitors_router
from app.api.dashboards import router as dashboards_router
from app.api.failures import approvals_router
from app.api.failures import router as failures_router
from app.api.formulations import router as formulations_router
from app.api.health import router as health_router
from app.api.knowledge import router as knowledge_router
from app.api.laboratory import router as laboratory_router
from app.api.material_safety import router as material_safety_router
from app.api.materials import router as materials_router
from app.api.materials import suppliers_router
from app.api.me import router as me_router
from app.api.messaging import router as messaging_router
from app.api.msd import router as msd_router
from app.api.opportunities import router as opportunities_router
from app.api.projects import router as projects_router
from app.api.research import router as research_router
from app.api.tasks import router as tasks_router
from app.api.testing import reference_router as testing_reference_router
from app.api.testing import router as testing_router
from app.core.config import settings
from app.core.logging import configure_logging

__all__ = ["app", "create_app"]

configure_logging()
log = structlog.get_logger(__name__)

REQUESTS = Counter(
    "evercoat_http_requests_total",
    "HTTP requests",
    ["method", "path", "status"],
)
LATENCY = Histogram(
    "evercoat_http_request_seconds",
    "HTTP request latency",
    ["method", "path"],
)

# The one label value every unrouted request collapses into.
UNMATCHED_ROUTE_LABEL = "<unmatched>"


def _metric_label(request: Request) -> str:
    """The ROUTE TEMPLATE for metrics labels, or a single fixed value.

    🔴 THIS MUST BE CALLED **AFTER** ``call_next``, NEVER BEFORE.

    The previous version read ``request.scope["route"]`` at the top of the
    middleware and fell back to ``request.url.path``. Starlette's router
    is what puts ``route`` into the scope, and the router runs *inside*
    ``call_next`` -- so at middleware entry the key is never present and
    the fallback fired on **every single request**. The comment said
    "route template, not the concrete path"; the code did the exact
    opposite of its own comment.

    The cost is not cosmetic. Prometheus creates one time series per
    distinct label value, so ``/api/projects/<uuid>`` minted a new series
    per project, and an anonymous caller could mint an unbounded number
    by requesting ``/whatever/<nonce>`` -- growing API and Prometheus
    memory until one of them fell over. Found by Codex.

    Requests that match no route have no template to report. They collapse
    into one fixed label rather than reporting their path, because a 404
    probe is precisely the attacker-controlled input this bounds.

    🔴 WHAT `route.path` CONTAINS IS VERSION-DEPENDENT. MEASURED:

        fastapi 0.135.3 / starlette 1.3.1   ->  "/health/live"
        fastapi 0.141.1 / starlette 1.6.0   ->  "/live"

    The newer stack reports the path RELATIVE TO THE ROUTER rather than
    the fully-prefixed one. This cost a CI round trip: a test that
    hard-coded `/health/live` passed locally and failed on the runner.

    **The security property is unaffected either way** — both are route
    TEMPLATES, so the label set stays bounded by the size of the route
    table and no attacker-controlled value reaches it. Only the label's
    readability changes, and `root_path` is prepended to recover the
    prefix where the framework supplies it there instead.

    Do not re-introduce an assertion on the exact string. Assert the
    property that matters: it is a template, and it is not the raw path.
    """
    route = request.scope.get("route")
    path = getattr(route, "path", None)
    if not isinstance(path, str) or not path:
        return UNMATCHED_ROUTE_LABEL

    # Empty on the older stack (the prefix is already in `route.path`),
    # so this is a no-op there and a repair on the newer one. Never
    # request-controlled: `root_path` is set by the mount, not the caller.
    root = request.scope.get("root_path") or ""
    return f"{root}{path}" if isinstance(root, str) else path


@asynccontextmanager
async def lifespan(app: FastAPI):  # type: ignore[no-untyped-def]
    log.info(
        "startup",
        app=settings.app_name,
        env=settings.app_env,
        version=app.version,
    )
    yield
    log.info("shutdown", app=settings.app_name)


def create_app() -> FastAPI:
    application = FastAPI(
        title=settings.app_name,
        version="0.1.0",
        description=(
            "Integrated R&D, Smart Formulation, Laboratory Testing, "
            "Product Modeling and Product Development Intelligence Platform"
        ),
        lifespan=lifespan,
        # No interactive docs in production: the schema enumerates every
        # controlled endpoint and is free reconnaissance.
        docs_url=None if settings.is_production else "/docs",
        redoc_url=None,
        openapi_url=None if settings.is_production else "/openapi.json",
    )

    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_allowed_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PATCH", "PUT", "DELETE"],
        allow_headers=["Authorization", "Content-Type", "X-Organization-Id", "X-CSRF-Token"],
    )

    @application.middleware("http")
    async def observe(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        """Correlation id, structured access log, metrics.

        The correlation id is echoed to the client and bound to every log
        line for the request, so an incident can be reconstructed from the
        audit trail plus traces (SECURITY.md §16).
        """
        correlation_id = request.headers.get("X-Correlation-Id") or str(uuid.uuid4())
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(
            correlation_id=correlation_id,
            method=request.method,
            path=request.url.path,
        )

        started = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            elapsed = time.perf_counter() - started
            label_path = _metric_label(request)
            REQUESTS.labels(request.method, label_path, "500").inc()
            LATENCY.labels(request.method, label_path).observe(elapsed)
            # exc_info, but never the request body -- formulation payloads
            # must not reach logs (SECURITY.md §11).
            log.exception("request_failed", elapsed_ms=round(elapsed * 1000, 2))
            return JSONResponse(
                status_code=500,
                content={"detail": "internal error", "correlation_id": correlation_id},
                headers={"X-Correlation-Id": correlation_id},
            )

        elapsed = time.perf_counter() - started
        label_path = _metric_label(request)
        REQUESTS.labels(request.method, label_path, str(response.status_code)).inc()
        LATENCY.labels(request.method, label_path).observe(elapsed)
        log.info(
            "request",
            status=response.status_code,
            elapsed_ms=round(elapsed * 1000, 2),
        )
        response.headers["X-Correlation-Id"] = correlation_id
        return response

    @application.middleware("http")
    async def security_headers(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        if settings.is_production:
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        return response

    application.include_router(health_router, prefix="/health", tags=["health"])
    # Administration section 1 -- the write path for users, roles and
    # permissions. Live from Slice 1 (ADR-021): a configuration value
    # with no screen is a value nobody can write.
    application.include_router(admin_router, prefix="/api/admin")
    # Administration section 2 -- stage-gate configuration. Same prefix,
    # separate module: the pipeline reads stage_definitions on every
    # transition, so ADR-021 requires the screen that writes them to ship
    # in the same slice as the code that reads them.
    application.include_router(admin_stage_gates_router, prefix="/api/admin")
    # Administration section 3 -- units and product families. Slice 3's
    # own Administration section: migration 015 creates the tables and
    # this is their write path, so they do not join the list of tables
    # nothing can write.
    application.include_router(admin_reference_data_router, prefix="/api/admin")
    # Identity, BEFORE a tenant has been chosen.
    #
    # 🔴 The only authenticated route that does not require
    # X-Organization-Id. Everything else depends on get_principal, which
    # demands it -- so without this a browser that had just signed in had
    # a valid token and no way to discover a tenant to ask for. See
    # app/api/me.py and migration 024.
    application.include_router(me_router, prefix="/api/me")
    application.include_router(dashboards_router, prefix="/api/dashboards")
    # Registered in the SAME change as the report it serves. A router
    # written and not included is the "no caller" defect one level up.
    application.include_router(analysis_router, prefix="/api/analysis")
    application.include_router(projects_router, prefix="/api/projects")
    application.include_router(opportunities_router, prefix="/api/opportunities")
    # My Work. Mounted at its own prefix rather than under /api/projects
    # because a task need not belong to a project at all.
    application.include_router(tasks_router, prefix="/api/my-work")
    # Slice 3. Materials and suppliers are ORGANIZATION-scoped reference
    # data, so they sit at the top level rather than under a project --
    # a chemist on any project must be able to see the whole library.
    application.include_router(materials_router, prefix="/api/materials")
    application.include_router(suppliers_router, prefix="/api/suppliers")
    # Formulations ARE project-scoped, but they are addressed by their own
    # id and RLS applies the project-membership predicate to every row, so
    # the prefix carries no project segment. See the module docstring.
    application.include_router(formulations_router, prefix="/api/formulations")
    # Slice 4. Batches are project-scoped and addressed by their own id,
    # like formulations: RLS applies the project-membership predicate to
    # every row, so the prefix carries no project segment.
    application.include_router(laboratory_router, prefix="/api/laboratory/batches")
    # Slice 5. The Test Module. Project-scoped through the sample the test
    # was taken from, so RLS applies the membership predicate to every row
    # and the prefix carries no project segment.
    application.include_router(testing_router, prefix="/api/testing/tests")
    # Reference data for the module, one level up: a test METHOD is not a
    # sub-resource of a test. See `app/api/testing.py`.
    application.include_router(testing_reference_router, prefix="/api/testing")
    # Slice 6. Failure investigation, and the ONE shared approval engine —
    # polymorphic over (entity_type, entity_id) so Validation, Pilot,
    # Qualification and Release add zero approval infrastructure (§9).
    application.include_router(failures_router, prefix="/api/quality/failures")
    application.include_router(approvals_router, prefix="/api/approvals")
    # Messaging is mounted last because it is the layer every other
    # domain links INTO -- a thread hangs off a formula, a batch, a
    # failure -- and nothing in it is a prerequisite for them.
    application.include_router(messaging_router, prefix="/api/messaging", tags=["messaging"])
    # MSD — the Material Science & Development Assistant.
    #
    # 🔴 Reached through `app/agents/orchestrators/root_orchestrator.py`
    # and never through a conductor or a tool (§0.2). Mounted last
    # because it READS across every other domain and is a prerequisite
    # for none of them.
    # The knowledge library. Mounted before MSD because MSD RETRIEVES from it:
    # this is the write path that migration 042 shipped without (I74), and
    # without it the assistant's knowledge branch can only ever refuse.
    #
    # These routes call `app.domains.knowledge.service` directly, NOT the
    # agent tool -- a route reaching into `app/agents/tools/` is the §0.2
    # violation `tests/test_agent_topology.py` fails the build for.
    application.include_router(knowledge_router, prefix="/api/knowledge", tags=["knowledge"])
    application.include_router(msd_router, prefix="/api/msd", tags=["msd"])
    # 🔴 THE MATERIAL SAFETY DATA & RESEARCH CENTER, NAMED IN FULL.
    #
    # Not `/api/msd`, and nothing here contains `msd`. In this codebase MSD
    # means the Material Science & Development Assistant -- a different
    # capability with its own tables, permission and conversations -- and the
    # specification for this one writes "Material Safety Data" out in full all
    # 48 times it uses it. Two things that both abbreviate to MSD would make
    # authorization, audit and stored conversations ambiguous forever.
    application.include_router(
        material_safety_router, prefix="/api/material-safety", tags=["material-safety"]
    )
    # Competitor intelligence. Its label upload delegates to the materials
    # document writer rather than storing anything itself -- §14 forbids a
    # second document repository, and the register is one table.
    application.include_router(competitors_router, prefix="/api/competitors", tags=["competitors"])
    application.include_router(research_router, prefix="/api/research", tags=["research"])

    if settings.metrics_enabled:

        @application.get("/metrics", include_in_schema=False)
        async def metrics() -> Response:
            return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)

    return application


app = create_app()
