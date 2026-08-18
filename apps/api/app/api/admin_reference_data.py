"""Administration -- section 3: units and product families.

ADR-021 and `IMPLEMENTATION_PLAN.md` section H both say the same thing:
**a configuration value referenced anywhere must have an Administration
screen in the same slice or earlier, and the slice gate checks that.**
Section H names "Units, product families, material statuses" as Slice
3's Administration section, because formulation needs canonical units.

This router exists because migration 015 creates
`materials.units` and `materials.product_families`, and a table with no
writer is this platform's most-repeated defect -- five roles and one
permission have now been found with no production path. Creating two
config tables in the same change that criticises that pattern, and then
leaving them writable only by a seed script, would have been the sixth
and seventh.

**Material statuses are deliberately NOT here.** Section H lists them
alongside units, but they are a CHECK constraint on
`materials.materials.status` and each one is reachable through a distinct
permission (`material.approve_lab`, `material.approve_production`,
`material.restrict`). Making them editable rows would mean a status could
be added that no permission grants and no `StatusBadge` renders. The
write path for a material's status is `POST /api/materials/{id}/status`,
which already exists; the vocabulary itself is a schema decision.

**Retired, never deleted.** `is_active = false`, for the same reason
stage definitions are retired: a unit that has been used on a requirement
is part of that requirement's meaning, and deleting the row would leave
the measurement dimensionless.
"""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.audit import AuditEvent, write_audit
from app.core.security import Principal, get_db, require_permission

router = APIRouter()

__all__ = ["router"]

# The two tables this router administers, and the audit entity name for
# each. A dict rather than two near-identical modules: the shape is
# genuinely the same, and duplicating it would create the second list
# that drifts from the first.
_TABLES = {
    "units": ("materials.units", "unit"),
    "product-families": ("materials.product_families", "product_family"),
}


class UnitCreate(BaseModel):
    code: str = Field(min_length=1, max_length=50)
    name: str = Field(min_length=1, max_length=200)
    # Required, not optional. A unit with no quantity kind cannot be
    # offered as a choice for a requirement -- the form has to know that
    # MPa is a stress and minutes are a time, or it lists every unit in
    # the system for every measurement.
    quantity_kind: str = Field(min_length=1, max_length=50)
    display_order: int = Field(default=100, ge=0)


class ProductFamilyCreate(BaseModel):
    code: str = Field(min_length=1, max_length=50)
    name: str = Field(min_length=1, max_length=200)
    description: str | None = None
    display_order: int = Field(default=100, ge=0)


class ActiveFlag(BaseModel):
    is_active: bool


def _conflict(detail: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=detail)


@router.get("/units", tags=["administration"])
def get_units(
    include_inactive: bool = False,
    principal: Principal = Depends(require_permission("admin.reference_data", "material.view")),
    session: Session = Depends(get_db),
) -> list[dict[str, Any]]:
    """The canonical unit list.

    Readable with `material.view` as well as `admin.reference_data`,
    because every measurement form in the product needs it. Requiring the
    administration permission to READ would leave the unit dropdown empty
    for every chemist.
    """
    rows = session.execute(
        text(
            """
            SELECT id, code, name, quantity_kind, is_active, display_order
            FROM materials.units
            WHERE organization_id = :org AND (:all OR is_active)
            ORDER BY display_order, code
            """
        ),
        {"org": principal.organization_id, "all": include_inactive},
    ).mappings()
    return [dict(r) for r in rows]


@router.post("/units", status_code=status.HTTP_201_CREATED, tags=["administration"])
def post_unit(
    payload: UnitCreate,
    principal: Principal = Depends(require_permission("admin.reference_data")),
    session: Session = Depends(get_db),
) -> dict[str, str]:
    try:
        unit_id = session.execute(
            text(
                """
                INSERT INTO materials.units
                    (organization_id, code, name, quantity_kind, display_order)
                VALUES (:org, :code, :name, :kind, :order)
                RETURNING id
                """
            ),
            {
                "org": principal.organization_id,
                "code": payload.code,
                "name": payload.name,
                "kind": payload.quantity_kind,
                "order": payload.display_order,
            },
        ).scalar_one()
    except IntegrityError as exc:
        session.rollback()
        if "units_org_code_key" in str(exc.orig):
            raise _conflict(f"unit '{payload.code}' already exists") from exc
        raise _conflict(str(exc.orig)) from exc

    write_audit(
        session,
        AuditEvent(
            action="admin.unit_created",
            entity_type="unit",
            entity_id=str(unit_id),
            organization_id=principal.organization_id,
            user_id=principal.user_id,
            new_state={"code": payload.code, "quantity_kind": payload.quantity_kind},
            reason="reference data added",
        ),
    )
    return {"id": str(unit_id)}


