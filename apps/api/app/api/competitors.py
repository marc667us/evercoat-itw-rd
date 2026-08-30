"""Competitor intelligence, over HTTP.

🔴 THE LABEL UPLOAD GOES THROUGH THE MATERIALS DOCUMENT WRITER.

`POST /api/competitors/{id}/documents` does not store a file. It calls
`materials.store_document` — the same function an SDS goes through — with a
competitor product as the owner instead of a material. So a competitor's label
gets the identical treatment: type validation against the real bytes, a malware
scan whose verdict is recorded, a checksum, an object-storage key, and the
supersession rules. §14: *"Do not build a second document repository."*

That is also why the status codes below are the same five: they are the
document writer's, not this module's.

🔴 EVIDENCE IS RECORDED AT `possible`. NOTHING HERE CAN CREATE A VERIFIED CLAIM.

`POST .../evidence` takes no confidence. Moving a claim to `verified` is a
separate route requiring `compliance.review_sds`, and the database additionally
refuses unless the named verifier actually holds it. The specification forbids
presenting an inferred competitor recipe as a known formula, and this is the
mechanism rather than the intention.
"""

from __future__ import annotations

import datetime as dt
import uuid
from typing import Any

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.documents import get_object_store, get_scanner
from app.core.file_types import FileTypeRejectedError
from app.core.malware import (
    MalwareFoundError,
    MalwareScannerPort,
    MalwareScanUnavailableError,
)
from app.core.object_storage import ObjectStorageError, ObjectStoragePort
from app.core.security import Principal, get_db, require_permission
from app.core.tenancy import CrossTenantReferenceError
from app.domains.competitor_intelligence.service import (
    CompetitorError,
    CompetitorNotFoundError,
    CompetitorStateError,
    EvidenceInput,
    adopt_public_product,
    composition_matrix,
    list_benchmarks,
    list_products,
    list_samples,
    record_benchmark,
    record_evidence,
    register_product,
    register_sample,
    verify_evidence,
)
from app.domains.materials.service import (
    DocumentInput,
    MaterialInvalidError,
    MaterialNotFoundError,
    list_competitor_documents,
    store_document,
)

router = APIRouter()

__all__ = ["router"]


class ProductCreate(BaseModel):
    manufacturer: str = Field(min_length=1, max_length=300)
    product_name: str = Field(min_length=1, max_length=300)
    product_code: str | None = Field(default=None, max_length=100)
    market_segment: str | None = Field(default=None, max_length=200)
    # Optional by design: most competitor products are public and belong to the
    # organization rather than to one project.
    project_id: uuid.UUID | None = None
    notes: str | None = Field(default=None, max_length=4000)


class SampleCreate(BaseModel):
    sample_reference: str = Field(min_length=1, max_length=100)
    acquired_on: dt.date | None = None
    batch_marking: str | None = Field(default=None, max_length=200)
    observations: str | None = Field(default=None, max_length=4000)


class EvidenceCreate(BaseModel):
    component_name: str = Field(min_length=1, max_length=300)
    # 🔴 NO `confidence` FIELD. A claim is recorded as `possible` and promoted
    # only by a reviewer. Accepting it here would let the caller decide whether
    # their own guess counts as verified.
    evidence_source: str = Field(
        pattern="^(document|manual_observation|laboratory|literature|patent|inference|model)$"
    )
    evidence_grade: str = Field(pattern="^[ABCDX]$")
    cas_number: str | None = Field(default=None, pattern=r"^[0-9]{2,7}-[0-9]{2}-[0-9]$")
    component_function: str | None = Field(default=None, max_length=200)
    # Strings all the way to PostgreSQL's NUMERIC. A float here would round the
    # disclosed range before the database ever saw it (CLAUDE.md §5).
    concentration_low: str | None = Field(default=None, pattern=r"^[0-9]{1,3}(\.[0-9]{1,4})?$")
    concentration_high: str | None = Field(default=None, pattern=r"^[0-9]{1,3}(\.[0-9]{1,4})?$")
    is_balance: bool = False
    source_document_id: uuid.UUID | None = None
    sample_id: uuid.UUID | None = None
    test_id: uuid.UUID | None = None
    source_locator: str | None = Field(default=None, max_length=500)
    rationale: str | None = Field(default=None, max_length=4000)


class EvidenceGrade(BaseModel):
    confidence: str = Field(pattern="^(verified|supported|probable|possible|unknown)$")


class BenchmarkCreate(BaseModel):
    project_id: uuid.UUID
    attribute: str = Field(min_length=1, max_length=200)
    gap_summary: str = Field(min_length=1, max_length=2000)
    competitor_value: str | None = Field(default=None, max_length=200)
    our_value: str | None = Field(default=None, max_length=200)
    formula_version_id: uuid.UUID | None = None
    test_id: uuid.UUID | None = None


