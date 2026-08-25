"""Testing — the department conductor.

Structural, exactly as `laboratory_conductor`: the department's permission
gate plus dispatch to `app.domains.testing.service`. The full reasoning for
why the conductor tier owns the gate is in `app/agents/boundary.py`.

🔴 `test.view` GATES READS. IT DOES NOT GATE JUDGEMENT.

Testing is the department where §10's derived status lives, and it is worth
being exact about what this conductor does and does not do. It returns what
the domain service computed. It never derives, adjusts or explains a
`display_color`, a `final_status` or a `calculated_result` — those are
server-owned and rule-derived (§10), and a conductor that re-implemented the
ordered algorithm would create a second answer to a question that must have
exactly one.

Nor does it approve anything. §4 is categorical: AI must not move a result
from YELLOW to GREEN, confirm a root cause, or override a reviewer. The
write-side entry points of `testing.service` — `confirm_test`, `approve`,
`record_decision` — are deliberately NOT exposed here. If an agent ever needs
to *propose* one, that arrives as a proposal a human acts on, through the
approval engine, not as a call from this module.
"""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy.orm import Session

from app.agents.boundary import require
from app.domains.testing import service as testing

__all__ = ["DEPARTMENT", "methods", "test", "tests"]

DEPARTMENT = "testing"

VIEW = "test.view"


def tests(
    session: Session,
    *,
    organization_id: uuid.UUID,
    permissions: frozenset[str],
    project_id: uuid.UUID | None = None,
    review_state: str | None = None,
    limit: int = 200,
) -> list[dict[str, Any]]:
    """The test queue this caller may see."""
    require(permissions, department=DEPARTMENT, permission=VIEW)
    return testing.list_tests(
        session,
        organization_id=organization_id,
        project_id=project_id,
        review_state=review_state,
        limit=limit,
    )


def test(
    session: Session,
    *,
    test_id: uuid.UUID,
    organization_id: uuid.UUID,
    permissions: frozenset[str],
) -> dict[str, Any]:
    """One test, with the five stored axes and the derived disposition.

    Returned as the domain service computed them. See the module docstring:
    this conductor does not derive status and does not confirm one.
    """
    require(permissions, department=DEPARTMENT, permission=VIEW)
    return testing.get_test(session, test_id=test_id, organization_id=organization_id)


def methods(
    session: Session,
    *,
    organization_id: uuid.UUID,
    permissions: frozenset[str],
    limit: int = 200,
) -> list[dict[str, Any]]:
    """Test methods, with the limits §10's derivation reads."""
    require(permissions, department=DEPARTMENT, permission=VIEW)
    return testing.list_methods(session, organization_id=organization_id, limit=limit)
