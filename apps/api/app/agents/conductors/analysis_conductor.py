"""Analysis — the department conductor. NEW.

The fourth department, and the first that did not already exist as a
route-backed agent surface. Structural, like laboratory and testing: the
department's permission gate plus dispatch to
`app.domains.dashboards.service`. The reasoning for why the conductor tier
owns the gate is in `app/agents/boundary.py`.

🔴 THE GATE IS `project.view`, AND THE FIRST DRAFT GOT IT WRONG.

I gated this on `analytics.view` because the permission catalogue files the
dashboards under the `analytics` domain. `app/api/dashboards.py` — the route
that has been serving these same dashboards — gates on **`project.view`**.
Two boundaries answering the same question differently is not a style
difference, and measured against the seeded roles they come apart in BOTH
directions:

    procurement_specialist   analytics.view  YES   project.view  NO
    laboratory_technician    analytics.view  NO    project.view  YES

So the first draft would have **granted a procurement specialist a dashboard
the route refuses them**, and refused a laboratory technician one the route
allows. The route is the shipped contract; the conductor matches it. When
`analytics.view` should gate something, it will gate it in both places at
once or not at all.

🔴 AND THE TABLE IS THE SERVICE'S, NOT A SECOND COPY.

The first draft wrote out its own `{"lead": lead_dashboard, ...}` mapping
beside the service's `ROLE_DASHBOARDS`, which the route already uses. Two
literals in two files cannot be type-checked into agreement — this
repository's own most-repeated defect, and it would have meant a dashboard
added to one and not the other. There is one table, and it lives with the
service that owns it.

⚠️ `held_permissions` IS PASSED, AND OMITTING IT FAILS SILENTLY.
The builders gate individual panels on it — `"test.review" in
held_permissions`, `held_permissions & {"batch.execute", "batch.complete"}`,
`"opportunity.view" in held_permissions` — and it DEFAULTS TO `frozenset()`.
The first draft did not pass it, so the conductor returned the same dashboard
with several panels quietly missing: correct-looking, smaller, and wrong. It
failed closed, which is why nothing raised, and *"a dashboard's failure mode
is an EMPTY PANEL"* is exactly the lesson this project already recorded.

⚠️ A DASHBOARD'S EMPTY SECTION IS AN ANSWER; AN INVENTED ONE IS NOT. The
service's result is returned unchanged. Substituting anything for an empty
panel is the defect shipped on 08-19, when a failed `/api/me` turned into
demonstration data.

⚠️ AND IT IS THE CALLER'S OWN RLS-SCOPED SESSION, always. Analytics reads
across more tables than any other department, so a conductor that borrowed a
privileged connection would aggregate other tenants' work into one number and
be very hard to notice.
"""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy.orm import Session

from app.agents.boundary import require
from app.domains.dashboards.service import ROLE_DASHBOARDS
from app.domains.reporting.service import test_results_report

__all__ = ["DEPARTMENT", "REPORT", "VIEW", "UnknownDashboardError", "dashboard", "report"]

DEPARTMENT = "analysis"

# 🔴 Kept identical to `app/api/dashboards.py`'s dependency on purpose, and
# `tests/test_conductor_boundary.py` reads that route's source to prove it.
# A constant named once here and asserted against the route there is the only
# arrangement in which the two cannot drift apart unnoticed.
VIEW = "project.view"

# 🔴 `report.generate`'s FIRST ENFORCEMENT POINT, ANYWHERE.
#
# Measured before writing this: `report.generate` is granted to FIVE roles,
# `analytics.portfolio` to two and `analytics.view` to nine -- and not one of
# the three is referenced by a single line of application code. They were
# permissions with no production path that reads them, which is this
# repository's most-repeated question turned on the permission catalogue
# itself: *ask of every role, which production path enforces it?*
#
# Generating a report is a distinct act from reading a dashboard -- it
# aggregates across records and is the thing a person exports and sends
# onwards -- so it takes the permission the catalogue already reserved for
# it rather than riding on VIEW.
REPORT = "report.generate"


class UnknownDashboardError(ValueError):
    """A dashboard name the service does not build."""


def dashboard(
    session: Session,
    *,
    name: str,
    user_id: uuid.UUID,
    organization_id: uuid.UUID,
    permissions: frozenset[str],
) -> dict[str, Any]:
    """One dashboard, by name, for the calling user.

    `user_id` comes from the verified principal. A caller that could name
    somebody else's would be asking what is waiting for a colleague — the
    hole `root_orchestrator` already warns about.
    """
    require(permissions, department=DEPARTMENT, permission=VIEW)
    build = ROLE_DASHBOARDS.get(name)
    if build is None:
        raise UnknownDashboardError(
            f"no such dashboard; the roles with a dashboard are {sorted(ROLE_DASHBOARDS)}"
        )
    return build(
        session,
        user_id=user_id,
        organization_id=organization_id,
        held_permissions=permissions,
    )


def report(
    session: Session,
    *,
    organization_id: uuid.UUID,
    permissions: frozenset[str],
    project_id: uuid.UUID | None = None,
    limit: int = 200,
) -> dict[str, Any]:
    """Test results, aggregated by their derived disposition.

    Gated on `report.generate`, not `VIEW`: see REPORT above. A caller who may
    read a dashboard is not automatically a caller who may generate a report
    over the whole portfolio.

    ⚠️ THE REPORT READS §10's DERIVATION, IT DOES NOT REPEAT IT. See
    `app/domains/reporting/service.py` -- a report that regrouped tests by
    re-implementing the fourteen ordered rules would be the second answer
    `app/calculations/testing.py` exists to prevent.
    """
    require(permissions, department=DEPARTMENT, permission=REPORT)
    return test_results_report(
        session,
        organization_id=organization_id,
        project_id=project_id,
        limit=limit,
    )
