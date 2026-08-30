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

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

# 🔴 THE READS GO THROUGH THE ORCHESTRATOR (§0.2).
#
# This module called its domain service directly, so the materials department
# existed for HTTP callers and not for the agent tier at all. `usage` is the
# reason it matters most: *"which formulas use this material"* needs
# `formula.view` as well as `material.view`, and the two callers that hold the
# first and not the second -- the administrator and the procurement specialist,
# measured 2026-08-27 -- were refused by this route and by nothing on the
# agent path.
#
# ⚠️ THE WRITES DELIBERATELY DO NOT. §4: humans approve. The orchestrator
# exposes no write-side entry point at all, and every mutation below still
# calls the domain service directly. The asymmetry is the rule, not an
# omission -- if a write ever appears on that door, it is a §4 violation and
# not a convenience.
#
# ⚠️ `require_permission(...)` ON EACH ROUTE STAYS. The conductor asserts the
# same permission; that is defence in depth. The dependency refuses an
# unauthenticated caller before any handler runs, and the conductor refuses on
# the paths that have no route.
from app.agents.orchestrators.root_orchestrator import (
    AgentPrincipal,
    materials_documents,
    materials_material,
    materials_materials,
    materials_suppliers,
    materials_usage,
)
from app.core.audit import AuditEvent, write_audit
from app.core.documents import get_object_store, get_scanner
from app.core.file_types import FileTypeRejectedError
from app.core.malware import MalwareFoundError, MalwareScannerPort, MalwareScanUnavailableError
from app.core.object_storage import ObjectStorageError, ObjectStoragePort
from app.core.security import PermissionDenied, Principal, get_db, get_principal, require_permission
from app.core.tenancy import CrossTenantReferenceError
from app.domains.materials.service import (
    DocumentInput,
    MaterialDuplicateError,
    MaterialInput,
    MaterialInvalidError,
    MaterialNotFoundError,
    MaterialPermissionError,
    MaterialsError,
    SupplierDuplicateError,
    SupplierError,
    SupplierInput,
    SupplierLinkInput,
    SupplierNotFoundError,
    create_material,
    create_supplier,
    link_supplier,
    set_material_status,
    set_supplier_status,
    store_document,
    update_material,
)

router = APIRouter()
suppliers_router = APIRouter()

__all__ = ["router", "suppliers_router"]


# THE PERMISSION FOR A STATUS CHANGE IS NOT DECIDED HERE ANY MORE.
#
# This module used to hold a `STATUS_PERMISSION` table keyed by the
# DESTINATION status. The Supervisor found the hole: `development` was
# reachable with `material.edit`, so anyone who could fix a typo could
# take a material QA had restricted for a safety finding and move it back
# to `development` -- clearing the restriction reason and unblocking every
# formula that used it.
#
# The authority now belongs to the EDGE (`from -> to`), and the table
# lives in the service beside the transition rules it qualifies, because
# the two are one decision. The route's job is to hand over what the
# caller holds and translate the refusal.


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