@router.get("/product-families", tags=["administration"])
def get_product_families(
    include_inactive: bool = False,
    principal: Principal = Depends(require_permission("admin.reference_data", "material.view")),
    session: Session = Depends(get_db),
) -> list[dict[str, Any]]:
    rows = session.execute(
        text(
            """
            SELECT id, code, name, description, is_active, display_order
            FROM materials.product_families
            WHERE organization_id = :org AND (:all OR is_active)
            ORDER BY display_order, code
            """
        ),
        {"org": principal.organization_id, "all": include_inactive},
    ).mappings()
    return [dict(r) for r in rows]


@router.post("/product-families", status_code=status.HTTP_201_CREATED, tags=["administration"])
def post_product_family(
    payload: ProductFamilyCreate,
    principal: Principal = Depends(require_permission("admin.reference_data")),
    session: Session = Depends(get_db),
) -> dict[str, str]:
    try:
        family_id = session.execute(
            text(
                """
                INSERT INTO materials.product_families
                    (organization_id, code, name, description, display_order)
                VALUES (:org, :code, :name, :description, :order)
                RETURNING id
                """
            ),
            {
                "org": principal.organization_id,
                "code": payload.code,
                "name": payload.name,
                "description": payload.description,
                "order": payload.display_order,
            },
        ).scalar_one()
    except IntegrityError as exc:
        session.rollback()
        if "product_families_org_code_key" in str(exc.orig):
            raise _conflict(f"product family '{payload.code}' already exists") from exc
        raise _conflict(str(exc.orig)) from exc

    write_audit(
        session,
        AuditEvent(
            action="admin.product_family_created",
            entity_type="product_family",
            entity_id=str(family_id),
            organization_id=principal.organization_id,
            user_id=principal.user_id,
            new_state={"code": payload.code, "name": payload.name},
            reason="reference data added",
        ),
    )
    return {"id": str(family_id)}


@router.patch("/{collection}/{item_id}", tags=["administration"])
def patch_active(
    collection: str,
    item_id: uuid.UUID,
    payload: ActiveFlag,
    principal: Principal = Depends(require_permission("admin.reference_data")),
    session: Session = Depends(get_db),
) -> dict[str, Any]:
    """Retire or restore one reference-data row.

    The table name comes from a fixed dictionary, never from the path
    segment itself. `collection` reaches an f-string, so an unvalidated
    value would be SQL injection through a URL -- the lookup makes the set
    of reachable tables closed by construction rather than by a check
    somebody could later relax.
    """
    if collection not in _TABLES:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="no such collection")
    table, entity = _TABLES[collection]

    row = (
        session.execute(
            text(
                f"""
                WITH prev AS (
                    SELECT id, is_active FROM {table}
                    WHERE id = :id AND organization_id = :org
                    FOR UPDATE
                )
                UPDATE {table} t
                SET is_active = :active, updated_at = now()
                FROM prev
                WHERE t.id = prev.id
                RETURNING t.id, t.code, t.is_active, prev.is_active AS previous_active
                """  # noqa: S608 - `table` comes from _TABLES, never from the request
            ),
            {"id": item_id, "org": principal.organization_id, "active": payload.is_active},
        )
        .mappings()
        .one_or_none()
    )
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="no such item")

    write_audit(
        session,
        AuditEvent(
            action=f"admin.{entity}_{'restored' if payload.is_active else 'retired'}",
            entity_type=entity,
            entity_id=str(item_id),
            organization_id=principal.organization_id,
            user_id=principal.user_id,
            previous_state={"is_active": row["previous_active"]},
            new_state={"is_active": payload.is_active},
            reason="reference data retired or restored",
        ),
    )
    return dict(row)
