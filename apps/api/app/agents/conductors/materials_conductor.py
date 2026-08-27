"""Materials — the department conductor.

§0.2: department conductors live at
`app/agents/conductors/<dept>_conductor.py`, specialists never call other
agents, and API routes never call specialists directly.

Structural, like `laboratory_conductor`: no tools, no model, no reasoning.

🔴 WHAT IT OWNS, AND WHY ONE FUNCTION HERE NEEDS TWO PERMISSIONS.

`material.view` reaches the department. `usage` needs `material.view` **AND**
`formula.view`, because *"which formulas use this raw material"* is a statement
about formulas wearing a material's label — the route already says so with
`require_permission("material.view", "formula.view", require_all=True)`, and a
conductor that gated on `material.view` alone would be a second, weaker copy of
that decision reachable by a path with no route at all.

⚠️ IT IS `require_all`, WHICH `require()` DOES NOT DO. `app/agents/boundary.py`
takes ONE permission, so the second is a second call. Written as two explicit
lines rather than by widening the shared gate: a gate that accepts a list grows
an `any`/`all` flag, and a flag with two settings is where an `any` gets
written where an `all` was meant. Two calls cannot be misread.

⚠️ SUPPLIERS ARE IN THIS DEPARTMENT AND SHARE ITS PERMISSION. `GET
/api/suppliers` declares `material.view`, not a `supplier.*` code — a supplier
is reached as the origin of a material. `supplier.manage` exists and governs
WRITES, which do not come through this door at all (§4).

🔴 THE SESSION IS THE CALLER'S OWN, AND `authorize()` CHECKS IT.

⚠️ READS ONLY (§4). No `create_material`, no `approve`, no `supplier.manage`
path is reachable from here.
"""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy.orm import Session

# 🔴 THE SERVICE IS ALIASED `raw_materials`, NOT `materials`. The department's
# list function is `materials()` below, and aliasing the service to the same
# name would rebind the module-level name to the function — so
# `materials.list_materials` inside it would resolve to the function and raise
# AttributeError at the first call. A shadow that only fails at runtime, on the
# one department whose name is also its plural.
from app.agents.boundary import require
from app.agents.principal import AgentPrincipal
from app.domains.materials import service as raw_materials

__all__ = [
    "DEPARTMENT",
    "documents",
    "material",
    "materials",
    "suppliers",
    "usage",
]

DEPARTMENT = "materials"

# Named once rather than repeated per function — the repeated form is how one
# of them ends up checking a different code from the others.
VIEW = "material.view"

# The second permission `usage` needs, because the answer is about formulas.
FORMULA_VIEW = "formula.view"


def materials(
    session: Session,
    *,
    caller: AgentPrincipal,
    status: str | None = None,
    role: str | None = None,
    search: str | None = None,
    limit: int = 200,
) -> list[dict[str, Any]]:
    """The raw materials this caller may see."""
    caller = caller.authorize(session)
    require(caller, department=DEPARTMENT, permission=VIEW)
    return raw_materials.list_materials(
        session,
        organization_id=caller.organization_id,
        status=status,
        role=role,
        search=search,
        limit=limit,
    )


def material(
    session: Session,
    *,
    material_id: uuid.UUID,
    caller: AgentPrincipal,
) -> dict[str, Any]:
    """One raw material."""
    caller = caller.authorize(session)
    require(caller, department=DEPARTMENT, permission=VIEW)
    return raw_materials.get_material(
        session,
        material_id=material_id,
        organization_id=caller.organization_id,
    )


def usage(
    session: Session,
    *,
    material_id: uuid.UUID,
    caller: AgentPrincipal,
) -> list[dict[str, Any]]:
    """Where this material is used — which is a statement about FORMULAS.

    🔴 BOTH PERMISSIONS, ASSERTED SEPARATELY. `material.view` to be in this
    department at all, and `formula.view` because the answer names formula
    versions. Measured on the seeded realm 2026-08-27: eight of ten roles hold
    `material.view` and seven hold `formula.view`, and the procurement
    specialist and administrator are in the first set and not the second — so
    this is not a distinction without a difference. They are the two callers
    this refuses.
    """
    caller = caller.authorize(session)
    require(caller, department=DEPARTMENT, permission=VIEW)
    require(caller, department=DEPARTMENT, permission=FORMULA_VIEW)
    return raw_materials.material_usage(
        session,
        material_id=material_id,
        organization_id=caller.organization_id,
    )


def documents(
    session: Session,
    *,
    material_id: uuid.UUID,
    caller: AgentPrincipal,
) -> list[dict[str, Any]]:
    """The material's documents — SDS and the rest."""
    caller = caller.authorize(session)
    require(caller, department=DEPARTMENT, permission=VIEW)
    return raw_materials.list_material_documents(
        session,
        material_id=material_id,
        organization_id=caller.organization_id,
    )


def suppliers(
    session: Session,
    *,
    caller: AgentPrincipal,
    status: str | None = None,
    limit: int = 200,
) -> list[dict[str, Any]]:
    """Suppliers, on the department's own permission."""
    caller = caller.authorize(session)
    require(caller, department=DEPARTMENT, permission=VIEW)
    return raw_materials.list_suppliers(
        session,
        organization_id=caller.organization_id,
        status=status,
        limit=limit,
    )
