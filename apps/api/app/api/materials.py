"""Material library and supplier routes.

**Status changes are permission-routed, not free.** `material.create` does
not carry the right to say a material is production-approved. The Chemist
holds create/edit; the Lead holds `material.approve_lab`; QA holds
`material.restrict` and `material.approve_production`. So the status
endpoint resolves the permission FROM the requested status rather than
guarding the whole endpoint with one code -- a single
`require_permission("material.edit")` on a status route would hand every
promotion to everyone who can fix a typo.

Domain errors become HTTP here and nowhere else. The services raise
business exceptions; a service that imported `HTTPException` could not be
called from the Celery worker.
"""

from __future__ import annotations

import datetime as dt
import uuid
from decimal import Decimal
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.security import PermissionDenied, Principal, get_db, get_principal, require_permission
from app.core.tenancy import CrossTenantReferenceError
from app.domains.materials.service import (
    MaterialDuplicateError,
    MaterialInput,
    MaterialInvalidError,
    MaterialNotFoundError,
    MaterialsError,
    SupplierDuplicateError,
    SupplierError,
    SupplierInput,
    SupplierLinkInput,
    SupplierNotFoundError,
    create_material,
    create_supplier,
    get_material,
    link_supplier,
    list_materials,
    list_suppliers,
    material_usage,
    set_material_status,
    set_supplier_status,
    update_material,
)

router = APIRouter()
suppliers_router = APIRouter()

__all__ = ["router", "suppliers_router"]


# WHICH PERMISSION EACH STATUS REQUIRES.
#
# One table, consulted by the endpoint, rather than a chain of ifs. The
# mapping is the authorization model for a material's lifecycle and it is
# short enough to read in one glance -- which is the point, because a
# reader must be able to check it against migration 002 without following
# control flow.
#
# `development` is reachable with `material.edit` because returning a
# material to evaluation is a correction, not a promotion. Every OTHER
# transition needs an approval permission.
STATUS_PERMISSION: dict[str, str] = {
    "development": "material.edit",
    "approved": "material.approve_lab",
    "preferred": "material.approve_production",
    "restricted": "material.restrict",
    "obsolete": "material.restrict",
}


class MaterialCreate(BaseModel):
    """A new material.

    Every quantity is `Decimal`, never `float`. Pydantic parses JSON
    numbers into `Decimal` for these fields, so a percentage never passes
    through binary floating point on its way to the database -- the same
    guarantee the calculation engine enforces at its own boundary.

    `status` is absent on purpose: creation always yields `development`.
    """

    material_code: str = Field(min_length=2, max_length=50)
    name: str = Field(min_length=1, max_length=200)
    category: str = Field(min_length=1, max_length=100)
    role: str = Field(
        default="other",
        pattern="^(resin|binder|hardener|catalyst|filler|extender|pigment|additive|solvent|other)$",
    )
    description: str | None = None
    cas_number: str | None = Field(default=None, max_length=50)
    density_g_cm3: Decimal | None = Field(default=None, gt=0)
    solids_fraction: Decimal | None = Field(default=None, ge=0, le=1)
    voc_fraction: Decimal | None = Field(default=None, ge=0, le=1)
    cost_per_kg: Decimal | None = Field(default=None, ge=0)
    epoxy_equivalent_weight: Decimal | None = Field(default=None, gt=0)
    amine_hydrogen_equivalent_weight: Decimal | None = Field(default=None, gt=0)
    hazard_summary: str | None = None
    requires_sds: bool = True
    notes: str | None = None

    def to_input(self) -> MaterialInput:
        return MaterialInput(**self.model_dump())


class MaterialStatusChange(BaseModel):
    status: str = Field(pattern="^(development|approved|preferred|restricted|obsolete)$")
    # Required for `restricted` by the service AND by a CHECK constraint.
    # Optional here so the message about it comes from the domain, in
    # domain language, rather than as a Pydantic field error.
    restriction_reason: str | None = Field(default=None, max_length=1000)
    reason: str = Field(min_length=3, max_length=1000)