class DocumentCreate(BaseModel):
    """Register a TDS / SDS / CoA against a material.

    Metadata and a storage key, never bytes -- SECURITY.md section 6.
    """

    document_type: str = Field(pattern="^(TDS|SDS|CoA|regulatory|other)$")
    title: str = Field(min_length=1, max_length=200)
    storage_key: str = Field(min_length=1, max_length=500)
    content_type: str | None = Field(default=None, max_length=200)
    byte_size: int | None = Field(default=None, ge=0)
    checksum_sha256: str | None = Field(default=None, pattern="^[0-9a-f]{64}$")
    issued_on: dt.date | None = None
    expires_on: dt.date | None = None
    supersedes_id: uuid.UUID | None = None

    def to_input(self) -> DocumentInput:
        return DocumentInput(**self.model_dump())


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
    # `None` means "leave the flag alone". A plain `bool` defaulting to
    # False silently demoted the primary supplier whenever somebody edited
    # a lead time -- this endpoint is an upsert. Raised by the Supervisor.
    is_primary: bool | None = None
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
    return materials_materials(
        session,
        caller=AgentPrincipal.of(principal),
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
    # 🔴 THE CODE COMES BACK, AND LEAVING IT OUT BROKE THE FORM WITHOUT
    # BREAKING THE WRITE.
    #
    # This returned `{"id": ...}` alone. `createMaterial` in the browser parses
    # `{ id, material_code }` -- `material_code` REQUIRED, because the screen
    # reports "RM-014 created" using the server's own code rather than echoing
    # what was typed. So every creation SUCCEEDED and then failed to parse its
    # own response: the material was in the database, and the screen showed
    # "the client and the server disagree about this endpoint".
    #
    # Nothing caught it. The write was correct, so no server test failed; the
    # client test stubs the response, so it parsed what it expected. The live
    # suite pressing the button is what found it -- and the row it had just
    # created was sitting in the table behind the error.
    #
    # The code is `spec.material_code` verbatim: the INSERT binds it unchanged,
    # so this is what was stored, not merely what was asked for.
    return {"id": str(material_id), "material_code": payload.material_code}


@router.get("/{material_id}", tags=["materials"])
def get_one_material(
    material_id: uuid.UUID,
    principal: Principal = Depends(require_permission("material.view")),
    session: Session = Depends(get_db),
) -> dict[str, Any]:
    try:
        return materials_material(
            session, material_id=material_id, caller=AgentPrincipal.of(principal)
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

    Depends on `get_principal` rather than on a single
    `require_permission(...)` because the required authority depends on
    BOTH ends of the move -- promoting to `preferred` needs
    `material.approve_production`, while lifting a restriction needs
    `material.restrict` no matter where it lands. A single permission on
    the endpoint would mean whoever may make any status change may make
    every status change.

    The permission set is handed to the service, which resolves it against
    the edge table inside the UPDATE's own WHERE clause. So authorization
    and the write are the same statement, and there is no window between
    "may they?" and the row moving.
    """
    try:
        return set_material_status(
            session,
            material_id=material_id,
            organization_id=principal.organization_id,
            actor_id=principal.user_id,
            held_permissions=principal.permissions,
            status=payload.status,
            restriction_reason=payload.restriction_reason,
            reason=payload.reason,
        )
    except MaterialNotFoundError as exc:
        raise _missing(exc) from exc
    except MaterialPermissionError as exc:
        # 403, not 422: the move is possible, this caller may not make it.
        raise PermissionDenied(str(exc)) from exc
    except MaterialInvalidError as exc:
        raise _invalid(exc) from exc


@router.get("/{material_id}/usage", tags=["materials"])
def get_material_usage(
    material_id: uuid.UUID,
    principal: Principal = Depends(
        # BOTH, not either. `require_permission` defaults to ANY, and this
        # endpoint returns formula codes, version codes and per-component
        # percentages -- the composition data every other route in this
        # module gates carefully. `procurement_specialist` and
        # `administrator` hold `material.view` and NOT `formula.view`, so
        # the default would have handed them formulations. Raised by the
        # Supervisor.
        require_permission("material.view", "formula.view", require_all=True)
    ),
    session: Session = Depends(get_db),
) -> list[dict[str, Any]]:
    """Which formula versions use this material.

    The rows are RLS-filtered, so a caller who is not a member of a
    restricted project does not see its formulas here. That is correct and
    it is why the endpoint returns the rows rather than a count: a bare
    number that RLS had quietly reduced would present as a fact.
    """
    return materials_usage(session, material_id=material_id, caller=AgentPrincipal.of(principal))


@router.get("/{material_id}/documents", tags=["materials"])
def get_material_documents(
    material_id: uuid.UUID,
    principal: Principal = Depends(require_permission("material.view")),
    session: Session = Depends(get_db),
) -> list[dict[str, Any]]:
    """The document register: TDS, SDS, CoA, regulatory."""
    return materials_documents(
        session, material_id=material_id, caller=AgentPrincipal.of(principal)
    )


@router.post("/{material_id}/documents", status_code=status.HTTP_201_CREATED, tags=["materials"])
async def post_material_document(
    material_id: uuid.UUID,
    file: UploadFile = File(..., description="The document itself. Required."),
    document_type: str = Form(..., description="TDS | SDS | CoA | regulatory | other"),
    title: str = Form(...),
    issued_on: dt.date | None = Form(None),
    expires_on: dt.date | None = Form(None),
    supersedes_id: uuid.UUID | None = Form(None),
    principal: Principal = Depends(require_permission("material.edit", "supplier.manage")),
    session: Session = Depends(get_db),
    # 🔴 INJECTED, NOT CALLED. Written first as plain calls to
    # `get_object_store()` / `get_scanner()` inside the body, which works and is
    # untestable: `app.dependency_overrides` only reaches `Depends`, so a route
    # test could not have substituted a temporary store or an unavailable
    # scanner. The 503-on-no-scanner assertion is the one that matters most and
    # is precisely the one that would have been impossible to write.
    store: ObjectStoragePort = Depends(get_object_store),
    scanner: MalwareScannerPort = Depends(get_scanner),
) -> dict[str, str]:
    """Upload a controlled document against a material.

    🔴 THIS ROUTE USED TO TAKE JSON AND A `storage_key`, AND THAT WAS I41.

    It registered a row describing a file, and nothing anywhere stored one. The
    formulation safety check counts SDS ROWS, so any holder of `material.edit`
    satisfied the hazard-documentation control the golden scenario exists to
    demonstrate by posting `{"storage_key": "sds/anything.pdf"}`. The row WAS
    the safety evidence.

    It now takes multipart with the file itself. The contract is REPLACED, not
    extended -- a JSON path left alongside would be the I5/I36 shape this
    codebase has logged twice, where the weaker of two implementations stays
    reachable.

    Either permission: the Chemist who owns the material's data and the
    Procurement Specialist who owns its documentation are both legitimate
    authors of this record.

    STATUS CODES, and each is a different statement:
      201 stored, scanned clean, usable as safety evidence
      400 the file is not an accepted type, or its bytes contradict its name
      404 no such material in this organization
      422 the malware scanner found something
      503 no verdict could be obtained -- NOT "clean". See MalwareScannerPort
    """
    data = await file.read()
    try:
        document_id = store_document(
            session,
            material_id=material_id,
            organization_id=principal.organization_id,
            actor_id=principal.user_id,
            spec=DocumentInput(
                document_type=document_type,
                title=title,
                content_type=file.content_type,
                issued_on=issued_on,
                expires_on=expires_on,
                supersedes_id=supersedes_id,
            ),
            data=data,
            filename=file.filename or "document",
            store=store,
            scanner=scanner,
        )
    except MaterialNotFoundError as exc:
        raise _missing(exc) from exc
    except MaterialInvalidError as exc:
        raise _invalid(exc) from exc
    except FileTypeRejectedError as exc:
        # 400, not 422: the request carried something this endpoint does not
        # accept. 422 is reserved for the scanner's verdict below, so a client
        # can tell "send a PDF instead" from "that file was hostile".
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except MalwareFoundError as exc:
        # The upload is refused and the signature is recorded. The file was
        # never stored -- store.put runs only after a clean verdict -- so there
        # is nothing to quarantine and nothing to clean up.
        write_audit(
            session,
            AuditEvent(
                action="material.document_rejected_malware",
                entity_type="material",
                entity_id=str(material_id),
                organization_id=principal.organization_id,
                user_id=principal.user_id,
                new_state={"signature": exc.signature, "filename": file.filename},
                reason="a malware scanner identified an uploaded document",
            ),
        )
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f"the uploaded file was identified as malware: {exc.signature}",
        ) from exc
    except MalwareScanUnavailableError as exc:
        # 🔴 503, NOT 201. An upload that cannot be scanned is not accepted.
        # Mapping this to success is precisely the defect the port exists to
        # prevent, and it would be invisible: every file admitted, nothing in
        # the logs, the control simply absent.
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(f"uploads are unavailable because no malware scan could be performed: {exc}"),
        ) from exc
    except ObjectStorageError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"the document store is unavailable: {exc}",
        ) from exc
    return {"id": str(document_id)}


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
    return materials_suppliers(session, caller=AgentPrincipal.of(principal), status=status_filter)


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