def _refuse(exc: CompetitorError) -> HTTPException:
    if isinstance(exc, CompetitorNotFoundError):
        return HTTPException(status.HTTP_404_NOT_FOUND, str(exc))
    if isinstance(exc, CompetitorStateError):
        return HTTPException(status.HTTP_409_CONFLICT, str(exc))
    return HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc))


@router.get("", summary="Competitor products this caller can reach")
def get_products(
    principal: Principal = Depends(require_permission("material.view")),
    session: Session = Depends(get_db),
    limit: int = Query(default=200, ge=1, le=500),
) -> list[dict[str, Any]]:
    """Gated on `material.view`, not a new `competitor.view`.

    A competitor product is technical reference material of the same kind as a
    raw material, and the roles that may look at one are the roles that need
    the other. Minting a permission nobody holds is the defect this project has
    caught five times, and the catalogue already carries 29 permissions with no
    enforcement point.
    """
    return list_products(session, organization_id=principal.organization_id, limit=limit)


@router.post("", status_code=status.HTTP_201_CREATED, summary="Register a competitor product")
def post_product(
    payload: ProductCreate,
    principal: Principal = Depends(require_permission("material.edit")),
    session: Session = Depends(get_db),
) -> dict[str, Any]:
    try:
        result = register_product(
            session,
            organization_id=principal.organization_id,
            actor_id=principal.user_id,
            manufacturer=payload.manufacturer,
            product_name=payload.product_name,
            product_code=payload.product_code,
            market_segment=payload.market_segment,
            project_id=payload.project_id,
            notes=payload.notes,
        )
    except CompetitorError as exc:
        raise _refuse(exc) from exc
    except CrossTenantReferenceError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc
    session.commit()
    return result


@router.post(
    "/{competitor_product_id}/documents",
    status_code=status.HTTP_201_CREATED,
    summary="Upload a label, a product photograph, an SDS or literature",
)
async def post_competitor_document(
    competitor_product_id: uuid.UUID,
    file: UploadFile = File(..., description="The label, photograph or document itself."),
    document_type: str = Form(
        ..., description="label | product_image | SDS | TDS | literature | patent | other"
    ),
    title: str = Form(...),
    issued_on: dt.date | None = Form(None),
    expires_on: dt.date | None = Form(None),
    principal: Principal = Depends(require_permission("material.edit")),
    session: Session = Depends(get_db),
    store: ObjectStoragePort = Depends(get_object_store),
    scanner: MalwareScannerPort = Depends(get_scanner),
) -> dict[str, str]:
    """The operator's first entry mode: a photograph of the label, or of the tin.

    🔴 IT DELEGATES TO `materials.store_document`. Not a copy of it, and not a
    second document table — the same writer, with a competitor product as the
    owner. So this upload is type-validated against its real bytes, scanned,
    checksummed and stored exactly as a Safety Data Sheet is, and it appears in
    `materials.usable_documents` under the same five conditions.

    ⚠️ UPLOADING DOES NOT POPULATE THE EVIDENCE MATRIX. There is no automatic
    extraction (chosen 2026-08-28: no OCR dependency, and neither installed
    Ollama model can read an image). The file is stored as the evidence a claim
    can CITE; a person then records what it says, and each claim points back at
    this document and the place in it. Pretending otherwise would put invented
    components on a competitor's product.

    STATUS CODES, each a different statement:
      201 stored, scanned clean, citable as evidence
      400 not an accepted type, or the bytes contradict the name
      404 no such competitor product in this organization
      422 the malware scanner found something
      503 no verdict could be obtained -- NOT "clean"
    """
    data = await file.read()
    try:
        document_id = store_document(
            session,
            competitor_product_id=competitor_product_id,
            organization_id=principal.organization_id,
            actor_id=principal.user_id,
            spec=DocumentInput(
                document_type=document_type,
                title=title,
                content_type=file.content_type,
                issued_on=issued_on,
                expires_on=expires_on,
                supersedes_id=None,
            ),
            data=data,
            filename=file.filename or "label",
            store=store,
            scanner=scanner,
        )
    except MaterialNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc
    except MaterialInvalidError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc
    except FileTypeRejectedError as exc:
        # 400, not 422: 422 is reserved for the scanner's verdict, so a client
        # can tell "send a different file" from "that file was hostile".
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc
    except MalwareFoundError as exc:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            f"the uploaded file was identified as malware: {exc.signature}",
        ) from exc
    except MalwareScanUnavailableError as exc:
        # 🔴 503, NEVER 201. "No verdict" is not "clean". Storing an unscanned
        # label as citable evidence is how a hostile upload becomes a record
        # somebody later relies on -- and it would be invisible: every file
        # admitted, nothing in the logs, the control simply absent.
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            f"uploads are unavailable because no malware scan could be performed: {exc}",
        ) from exc
    except ObjectStorageError as exc:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE, f"the document store is unavailable: {exc}"
        ) from exc
    session.commit()
    return {"id": str(document_id)}


