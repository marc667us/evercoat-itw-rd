"""Analysis — reporting endpoints.

🔴 THIS ROUTE EXISTS SO THE REPORT IS REACHABLE, WHICH IS THE WHOLE LESSON
OF THE PREVIOUS COMMIT.

The analysis conductor was written, gated, tested — and nothing called it, so
the department was a Python module unreachable from the running product. A
layer with no caller is the same defect as a route with no caller. The report
lands with its route in the same change rather than waiting for one.

§0.2: API routes never call specialists directly, so this imports the ROOT
ORCHESTRATOR and never the conductor. `tests/test_agent_topology.py` fails the
build if that changes.

⚠️ GATED ON `report.generate`, NOT ON `project.view`.
Generating a report is a distinct act from reading a dashboard: it aggregates
across records and is the thing a person exports and sends onwards. The
catalogue already reserved the permission and — measured before this was
written — **nothing in the application enforced it**, along with
`analytics.view` and `analytics.portfolio`. This is its first enforcement
point anywhere.

The conductor asserts the same permission. That is defence in depth: this
dependency refuses an unauthenticated caller before any handler runs, and the
conductor refuses on the paths that have no route at all.
"""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.agents.orchestrators.root_orchestrator import (
    AgentPrincipal,
    analysis_analytics,
    analysis_report,
)
from app.core.security import Principal, get_db, require_permission

router = APIRouter()

__all__ = ["router"]


@router.get("/reports/test-results", tags=["analysis"])
def get_test_results_report(
    project_id: uuid.UUID | None = Query(default=None),
    limit: int = Query(default=200, ge=1, le=200),
    principal: Principal = Depends(require_permission("report.generate")),
    session: Session = Depends(get_db),
) -> dict[str, Any]:
    """Test results aggregated by their derived disposition.

    Returns `by_colour`, `by_rule`, and a row per test carrying `test_id` and
    `test_number` — §2 requires analytics to drill down to real source
    records, and an aggregate nobody can trace back to a record is a number
    without evidence.

    ⚠️ `calculated_result` AND `disposition` ARE BOTH RETURNED, SEPARATELY.
    §10: a low-margin pass awaiting approval is both a pass and not final, and
    one field cannot say that. A client rendering only one is rendering half
    the truth.

    ⚠️ THE REPORT DOES NOT DERIVE STATUS. It reads what `testing` derived, so
    there is exactly one answer to "is this test GREEN". See
    `app/domains/reporting/service.py`.
    """
    return analysis_report(
        session,
        caller=AgentPrincipal.of(principal),
        project_id=project_id,
        limit=limit,
    )


@router.get("/analytics", tags=["analysis"])
def get_analytics(
    project_id: uuid.UUID | None = Query(default=None),
    limit: int = Query(default=200, ge=1, le=200),
    # 🔴 `analytics.view` — AND UNTIL THIS ROUTE, NO CODE READ IT.
    #
    # It is granted to NINE of the ten seeded roles and was enforced nowhere,
    # alongside `analytics.portfolio` (two roles). `report.generate` was the
    # third of that set and got a home on 2026-08-25; these two did not, and
    # the session-close record listed them as still open. A permission with no
    # enforcement point is the same defect as a route with no caller: it looks
    # like governance and grants nothing, refuses nothing, audits as nothing.
    #
    # ⚠️ IT IS NOT `project.view`, AND THE NEIGHBOURING ROUTE IS. That is not
    # drift. `apps/web/lib/navigation.ts` declares this screen as
    # `permission: "analytics.view"` and `app/api/dashboards.py` has always
    # required `project.view` for dashboards; each route matches its own
    # shipped contract, and `tests/test_conductor_boundary.py` pins both by
    # reading the source rather than trusting a comment. Measured, the two
    # come apart in both directions — a procurement specialist holds
    # `analytics.view` and not `project.view`, a laboratory technician the
    # reverse — so unifying them would have granted and refused people by
    # accident.
    principal: Principal = Depends(require_permission("analytics.view")),
    session: Session = Depends(get_db),
) -> dict[str, Any]:
    """Testing and laboratory activity, counted — the Intelligence surface.

    Returns `testing` (counts by derived disposition, by which of §10's
    fourteen rules fired, and by automatic evaluation, authority and purpose),
    `laboratory` (batches by lifecycle status), and `rows` carrying `test_id`
    and `test_number` so every figure drills down to a real record (§2).

    ⚠️ `by_colour` AND `by_calculated_result` ARE BOTH RETURNED, SEPARATELY.
    §10: a low-margin pass awaiting approval is both a pass and not final, and
    one field cannot say that. At portfolio scale the same rule reads "nine
    passed, four of them not yet final" — a client rendering only one of the
    two is rendering half the truth.

    ⚠️ NOTHING HERE DERIVES A STATUS. Every disposition is the one
    `app/domains/testing` already derived, read rather than recomputed, so
    there is exactly one answer to "is this test GREEN".

    🔴 `by_project` IS `null`, NOT `[]`, WITHOUT `analytics.portfolio`.
    The organization-wide breakdown is a SECOND gate, checked before it is
    computed rather than after (§7 filters before, never after) — so a caller
    without it does not have one report per project run on their behalf and
    then discarded. `portfolio_included` says which happened. An empty list
    would claim this organization has no projects.
    """
    return analysis_analytics(
        session,
        caller=AgentPrincipal.of(principal),
        project_id=project_id,
        limit=limit,
    )
