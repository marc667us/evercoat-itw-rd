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

from app.agents.orchestrators.root_orchestrator import analysis_report
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
        organization_id=principal.organization_id,
        permissions=principal.permissions,
        project_id=project_id,
        limit=limit,
    )