@router.get("/{competitor_product_id}/documents", summary="Labels and documents on file")
def get_competitor_documents(
    competitor_product_id: uuid.UUID,
    principal: Principal = Depends(require_permission("material.view")),
    session: Session = Depends(get_db),
) -> list[dict[str, Any]]:
    """What has been uploaded, so a claim can cite one of them."""
    return list_competitor_documents(
        session,
        organization_id=principal.organization_id,
        competitor_product_id=competitor_product_id,
    )


@router.post(
    "/{competitor_product_id}/samples",
    status_code=status.HTTP_201_CREATED,
    summary="Register a physical sample",
)
def post_sample(
    competitor_product_id: uuid.UUID,
    payload: SampleCreate,
    principal: Principal = Depends(require_permission("material.edit")),
    session: Session = Depends(get_db),
) -> dict[str, Any]:
    try:
        result = register_sample(
            session,
            organization_id=principal.organization_id,
            actor_id=principal.user_id,
            competitor_product_id=competitor_product_id,
            sample_reference=payload.sample_reference,
            acquired_on=payload.acquired_on.isoformat() if payload.acquired_on else None,
            batch_marking=payload.batch_marking,
            observations=payload.observations,
        )
    except CompetitorError as exc:
        raise _refuse(exc) from exc
    session.commit()
    return result


@router.get("/{competitor_product_id}/samples", summary="Physical samples on file")
def get_samples(
    competitor_product_id: uuid.UUID,
    principal: Principal = Depends(require_permission("material.view")),
    session: Session = Depends(get_db),
) -> list[dict[str, Any]]:
    """The tins we actually hold, so an observation can say which one it read.

    `material.view` and not `test.view`: a sample is part of the competitor
    record, and the person transcribing a label is doing material work.
    """
    return list_samples(
        session,
        organization_id=principal.organization_id,
        competitor_product_id=competitor_product_id,
    )


@router.get("/{competitor_product_id}/composition", summary="The Composition Evidence Matrix")
def get_composition(
    competitor_product_id: uuid.UUID,
    principal: Principal = Depends(require_permission("material.view")),
    session: Session = Depends(get_db),
) -> dict[str, Any]:
    """A candidate composition where every line says what it rests on.

    🔴 THE RESPONSE CARRIES ITS OWN DISCLAIMER, in the payload rather than left
    to the screen to remember. A client that forgot it would be presenting an
    inferred recipe as a known formula, which the specification forbids
    outright — so the words travel with the data.
    """
    return composition_matrix(
        session,
        organization_id=principal.organization_id,
        competitor_product_id=competitor_product_id,
    )


@router.post(
    "/{competitor_product_id}/evidence",
    status_code=status.HTTP_201_CREATED,
    summary="Record one claim about what the product contains",
)
def post_evidence(
    competitor_product_id: uuid.UUID,
    payload: EvidenceCreate,
    principal: Principal = Depends(require_permission("material.edit")),
    session: Session = Depends(get_db),
) -> dict[str, Any]:
    """Recorded at `possible`. Promotion is a separate, permissioned act."""
    try:
        result = record_evidence(
            session,
            organization_id=principal.organization_id,
            actor_id=principal.user_id,
            competitor_product_id=competitor_product_id,
            spec=EvidenceInput(
                component_name=payload.component_name,
                evidence_source=payload.evidence_source,
                evidence_grade=payload.evidence_grade,
                cas_number=payload.cas_number,
                component_function=payload.component_function,
                concentration_low=payload.concentration_low,
                concentration_high=payload.concentration_high,
                is_balance=payload.is_balance,
                source_document_id=payload.source_document_id,
                sample_id=payload.sample_id,
                test_id=payload.test_id,
                source_locator=payload.source_locator,
                rationale=payload.rationale,
            ),
        )
    except CompetitorError as exc:
        raise _refuse(exc) from exc
    session.commit()
    return result