class SupplierCreate(BaseModel):
    supplier_code: str = Field(min_length=2, max_length=50)
    name: str = Field(min_length=1, max_length=200)
    country: str | None = Field(default=None, max_length=100)
    quality_rating: str | None = Field(default=None, pattern="^[ABCD]$")
    contact_name: str | None = None
    contact_email: str | None = None
    notes: str | None = None

    def to_input(self) -> SupplierInput:
        return SupplierInput(**self.model_dump())


class SupplierStatusChange(BaseModel):
    status: str = Field(pattern="^(pending|qualified|approved|suspended|disqualified)$")
    reason: str = Field(min_length=3, max_length=1000)


class SupplierLink(BaseModel):
    supplier_id: uuid.UUID
    supplier_part_code: str | None = Field(default=None, max_length=100)
    is_primary: bool = False
    lead_time_days: int | None = Field(default=None, ge=0)
    quoted_price_per_kg: Decimal | None = Field(default=None, ge=0)
    currency: str | None = Field(default=None, max_length=3)
    qualified_on: dt.date | None = None
    notes: str | None = None

    def to_input(self) -> SupplierLinkInput:
        return SupplierLinkInput(**self.model_dump())


def _missing(exc: Exception) -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


def _refuse(exc: Exception) -> HTTPException:
    return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))


def _invalid(exc: Exception) -> HTTPException:
    return HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))


# ---------------------------------------------------------------------------
# Materials
# ---------------------------------------------------------------------------


@router.get("", tags=["materials"])
def get_materials(
    status_filter: str | None = Query(default=None, alias="status"),
    role: str | None = Query(default=None),
    search: str | None = Query(default=None, max_length=100),
    principal: Principal = Depends(require_permission("material.view")),
    session: Session = Depends(get_db),
) -> list[dict[str, Any]]:
    """The material library."""
    return list_materials(
        session,
        organization_id=principal.organization_id,
        status=status_filter,
        role=role,
        search=search,
    )


@router.post("", status_code=status.HTTP_201_CREATED, tags=["materials"])
def post_material(
    payload: MaterialCreate,
    principal: Principal = Depends(require_permission("material.create")),
    session: Session = Depends(get_db),
) -> dict[str, str]:
    try:
        material_id = create_material(
            session,
            organization_id=principal.organization_id,
            actor_id=principal.user_id,
            spec=payload.to_input(),
        )
    except MaterialDuplicateError as exc:
        raise _refuse(exc) from exc
    except CrossTenantReferenceError as exc:
        raise _invalid(exc) from exc
    except MaterialsError as exc:
        raise _invalid(exc) from exc
    return {"id": str(material_id)}


@router.get("/{material_id}", tags=["materials"])
def get_one_material(
    material_id: uuid.UUID,
    principal: Principal = Depends(require_permission("material.view")),
    session: Session = Depends(get_db),
) -> dict[str, Any]:
    try:
        return get_material(
            session, material_id=material_id, organization_id=principal.organization_id
        )
    except MaterialNotFoundError as exc:
        raise _missing(exc) from exc


@router.put("/{material_id}", tags=["materials"])
def put_material(
    material_id: uuid.UUID,
    payload: MaterialCreate,
    principal: Principal = Depends(require_permission("material.edit")),
    session: Session = Depends(get_db),
) -> dict[str, Any]:
    """Edit a material's data. The code and the status are not editable here.

    A PUT, not a PATCH, because the body is the complete editable state:
    a partial update of a property set whose members are individually
    meaningful ("clear the VOC fraction" vs "leave it alone") is
    ambiguous, and the ambiguity would be resolved differently by every
    caller.
    """
    try:
        return update_material(
            session,
            material_id=material_id,
            organization_id=principal.organization_id,
            actor_id=principal.user_id,
            spec=payload.to_input(),
        )
    except MaterialNotFoundError as exc:
        raise _missing(exc) from exc
    except (MaterialInvalidError, CrossTenantReferenceError) as exc:
        raise _invalid(exc) from exc


