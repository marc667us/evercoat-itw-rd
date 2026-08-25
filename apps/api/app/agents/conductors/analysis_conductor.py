"""Analysis — the department conductor. NEW.

The fourth department, and the first one that did not already exist as a
route-backed surface. Structural, like laboratory and testing: the
department's permission gate plus dispatch to
`app.domains.dashboards.service`.

🔴 WHY THE ANALYSIS DEPARTMENT IS `analytics.view`, NOT A ROLE.

The dashboards are named after roles — `chemist_dashboard`, `lead_dashboard`,
`engineer_dashboard`, `director_dashboard` — and it would be easy to gate
them by role name. §6 forbids exactly that: *authorize on permissions, not
role names.* A product_development_lead who has not been granted
`analytics.view` must not read the lead dashboard because of what they are
called.

So the caller names which dashboard they want, and the gate is the
permission. The role in the function name describes the SHAPE of the
answer — which panels, which queues — not who may ask for it.

⚠️ A DASHBOARD'S FAILURE MODE IS AN EMPTY PANEL, NOT AN ERROR.
That is recorded from 2026-08-21 and it is why this conductor returns the
service's answer unchanged rather than "helpfully" substituting anything for
an empty section. A panel that shows demonstration figures when the real
query returned nothing is the defect this project has already shipped once
(08-19: a failed `/api/me` turned into demonstration data). Empty is an
answer; invented is not.

⚠️ AND IT IS THE CALLER'S OWN RLS-SCOPED SESSION, always. Analytics reads
across more tables than any other department, so a conductor here that
borrowed a privileged connection would aggregate other tenants' work into a
single number and be very hard to notice.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable
from typing import Any

from sqlalchemy.orm import Session

from app.agents.boundary import require
from app.domains.dashboards import service as dashboards

# A named alias rather than `dict[str, Any]`: with Any the dispatch below
# returns Any, mypy's --strict rightly objects, and the obvious silencer is
# a cast that would also hide a genuinely wrong return type.
_DashboardFn = Callable[..., dict[str, Any]]

__all__ = ["DASHBOARDS", "DEPARTMENT", "UnknownDashboardError", "dashboard"]

DEPARTMENT = "analysis"

VIEW = "analytics.view"

# The dashboards this conductor will serve, by name. Written out rather than
# resolved with `getattr(dashboards, f"{name}_dashboard")`: a dynamic lookup
# turns any attribute of the service module into a reachable endpoint, which
# is how a private helper becomes public without anyone deciding it should
# be. The same reasoning `_RESOLVERS` uses in messaging/service.py.
DASHBOARDS: dict[str, _DashboardFn] = {
    "chemist": dashboards.chemist_dashboard,
    "engineer": dashboards.engineer_dashboard,
    "lead": dashboards.lead_dashboard,
    "director": dashboards.director_dashboard,
}


class UnknownDashboardError(ValueError):
    """A dashboard name this conductor does not serve."""


def dashboard(
    session: Session,
    *,
    name: str,
    user_id: uuid.UUID,
    organization_id: uuid.UUID,
    permissions: frozenset[str],
) -> dict[str, Any]:
    """One dashboard, by name, for the calling user.

    `user_id` comes from the verified principal and is passed to the service,
    which uses it for "assigned to me" style panels. A caller that could name
    somebody else's `user_id` here would be asking what is waiting for a
    colleague — the same hole `root_orchestrator` already warns about.
    """
    require(permissions, department=DEPARTMENT, permission=VIEW)
    try:
        build = DASHBOARDS[name]
    except KeyError:
        raise UnknownDashboardError(
            f"{name!r} is not a dashboard this conductor serves; "
            f"expected one of {sorted(DASHBOARDS)}"
        ) from None
    return build(session, user_id=user_id, organization_id=organization_id)