@router.post("/evidence/{evidence_id}/grade", summary="Change a claim's confidence")
def post_grade(
    evidence_id: uuid.UUID,
    payload: EvidenceGrade,
    principal: Principal = Depends(require_permission("compliance.review_sds")),
    session: Session = Depends(get_db),
) -> dict[str, Any]:
    """Moving a claim to `verified` is a controlled act.

    Gated on `compliance.review_sds` — the same permission that confirms a
    Safety Data Sheet reading, because both are judgements about whether a
    documented claim may be relied upon. The database independently refuses
    unless the named verifier holds it, so a direct SQL write cannot forge a
    verification without naming a real reviewer in the audit record.
    """
    try:
        result = verify_evidence(
            session,
            organization_id=principal.organization_id,
            reviewer_id=principal.user_id,
            evidence_id=evidence_id,
            confidence=payload.confidence,
        )
    except CompetitorError as exc:
        raise _refuse(exc) from exc
    session.commit()
    return result


@router.post(
    "/{competitor_product_id}/benchmarks",
    status_code=status.HTTP_201_CREATED,
    summary="Record a measured comparison against our own work",
)
def post_benchmark(
    competitor_product_id: uuid.UUID,
    payload: BenchmarkCreate,
    principal: Principal = Depends(
        require_permission("material.edit", "test.view", require_all=True)
    ),
    session: Session = Depends(get_db),
) -> dict[str, Any]:
    """It cites a test; it does not grade one. Testing owns GREEN/YELLOW/RED.

    🔴 THIS WAS GATED ON `test.view` ALONE, WHICH IS A READ PERMISSION ON A
    WRITE ROUTE (Codex P1, 2026-08-28). Anybody who could merely LOOK at tests
    could author competitor comparisons and gap summaries, and RLS could not
    stop it: the writer is inside a project they legitimately reach, so the
    policy passes. A read permission never authorizes a write.

    BOTH, not either. `material.edit` is the authoring right the rest of this
    module uses; `test.view` is needed because a benchmark cites a test and
    displays values drawn from it, so an author who cannot see tests would be
    recording a comparison against something invisible to them.

    Measured: `product_development_chemist` holds both, which is exactly who
    benchmarks a competitor. `procurement_specialist` holds `material.edit`
    without `test.view` and is correctly excluded.
    """
    try:
        result = record_benchmark(
            session,
            organization_id=principal.organization_id,
            actor_id=principal.user_id,
            competitor_product_id=competitor_product_id,
            project_id=payload.project_id,
            attribute=payload.attribute,
            gap_summary=payload.gap_summary,
            competitor_value=payload.competitor_value,
            our_value=payload.our_value,
            formula_version_id=payload.formula_version_id,
            test_id=payload.test_id,
        )
    except CompetitorError as exc:
        raise _refuse(exc) from exc
    session.commit()
    return result


@router.get("/{competitor_product_id}/benchmarks", summary="Measured comparisons on file")
def get_benchmarks(
    competitor_product_id: uuid.UUID,
    principal: Principal = Depends(require_permission("test.view")),
    session: Session = Depends(get_db),
) -> list[dict[str, Any]]:
    """⚠️ `test.view`, MATCHING ITS WRITER — a benchmark is testing output.

    A reader who may not see tests may not see comparisons drawn from them,
    which would otherwise be a way to read test results through a side door.
    """
    return list_benchmarks(
        session,
        organization_id=principal.organization_id,
        competitor_product_id=competitor_product_id,
    )


class AdoptPublicProduct(BaseModel):
    """Bring a public catalogue product into this tenant's pipeline."""

    public_product_id: uuid.UUID
    project_id: uuid.UUID | None = None


@router.post(
    "/from-public",
    status_code=status.HTTP_201_CREATED,
    summary="Adopt a product from the public catalogue into this tenant",
)
def post_adopt_public_product(
    payload: AdoptPublicProduct,
    principal: Principal = Depends(require_permission("material.edit")),
    session: Session = Depends(get_db),
) -> dict[str, Any]:
    """The signed-in half of a public product card.

    🔴 IT MAKES NO COMPOSITION CLAIM. It creates the tenant's own competitor
    record and links it to the public row; the evidence matrix stays empty
    until a document, a sample or a test fills it. This application does not
    hold a competitor's formula and does not infer one — 056 settled that.

    `material.edit`, the same permission `POST /competitors/products` already
    requires, because this IS that write with its fields read from the public
    catalogue rather than typed by hand.
    """
    try:
        result = adopt_public_product(
            session,
            organization_id=principal.organization_id,
            actor_id=principal.user_id,
            public_product_id=payload.public_product_id,
            project_id=payload.project_id,
        )
    except CompetitorNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc
    except CompetitorError as exc:
        raise _refuse(exc) from exc
    session.commit()
    return result