@router.post("/{material_id}/status", tags=["materials"])
def post_material_status(
    material_id: uuid.UUID,
    payload: MaterialStatusChange,
    principal: Principal = Depends(get_principal),
    session: Session = Depends(get_db),
) -> dict[str, Any]:
    """Move a material through its lifecycle.

    The permission is resolved from the REQUESTED STATUS, which is why
    this endpoint depends on `get_principal` rather than on a single
    `require_permission(...)`. Guarding the endpoint with one code would
    mean whoever may set any status may set every status -- and the whole
    point of `material.approve_production` being a separate permission is
    that promoting a material into commercial products is not the same
    authority as promoting it into a laboratory.
    """
    required = STATUS_PERMISSION[payload.status]
    if not principal.has(required):
        raise PermissionDenied()

    try:
        return set_material_status(
            session,
            material_id=material_id,
            organization_id=principal.organization_id,
            actor_id=principal.user_id,
            status=payload.status,
            restriction_reason=payload.restriction_reason,
            reason=payload.reason,
        )
    except MaterialNotFoundError as exc:
        raise _missing(exc) from exc
    except MaterialInvalidError as exc:
        raise _invalid(exc) from exc


@router.get("/{material_id}/usage", tags=["materials"])
def get_material_usage(
    material_id: uuid.UUID,
    principal: Principal = Depends(require_permission("material.view", "formula.view")),
    session: Session = Depends(get_db),
) -> list[dict[str, Any]]:
    """Which formula versions use this material.

    The rows are RLS-filtered, so a caller who is not a member of a
    restricted project does not see its formulas here. That is correct and
    it is why the endpoint returns the rows rather than a count: a bare
    number that RLS had quietly reduced would present as a fact.
    """
    return material_usage(
        session, material_id=material_id, organization_id=principal.organization_id
    )


@router.post("/{material_id}/suppliers", status_code=status.HTTP_201_CREATED, tags=["materials"])
def post_material_supplier(
    material_id: uuid.UUID,
    payload: SupplierLink,
    principal: Principal = Depends(require_permission("supplier.manage")),
    session: Session = Depends(get_db),
) -> dict[str, str]:
    """Attach a supplier to a material, or update the pair's terms."""
    try:
        link_id = link_supplier(
            session,
            material_id=material_id,
            organization_id=principal.organization_id,
            actor_id=principal.user_id,
            spec=payload.to_input(),
        )
    except (MaterialNotFoundError, SupplierNotFoundError) as exc:
        raise _missing(exc) from exc
    except SupplierError as exc:
        raise _invalid(exc) from exc
    return {"id": str(link_id)}


# ---------------------------------------------------------------------------
# Suppliers
# ---------------------------------------------------------------------------


@suppliers_router.get("", tags=["suppliers"])
def get_suppliers(
    status_filter: str | None = Query(default=None, alias="status"),
    principal: Principal = Depends(require_permission("material.view")),
    session: Session = Depends(get_db),
) -> list[dict[str, Any]]:
    """The supplier list.

    Readable with `material.view` rather than `supplier.manage`: a chemist
    choosing a raw material needs to see who supplies it, and requiring
    the maintenance permission to READ would make the material detail page
    half-empty for the role that uses it most.
    """
    return list_suppliers(session, organization_id=principal.organization_id, status=status_filter)


@suppliers_router.post("", status_code=status.HTTP_201_CREATED, tags=["suppliers"])
def post_supplier(
    payload: SupplierCreate,
    principal: Principal = Depends(require_permission("supplier.manage")),
    session: Session = Depends(get_db),
) -> dict[str, str]:
    try:
        supplier_id = create_supplier(
            session,
            organization_id=principal.organization_id,
            actor_id=principal.user_id,
            spec=payload.to_input(),
        )
    except SupplierDuplicateError as exc:
        raise _refuse(exc) from exc
    except (SupplierError, CrossTenantReferenceError) as exc:
        raise _invalid(exc) from exc
    return {"id": str(supplier_id)}


@suppliers_router.post("/{supplier_id}/status", tags=["suppliers"])
def post_supplier_status(
    supplier_id: uuid.UUID,
    payload: SupplierStatusChange,
    principal: Principal = Depends(require_permission("supplier.manage")),
    session: Session = Depends(get_db),
) -> dict[str, Any]:
    try:
        return set_supplier_status(
            session,
            supplier_id=supplier_id,
            organization_id=principal.organization_id,
            actor_id=principal.user_id,
            status=payload.status,
            reason=payload.reason,
        )
    except SupplierNotFoundError as exc:
        raise _missing(exc) from exc
    except SupplierError as exc:
        raise _invalid(exc) from exc
