OpenAI Codex v0.147.0
--------
workdir: C:\Users\USER\Documents\evercoat-itw-rd-workspace\EvercoatITWRD APP
model: gpt-5.6-sol
provider: openai
approval: never
sandbox: read-only
reasoning effort: none
reasoning summaries: none
session id: 01a04a5d-c9c6-7991-9b6e-9d0f50417c65
--------
user
You are reviewing commit c98420a in the EvercoatITWRD APP repository.

REVIEW ONLY THAT COMMIT. Do not review earlier commits, do not comment on
pre-existing code it did not touch, and do not report findings about files it
does not change. Stale-artifact drift has been a repeated problem: if you find
yourself reading something c98420a did not modify, stop and return to the diff.

Start with:
  git show --stat --oneline c98420a
  git show --format=fuller --no-ext-diff c98420a

CONTEXT
This is Phase 3 of the Material Safety Data & Research Center. Migration 056
(already committed in 4e32a54) created competitors.products, .samples,
.composition_evidence and .benchmarks, all with FORCE RLS. This commit adds:
  - list_samples / list_benchmarks in the competitor_intelligence service
  - GET /api/competitors/{id}/samples and .../benchmarks
  - the browser client, hooks and screen controls for both
  - sample_id on the evidence request, which the API always accepted and no
    client had ever sent
  - apps/api/tests/db/test_056_competitor_intelligence.py, 19 cases

BINDING PROJECT RULES THAT FINDINGS MUST RESPECT
- Authorize on permissions, never role names. Every control is re-enforced
  server side; frontend permission checks are cosmetic.
- RLS with FORCE on organization_id; the app connects as a non-superuser.
  Cross-tenant reach must be counted as what a user can reach, not by reading
  a policy.
- NUMERIC never float for measured values and percentages; concentrations
  cross the wire as STRINGS deliberately.
- Testing owns GREEN/YELLOW/RED. This module must not produce a second
  disposition anywhere.
- Never build a second document repository; materials.material_documents is the
  register and materials.usable_documents is the only definition of usable.
- A route with no browser caller, a permission with no enforcement point and a
  table with no writer are all treated as the same defect here.

WHAT I MOST WANT CHALLENGED
1. Do the two new GET routes carry the RIGHT permission? GET /samples uses
   material.view, GET /benchmarks uses test.view. Is test.view actually the
   correct gate, and can benchmarks leak test results to a reader who may not
   see tests?
2. Are the new readers correctly scoped? They pass organization_id explicitly
   AND rely on RLS. Is there any path where that explicit filter is doing the
   work and RLS is not, or where a restricted project's rows leak?
3. The test file claims to falsify three specific holes. Are any of the 19
   cases capable of passing for the wrong reason - a guard that cannot fail, a
   fixture that never produced a valid row, an assertion on a message rather
   than on the mechanism?
4. The evidence form now sends sample_id only when evidence_source is
   manual_observation. Is that consistent with the DB CHECK constraints in
   migration 056, and can a client produce a row the database refuses, or a row
   the database accepts that should have been refused?
5. Anything in the React page that could throw, render a wrong value, or
   present an inferred competitor composition as established fact.

Report ONLY concrete defects with file:line references, each with the failure
scenario that makes it real. Rank P1/P2/P3. If something is fine, do not pad
the report with it. End with a single line: VERDICT: PASS or VERDICT: FAIL

codex
I’ll constrain the review to the commit diff and trace only the changed routes, service readers, tests, and UI paths. I’ll begin with the two requested `git show` commands.
exec
"C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command 'git show --stat --oneline c98420a; git show --format=fuller --no-ext-diff c98420a' in C:\Users\USER\Documents\evercoat-itw-rd-workspace\EvercoatITWRD APP
codex
The full patch is still streaming; once it completes, I’ll use its changed-file list as the hard boundary for all follow-up inspection.
 succeeded in 670ms:
c98420a feat(competitors): the services, the screen, and the guards the migration was missing
 apps/api/app/api/competitors.py                    | 465 ++++++++++
 .../domains/competitor_intelligence/__init__.py    |   8 +
 .../app/domains/competitor_intelligence/service.py | 672 +++++++++++++++
 apps/api/app/domains/materials/service.py          |  27 +
 apps/api/app/main.py                               |   5 +
 .../tests/db/test_056_competitor_intelligence.py   | 670 +++++++++++++++
 apps/web/app/material-safety/competitors/page.tsx  | 932 +++++++++++++++++++++
 apps/web/lib/api/competitors.ts                    | 358 ++++++++
 apps/web/lib/api/hooks.ts                          | 214 +++++
 apps/web/lib/navigation.ts                         |  11 +
 tests/e2e/shell/accessibility.spec.ts              |   1 +
 11 files changed, 3363 insertions(+)
commit c98420a5813f2e38702d152e6aa657ff9b25f73f
Author:     Marc <marc667us@yahoo.com>
AuthorDate: Fri Aug 28 14:53:37 2026 -0700
Commit:     Marc <marc667us@yahoo.com>
CommitDate: Fri Aug 28 14:53:37 2026 -0700

    feat(competitors): the services, the screen, and the guards the migration was missing
    
    Phase 3's vertical. 056 shipped four tables; two of them had a writer route and
    nothing that could press it, and none of the three holes 4e32a54 claims to have
    closed was asserted anywhere.
    
    🔴 TWO TABLES HAD A WRITER AND NO READER, AND NO CONTROL AT ALL.
    
    `POST /{id}/samples` and `POST /{id}/benchmarks` existed. Nothing in the browser
    called either, and there was no GET for either, so `competitors.samples` and
    `competitors.benchmarks` could be written only by something that was never
    built and read by nothing at all. That is the defect class this project has
    counted 23+ instances of, and it violates the plan's own §10 rule that every
    table gets its writer AND its control in the same phase.
    
    Added `list_samples` / `list_benchmarks`, their two GET routes, their client
    functions, hooks and two panels on the screen. `GET /samples` takes
    `material.view`; `GET /benchmarks` takes `test.view`, matching its writer --
    a reader who may not see tests may not read comparisons drawn from them, which
    would otherwise be a side door onto test results.
    
    🔴 THE SERVER HAD ALWAYS ACCEPTED `sample_id` ON EVIDENCE AND NOTHING SENT IT.
    
    `manual_observation` means a person read a physical tin. The matrix stores WHICH
    tin, and until this commit no screen could offer the choice -- so every
    observation was recorded unattributable, and the whole first entry mode was
    half-wired. The evidence form now names the sample when the source is an
    observation.
    
    TESTS: 19 CASES OVER THE THREE CLAIMED HOLES, FALSIFIED BY BREAKING THE DATABASE
    
    Dropping `material_documents_supersedes_same_owner` turns two of them red --
    including the one asserting the CONSEQUENCE, that the SDS is still in
    `materials.usable_documents` and the formula therefore still submittable.
    Restored and re-measured green.
    
    THREE THINGS THE TESTS MEASURED THAT REASONING HAD WRONG
    
    - `core.roles` has NO `organization_id`. A role is platform-level; the
      MEMBERSHIP binds it to a tenant, which is why the verifier trigger joins
      through `core.organization_members`.
    - A BEFORE INSERT trigger runs before row CHECKs, so
      `composition_evidence_verification_complete` is unreachable until the verifier
      actually holds `compliance.review_sds`. Without the grant the test would have
      passed while measuring a different mechanism entirely.
    - Triggers fire in NAME order. `material_documents_evidence_write_once` (038)
      sorts before `material_documents_owner_write_once` (056), so 056's
      `material_id` branch is unreachable defence-in-depth. Its
      `competitor_product_id` branch IS load-bearing: 038 checks material,
      organization and document type only. The test asserts the outcome rather than
      a message, so it does not depend on which trigger happens to sort first.
    
    Also asserts FORCE RLS on all four tables read from `pg_class`, cross-tenant
    reach counted as what a user can reach (both directions), that no second
    document repository exists (§14), and that `materials.usable_documents` kept
    `security_invoker` -- 056 recreated the view the formula-submission gate reads,
    and losing that option would be invisible: every query keeps working and returns
    more rows.
    
    apps/api 866 -> 885 passed / 0 failed / 11 skipped. apps/web 218 passed.
    
    Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
    Claude-Session: https://claude.ai/code/session_01UFF6aKLmvRYBbfgp9ZRXdC

diff --git a/apps/api/app/api/competitors.py b/apps/api/app/api/competitors.py
new file mode 100644
index 0000000..dc204cb
--- /dev/null
+++ b/apps/api/app/api/competitors.py
@@ -0,0 +1,465 @@
+"""Competitor intelligence, over HTTP.
+
+🔴 THE LABEL UPLOAD GOES THROUGH THE MATERIALS DOCUMENT WRITER.
+
+`POST /api/competitors/{id}/documents` does not store a file. It calls
+`materials.store_document` — the same function an SDS goes through — with a
+competitor product as the owner instead of a material. So a competitor's label
+gets the identical treatment: type validation against the real bytes, a malware
+scan whose verdict is recorded, a checksum, an object-storage key, and the
+supersession rules. §14: *"Do not build a second document repository."*
+
+That is also why the status codes below are the same five: they are the
+document writer's, not this module's.
+
+🔴 EVIDENCE IS RECORDED AT `possible`. NOTHING HERE CAN CREATE A VERIFIED CLAIM.
+
+`POST .../evidence` takes no confidence. Moving a claim to `verified` is a
+separate route requiring `compliance.review_sds`, and the database additionally
+refuses unless the named verifier actually holds it. The specification forbids
+presenting an inferred competitor recipe as a known formula, and this is the
+mechanism rather than the intention.
+"""
+
+from __future__ import annotations
+
+import datetime as dt
+import uuid
+from typing import Any
+
+from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
+from pydantic import BaseModel, Field
+from sqlalchemy.orm import Session
+
+from app.core.documents import get_object_store, get_scanner
+from app.core.file_types import FileTypeRejectedError
+from app.core.malware import (
+    MalwareFoundError,
+    MalwareScannerPort,
+    MalwareScanUnavailableError,
+)
+from app.core.object_storage import ObjectStorageError, ObjectStoragePort
+from app.core.security import Principal, get_db, require_permission
+from app.core.tenancy import CrossTenantReferenceError
+from app.domains.competitor_intelligence.service import (
+    CompetitorError,
+    CompetitorNotFoundError,
+    CompetitorStateError,
+    EvidenceInput,
+    composition_matrix,
+    list_benchmarks,
+    list_products,
+    list_samples,
+    record_benchmark,
+    record_evidence,
+    register_product,
+    register_sample,
+    verify_evidence,
+)
+from app.domains.materials.service import (
+    DocumentInput,
+    MaterialInvalidError,
+    MaterialNotFoundError,
+    list_competitor_documents,
+    store_document,
+)
+
+router = APIRouter()
+
+__all__ = ["router"]
+
+
+class ProductCreate(BaseModel):
+    manufacturer: str = Field(min_length=1, max_length=300)
+    product_name: str = Field(min_length=1, max_length=300)
+    product_code: str | None = Field(default=None, max_length=100)
+    market_segment: str | None = Field(default=None, max_length=200)
+    # Optional by design: most competitor products are public and belong to the
+    # organization rather than to one project.
+    project_id: uuid.UUID | None = None
+    notes: str | None = Field(default=None, max_length=4000)
+
+
+class SampleCreate(BaseModel):
+    sample_reference: str = Field(min_length=1, max_length=100)
+    acquired_on: dt.date | None = None
+    batch_marking: str | None = Field(default=None, max_length=200)
+    observations: str | None = Field(default=None, max_length=4000)
+
+
+class EvidenceCreate(BaseModel):
+    component_name: str = Field(min_length=1, max_length=300)
+    # 🔴 NO `confidence` FIELD. A claim is recorded as `possible` and promoted
+    # only by a reviewer. Accepting it here would let the caller decide whether
+    # their own guess counts as verified.
+    evidence_source: str = Field(
+        pattern="^(document|manual_observation|laboratory|literature|patent|inference|model)$"
+    )
+    evidence_grade: str = Field(pattern="^[ABCDX]$")
+    cas_number: str | None = Field(default=None, pattern=r"^[0-9]{2,7}-[0-9]{2}-[0-9]$")
+    component_function: str | None = Field(default=None, max_length=200)
+    # Strings all the way to PostgreSQL's NUMERIC. A float here would round the
+    # disclosed range before the database ever saw it (CLAUDE.md §5).
+    concentration_low: str | None = Field(default=None, pattern=r"^[0-9]{1,3}(\.[0-9]{1,4})?$")
+    concentration_high: str | None = Field(default=None, pattern=r"^[0-9]{1,3}(\.[0-9]{1,4})?$")
+    is_balance: bool = False
+    source_document_id: uuid.UUID | None = None
+    sample_id: uuid.UUID | None = None
+    test_id: uuid.UUID | None = None
+    source_locator: str | None = Field(default=None, max_length=500)
+    rationale: str | None = Field(default=None, max_length=4000)
+
+
+class EvidenceGrade(BaseModel):
+    confidence: str = Field(pattern="^(verified|supported|probable|possible|unknown)$")
+
+
+class BenchmarkCreate(BaseModel):
+    project_id: uuid.UUID
+    attribute: str = Field(min_length=1, max_length=200)
+    gap_summary: str = Field(min_length=1, max_length=2000)
+    competitor_value: str | None = Field(default=None, max_length=200)
+    our_value: str | None = Field(default=None, max_length=200)
+    formula_version_id: uuid.UUID | None = None
+    test_id: uuid.UUID | None = None
+
+
+def _refuse(exc: CompetitorError) -> HTTPException:
+    if isinstance(exc, CompetitorNotFoundError):
+        return HTTPException(status.HTTP_404_NOT_FOUND, str(exc))
+    if isinstance(exc, CompetitorStateError):
+        return HTTPException(status.HTTP_409_CONFLICT, str(exc))
+    return HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc))
+
+
+@router.get("", summary="Competitor products this caller can reach")
+def get_products(
+    principal: Principal = Depends(require_permission("material.view")),
+    session: Session = Depends(get_db),
+    limit: int = Query(default=200, ge=1, le=500),
+) -> list[dict[str, Any]]:
+    """Gated on `material.view`, not a new `competitor.view`.
+
+    A competitor product is technical reference material of the same kind as a
+    raw material, and the roles that may look at one are the roles that need
+    the other. Minting a permission nobody holds is the defect this project has
+    caught five times, and the catalogue already carries 29 permissions with no
+    enforcement point.
+    """
+    return list_products(session, organization_id=principal.organization_id, limit=limit)
+
+
+@router.post("", status_code=status.HTTP_201_CREATED, summary="Register a competitor product")
+def post_product(
+    payload: ProductCreate,
+    principal: Principal = Depends(require_permission("material.edit")),
+    session: Session = Depends(get_db),
+) -> dict[str, Any]:
+    try:
+        result = register_product(
+            session,
+            organization_id=principal.organization_id,
+            actor_id=principal.user_id,
+            manufacturer=payload.manufacturer,
+            product_name=payload.product_name,
+            product_code=payload.product_code,
+            market_segment=payload.market_segment,
+            project_id=payload.project_id,
+            notes=payload.notes,
+        )
+    except CompetitorError as exc:
+        raise _refuse(exc) from exc
+    except CrossTenantReferenceError as exc:
+        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc
+    session.commit()
+    return result
+
+
+@router.post(
+    "/{competitor_product_id}/documents",
+    status_code=status.HTTP_201_CREATED,
+    summary="Upload a label, a product photograph, an SDS or literature",
+)
+async def post_competitor_document(
+    competitor_product_id: uuid.UUID,
+    file: UploadFile = File(..., description="The label, photograph or document itself."),
+    document_type: str = Form(
+        ..., description="label | product_image | SDS | TDS | literature | patent | other"
+    ),
+    title: str = Form(...),
+    issued_on: dt.date | None = Form(None),
+    expires_on: dt.date | None = Form(None),
+    principal: Principal = Depends(require_permission("material.edit")),
+    session: Session = Depends(get_db),
+    store: ObjectStoragePort = Depends(get_object_store),
+    scanner: MalwareScannerPort = Depends(get_scanner),
+) -> dict[str, str]:
+    """The operator's first entry mode: a photograph of the label, or of the tin.
+
+    🔴 IT DELEGATES TO `materials.store_document`. Not a copy of it, and not a
+    second document table — the same writer, with a competitor product as the
+    owner. So this upload is type-validated against its real bytes, scanned,
+    checksummed and stored exactly as a Safety Data Sheet is, and it appears in
+    `materials.usable_documents` under the same five conditions.
+
+    ⚠️ UPLOADING DOES NOT POPULATE THE EVIDENCE MATRIX. There is no automatic
+    extraction (chosen 2026-08-28: no OCR dependency, and neither installed
+    Ollama model can read an image). The file is stored as the evidence a claim
+    can CITE; a person then records what it says, and each claim points back at
+    this document and the place in it. Pretending otherwise would put invented
+    components on a competitor's product.
+
+    STATUS CODES, each a different statement:
+      201 stored, scanned clean, citable as evidence
+      400 not an accepted type, or the bytes contradict the name
+      404 no such competitor product in this organization
+      422 the malware scanner found something
+      503 no verdict could be obtained -- NOT "clean"
+    """
+    data = await file.read()
+    try:
+        document_id = store_document(
+            session,
+            competitor_product_id=competitor_product_id,
+            organization_id=principal.organization_id,
+            actor_id=principal.user_id,
+            spec=DocumentInput(
+                document_type=document_type,
+                title=title,
+                content_type=file.content_type,
+                issued_on=issued_on,
+                expires_on=expires_on,
+                supersedes_id=None,
+            ),
+            data=data,
+            filename=file.filename or "label",
+            store=store,
+            scanner=scanner,
+        )
+    except MaterialNotFoundError as exc:
+        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc
+    except MaterialInvalidError as exc:
+        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc
+    except FileTypeRejectedError as exc:
+        # 400, not 422: 422 is reserved for the scanner's verdict, so a client
+        # can tell "send a different file" from "that file was hostile".
+        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc
+    except MalwareFoundError as exc:
+        raise HTTPException(
+            status.HTTP_422_UNPROCESSABLE_CONTENT,
+            f"the uploaded file was identified as malware: {exc.signature}",
+        ) from exc
+    except MalwareScanUnavailableError as exc:
+        # 🔴 503, NEVER 201. "No verdict" is not "clean". Storing an unscanned
+        # label as citable evidence is how a hostile upload becomes a record
+        # somebody later relies on -- and it would be invisible: every file
+        # admitted, nothing in the logs, the control simply absent.
+        raise HTTPException(
+            status.HTTP_503_SERVICE_UNAVAILABLE,
+            f"uploads are unavailable because no malware scan could be performed: {exc}",
+        ) from exc
+    except ObjectStorageError as exc:
+        raise HTTPException(
+            status.HTTP_503_SERVICE_UNAVAILABLE, f"the document store is unavailable: {exc}"
+        ) from exc
+    session.commit()
+    return {"id": str(document_id)}
+
+
+@router.get("/{competitor_product_id}/documents", summary="Labels and documents on file")
+def get_competitor_documents(
+    competitor_product_id: uuid.UUID,
+    principal: Principal = Depends(require_permission("material.view")),
+    session: Session = Depends(get_db),
+) -> list[dict[str, Any]]:
+    """What has been uploaded, so a claim can cite one of them."""
+    return list_competitor_documents(
+        session,
+        organization_id=principal.organization_id,
+        competitor_product_id=competitor_product_id,
+    )
+
+
+@router.post(
+    "/{competitor_product_id}/samples",
+    status_code=status.HTTP_201_CREATED,
+    summary="Register a physical sample",
+)
+def post_sample(
+    competitor_product_id: uuid.UUID,
+    payload: SampleCreate,
+    principal: Principal = Depends(require_permission("material.edit")),
+    session: Session = Depends(get_db),
+) -> dict[str, Any]:
+    try:
+        result = register_sample(
+            session,
+            organization_id=principal.organization_id,
+            actor_id=principal.user_id,
+            competitor_product_id=competitor_product_id,
+            sample_reference=payload.sample_reference,
+            acquired_on=payload.acquired_on.isoformat() if payload.acquired_on else None,
+            batch_marking=payload.batch_marking,
+            observations=payload.observations,
+        )
+    except CompetitorError as exc:
+        raise _refuse(exc) from exc
+    session.commit()
+    return result
+
+
+@router.get("/{competitor_product_id}/samples", summary="Physical samples on file")
+def get_samples(
+    competitor_product_id: uuid.UUID,
+    principal: Principal = Depends(require_permission("material.view")),
+    session: Session = Depends(get_db),
+) -> list[dict[str, Any]]:
+    """The tins we actually hold, so an observation can say which one it read.
+
+    `material.view` and not `test.view`: a sample is part of the competitor
+    record, and the person transcribing a label is doing material work.
+    """
+    return list_samples(
+        session,
+        organization_id=principal.organization_id,
+        competitor_product_id=competitor_product_id,
+    )
+
+
+@router.get("/{competitor_product_id}/composition", summary="The Composition Evidence Matrix")
+def get_composition(
+    competitor_product_id: uuid.UUID,
+    principal: Principal = Depends(require_permission("material.view")),
+    session: Session = Depends(get_db),
+) -> dict[str, Any]:
+    """A candidate composition where every line says what it rests on.
+
+    🔴 THE RESPONSE CARRIES ITS OWN DISCLAIMER, in the payload rather than left
+    to the screen to remember. A client that forgot it would be presenting an
+    inferred recipe as a known formula, which the specification forbids
+    outright — so the words travel with the data.
+    """
+    return composition_matrix(
+        session,
+        organization_id=principal.organization_id,
+        competitor_product_id=competitor_product_id,
+    )
+
+
+@router.post(
+    "/{competitor_product_id}/evidence",
+    status_code=status.HTTP_201_CREATED,
+    summary="Record one claim about what the product contains",
+)
+def post_evidence(
+    competitor_product_id: uuid.UUID,
+    payload: EvidenceCreate,
+    principal: Principal = Depends(require_permission("material.edit")),
+    session: Session = Depends(get_db),
+) -> dict[str, Any]:
+    """Recorded at `possible`. Promotion is a separate, permissioned act."""
+    try:
+        result = record_evidence(
+            session,
+            organization_id=principal.organization_id,
+            actor_id=principal.user_id,
+            competitor_product_id=competitor_product_id,
+            spec=EvidenceInput(
+                component_name=payload.component_name,
+                evidence_source=payload.evidence_source,
+                evidence_grade=payload.evidence_grade,
+                cas_number=payload.cas_number,
+                component_function=payload.component_function,
+                concentration_low=payload.concentration_low,
+                concentration_high=payload.concentration_high,
+                is_balance=payload.is_balance,
+                source_document_id=payload.source_document_id,
+                sample_id=payload.sample_id,
+                test_id=payload.test_id,
+                source_locator=payload.source_locator,
+                rationale=payload.rationale,
+            ),
+        )
+    except CompetitorError as exc:
+        raise _refuse(exc) from exc
+    session.commit()
+    return result
+
+
+@router.post("/evidence/{evidence_id}/grade", summary="Change a claim's confidence")
+def post_grade(
+    evidence_id: uuid.UUID,
+    payload: EvidenceGrade,
+    principal: Principal = Depends(require_permission("compliance.review_sds")),
+    session: Session = Depends(get_db),
+) -> dict[str, Any]:
+    """Moving a claim to `verified` is a controlled act.
+
+    Gated on `compliance.review_sds` — the same permission that confirms a
+    Safety Data Sheet reading, because both are judgements about whether a
+    documented claim may be relied upon. The database independently refuses
+    unless the named verifier holds it, so a direct SQL write cannot forge a
+    verification without naming a real reviewer in the audit record.
+    """
+    try:
+        result = verify_evidence(
+            session,
+            organization_id=principal.organization_id,
+            reviewer_id=principal.user_id,
+            evidence_id=evidence_id,
+            confidence=payload.confidence,
+        )
+    except CompetitorError as exc:
+        raise _refuse(exc) from exc
+    session.commit()
+    return result
+
+
+@router.post(
+    "/{competitor_product_id}/benchmarks",
+    status_code=status.HTTP_201_CREATED,
+    summary="Record a measured comparison against our own work",
+)
+def post_benchmark(
+    competitor_product_id: uuid.UUID,
+    payload: BenchmarkCreate,
+    principal: Principal = Depends(require_permission("test.view")),
+    session: Session = Depends(get_db),
+) -> dict[str, Any]:
+    """It cites a test; it does not grade one. Testing owns GREEN/YELLOW/RED."""
+    try:
+        result = record_benchmark(
+            session,
+            organization_id=principal.organization_id,
+            actor_id=principal.user_id,
+            competitor_product_id=competitor_product_id,
+            project_id=payload.project_id,
+            attribute=payload.attribute,
+            gap_summary=payload.gap_summary,
+            competitor_value=payload.competitor_value,
+            our_value=payload.our_value,
+            formula_version_id=payload.formula_version_id,
+            test_id=payload.test_id,
+        )
+    except CompetitorError as exc:
+        raise _refuse(exc) from exc
+    session.commit()
+    return result
+
+
+@router.get("/{competitor_product_id}/benchmarks", summary="Measured comparisons on file")
+def get_benchmarks(
+    competitor_product_id: uuid.UUID,
+    principal: Principal = Depends(require_permission("test.view")),
+    session: Session = Depends(get_db),
+) -> list[dict[str, Any]]:
+    """⚠️ `test.view`, MATCHING ITS WRITER — a benchmark is testing output.
+
+    A reader who may not see tests may not see comparisons drawn from them,
+    which would otherwise be a way to read test results through a side door.
+    """
+    return list_benchmarks(
+        session,
+        organization_id=principal.organization_id,
+        competitor_product_id=competitor_product_id,
+    )
diff --git a/apps/api/app/domains/competitor_intelligence/__init__.py b/apps/api/app/domains/competitor_intelligence/__init__.py
new file mode 100644
index 0000000..22dac98
--- /dev/null
+++ b/apps/api/app/domains/competitor_intelligence/__init__.py
@@ -0,0 +1,8 @@
+"""Competitor intelligence — evidence about a competitor's product.
+
+Part of the Material Safety Data & Research Center, named in full. Nothing here
+abbreviates to `MSD`, which in this codebase means the Material Science &
+Development Assistant.
+"""
+
+from __future__ import annotations
diff --git a/apps/api/app/domains/competitor_intelligence/service.py b/apps/api/app/domains/competitor_intelligence/service.py
new file mode 100644
index 0000000..d497ed8
--- /dev/null
+++ b/apps/api/app/domains/competitor_intelligence/service.py
@@ -0,0 +1,672 @@
+"""Competitor intelligence: products, samples, and the Composition Evidence Matrix.
+
+🔴 THE ONE RULE THIS MODULE EXISTS TO KEEP
+
+The specification, on competitor formulation analysis:
+
+    "Safety Data Sheets often disclose only hazardous components or
+     concentration ranges and normally do not reveal a complete proprietary
+     formulation. The application shall therefore NEVER automatically present
+     an inferred competitor recipe as a known or verified formula."
+
+So there is no competitor formula anywhere in this module. There is a matrix of
+CLAIMS, each carrying how it is known and how far it can be trusted. Reading the
+matrix end to end gives a candidate composition — which is what the operator
+asked for — and every line of it says what it rests on.
+
+The purpose is stated in the same section and is worth keeping in view: this is
+not for reconstructing somebody's proprietary information. It is for
+understanding comparable chemistry, likely material functions, performance
+characteristics and technology approaches, so that a technically superior
+product can be developed. Lawful benchmarking, with evidence and inference kept
+visibly apart.
+
+🔴 THE THREE ENTRY MODES ARE PEERS
+
+Label, product image, and manual entry. A person reading the back of a tin is
+making an OBSERVATION, not an inference, and `manual_observation` says so —
+an earlier design forced honest transcription into `inference`, which
+misdescribed the person's work. What manual entry cannot do is reach
+`verified`, because there is no document anybody else can re-check.
+
+⚠️ DOCUMENTS BELONG TO THE ONE REGISTER. Uploading a label calls
+`materials.store_document`, the same writer an SDS goes through, so a
+competitor label gets the identical malware scan, checksum, expiry and
+supersession rules. §14: do not build a second document repository.
+"""
+
+from __future__ import annotations
+
+import uuid
+from dataclasses import dataclass
+from decimal import Decimal
+from typing import Any
+
+from sqlalchemy import text
+from sqlalchemy.exc import DBAPIError
+from sqlalchemy.orm import Session
+
+from app.core.audit import AuditEvent, write_audit
+from app.core.db import guarded_write
+
+__all__ = [
+    "CompetitorError",
+    "CompetitorNotFoundError",
+    "CompetitorStateError",
+    "EvidenceInput",
+    "composition_matrix",
+    "list_benchmarks",
+    "list_products",
+    "list_samples",
+    "record_benchmark",
+    "record_evidence",
+    "register_product",
+    "register_sample",
+    "verify_evidence",
+]
+
+
+class CompetitorError(RuntimeError):
+    """A competitor record could not be written as asked."""
+
+
+class CompetitorNotFoundError(CompetitorError):
+    """It does not exist, or the caller cannot reach it."""
+
+
+class CompetitorStateError(CompetitorError):
+    """It exists but is not in a state that allows this."""
+
+
+def _decimal_strings(row: Any) -> dict[str, Any]:
+    """Every `Decimal` as a string; everything else untouched.
+
+    🔴 WITHOUT THIS, `NUMERIC` LEAVES THE API AS A FLOAT. FastAPI's
+    `jsonable_encoder` maps `Decimal` to float, so a disclosed range of
+    10.0000-25.0000 arrives as 10.0-25.0: the manufacturer's stated precision
+    destroyed, a float on a controlled record against CLAUDE.md §5, and the
+    client's `z.string()` rejecting the response.
+
+    This module is the FOURTH to need it — `formulations`, `laboratory`,
+    `testing` and `material_safety` each carry a copy, because importing across
+    domain services is the cross-domain dependency §0.3 forbids. Four copies is
+    the point at which it should move to `core`; recorded here rather than done
+    mid-slice, because moving it touches 36 existing call sites.
+    """
+    return {
+        key: (str(value) if isinstance(value, Decimal) else value) for key, value in row.items()
+    }
+
+
+def _translate(exc: DBAPIError) -> CompetitorError:
+    """A PostgreSQL refusal, as an answer a client can act on."""
+    detail = str(getattr(exc, "orig", exc))
+
+    if "products_org_name_key" in detail:
+        return CompetitorStateError(
+            "that manufacturer and product are already registered in this "
+            "organization. Add evidence to the existing product rather than "
+            "creating a second record of the same thing."
+        )
+    if "samples_org_reference_key" in detail:
+        return CompetitorStateError("that sample reference is already used here")
+    if "composition_evidence_document_fk" in detail:
+        return CompetitorStateError(
+            "that document does not belong to this competitor product. A label "
+            "uploaded for one product cannot support a claim about another."
+        )
+    if "composition_evidence_verifiable_source" in detail:
+        return CompetitorStateError(
+            "only a document-backed or laboratory-backed claim can be verified. "
+            "An observation, an inference or a model result can be supported, "
+            "probable or possible -- never verified."
+        )
+    if "may only be marked verified by an active member holding" in detail:
+        return CompetitorStateError(detail.strip().splitlines()[0])
+    if "composition_evidence_observation_shape" in detail:
+        return CompetitorError(
+            "a manual observation must name who observed it and say what they saw"
+        )
+    if "composition_evidence_reasoned_shape" in detail:
+        return CompetitorError("an inference must state what it was reasoned from")
+    if "composition_evidence_document_shape" in detail:
+        return CompetitorError("document-backed evidence must name the document")
+    if "composition_evidence_balance_has_no_range" in detail:
+        return CompetitorError("'the balance' is not also a concentration range")
+    if "row-level security" in detail:
+        return CompetitorStateError("this record names a project you cannot reach")
+    return CompetitorError(detail)
+
+
+# ---------------------------------------------------------------------------
+# Products and samples
+# ---------------------------------------------------------------------------
+
+
+def register_product(
+    session: Session,
+    *,
+    organization_id: uuid.UUID,
+    actor_id: uuid.UUID,
+    manufacturer: str,
+    product_name: str,
+    product_code: str | None = None,
+    market_segment: str | None = None,
+    project_id: uuid.UUID | None = None,
+    notes: str | None = None,
+) -> dict[str, Any]:
+    """Register a competitor product.
+
+    `project_id` is optional and that is the specification's own shape: a
+    competitor product *may* be registered against a project. Most are public
+    products the whole organization may see, and NULL says exactly that.
+    """
+    try:
+        with guarded_write(session):
+            product_id = session.execute(
+                text(
+                    """
+                    INSERT INTO competitors.products
+                        (organization_id, project_id, manufacturer, product_name,
+                         product_code, market_segment, notes, registered_by)
+                    VALUES (:org, :project, :manufacturer, :name, :code, :segment,
+                            :notes, :actor)
+                    RETURNING id
+                    """
+                ),
+                {
+                    "org": organization_id,
+                    "project": project_id,
+                    "manufacturer": manufacturer,
+                    "name": product_name,
+                    "code": product_code,
+                    "segment": market_segment,
+                    "notes": notes,
+                    "actor": actor_id,
+                },
+            ).scalar_one()
+    except DBAPIError as exc:
+        raise _translate(exc) from exc
+
+    write_audit(
+        session,
+        AuditEvent(
+            action="COMPETITOR_CREATED",
+            entity_type="competitor_product",
+            entity_id=str(product_id),
+            organization_id=organization_id,
+            user_id=actor_id,
+            new_state={"manufacturer": manufacturer, "product_name": product_name},
+        ),
+    )
+    return {"id": product_id}
+
+
+def list_products(
+    session: Session, *, organization_id: uuid.UUID, limit: int = 200
+) -> list[dict[str, Any]]:
+    """Competitor products this caller can reach.
+
+    RLS applies the project predicate, so a product registered against a
+    restricted project is invisible to a non-member. Counts of documents and
+    evidence come with it, because a product with neither is a stub somebody
+    started and abandoned, and the screen should say so.
+    """
+    return [
+        dict(r)
+        for r in session.execute(
+            text(
+                """
+                SELECT p.id, p.manufacturer, p.product_name, p.product_code,
+                       p.market_segment, p.project_id, p.created_at,
+                       (SELECT count(*) FROM materials.material_documents d
+                         WHERE d.competitor_product_id = p.id
+                           AND d.organization_id = p.organization_id) AS document_count,
+                       (SELECT count(*) FROM competitors.composition_evidence e
+                         WHERE e.competitor_product_id = p.id
+                           AND e.organization_id = p.organization_id) AS evidence_count
+                  FROM competitors.products p
+                 WHERE p.organization_id = :org
+                 ORDER BY p.manufacturer, p.product_name
+                 LIMIT :limit
+                """
+            ),
+            {"org": organization_id, "limit": limit},
+        ).mappings()
+    ]
+
+
+def register_sample(
+    session: Session,
+    *,
+    organization_id: uuid.UUID,
+    actor_id: uuid.UUID,
+    competitor_product_id: uuid.UUID,
+    sample_reference: str,
+    acquired_on: str | None = None,
+    batch_marking: str | None = None,
+    observations: str | None = None,
+) -> dict[str, Any]:
+    """Register a physical sample of a competitor product."""
+    try:
+        with guarded_write(session):
+            sample_id = session.execute(
+                text(
+                    """
+                    INSERT INTO competitors.samples
+                        (organization_id, competitor_product_id, sample_reference,
+                         acquired_on, batch_marking, observations, registered_by)
+                    VALUES (:org, :product, :ref, CAST(:acquired AS DATE), :batch,
+                            :observations, :actor)
+                    RETURNING id
+                    """
+                ),
+                {
+                    "org": organization_id,
+                    "product": competitor_product_id,
+                    "ref": sample_reference,
+                    "acquired": acquired_on,
+                    "batch": batch_marking,
+                    "observations": observations,
+                    "actor": actor_id,
+                },
+            ).scalar_one()
+    except DBAPIError as exc:
+        raise _translate(exc) from exc
+
+    write_audit(
+        session,
+        AuditEvent(
+            action="COMPETITOR_SAMPLE_REGISTERED",
+            entity_type="competitor_sample",
+            entity_id=str(sample_id),
+            organization_id=organization_id,
+            user_id=actor_id,
+            new_state={"sample_reference": sample_reference},
+        ),
+    )
+    return {"id": sample_id}
+
+
+def list_samples(
+    session: Session, *, organization_id: uuid.UUID, competitor_product_id: uuid.UUID
+) -> list[dict[str, Any]]:
+    """Physical samples on file for one competitor product, newest first.
+
+    🔴 WRITTEN BECAUSE `register_sample` HAD NO READER, AND A SAMPLE NOBODY
+    CAN LIST IS A ROW THAT CANNOT BE CITED. `composition_evidence.sample_id`
+    exists precisely so a `manual_observation` claim can name the tin it was
+    read from -- and naming one requires being shown which ones exist. A
+    writer without its reader is the same defect as a route without its
+    control, one tier down.
+
+    RLS supplies the organization and project predicate; the explicit
+    `organization_id` here is the same belt-and-braces every reader in this
+    module uses, not a substitute for it.
+    """
+    return [
+        dict(r)
+        for r in session.execute(
+            text(
+                """
+                SELECT s.id, s.sample_reference, s.acquired_on, s.batch_marking,
+                       s.observations, s.registered_by, s.created_at,
+                       (SELECT count(*) FROM competitors.composition_evidence e
+                         WHERE e.sample_id = s.id
+                           AND e.organization_id = s.organization_id) AS evidence_count
+                  FROM competitors.samples s
+                 WHERE s.organization_id = :org
+                   AND s.competitor_product_id = :product
+                 ORDER BY s.acquired_on DESC NULLS LAST, s.created_at DESC
+                """
+            ),
+            {"org": organization_id, "product": competitor_product_id},
+        ).mappings()
+    ]
+
+
+# ---------------------------------------------------------------------------
+# The Composition Evidence Matrix
+# ---------------------------------------------------------------------------
+
+
+@dataclass(frozen=True, slots=True)
+class EvidenceInput:
+    component_name: str
+    evidence_source: str
+    evidence_grade: str
+    cas_number: str | None = None
+    component_function: str | None = None
+    # Strings, not floats. NUMERIC(7,4) in PostgreSQL, and a float would round
+    # the disclosed range before the database saw it.
+    concentration_low: str | None = None
+    concentration_high: str | None = None
+    is_balance: bool = False
+    source_document_id: uuid.UUID | None = None
+    sample_id: uuid.UUID | None = None
+    test_id: uuid.UUID | None = None
+    source_locator: str | None = None
+    rationale: str | None = None
+
+
+def record_evidence(
+    session: Session,
+    *,
+    organization_id: uuid.UUID,
+    actor_id: uuid.UUID,
+    competitor_product_id: uuid.UUID,
+    spec: EvidenceInput,
+) -> dict[str, Any]:
+    """Record one claim about what a competitor product contains.
+
+    🔴 IT IS RECORDED AT `possible`, NEVER AT `verified`.
+
+    `confidence` is not an argument. A claim arrives as something somebody
+    noticed; it becomes verified only through `verify_evidence`, which is a
+    separate act by somebody holding `compliance.review_sds` — the same shape
+    as a root cause, where §3 rule 4 says only a human moves a hypothesis to
+    accepted. Letting the writer set `verified` would make the matrix's
+    central distinction a matter of what the caller typed.
+
+    `observed_by` is the actor for a manual observation: the person recording
+    what they saw is the person who saw it, and the database requires a name.
+    """
+    try:
+        with guarded_write(session):
+            evidence_id = session.execute(
+                text(
+                    """
+                    INSERT INTO competitors.composition_evidence
+                        (organization_id, competitor_product_id, component_name,
+                         cas_number, component_function, concentration_low,
+                         concentration_high, is_balance, evidence_source,
+                         evidence_grade, confidence, source_document_id, sample_id,
+                         test_id, source_locator, rationale, observed_by, recorded_by)
+                    VALUES (:org, :product, :name, :cas, :function,
+                            CAST(:low AS NUMERIC), CAST(:high AS NUMERIC), :balance,
+                            :source, :grade, 'possible', :doc, :sample, :test,
+                            :locator, :rationale, :observed, :actor)
+                    RETURNING id
+                    """
+                ),
+                {
+                    "org": organization_id,
+                    "product": competitor_product_id,
+                    "name": spec.component_name,
+                    "cas": spec.cas_number,
+                    "function": spec.component_function,
+                    "low": spec.concentration_low,
+                    "high": spec.concentration_high,
+                    "balance": spec.is_balance,
+                    "source": spec.evidence_source,
+                    "grade": spec.evidence_grade,
+                    "doc": spec.source_document_id,
+                    "sample": spec.sample_id,
+                    "test": spec.test_id,
+                    "locator": spec.source_locator,
+                    "rationale": spec.rationale,
+                    "observed": actor_id if spec.evidence_source == "manual_observation" else None,
+                    "actor": actor_id,
+                },
+            ).scalar_one()
+    except DBAPIError as exc:
+        raise _translate(exc) from exc
+
+    write_audit(
+        session,
+        AuditEvent(
+            action="COMPETITOR_EVIDENCE_RECORDED",
+            entity_type="composition_evidence",
+            entity_id=str(evidence_id),
+            organization_id=organization_id,
+            user_id=actor_id,
+            # The component name is not a payload to withhold -- it is the
+            # identity of the claim -- but the rationale and locator are, and
+            # they are not copied here.
+            new_state={
+                "component_name": spec.component_name,
+                "evidence_source": spec.evidence_source,
+                "evidence_grade": spec.evidence_grade,
+                "confidence": "possible",
+            },
+        ),
+    )
+    return {"id": evidence_id, "confidence": "possible"}
+
+
+def verify_evidence(
+    session: Session,
+    *,
+    organization_id: uuid.UUID,
+    reviewer_id: uuid.UUID,
+    evidence_id: uuid.UUID,
+    confidence: str,
+) -> dict[str, Any]:
+    """Move a claim's confidence, including to `verified`.
+
+    🔴 `verified` IS THE ONLY STATE THAT NEEDS A REVIEWER, AND THE DATABASE
+    CHECKS THE REVIEWER HOLDS THE PERMISSION.
+
+    A CHECK constraint can require a name and a time; it cannot establish that
+    the named person was entitled. A trigger joins `member_roles` ->
+    `role_permissions` -> `permissions` and refuses unless `verified_by` holds
+    `compliance.review_sds` in this organization.
+
+    ⚠️ A MISUSE BARRIER, NOT A BOUNDARY. Anything already running arbitrary SQL
+    as `evercoat_app` is inside the trust boundary. This removes every
+    accidental path and makes a deliberate one attributable — the same
+    distinction I109/ADR-032 draws.
+    """
+    verified = confidence == "verified"
+    row = (
+        session.execute(
+            text(
+                """
+                UPDATE competitors.composition_evidence
+                   SET confidence  = :confidence,
+                       verified_by = CASE WHEN :verified THEN :reviewer ELSE NULL END,
+                       verified_at = CASE WHEN :verified THEN clock_timestamp() ELSE NULL END
+                 WHERE id = :eid AND organization_id = :org
+                RETURNING id, confidence, verified_at
+                """
+            ),
+            {
+                "eid": evidence_id,
+                "org": organization_id,
+                "confidence": confidence,
+                "verified": verified,
+                "reviewer": reviewer_id,
+            },
+        )
+        .mappings()
+        .one_or_none()
+    )
+    if row is None:
+        raise CompetitorNotFoundError("no such evidence that you can reach")
+
+    write_audit(
+        session,
+        AuditEvent(
+            action="COMPETITOR_EVIDENCE_GRADED",
+            entity_type="composition_evidence",
+            entity_id=str(evidence_id),
+            organization_id=organization_id,
+            user_id=reviewer_id,
+            new_state={"confidence": confidence},
+        ),
+    )
+    return dict(row)
+
+
+def composition_matrix(
+    session: Session, *, organization_id: uuid.UUID, competitor_product_id: uuid.UUID
+) -> dict[str, Any]:
+    """🔴 A CANDIDATE COMPOSITION, AND EVERY LINE SAYS WHAT IT RESTS ON.
+
+    This is the answer to *"what is in the competitor's product"* — and it is
+    deliberately not shaped like a formula. It is the claims, strongest
+    evidence first, each with its source, its grade, its confidence and the
+    locator somebody else can use to re-check it.
+
+    The summary counts exist so a reader can see at a glance how much of the
+    picture is actually established: "3 verified, 2 supported, 6 inferred" is a
+    different product understanding from "11 verified", and a bare list makes
+    them look alike.
+    """
+    rows = [
+        _decimal_strings(r)
+        for r in session.execute(
+            text(
+                """
+                SELECT e.id, e.component_name, e.cas_number, e.component_function,
+                       e.concentration_low, e.concentration_high, e.is_balance,
+                       e.evidence_source, e.evidence_grade, e.confidence,
+                       e.source_locator, e.rationale, e.verified_at,
+                       e.source_document_id, e.sample_id, e.test_id,
+                       d.title AS source_document_title,
+                       d.document_type AS source_document_type
+                  FROM competitors.composition_evidence e
+                  LEFT JOIN materials.material_documents d
+                    ON d.id = e.source_document_id AND d.organization_id = e.organization_id
+                 WHERE e.organization_id = :org AND e.competitor_product_id = :product
+                 ORDER BY
+                   -- Strongest first: a reader scanning the top of this list
+                   -- should be reading the best-established claims.
+                   CASE e.confidence WHEN 'verified'  THEN 0
+                                     WHEN 'supported' THEN 1
+                                     WHEN 'probable'  THEN 2
+                                     WHEN 'possible'  THEN 3
+                                     ELSE 4 END,
+                   e.evidence_grade,
+                   e.concentration_high DESC NULLS LAST,
+                   e.component_name
+                """
+            ),
+            {"org": organization_id, "product": competitor_product_id},
+        ).mappings()
+    ]
+
+    by_confidence: dict[str, int] = {}
+    for row in rows:
+        key = str(row["confidence"])
+        by_confidence[key] = by_confidence.get(key, 0) + 1
+
+    return {
+        "rows": rows,
+        "summary": by_confidence,
+        # 🔴 STATED IN THE PAYLOAD, NOT LEFT TO THE SCREEN TO REMEMBER.
+        # Any client rendering this must say it, and a client that forgets
+        # would be presenting an inferred recipe as a known one -- the single
+        # thing the specification forbids outright.
+        "disclaimer": (
+            "This is a candidate composition assembled from evidence of "
+            "differing strength. It is not a known or verified formula, and "
+            "rows that are not marked verified have not been confirmed."
+        ),
+    }
+
+
+def record_benchmark(
+    session: Session,
+    *,
+    organization_id: uuid.UUID,
+    actor_id: uuid.UUID,
+    competitor_product_id: uuid.UUID,
+    project_id: uuid.UUID,
+    attribute: str,
+    gap_summary: str,
+    competitor_value: str | None = None,
+    our_value: str | None = None,
+    formula_version_id: uuid.UUID | None = None,
+    test_id: uuid.UUID | None = None,
+) -> dict[str, Any]:
+    """Record a measured comparison against our own work.
+
+    ⚠️ IT CITES A TEST; IT DOES NOT GRADE ONE. Testing owns GREEN/YELLOW/RED
+    (CLAUDE.md §10) and this module must not produce a second disposition. The
+    gap is stated in words for the same reason: the arithmetic belongs to the
+    engine (§3 rule 2), and a delta computed here would be a second answer to a
+    question Testing already answers.
+    """
+    try:
+        with guarded_write(session):
+            benchmark_id = session.execute(
+                text(
+                    """
+                    INSERT INTO competitors.benchmarks
+                        (organization_id, competitor_product_id, project_id,
+                         formula_version_id, test_id, attribute, competitor_value,
+                         our_value, gap_summary, recorded_by)
+                    VALUES (:org, :product, :project, :version, :test, :attribute,
+                            :theirs, :ours, :gap, :actor)
+                    RETURNING id
+                    """
+                ),
+                {
+                    "org": organization_id,
+                    "product": competitor_product_id,
+                    "project": project_id,
+                    "version": formula_version_id,
+                    "test": test_id,
+                    "attribute": attribute,
+                    "theirs": competitor_value,
+                    "ours": our_value,
+                    "gap": gap_summary,
+                    "actor": actor_id,
+                },
+            ).scalar_one()
+    except DBAPIError as exc:
+        raise _translate(exc) from exc
+
+    write_audit(
+        session,
+        AuditEvent(
+            action="COMPETITOR_BENCHMARK_RECORDED",
+            entity_type="competitor_benchmark",
+            entity_id=str(benchmark_id),
+            organization_id=organization_id,
+            user_id=actor_id,
+            new_state={"attribute": attribute},
+        ),
+    )
+    return {"id": benchmark_id}
+
+
+def list_benchmarks(
+    session: Session, *, organization_id: uuid.UUID, competitor_product_id: uuid.UUID
+) -> list[dict[str, Any]]:
+    """Measured comparisons recorded against one competitor product.
+
+    🔴 WRITTEN BECAUSE `record_benchmark` HAD NO READER EITHER. The whole
+    point of a benchmark is that somebody later reads it beside the gap it
+    describes; a write-only benchmark table is an audit trail nobody can
+    consult.
+
+    ⚠️ IT REPORTS THE CITED TEST, IT DOES NOT REPORT A DISPOSITION. Testing
+    owns GREEN/YELLOW/RED (`CLAUDE.md` §10) and this query deliberately does
+    not join one in: a colour surfaced here would be a second answer to a
+    question Testing already answers, and the two would drift.
+
+    The project name is joined because `project_id` alone is a UUID a reader
+    cannot act on -- the same reason `list_products` carries its counts.
+    """
+    return [
+        dict(r)
+        for r in session.execute(
+            text(
+                """
+                SELECT b.id, b.attribute, b.competitor_value, b.our_value,
+                       b.gap_summary, b.project_id, b.formula_version_id,
+                       b.test_id, b.recorded_by, b.created_at,
+                       p.name AS project_name, p.project_code
+                  FROM competitors.benchmarks b
+                  LEFT JOIN projects.projects p
+                    ON p.id = b.project_id AND p.organization_id = b.organization_id
+                 WHERE b.organization_id = :org
+                   AND b.competitor_product_id = :product
+                 ORDER BY b.created_at DESC
+                """
+            ),
+            {"org": organization_id, "product": competitor_product_id},
+        ).mappings()
+    ]
diff --git a/apps/api/app/domains/materials/service.py b/apps/api/app/domains/materials/service.py
index 03b8e91..18d670c 100644
--- a/apps/api/app/domains/materials/service.py
+++ b/apps/api/app/domains/materials/service.py
@@ -86,6 +86,7 @@ __all__ = [
     "create_supplier",
     "get_material",
     "link_supplier",
+    "list_competitor_documents",
     "list_material_documents",
     "list_materials",
     "list_suppliers",
@@ -1290,6 +1291,32 @@ def store_document(
     return document_id
 
 
+def list_competitor_documents(
+    session: Session, *, competitor_product_id: uuid.UUID, organization_id: uuid.UUID
+) -> list[dict[str, Any]]:
+    """The document register for one competitor product, newest first.
+
+    Beside `list_material_documents` rather than inside it: the two take
+    different owners and a single function with two optional arguments would
+    have a branch nobody reads. They share the TABLE, which is the thing §14
+    cares about; sharing the query would save four lines and cost the caller
+    clarity about which owner it is asking for.
+    """
+    rows = session.execute(
+        text(
+            """
+            SELECT id, document_type, title, storage_key, content_type, byte_size,
+                   checksum_sha256, issued_on, expires_on, supersedes_id, created_at
+            FROM materials.material_documents
+            WHERE competitor_product_id = :cpid AND organization_id = :org
+            ORDER BY document_type, issued_on DESC NULLS LAST, created_at DESC
+            """
+        ),
+        {"cpid": competitor_product_id, "org": organization_id},
+    ).mappings()
+    return [dict(r) for r in rows]
+
+
 def list_material_documents(
     session: Session, *, material_id: uuid.UUID, organization_id: uuid.UUID
 ) -> list[dict[str, Any]]:
diff --git a/apps/api/app/main.py b/apps/api/app/main.py
index 588806c..6e52773 100644
--- a/apps/api/app/main.py
+++ b/apps/api/app/main.py
@@ -23,6 +23,7 @@ from app.api.admin import router as admin_router
 from app.api.admin_reference_data import router as admin_reference_data_router
 from app.api.admin_stage_gates import router as admin_stage_gates_router
 from app.api.analysis import router as analysis_router
+from app.api.competitors import router as competitors_router
 from app.api.dashboards import router as dashboards_router
 from app.api.failures import approvals_router
 from app.api.failures import router as failures_router
@@ -299,6 +300,10 @@ def create_app() -> FastAPI:
     application.include_router(
         material_safety_router, prefix="/api/material-safety", tags=["material-safety"]
     )
+    # Competitor intelligence. Its label upload delegates to the materials
+    # document writer rather than storing anything itself -- §14 forbids a
+    # second document repository, and the register is one table.
+    application.include_router(competitors_router, prefix="/api/competitors", tags=["competitors"])
 
     if settings.metrics_enabled:
 
diff --git a/apps/api/tests/db/test_056_competitor_intelligence.py b/apps/api/tests/db/test_056_competitor_intelligence.py
new file mode 100644
index 0000000..fad3822
--- /dev/null
+++ b/apps/api/tests/db/test_056_competitor_intelligence.py
@@ -0,0 +1,670 @@
+"""Migration 056 — the competitor register and the Composition Evidence Matrix.
+
+🔴 WRITTEN BECAUSE `4e32a54` CLAIMED THREE HOLES CLOSED AND ASSERTED NONE OF THEM.
+
+The commit message states that the review found, before any of it was written:
+
+  1. `supersedes_id` constrained the tenant but not the OWNER, so a competitor
+     label could supersede a material's Safety Data Sheet — removing that SDS
+     from `materials.usable_documents`, which decides whether a formula may be
+     submitted.
+  2. The write-once set protected the BYTES but not the OWNER, so an approved,
+     scan-clean label could be re-pointed at a different product and carry its
+     clean verdict there.
+  3. The product-bound composite foreign key on evidence needed a unique key
+     that did not exist, without which a label for product A could back a claim
+     about product B.
+
+All three were fixed in the migration. None was exercised by a test, so all
+three were claims rather than measurements. This project's standing lesson is
+that **a test which has only ever PASSED has not been shown to detect
+anything**, so every guard below is exercised in BOTH directions: the legal
+case must succeed and the illegal case must be refused, for the stated reason.
+
+⚠️ THE LEGAL CASES ARE NOT DECORATION. Without them a refusal proves only that
+something failed — a fixture that never produced a valid row would make every
+`pytest.raises` below pass while measuring nothing at all. That precise trap
+already caught this suite once: `test_054`'s first non-SDS refusal matched zero
+rows and reported a clean `INSERT 0 0` that looked exactly like a pass.
+"""
+
+from __future__ import annotations
+
+import uuid
+
+import pytest
+from sqlalchemy import text
+from sqlalchemy.exc import DBAPIError, IntegrityError
+from sqlalchemy.orm import Session
+
+pytestmark = pytest.mark.db
+
+
+# ---------------------------------------------------------------------------
+# Fixture — one organization, one material with an approved SDS, and two
+# competitor products, so "the other product" is a real row and not a UUID
+# that simply does not exist.
+# ---------------------------------------------------------------------------
+
+
+@pytest.fixture
+def competitor_fixture(owner_session: Session) -> dict[str, uuid.UUID]:
+    suffix = uuid.uuid4().hex[:8]
+
+    org_id = owner_session.execute(
+        text("INSERT INTO core.organizations (code, name) VALUES (:c, :n) RETURNING id"),
+        {"c": f"COMP-{suffix}", "n": "Competitor Test Org"},
+    ).scalar_one()
+
+    user_id = owner_session.execute(
+        text(
+            "INSERT INTO core.users (keycloak_sub, email, display_name) "
+            "VALUES (:s, :e, :n) RETURNING id"
+        ),
+        {"s": f"comp-{suffix}", "e": f"comp-{suffix}@example.test", "n": "Competitor Tester"},
+    ).scalar_one()
+    member_id = owner_session.execute(
+        text(
+            "INSERT INTO core.organization_members "
+            "(organization_id, user_id, status, email, display_name) "
+            "VALUES (:o, :u, 'active', :e, :n) RETURNING id"
+        ),
+        {
+            "o": org_id,
+            "u": user_id,
+            "e": f"comp-{suffix}@example.test",
+            "n": "Competitor Tester",
+        },
+    ).scalar_one()
+
+    material_id = owner_session.execute(
+        text(
+            """
+            INSERT INTO materials.materials
+                (organization_id, material_code, name, category, role, status, created_by)
+            VALUES (:o, :code, 'Test resin', 'Resin', 'resin', 'approved', :u)
+            RETURNING id
+            """
+        ),
+        {"o": org_id, "code": f"RM-{suffix}", "u": user_id},
+    ).scalar_one()
+
+    project_id = owner_session.execute(
+        text(
+            "INSERT INTO projects.projects (organization_id, project_code, name) "
+            "VALUES (:o, :c, 'Benchmark project') RETURNING id"
+        ),
+        {"o": org_id, "c": f"PRJ-{suffix}"},
+    ).scalar_one()
+
+    # FORCE RLS binds the table owner too, so even this session must declare
+    # its tenant. Without it the INSERTs below fail with "new row violates
+    # row-level security policy" -- the guard working, not a defect.
+    owner_session.execute(
+        text("SELECT set_config('app.current_org', :o, true)"), {"o": str(org_id)}
+    )
+    owner_session.execute(
+        text("SELECT set_config('app.current_user_id', :u, true)"), {"u": str(user_id)}
+    )
+
+    product_a = _make_product(owner_session, org_id, user_id, f"A-{suffix}")
+    product_b = _make_product(owner_session, org_id, user_id, f"B-{suffix}")
+
+    sds_id = _make_document(owner_session, org_id, user_id, suffix, "SDS", material_id=material_id)
+    label_a = _make_document(
+        owner_session, org_id, user_id, suffix, "label", competitor_product_id=product_a
+    )
+    owner_session.flush()
+
+    return {
+        "org_id": org_id,
+        "user_id": user_id,
+        "member_id": member_id,
+        "material_id": material_id,
+        "project_id": project_id,
+        "product_a": product_a,
+        "product_b": product_b,
+        "sds_id": sds_id,
+        "label_a": label_a,
+    }
+
+
+def _make_product(
+    session: Session, org_id: uuid.UUID, user_id: uuid.UUID, name: str
+) -> uuid.UUID:
+    return session.execute(  # type: ignore[no-any-return]
+        text(
+            "INSERT INTO competitors.products "
+            "(organization_id, manufacturer, product_name, registered_by) "
+            "VALUES (:o, 'Rival Chemicals', :n, :u) RETURNING id"
+        ),
+        {"o": org_id, "n": name, "u": user_id},
+    ).scalar_one()
+
+
+def _make_document(
+    session: Session,
+    org_id: uuid.UUID,
+    user_id: uuid.UUID,
+    suffix: str,
+    document_type: str,
+    *,
+    material_id: uuid.UUID | None = None,
+    competitor_product_id: uuid.UUID | None = None,
+    supersedes_id: uuid.UUID | None = None,
+) -> uuid.UUID:
+    """An APPROVED, scan-clean, unexpired document owned by exactly one thing.
+
+    Every column 036's `material_documents_approved_has_evidence` demands is
+    supplied, so the row genuinely appears in `materials.usable_documents`.
+    A quarantined fixture row would make the refusals pass for the wrong reason.
+    """
+    return session.execute(  # type: ignore[no-any-return]
+        text(
+            """
+            INSERT INTO materials.material_documents
+                (organization_id, material_id, competitor_product_id, document_type,
+                 title, storage_key, content_type, byte_size, checksum_sha256,
+                 status, scan_status, scanner_name, scanner_version, scanned_at,
+                 supersedes_id, uploaded_by)
+            VALUES (:o, :m, :cp, :dt, :title, :key, 'application/pdf', 2048,
+                    :checksum, 'approved', 'clean', 'test-scanner', '1.0', now(),
+                    :sup, :u)
+            RETURNING id
+            """
+        ),
+        {
+            "o": org_id,
+            "m": material_id,
+            "cp": competitor_product_id,
+            "dt": document_type,
+            "title": f"{document_type} for testing",
+            "key": f"test/{document_type}-{suffix}-{uuid.uuid4().hex[:6]}",
+            "checksum": uuid.uuid4().hex + uuid.uuid4().hex,
+            "sup": supersedes_id,
+            "u": user_id,
+        },
+    ).scalar_one()
+
+
+def _claim(session: Session, fx: dict[str, uuid.UUID], **overrides: object) -> uuid.UUID:
+    """A document-sourced claim on product A, which is the legal shape."""
+    params: dict[str, object] = {
+        "o": fx["org_id"],
+        "p": overrides.get("competitor_product_id", fx["product_a"]),
+        "d": overrides.get("source_document_id", fx["label_a"]),
+        "src": overrides.get("evidence_source", "document"),
+        "conf": overrides.get("confidence", "possible"),
+        "vby": overrides.get("verified_by"),
+        "vat": overrides.get("verified_at"),
+        "u": fx["user_id"],
+        "name": overrides.get("component_name", "Styrene"),
+    }
+    return session.execute(  # type: ignore[no-any-return]
+        text(
+            """
+            INSERT INTO competitors.composition_evidence
+                (organization_id, competitor_product_id, component_name,
+                 evidence_source, evidence_grade, confidence, source_document_id,
+                 source_locator, verified_by, verified_at, recorded_by)
+            VALUES (:o, :p, :name, :src, 'A', :conf, :d,
+                    'Section 3, ingredient table', :vby, CAST(:vat AS TIMESTAMPTZ), :u)
+            RETURNING id
+            """
+        ),
+        params,
+    ).scalar_one()
+
+
+def _grant_review_sds(session: Session, fx: dict[str, uuid.UUID]) -> None:
+    """Give the fixture's member a role actually carrying `compliance.review_sds`.
+
+    Built rather than looked up: a test that depended on a seeded role holding
+    the permission would silently stop exercising the trigger the day the seed
+    changed, and would report green.
+    """
+    # ⚠️ `core.roles` HAS NO `organization_id`. A role is a platform-level
+    # definition and the MEMBERSHIP is what binds it to a tenant -- which is
+    # also why the trigger joins through `core.organization_members` rather
+    # than looking for a tenant column on the role.
+    role_id = session.execute(
+        text("INSERT INTO core.roles (code, name) VALUES (:c, 'SDS Reviewer') RETURNING id"),
+        {"c": f"sds-reviewer-{uuid.uuid4().hex[:6]}"},
+    ).scalar_one()
+    permission_id = session.execute(
+        text("SELECT id FROM core.permissions WHERE code = 'compliance.review_sds'")
+    ).scalar_one()
+    session.execute(
+        text("INSERT INTO core.role_permissions (role_id, permission_id) VALUES (:r, :p)"),
+        {"r": role_id, "p": permission_id},
+    )
+    session.execute(
+        text("INSERT INTO core.member_roles (member_id, role_id) VALUES (:m, :r)"),
+        {"m": fx["member_id"], "r": role_id},
+    )
+    session.flush()
+
+
+# ---------------------------------------------------------------------------
+# HOLE 1 — supersession stays with one owner
+# ---------------------------------------------------------------------------
+
+
+def test_a_document_may_supersede_one_with_the_same_owner(
+    owner_session: Session, competitor_fixture
+) -> None:
+    """The legal case. Without it the refusal below proves only that something broke."""
+    fx = competitor_fixture
+    revision = _make_document(
+        owner_session,
+        fx["org_id"],
+        fx["user_id"],
+        "rev",
+        "label",
+        competitor_product_id=fx["product_a"],
+        supersedes_id=fx["label_a"],
+    )
+    assert revision is not None
+
+
+def test_a_competitor_label_cannot_supersede_a_materials_sds(
+    owner_session: Session, competitor_fixture
+) -> None:
+    """🔴 THE HOLE THAT REACHED THE FORMULA-SUBMISSION GATE.
+
+    `materials.usable_documents` excludes a document a newer approved revision
+    supersedes, and the formula-submission gate reads that view. So superseding
+    ACROSS owners would have let an upload against a competitor product remove a
+    material's SDS from the view -- changing whether a formula may be submitted,
+    on the strength of an unrelated file.
+    """
+    fx = competitor_fixture
+    with pytest.raises(DBAPIError) as caught:
+        _make_document(
+            owner_session,
+            fx["org_id"],
+            fx["user_id"],
+            "cross",
+            "label",
+            competitor_product_id=fx["product_a"],
+            supersedes_id=fx["sds_id"],  # a MATERIAL's document
+        )
+    assert "SAME owner" in str(caught.value)
+
+
+def test_the_superseded_sds_is_still_usable_after_the_refusal(
+    owner_session: Session, competitor_fixture
+) -> None:
+    """🔴 THE POINT OF THE GUARD, ASSERTED AS AN OUTCOME RATHER THAN A MESSAGE.
+
+    Checking only that an exception was raised would leave the actual claim --
+    that the SDS remains submittable -- unmeasured. This asserts the CONSEQUENCE.
+    """
+    fx = competitor_fixture
+    owner_session.execute(text("SAVEPOINT before_cross_owner"))
+    with pytest.raises(DBAPIError):
+        _make_document(
+            owner_session,
+            fx["org_id"],
+            fx["user_id"],
+            "cross2",
+            "label",
+            competitor_product_id=fx["product_a"],
+            supersedes_id=fx["sds_id"],
+        )
+    owner_session.execute(text("ROLLBACK TO SAVEPOINT before_cross_owner"))
+
+    still_usable = owner_session.execute(
+        text("SELECT count(*) FROM materials.usable_documents WHERE id = :d"),
+        {"d": fx["sds_id"]},
+    ).scalar_one()
+    assert still_usable == 1, "the SDS left usable_documents despite the refusal"
+
+
+# ---------------------------------------------------------------------------
+# HOLE 2 — the owner is write-once
+# ---------------------------------------------------------------------------
+
+
+def test_a_scanned_label_cannot_be_re_pointed_at_another_product(
+    owner_session: Session, competitor_fixture
+) -> None:
+    """An approved, scan-clean label must not carry its verdict to a different product."""
+    fx = competitor_fixture
+    with pytest.raises(DBAPIError) as caught:
+        owner_session.execute(
+            text(
+                "UPDATE materials.material_documents SET competitor_product_id = :b "
+                "WHERE id = :d"
+            ),
+            {"b": fx["product_b"], "d": fx["label_a"]},
+        )
+    assert "write-once" in str(caught.value)
+
+
+def test_a_document_cannot_be_re_owned_from_a_competitor_to_a_material(
+    owner_session: Session, competitor_fixture
+) -> None:
+    """The other half of the rule — and 🔴 A DIFFERENT TRIGGER ENFORCES IT.
+
+    MEASURED, not assumed. Triggers fire in NAME order, and
+    `material_documents_evidence_write_once` (038) sorts before
+    `material_documents_owner_write_once` (056). 038 already refuses a move to
+    another material, so on this path it fires first and 056's `material_id`
+    branch never executes — it is unreachable defence-in-depth.
+
+    056's `competitor_product_id` branch IS load-bearing: 038 checks material,
+    organization and document type only, so nothing but 056 stops a label being
+    re-pointed at another product. The preceding test is the one that measures
+    the new guard; this one measures that the OUTCOME holds either way.
+
+    Asserting the refusal message here would tie the test to whichever trigger
+    happens to sort first, so it asserts the consequence: the document still
+    belongs to the product it was uploaded for.
+    """
+    fx = competitor_fixture
+    # A SAVEPOINT, not a rollback: rolling the whole transaction back would
+    # discard the fixture too, and the row would then be absent rather than
+    # unchanged -- an assertion that passes for the wrong reason.
+    owner_session.execute(text("SAVEPOINT before_reown"))
+    with pytest.raises(DBAPIError):
+        owner_session.execute(
+            text(
+                "UPDATE materials.material_documents "
+                "SET material_id = :m, competitor_product_id = NULL WHERE id = :d"
+            ),
+            {"m": fx["material_id"], "d": fx["label_a"]},
+        )
+    owner_session.execute(text("ROLLBACK TO SAVEPOINT before_reown"))
+    owner = owner_session.execute(
+        text("SELECT competitor_product_id FROM materials.material_documents WHERE id = :d"),
+        {"d": fx["label_a"]},
+    ).scalar_one_or_none()
+    assert owner == fx["product_a"], "the label changed owner despite the refusal"
+
+
+def test_a_harmless_update_to_the_same_document_still_succeeds(
+    owner_session: Session, competitor_fixture
+) -> None:
+    """🔴 A GUARD THAT REFUSES EVERYTHING IS NOT A GUARD, IT IS AN OUTAGE.
+
+    The trigger fires `BEFORE UPDATE` on every column, so this asserts it lets
+    an unrelated edit through rather than blocking all writes to the table.
+    """
+    fx = competitor_fixture
+    owner_session.execute(
+        text("UPDATE materials.material_documents SET title = :t WHERE id = :d"),
+        {"t": "Label, 1L tin, 2026 packaging", "d": fx["label_a"]},
+    )
+    title = owner_session.execute(
+        text("SELECT title FROM materials.material_documents WHERE id = :d"),
+        {"d": fx["label_a"]},
+    ).scalar_one()
+    assert title == "Label, 1L tin, 2026 packaging"
+
+
+# ---------------------------------------------------------------------------
+# HOLE 3 — a document backs a claim only about ITS OWN product  (T2b)
+# ---------------------------------------------------------------------------
+
+
+def test_a_document_can_back_a_claim_about_its_own_product(
+    owner_session: Session, competitor_fixture
+) -> None:
+    """The legal case for the composite foreign key."""
+    fx = competitor_fixture
+    assert _claim(owner_session, fx) is not None
+
+
+def test_a_label_for_product_a_cannot_back_a_claim_about_product_b(
+    owner_session: Session, competitor_fixture
+) -> None:
+    """🔴 T2b. The composite FK is the mechanism; every other constraint holds."""
+    fx = competitor_fixture
+    with pytest.raises(IntegrityError) as caught:
+        _claim(owner_session, fx, competitor_product_id=fx["product_b"])
+    assert "composition_evidence_document_fk" in str(caught.value)
+
+
+def test_the_unique_key_the_composite_foreign_key_needs_exists(
+    owner_session: Session, competitor_fixture
+) -> None:
+    """🔴 ASSERT THE THING EXISTS BEFORE TRUSTING A PROPERTY OF IT.
+
+    The FK above is only expressible because 056 added
+    `material_documents_id_competitor_org_key`. Reading it from `pg_constraint`
+    rather than from the migration text: the file existing is not the schema.
+    """
+    kind = owner_session.execute(
+        text(
+            "SELECT contype FROM pg_constraint "
+            "WHERE conname = 'material_documents_id_competitor_org_key'"
+        )
+    ).scalar_one_or_none()
+    assert kind == "u", "the unique key the evidence FK depends on is missing"
+
+
+# ---------------------------------------------------------------------------
+# T2a / T2c — `verified` is not something a writer may assert about itself
+# ---------------------------------------------------------------------------
+
+
+def test_verified_requires_both_a_verifier_and_a_time(
+    owner_session: Session, competitor_fixture
+) -> None:
+    """T2c. `verified_by` alone is not verification, and neither is a bare flag.
+
+    🔴 THE PERMISSION MUST BE GRANTED FIRST TO REACH THE CONSTRAINT AT ALL.
+    A `BEFORE INSERT` trigger runs before row constraints are evaluated, so
+    without the grant this refusal comes from `verification_names_a_reviewer`
+    and the CHECK is never exercised — the test would pass while measuring a
+    different mechanism entirely.
+    """
+    fx = competitor_fixture
+    _grant_review_sds(owner_session, fx)
+    with pytest.raises(IntegrityError) as caught:
+        _claim(owner_session, fx, confidence="verified", verified_by=fx["user_id"])
+    assert "composition_evidence_verification_complete" in str(caught.value)
+
+
+def test_a_verifier_and_a_time_without_verified_is_also_refused(
+    owner_session: Session, competitor_fixture
+) -> None:
+    """🔴 BOTH DIRECTIONS. The constraint is an equivalence, not an implication.
+
+    A row carrying a verifier and a timestamp while claiming `possible` would
+    read, to anybody scanning the table, as a verified claim that had been
+    quietly downgraded.
+    """
+    fx = competitor_fixture
+    with pytest.raises(IntegrityError) as caught:
+        _claim(
+            owner_session,
+            fx,
+            confidence="possible",
+            verified_by=fx["user_id"],
+            verified_at="2026-08-28T00:00:00Z",
+        )
+    assert "composition_evidence_verification_complete" in str(caught.value)
+
+
+def test_an_observation_can_never_be_verified(
+    owner_session: Session, competitor_fixture
+) -> None:
+    """T2a. There is nothing anybody else can re-check, so the grade is unearnable.
+
+    A person reading the back of a tin is making an honest observation. What
+    they cannot do is certify it, and the database — not the screen — is what
+    says so.
+    """
+    fx = competitor_fixture
+    _grant_review_sds(owner_session, fx)
+    with pytest.raises(IntegrityError) as caught:
+        owner_session.execute(
+            text(
+                """
+                INSERT INTO competitors.composition_evidence
+                    (organization_id, competitor_product_id, component_name,
+                     evidence_source, evidence_grade, confidence, rationale,
+                     observed_by, verified_by, verified_at, recorded_by)
+                VALUES (:o, :p, 'Talc', 'manual_observation', 'C', 'verified',
+                        'Read from the back of the tin', :u, :u, now(), :u)
+                """
+            ),
+            {"o": fx["org_id"], "p": fx["product_a"], "u": fx["user_id"]},
+        )
+    assert "composition_evidence_verifiable_source" in str(caught.value)
+
+
+def test_the_named_verifier_must_actually_hold_the_permission(
+    owner_session: Session, competitor_fixture
+) -> None:
+    """🔴 THE TRIGGER, AND IT IS A MISUSE BARRIER RATHER THAN A BOUNDARY.
+
+    Anybody who can already run SQL as this role can grant themselves the role
+    first. What it stops is a verified claim naming somebody who never held
+    `compliance.review_sds` — which is the shape a mistake takes, and the shape
+    an audit reads.
+    """
+    fx = competitor_fixture
+    with pytest.raises(DBAPIError) as caught:
+        _claim(
+            owner_session,
+            fx,
+            confidence="verified",
+            verified_by=fx["user_id"],
+            verified_at="2026-08-28T00:00:00Z",
+        )
+    assert "compliance.review_sds" in str(caught.value)
+
+
+def test_a_holder_of_review_sds_can_verify(
+    owner_session: Session, competitor_fixture
+) -> None:
+    """🔴 FALSIFIES THE TRIGGER THE OTHER WAY.
+
+    Without this the refusal above would also pass if the trigger refused
+    EVERYONE — a guard that cannot succeed proves nothing about who may.
+    """
+    fx = competitor_fixture
+    _grant_review_sds(owner_session, fx)
+    claim_id = _claim(
+        owner_session,
+        fx,
+        confidence="verified",
+        verified_by=fx["user_id"],
+        verified_at="2026-08-28T00:00:00Z",
+    )
+    assert claim_id is not None
+
+
+# ---------------------------------------------------------------------------
+# T3a / T8 — reach, counted as what a user can reach
+# ---------------------------------------------------------------------------
+
+
+def test_every_competitor_table_forces_row_level_security(owner_session: Session) -> None:
+    """T8. FORCE from birth: the policies bind the table OWNER too.
+
+    Read from `pg_class`, not from the migration text — the database in front
+    of you is not the schema, and a migration is not applied because a file
+    exists.
+    """
+    rows = owner_session.execute(
+        text(
+            "SELECT c.relname, c.relrowsecurity, c.relforcerowsecurity "
+            "  FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace "
+            " WHERE n.nspname = 'competitors' AND c.relkind = 'r' ORDER BY c.relname"
+        )
+    ).all()
+    assert len(rows) == 4, f"expected four competitor tables, found {len(rows)}"
+    unforced = [r[0] for r in rows if not (r[1] and r[2])]
+    assert not unforced, f"these competitor tables are not FORCE RLS: {unforced}"
+
+
+def test_another_organization_reaches_none_of_it(
+    owner_session: Session, app_session: Session, competitor_fixture
+) -> None:
+    """🔴 T3a — COUNTED AS WHAT A USER CAN REACH, NOT BY READING A POLICY.
+
+    A policy can be present and still not apply. This asks the runtime role,
+    under a different tenant, how many rows it can actually see.
+    """
+    fx = competitor_fixture
+    owner_session.commit()
+
+    other_org = uuid.uuid4()
+    app_session.execute(
+        text("SELECT set_config('app.current_org', :o, true)"), {"o": str(other_org)}
+    )
+
+    for table in (
+        "competitors.products",
+        "competitors.samples",
+        "competitors.composition_evidence",
+        "competitors.benchmarks",
+    ):
+        reachable = app_session.execute(
+            text(f"SELECT count(*) FROM {table} WHERE organization_id = :o"),
+            {"o": fx["org_id"]},
+        ).scalar_one()
+        assert reachable == 0, f"another organization reached {reachable} rows of {table}"
+
+
+def test_the_owning_organization_does_reach_its_own_product(
+    owner_session: Session, app_session: Session, competitor_fixture
+) -> None:
+    """🔴 THE OTHER DIRECTION OF T3a.
+
+    Without it, the zeros above would also be produced by a policy that hides
+    the table from everybody — or by a fixture that never committed a row.
+    """
+    fx = competitor_fixture
+    owner_session.commit()
+
+    app_session.execute(
+        text("SELECT set_config('app.current_org', :o, true)"), {"o": str(fx["org_id"])}
+    )
+    app_session.execute(
+        text("SELECT set_config('app.current_user_id', :u, true)"), {"u": str(fx["user_id"])}
+    )
+    reachable = app_session.execute(
+        text("SELECT count(*) FROM competitors.products WHERE organization_id = :o"),
+        {"o": fx["org_id"]},
+    ).scalar_one()
+    assert reachable == 2, f"the owning organization reached {reachable} of its 2 products"
+
+
+# ---------------------------------------------------------------------------
+# The register was EXTENDED, not forked — §14
+# ---------------------------------------------------------------------------
+
+
+def test_there_is_no_second_document_table(owner_session: Session) -> None:
+    """§14: *"do not build a second document repository"*, asserted rather than intended."""
+    forked = owner_session.execute(
+        text(
+            "SELECT count(*) FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace "
+            " WHERE n.nspname = 'competitors' AND c.relkind = 'r' "
+            "   AND c.relname LIKE '%document%'"
+        )
+    ).scalar_one()
+    assert forked == 0, "a second document repository exists in the competitors schema"
+
+
+def test_usable_documents_kept_security_invoker(owner_session: Session) -> None:
+    """⚠️ 056 RECREATED THE VIEW THE FORMULA-SUBMISSION GATE READS.
+
+    `security_invoker = true` is what makes the view honour the CALLER's RLS.
+    Recreating a view silently drops its options, and the loss would be
+    invisible: every query would keep working, and would return more rows.
+    """
+    options = owner_session.execute(
+        text(
+            "SELECT c.reloptions FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace "
+            " WHERE n.nspname = 'materials' AND c.relname = 'usable_documents'"
+        )
+    ).scalar_one()
+    assert options is not None and any(
+        "security_invoker=true" in str(opt) for opt in options
+    ), f"usable_documents lost security_invoker; reloptions = {options}"
diff --git a/apps/web/app/material-safety/competitors/page.tsx b/apps/web/app/material-safety/competitors/page.tsx
new file mode 100644
index 0000000..c548150
--- /dev/null
+++ b/apps/web/app/material-safety/competitors/page.tsx
@@ -0,0 +1,932 @@
+"use client";
+
+/**
+ * Competitor intelligence — register a product, upload its label or a
+ * photograph, and build the Composition Evidence Matrix from them.
+ *
+ * 🔴 THIS SCREEN NEVER SHOWS A COMPETITOR RECIPE.
+ *
+ * The specification is explicit that the application *"shall NEVER
+ * automatically present an inferred competitor recipe as a known or verified
+ * formula"*. What it shows is a matrix of CLAIMS, strongest first, each
+ * carrying how it is known and how far it can be trusted — and the server's
+ * own disclaimer rendered verbatim above it. Reading the matrix gives a
+ * candidate composition, which is what was asked for; no line of it pretends
+ * to be more than it is.
+ *
+ * 🔴 THREE ENTRY MODES, AS PEERS.
+ *
+ *   1. Upload the LABEL.
+ *   2. Upload a PHOTOGRAPH of the product.
+ *   3. Type what you read, with no document at all.
+ *
+ * All three land in the same matrix. The third is `manual_observation` — not
+ * `inference`, because a person reading a tin is observing, not reasoning.
+ * What it cannot be is `verified`, since there is nothing anybody else can
+ * re-check, and the database refuses that combination outright.
+ *
+ * ⚠️ UPLOADING DOES NOT FILL THE MATRIX IN. There is no automatic extraction:
+ * that was a deliberate choice on 2026-08-28 (no OCR dependency, and neither
+ * installed Ollama model reads images). The file is stored as evidence a claim
+ * can CITE, and a person records what it says. A screen that implied otherwise
+ * would be inventing components on somebody's product.
+ */
+
+import { useState } from "react";
+
+import { DataSourceError, LiveOnlyPage } from "@/components/ui/data-source-banner";
+import { serverMessage } from "@/lib/api/client";
+import {
+  useCompetitorBenchmarks,
+  useCompetitorDocuments,
+  useCompetitorProducts,
+  useCompetitorSamples,
+  useCompetitorWrites,
+  useCompositionMatrix,
+  useProjects,
+} from "@/lib/api/hooks";
+import type { Project } from "@/lib/api/projects";
+import {
+  EVIDENCE_GRADES,
+  EVIDENCE_SOURCES,
+  type CompetitorProduct,
+  type EvidenceRow,
+} from "@/lib/api/competitors";
+
+const BUTTON =
+  "rounded bg-slate-900 px-3 py-1.5 text-sm font-medium text-white hover:bg-slate-700 " +
+  "disabled:cursor-not-allowed disabled:bg-slate-300";
+const SECONDARY =
+  "rounded border border-slate-300 px-3 py-1.5 text-sm font-medium text-slate-800 " +
+  "hover:bg-slate-100 disabled:cursor-not-allowed disabled:text-slate-400";
+const INPUT =
+  "mt-1 w-full rounded border border-slate-300 px-2 py-1.5 text-sm text-slate-900 " +
+  "focus:border-slate-500 focus:outline-none focus:ring-1 focus:ring-slate-500";
+const LABEL = "block text-xs font-medium text-slate-700";
+
+/**
+ * Confidence, as colour AND icon AND word.
+ *
+ * CLAUDE.md §11 forbids colour-only status, and here it matters more than
+ * usual: the difference between a verified disclosure and a model's guess is
+ * the entire point of the matrix, and a reader who cannot see colour must get
+ * the same answer.
+ */
+const CONFIDENCE: Record<
+  EvidenceRow["confidence"],
+  { icon: string; label: string; className: string }
+> = {
+  verified: {
+    icon: "✓",
+    label: "Verified",
+    className: "border-emerald-300 bg-emerald-50 text-emerald-900",
+  },
+  supported: {
+    icon: "+",
+    label: "Supported",
+    className: "border-sky-300 bg-sky-50 text-sky-900",
+  },
+  probable: {
+    icon: "~",
+    label: "Probable",
+    className: "border-amber-300 bg-amber-50 text-amber-900",
+  },
+  possible: {
+    icon: "?",
+    label: "Possible",
+    className: "border-slate-300 bg-slate-50 text-slate-800",
+  },
+  unknown: {
+    icon: "·",
+    label: "Unknown",
+    className: "border-slate-300 bg-white text-slate-600",
+  },
+};
+
+function concentration(row: EvidenceRow): string {
+  if (row.is_balance) return "the balance";
+  const { concentration_low: low, concentration_high: high } = row;
+  if (low === null && high === null) return "not disclosed";
+  if (low !== null && high !== null) return low === high ? `${low}%` : `${low}–${high}%`;
+  return `${low ?? high}%`;
+}
+
+function MatrixRow({ row }: { row: EvidenceRow }) {
+  const confidence = CONFIDENCE[row.confidence];
+  const source = EVIDENCE_SOURCES.find((s) => s.id === row.evidence_source);
+  return (
+    <li className="rounded border border-slate-200 bg-white p-3">
+      <div className="flex flex-wrap items-baseline gap-2">
+        <span
+          className={`rounded border px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide ${confidence.className}`}
+        >
+          <span aria-hidden="true">{confidence.icon}</span> {confidence.label}
+        </span>
+        <h3 className="flex-1 text-sm font-semibold text-slate-900">{row.component_name}</h3>
+        <span className="text-sm tabular-nums text-slate-800">{concentration(row)}</span>
+      </div>
+      <p className="mt-1 text-xs text-slate-600">
+        {source?.label ?? row.evidence_source} · grade {row.evidence_grade}
+        {row.cas_number !== null ? ` · CAS ${row.cas_number}` : ""}
+        {row.component_function !== null ? ` · ${row.component_function}` : ""}
+      </p>
+      {row.source_document_title !== null && (
+        <p className="mt-1 text-xs text-slate-600">
+          From {row.source_document_type}: {row.source_document_title}
+          {row.source_locator !== null ? ` (${row.source_locator})` : ""}
+        </p>
+      )}
+      {row.rationale !== null && (
+        <p className="mt-1 text-xs text-slate-700">{row.rationale}</p>
+      )}
+    </li>
+  );
+}
+
+function ProductWorkspace({ product }: { product: CompetitorProduct }) {
+  const matrix = useCompositionMatrix(product.id);
+  const documents = useCompetitorDocuments(product.id);
+  const samples = useCompetitorSamples(product.id);
+  const benchmarks = useCompetitorBenchmarks(product.id);
+  // 🔴 A BENCHMARK NEEDS A PROJECT, AND ASKING FOR A UUID IS NOT ASKING.
+  // The register-a-member form on Projects still demands one typed by hand
+  // and it is a standing complaint; this form does not repeat it.
+  const projectList = useProjects<Project[]>([], (live) => live);
+  const writes = useCompetitorWrites();
+
+  const [file, setFile] = useState<File | null>(null);
+  const [documentType, setDocumentType] = useState("label");
+  const [docTitle, setDocTitle] = useState("");
+
+  const [component, setComponent] = useState("");
+  const [cas, setCas] = useState("");
+  const [low, setLow] = useState("");
+  const [high, setHigh] = useState("");
+  const [evidenceSource, setEvidenceSource] = useState("manual_observation");
+  const [grade, setGrade] = useState("C");
+  const [sourceDocumentId, setSourceDocumentId] = useState("");
+  const [sampleId, setSampleId] = useState("");
+  const [locator, setLocator] = useState("");
+  const [rationale, setRationale] = useState("");
+
+  const [sampleReference, setSampleReference] = useState("");
+  const [acquiredOn, setAcquiredOn] = useState("");
+  const [batchMarking, setBatchMarking] = useState("");
+  const [sampleNotes, setSampleNotes] = useState("");
+
+  const [benchProject, setBenchProject] = useState("");
+  const [benchAttribute, setBenchAttribute] = useState("");
+  const [benchTheirs, setBenchTheirs] = useState("");
+  const [benchOurs, setBenchOurs] = useState("");
+  const [benchGap, setBenchGap] = useState("");
+
+  const needsDocument = evidenceSource === "document";
+  // An observation was made ON something. Until this screen could name the
+  // tin, every `manual_observation` was recorded with a null `sample_id`
+  // that the server had always accepted and no client had ever sent.
+  const isObservation = evidenceSource === "manual_observation";
+  const docs = documents.data ?? [];
+  const tins = samples.data ?? [];
+  const comparisons = benchmarks.data ?? [];
+  const projects = projectList.data ?? [];
+
+  return (
+    <div className="grid gap-6">
+      <section aria-labelledby="upload-heading">
+        <h3 id="upload-heading" className="text-sm font-semibold text-slate-900">
+          Upload a label or a photograph
+        </h3>
+        <p className="mt-1 text-xs text-slate-600">
+          Stored through the same controlled document register a Safety Data Sheet
+          goes through: validated against its real bytes, malware-scanned,
+          checksummed. It is kept as evidence a claim can <em>cite</em> — it does
+          not fill the matrix in by itself.
+        </p>
+        <div className="mt-3 grid gap-3 rounded border border-slate-200 bg-white p-4 sm:grid-cols-2">
+          <div>
+            <label className={LABEL} htmlFor="doc-kind">
+              What is it
+            </label>
+            <select
+              id="doc-kind"
+              className={INPUT}
+              value={documentType}
+              onChange={(event) => setDocumentType(event.target.value)}
+            >
+              <option value="label">The product label</option>
+              <option value="product_image">A photograph of the product</option>
+              <option value="SDS">Their published Safety Data Sheet</option>
+              <option value="TDS">Their technical data sheet</option>
+              <option value="literature">Product literature</option>
+              <option value="patent">A patent</option>
+            </select>
+          </div>
+          <div>
+            <label className={LABEL} htmlFor="doc-title">
+              Title
+            </label>
+            <input
+              id="doc-title"
+              className={INPUT}
+              value={docTitle}
+              onChange={(event) => setDocTitle(event.target.value)}
+              placeholder="Label, 1L tin, 2026 packaging"
+            />
+          </div>
+          <div className="sm:col-span-2">
+            <label className={LABEL} htmlFor="doc-file">
+              The file
+            </label>
+            <input
+              id="doc-file"
+              type="file"
+              className={`${INPUT} file:mr-3 file:rounded file:border-0 file:bg-slate-100 file:px-3 file:py-1 file:text-sm`}
+              onChange={(event) => setFile(event.target.files?.[0] ?? null)}
+            />
+          </div>
+          <div className="sm:col-span-2">
+            <button
+              type="button"
+              className={BUTTON}
+              disabled={writes.isPending || file === null || docTitle.trim() === ""}
+              onClick={() => {
+                if (file === null) return;
+                writes.upload(product.id, file, documentType, docTitle.trim(), () => {
+                  setFile(null);
+                  setDocTitle("");
+                });
+              }}
+            >
+              Upload
+            </button>
+          </div>
+        </div>
+
+        {docs.length > 0 && (
+          <ul className="mt-3 grid gap-2">
+            {docs.map((doc) => (
+              <li key={doc.id} className="text-xs text-slate-700">
+                <span className="rounded border border-slate-300 px-1.5 py-0.5 text-[10px] uppercase tracking-wide text-slate-600">
+                  {doc.document_type}
+                </span>{" "}
+                {doc.title}
+              </li>
+            ))}
+          </ul>
+        )}
+      </section>
+
+      <section aria-labelledby="samples-heading">
+        <h3 id="samples-heading" className="text-sm font-semibold text-slate-900">
+          Physical samples held
+        </h3>
+        <p className="mt-1 text-xs text-slate-600">
+          The tins we actually have. Registering one is what lets an observation
+          say <em>which</em> tin it was read from — a claim that cannot name its
+          source cannot be re-checked by anybody else.
+        </p>
+        <div className="mt-3 grid gap-3 rounded border border-slate-200 bg-white p-4 sm:grid-cols-2">
+          <div>
+            <label className={LABEL} htmlFor="sample-ref">
+              Reference
+            </label>
+            <input
+              id="sample-ref"
+              className={INPUT}
+              value={sampleReference}
+              onChange={(event) => setSampleReference(event.target.value)}
+              placeholder="COMP-2026-014"
+            />
+          </div>
+          <div>
+            <label className={LABEL} htmlFor="sample-acquired">
+              Acquired on
+            </label>
+            <input
+              id="sample-acquired"
+              type="date"
+              className={INPUT}
+              value={acquiredOn}
+              onChange={(event) => setAcquiredOn(event.target.value)}
+            />
+          </div>
+          <div>
+            <label className={LABEL} htmlFor="sample-batch">
+              Batch or lot marking
+            </label>
+            <input
+              id="sample-batch"
+              className={INPUT}
+              value={batchMarking}
+              onChange={(event) => setBatchMarking(event.target.value)}
+              placeholder="As printed on the tin"
+            />
+          </div>
+          <div>
+            <label className={LABEL} htmlFor="sample-notes">
+              Condition and provenance
+            </label>
+            <input
+              id="sample-notes"
+              className={INPUT}
+              value={sampleNotes}
+              onChange={(event) => setSampleNotes(event.target.value)}
+              placeholder="Sealed, bought at retail"
+            />
+          </div>
+          <div className="sm:col-span-2">
+            <button
+              type="button"
+              className={BUTTON}
+              disabled={writes.isPending || sampleReference.trim() === ""}
+              onClick={() =>
+                writes.registerSample(
+                  product.id,
+                  {
+                    sample_reference: sampleReference.trim(),
+                    ...(acquiredOn ? { acquired_on: acquiredOn } : {}),
+                    ...(batchMarking.trim() ? { batch_marking: batchMarking.trim() } : {}),
+                    ...(sampleNotes.trim() ? { observations: sampleNotes.trim() } : {}),
+                  },
+                  () => {
+                    setSampleReference("");
+                    setAcquiredOn("");
+                    setBatchMarking("");
+                    setSampleNotes("");
+                  },
+                )
+              }
+            >
+              Register the sample
+            </button>
+          </div>
+        </div>
+
+        {samples.error !== null ? (
+          <DataSourceError error={samples.error} />
+        ) : tins.length === 0 ? (
+          <p className="mt-3 text-sm text-slate-600">
+            No samples registered. An observation recorded now cannot name what
+            it was read from.
+          </p>
+        ) : (
+          <ul className="mt-3 grid gap-2">
+            {tins.map((tin) => (
+              <li
+                key={tin.id}
+                className="rounded border border-slate-200 bg-white px-3 py-2 text-xs text-slate-700"
+              >
+                <span className="font-medium text-slate-900">{tin.sample_reference}</span>
+                {tin.acquired_on !== null && <> · acquired {tin.acquired_on}</>}
+                {tin.batch_marking !== null && <> · batch {tin.batch_marking}</>}{" "}
+                · {tin.evidence_count} claim{tin.evidence_count === 1 ? "" : "s"} cite
+                {tin.evidence_count === 1 ? "s" : ""} it
+                {tin.observations !== null && (
+                  <span className="mt-1 block text-slate-600">{tin.observations}</span>
+                )}
+              </li>
+            ))}
+          </ul>
+        )}
+      </section>
+
+      <section aria-labelledby="claim-heading">
+        <h3 id="claim-heading" className="text-sm font-semibold text-slate-900">
+          Record what it contains
+        </h3>
+        <p className="mt-1 text-xs text-slate-600">
+          Every claim is recorded as <strong>possible</strong>. Only a reviewer
+          holding <code className="text-[11px]">compliance.review_sds</code> can
+          raise one to verified, and only when it cites a document or a
+          laboratory result.
+        </p>
+        <div className="mt-3 grid gap-3 rounded border border-slate-200 bg-white p-4 sm:grid-cols-2">
+          <div>
+            <label className={LABEL} htmlFor="ev-component">
+              Component
+            </label>
+            <input
+              id="ev-component"
+              className={INPUT}
+              value={component}
+              onChange={(event) => setComponent(event.target.value)}
+              placeholder="Styrene"
+            />
+          </div>
+          <div>
+            <label className={LABEL} htmlFor="ev-cas">
+              CAS number
+            </label>
+            <input
+              id="ev-cas"
+              className={INPUT}
+              value={cas}
+              onChange={(event) => setCas(event.target.value)}
+              placeholder="100-42-5"
+            />
+          </div>
+          <div>
+            <label className={LABEL} htmlFor="ev-low">
+              From (%)
+            </label>
+            {/* Text, not number: a float would round the disclosed range. */}
+            <input
+              id="ev-low"
+              className={INPUT}
+              inputMode="decimal"
+              value={low}
+              onChange={(event) => setLow(event.target.value)}
+            />
+          </div>
+          <div>
+            <label className={LABEL} htmlFor="ev-high">
+              To (%)
+            </label>
+            <input
+              id="ev-high"
+              className={INPUT}
+              inputMode="decimal"
+              value={high}
+              onChange={(event) => setHigh(event.target.value)}
+            />
+          </div>
+          <div>
+            <label className={LABEL} htmlFor="ev-source">
+              How is this known
+            </label>
+            <select
+              id="ev-source"
+              className={INPUT}
+              value={evidenceSource}
+              onChange={(event) => setEvidenceSource(event.target.value)}
+            >
+              {EVIDENCE_SOURCES.map((source) => (
+                <option key={source.id} value={source.id}>
+                  {source.label}
+                </option>
+              ))}
+            </select>
+          </div>
+          <div>
+            <label className={LABEL} htmlFor="ev-grade">
+              Evidence grade
+            </label>
+            <select
+              id="ev-grade"
+              className={INPUT}
+              value={grade}
+              onChange={(event) => setGrade(event.target.value)}
+            >
+              {EVIDENCE_GRADES.map((g) => (
+                <option key={g.id} value={g.id}>
+                  {g.label}
+                </option>
+              ))}
+            </select>
+          </div>
+
+          {needsDocument && (
+            <div className="sm:col-span-2">
+              <label className={LABEL} htmlFor="ev-doc">
+                Which document
+              </label>
+              <select
+                id="ev-doc"
+                className={INPUT}
+                value={sourceDocumentId}
+                onChange={(event) => setSourceDocumentId(event.target.value)}
+              >
+                <option value="">Choose one of the uploads above…</option>
+                {docs.map((doc) => (
+                  <option key={doc.id} value={doc.id}>
+                    {doc.document_type} — {doc.title}
+                  </option>
+                ))}
+              </select>
+              {docs.length === 0 && (
+                <p className="mt-1 text-xs text-slate-600">
+                  Nothing is uploaded yet, so no claim can cite a document.
+                </p>
+              )}
+            </div>
+          )}
+
+          {isObservation && (
+            <div className="sm:col-span-2">
+              <label className={LABEL} htmlFor="ev-sample">
+                Which sample did you read
+              </label>
+              <select
+                id="ev-sample"
+                className={INPUT}
+                value={sampleId}
+                onChange={(event) => setSampleId(event.target.value)}
+              >
+                <option value="">
+                  {tins.length === 0
+                    ? "No samples registered yet"
+                    : "Not recorded against a sample"}
+                </option>
+                {tins.map((tin) => (
+                  <option key={tin.id} value={tin.id}>
+                    {tin.sample_reference}
+                    {tin.batch_marking !== null ? ` — batch ${tin.batch_marking}` : ""}
+                  </option>
+                ))}
+              </select>
+            </div>
+          )}
+          <div className="sm:col-span-2">
+            <label className={LABEL} htmlFor="ev-locator">
+              Where exactly {needsDocument ? "in the document" : "on the product"}
+            </label>
+            <input
+              id="ev-locator"
+              className={INPUT}
+              value={locator}
+              onChange={(event) => setLocator(event.target.value)}
+              placeholder="Section 3, ingredient table / back of tin, small print"
+            />
+          </div>
+          <div className="sm:col-span-2">
+            <label className={LABEL} htmlFor="ev-rationale">
+              What you saw, or what you reasoned from
+            </label>
+            <textarea
+              id="ev-rationale"
+              className={INPUT}
+              rows={2}
+              value={rationale}
+              onChange={(event) => setRationale(event.target.value)}
+            />
+          </div>
+
+          <div className="sm:col-span-2">
+            <button
+              type="button"
+              className={BUTTON}
+              disabled={
+                writes.isPending ||
+                component.trim() === "" ||
+                (needsDocument && sourceDocumentId === "") ||
+                /* An observation or an inference must say what it rests on --
+                   the database refuses it otherwise, so the form should too
+                   rather than sending a request that cannot succeed. */
+                (["manual_observation", "inference", "model"].includes(evidenceSource) &&
+                  rationale.trim() === "")
+              }
+              onClick={() =>
+                writes.recordEvidence(
+                  product.id,
+                  {
+                    component_name: component.trim(),
+                    evidence_source: evidenceSource,
+                    evidence_grade: grade,
+                    ...(cas.trim() ? { cas_number: cas.trim() } : {}),
+                    ...(low.trim() ? { concentration_low: low.trim() } : {}),
+                    ...(high.trim() ? { concentration_high: high.trim() } : {}),
+                    ...(needsDocument ? { source_document_id: sourceDocumentId } : {}),
+                    ...(isObservation && sampleId !== "" ? { sample_id: sampleId } : {}),
+                    ...(locator.trim() ? { source_locator: locator.trim() } : {}),
+                    ...(rationale.trim() ? { rationale: rationale.trim() } : {}),
+                  },
+                  () => {
+                    setComponent("");
+                    setSampleId("");
+                    setCas("");
+                    setLow("");
+                    setHigh("");
+                    setLocator("");
+                    setRationale("");
+                  },
+                )
+              }
+            >
+              Add to the evidence matrix
+            </button>
+          </div>
+        </div>
+      </section>
+
+      <section aria-labelledby="matrix-heading">
+        <h3 id="matrix-heading" className="text-sm font-semibold text-slate-900">
+          Composition Evidence Matrix
+        </h3>
+        {matrix.error !== null ? (
+          <DataSourceError error={matrix.error} />
+        ) : matrix.data === undefined ? (
+          <p className="mt-2 text-sm text-slate-600">
+            {matrix.isLoading ? "Loading the matrix…" : ""}
+          </p>
+        ) : (
+          <>
+            {/* 🔴 THE SERVER'S OWN WORDS, RENDERED VERBATIM. Not a sentence
+                this screen composes: a screen that forgot it would be
+                presenting an inferred recipe as a known one. */}
+            <p className="mt-2 rounded border border-amber-300 bg-amber-50 px-3 py-2 text-xs text-amber-900">
+              {matrix.data.disclaimer}
+            </p>
+
+            {Object.keys(matrix.data.summary).length > 0 && (
+              <p className="mt-2 text-xs text-slate-700">
+                {Object.entries(matrix.data.summary)
+                  .map(([key, count]) => `${count} ${key}`)
+                  .join(" · ")}
+              </p>
+            )}
+
+            {matrix.data.rows.length === 0 ? (
+              <p className="mt-3 text-sm text-slate-600">
+                Nothing recorded yet. Upload a label or type what you can read,
+                above.
+              </p>
+            ) : (
+              <ul className="mt-3 grid gap-2">
+                {matrix.data.rows.map((row) => (
+                  <MatrixRow key={row.id} row={row} />
+                ))}
+              </ul>
+            )}
+          </>
+        )}
+      </section>
+
+      <section aria-labelledby="benchmark-heading">
+        <h3 id="benchmark-heading" className="text-sm font-semibold text-slate-900">
+          Measured comparisons
+        </h3>
+        <p className="mt-1 text-xs text-slate-600">
+          How our work compares on one attribute. ⚠️ The gap is stated in
+          words and no verdict colour is shown: Testing owns GREEN, YELLOW and
+          RED, and a second disposition invented here would drift from it.
+        </p>
+        <div className="mt-3 grid gap-3 rounded border border-slate-200 bg-white p-4 sm:grid-cols-2">
+          <div>
+            <label className={LABEL} htmlFor="bm-project">
+              Project
+            </label>
+            <select
+              id="bm-project"
+              className={INPUT}
+              value={benchProject}
+              onChange={(event) => setBenchProject(event.target.value)}
+            >
+              <option value="">Choose the project</option>
+              {projects.map((item) => (
+                <option key={item.id} value={item.id}>
+                  {item.project_code} — {item.name}
+                </option>
+              ))}
+            </select>
+          </div>
+          <div>
+            <label className={LABEL} htmlFor="bm-attribute">
+              Attribute
+            </label>
+            <input
+              id="bm-attribute"
+              className={INPUT}
+              value={benchAttribute}
+              onChange={(event) => setBenchAttribute(event.target.value)}
+              placeholder="Sand-through time"
+            />
+          </div>
+          <div>
+            <label className={LABEL} htmlFor="bm-theirs">
+              Theirs
+            </label>
+            <input
+              id="bm-theirs"
+              className={INPUT}
+              value={benchTheirs}
+              onChange={(event) => setBenchTheirs(event.target.value)}
+              placeholder="18 min"
+            />
+          </div>
+          <div>
+            <label className={LABEL} htmlFor="bm-ours">
+              Ours
+            </label>
+            <input
+              id="bm-ours"
+              className={INPUT}
+              value={benchOurs}
+              onChange={(event) => setBenchOurs(event.target.value)}
+              placeholder="22 min"
+            />
+          </div>
+          <div className="sm:col-span-2">
+            <label className={LABEL} htmlFor="bm-gap">
+              What the gap is, in words
+            </label>
+            <textarea
+              id="bm-gap"
+              className={INPUT}
+              rows={2}
+              value={benchGap}
+              onChange={(event) => setBenchGap(event.target.value)}
+              placeholder="Theirs sands about four minutes sooner at 20 °C."
+            />
+          </div>
+          <div className="sm:col-span-2">
+            <button
+              type="button"
+              className={BUTTON}
+              disabled={
+                writes.isPending ||
+                benchProject === "" ||
+                benchAttribute.trim() === "" ||
+                benchGap.trim() === ""
+              }
+              onClick={() =>
+                writes.recordBenchmark(
+                  product.id,
+                  {
+                    project_id: benchProject,
+                    attribute: benchAttribute.trim(),
+                    gap_summary: benchGap.trim(),
+                    ...(benchTheirs.trim() ? { competitor_value: benchTheirs.trim() } : {}),
+                    ...(benchOurs.trim() ? { our_value: benchOurs.trim() } : {}),
+                  },
+                  () => {
+                    setBenchAttribute("");
+                    setBenchTheirs("");
+                    setBenchOurs("");
+                    setBenchGap("");
+                  },
+                )
+              }
+            >
+              Record the comparison
+            </button>
+          </div>
+        </div>
+
+        {benchmarks.error !== null ? (
+          <DataSourceError error={benchmarks.error} />
+        ) : comparisons.length === 0 ? (
+          <p className="mt-3 text-sm text-slate-600">No comparisons recorded yet.</p>
+        ) : (
+          <ul className="mt-3 grid gap-2">
+            {comparisons.map((row) => (
+              <li
+                key={row.id}
+                className="rounded border border-slate-200 bg-white px-3 py-2 text-xs text-slate-700"
+              >
+                <span className="font-medium text-slate-900">{row.attribute}</span>
+                {row.project_code !== null && <> · {row.project_code}</>}
+                <span className="mt-1 block">
+                  Theirs {row.competitor_value ?? "not stated"} · ours{" "}
+                  {row.our_value ?? "not stated"}
+                </span>
+                <span className="mt-1 block text-slate-600">{row.gap_summary}</span>
+              </li>
+            ))}
+          </ul>
+        )}
+      </section>
+    </div>
+  );
+}
+
+export default function CompetitorsPage() {
+  const products = useCompetitorProducts();
+  const writes = useCompetitorWrites();
+  const [openId, setOpenId] = useState<string | null>(null);
+  const [manufacturer, setManufacturer] = useState("");
+  const [productName, setProductName] = useState("");
+
+  const rows: CompetitorProduct[] = products.data ?? [];
+  const open = rows.find((p) => p.id === openId);
+
+  return (
+    <LiveOnlyPage
+      title="Competitor Intelligence"
+      lede="Register a competitor product, upload its label or a photograph of it,
+            and build an evidence-based picture of what it contains. Every claim
+            records how it is known — this is never presented as a known formula."
+      unavailable={products.unavailable}
+      notInvented="competitor products"
+    >
+      {products.error !== null ? (
+        <DataSourceError error={products.error} />
+      ) : products.unavailable !== null ? (
+        <p className="text-sm text-slate-600">
+          No competitor data can be shown until this build is pointed at an API.
+        </p>
+      ) : (
+        <div className="grid gap-6">
+          {writes.error !== null && (
+            <p
+              role="alert"
+              className="rounded border border-red-300 bg-red-50 px-3 py-2 text-sm text-red-900"
+            >
+              {serverMessage(writes.error)}
+            </p>
+          )}
+
+          <section aria-labelledby="register-heading">
+            <h2 id="register-heading" className="text-sm font-semibold text-slate-900">
+              Register a competitor product
+            </h2>
+            <div className="mt-3 grid gap-3 rounded border border-slate-200 bg-white p-4 sm:grid-cols-3">
+              <div>
+                <label className={LABEL} htmlFor="cp-manufacturer">
+                  Manufacturer
+                </label>
+                <input
+                  id="cp-manufacturer"
+                  className={INPUT}
+                  value={manufacturer}
+                  onChange={(event) => setManufacturer(event.target.value)}
+                />
+              </div>
+              <div>
+                <label className={LABEL} htmlFor="cp-name">
+                  Product
+                </label>
+                <input
+                  id="cp-name"
+                  className={INPUT}
+                  value={productName}
+                  onChange={(event) => setProductName(event.target.value)}
+                />
+              </div>
+              <div className="flex items-end">
+                <button
+                  type="button"
+                  className={BUTTON}
+                  disabled={
+                    writes.isPending ||
+                    manufacturer.trim() === "" ||
+                    productName.trim() === ""
+                  }
+                  onClick={() =>
+                    writes.registerProduct(
+                      {
+                        manufacturer: manufacturer.trim(),
+                        product_name: productName.trim(),
+                      },
+                      () => {
+                        setManufacturer("");
+                        setProductName("");
+                      },
+                    )
+                  }
+                >
+                  Register
+                </button>
+              </div>
+            </div>
+          </section>
+
+          <section aria-labelledby="products-heading">
+            <h2 id="products-heading" className="text-sm font-semibold text-slate-900">
+              Competitor products
+            </h2>
+            {rows.length === 0 ? (
+              <p className="mt-3 text-sm text-slate-600">
+                {products.isLoading
+                  ? "Loading…"
+                  : "None registered yet. Register one above, then upload its label."}
+              </p>
+            ) : (
+              <ul className="mt-3 grid gap-3">
+                {rows.map((product) => (
+                  <li
+                    key={product.id}
+                    className="rounded border border-slate-200 bg-white p-4"
+                  >
+                    <div className="flex flex-wrap items-baseline gap-2">
+                      <h3 className="flex-1 text-sm font-semibold text-slate-900">
+                        {product.manufacturer} — {product.product_name}
+                      </h3>
+                      <span className="text-xs text-slate-600">
+                        {product.document_count} document(s) ·{" "}
+                        {product.evidence_count} claim(s)
+                      </span>
+                      <button
+                        type="button"
+                        className={SECONDARY}
+                        onClick={() =>
+                          setOpenId(openId === product.id ? null : product.id)
+                        }
+                      >
+                        {openId === product.id ? "Close" : "Open"}
+                      </button>
+                    </div>
+                    {openId === product.id && open !== undefined && (
+                      <div className="mt-4 border-t border-slate-200 pt-4">
+                        <ProductWorkspace product={open} />
+                      </div>
+                    )}
+                  </li>
+                ))}
+              </ul>
+            )}
+          </section>
+        </div>
+      )}
+    </LiveOnlyPage>
+  );
+}
diff --git a/apps/web/lib/api/competitors.ts b/apps/web/lib/api/competitors.ts
new file mode 100644
index 0000000..6b0e247
--- /dev/null
+++ b/apps/web/lib/api/competitors.ts
@@ -0,0 +1,358 @@
+/**
+ * Competitor intelligence, over HTTP.
+ *
+ * 🔴 THE MATRIX IS NOT A RECIPE, AND THIS MODULE MUST NOT LET IT LOOK LIKE ONE.
+ *
+ * The specification forbids presenting an inferred competitor composition as a
+ * known or verified formula. So `compositionMatrixSchema` carries a
+ * `disclaimer` the SERVER supplies and the screen renders — not a sentence the
+ * screen remembers to add, because a screen that forgets it would be doing the
+ * one thing the specification rules out.
+ *
+ * ⚠️ CONCENTRATIONS ARE STRINGS. `NUMERIC(7,4)` in PostgreSQL, and the server
+ * stringifies them at the boundary. Parsing to `number` here would reintroduce
+ * the float CLAUDE.md §5 forbids on a controlled record, and would render
+ * "10.0000" — a range disclosed to four decimal places — as "10".
+ */
+
+import { z } from "zod";
+
+import { apiRequest, type ApiCredentials } from "./client";
+import { API_BASE_URL } from "./config";
+
+export const competitorProductSchema = z.object({
+  id: z.string(),
+  manufacturer: z.string(),
+  product_name: z.string(),
+  product_code: z.string().nullable(),
+  market_segment: z.string().nullable(),
+  project_id: z.string().nullable(),
+  created_at: z.string(),
+  document_count: z.number(),
+  evidence_count: z.number(),
+});
+
+/**
+ * How a claim is known. SEPARATE from the document's type: a person reading a
+ * tin is making an observation, not an inference, and the two must not collapse
+ * into one field.
+ */
+export const EVIDENCE_SOURCES = [
+  { id: "document", label: "A document on file", needsDocument: true },
+  { id: "manual_observation", label: "Read from the product myself", needsDocument: false },
+  { id: "laboratory", label: "Our own laboratory result", needsDocument: false },
+  { id: "literature", label: "Published literature", needsDocument: false },
+  { id: "patent", label: "A patent", needsDocument: false },
+  { id: "inference", label: "Inferred from the above", needsDocument: false },
+  { id: "model", label: "Model hypothesis", needsDocument: false },
+] as const;
+
+/** The A–X ranking from the research source document. */
+export const EVIDENCE_GRADES = [
+  { id: "A", label: "A — validated internal evidence, a standard, or manufacturer documentation" },
+  { id: "B", label: "B — peer-reviewed literature, a patent, or a recognised institution" },
+  { id: "C", label: "C — supplier literature or a conference paper" },
+  { id: "D", label: "D — a general web source" },
+  { id: "X", label: "X — unverified or unreliable" },
+] as const;
+
+export const evidenceRowSchema = z.object({
+  id: z.string(),
+  component_name: z.string(),
+  cas_number: z.string().nullable(),
+  component_function: z.string().nullable(),
+  // Strings. See the header.
+  concentration_low: z.string().nullable(),
+  concentration_high: z.string().nullable(),
+  is_balance: z.boolean(),
+  evidence_source: z.string(),
+  evidence_grade: z.string(),
+  confidence: z.enum(["verified", "supported", "probable", "possible", "unknown"]),
+  source_locator: z.string().nullable(),
+  rationale: z.string().nullable(),
+  verified_at: z.string().nullable(),
+  source_document_id: z.string().nullable(),
+  sample_id: z.string().nullable(),
+  test_id: z.string().nullable(),
+  source_document_title: z.string().nullable(),
+  source_document_type: z.string().nullable(),
+});
+
+export const compositionMatrixSchema = z.object({
+  rows: z.array(evidenceRowSchema),
+  summary: z.record(z.string(), z.number()),
+  // 🔴 SUPPLIED BY THE SERVER AND RENDERED VERBATIM.
+  disclaimer: z.string(),
+});
+
+export const competitorDocumentSchema = z.object({
+  id: z.string(),
+  document_type: z.string(),
+  title: z.string(),
+  content_type: z.string().nullable(),
+  byte_size: z.number().nullable(),
+  issued_on: z.string().nullable(),
+  expires_on: z.string().nullable(),
+  created_at: z.string(),
+});
+
+export const competitorSampleSchema = z.object({
+  id: z.string(),
+  sample_reference: z.string(),
+  acquired_on: z.string().nullable(),
+  batch_marking: z.string().nullable(),
+  observations: z.string().nullable(),
+  registered_by: z.string(),
+  created_at: z.string(),
+  // A count, and it is named as one. `has_root_cause` was a column whose name
+  // asked a yes/no question and whose value was a number (2026-08-27); a field
+  // called `evidence_count` can only be read as the number it is.
+  evidence_count: z.number(),
+});
+
+export const competitorBenchmarkSchema = z.object({
+  id: z.string(),
+  attribute: z.string(),
+  competitor_value: z.string().nullable(),
+  our_value: z.string().nullable(),
+  gap_summary: z.string(),
+  project_id: z.string(),
+  project_name: z.string().nullable(),
+  project_code: z.string().nullable(),
+  formula_version_id: z.string().nullable(),
+  test_id: z.string().nullable(),
+  recorded_by: z.string(),
+  created_at: z.string(),
+  // 🔴 NO DISPOSITION FIELD, DELIBERATELY. Testing owns GREEN/YELLOW/RED and
+  // the server does not send one; a colour invented here would be a second
+  // answer to a question Testing already answers.
+});
+
+export type CompetitorProduct = z.infer<typeof competitorProductSchema>;
+export type EvidenceRow = z.infer<typeof evidenceRowSchema>;
+export type CompositionMatrix = z.infer<typeof compositionMatrixSchema>;
+export type CompetitorDocument = z.infer<typeof competitorDocumentSchema>;
+export type CompetitorSample = z.infer<typeof competitorSampleSchema>;
+export type CompetitorBenchmark = z.infer<typeof competitorBenchmarkSchema>;
+
+export interface ProductRequest {
+  readonly manufacturer: string;
+  readonly product_name: string;
+  readonly product_code?: string;
+  readonly market_segment?: string;
+  readonly notes?: string;
+}
+
+export interface EvidenceRequest {
+  readonly component_name: string;
+  readonly evidence_source: string;
+  readonly evidence_grade: string;
+  readonly cas_number?: string;
+  readonly component_function?: string;
+  readonly concentration_low?: string;
+  readonly concentration_high?: string;
+  readonly is_balance?: boolean;
+  readonly source_document_id?: string;
+  // 🔴 THE SERVER HAS ALWAYS ACCEPTED THIS AND NOTHING EVER SENT IT.
+  // `manual_observation` means somebody read a physical tin; without naming
+  // WHICH tin, the claim cannot be re-checked and the grade is unearned.
+  readonly sample_id?: string;
+  readonly source_locator?: string;
+  readonly rationale?: string;
+}
+
+export interface SampleRequest {
+  readonly sample_reference: string;
+  readonly acquired_on?: string;
+  readonly batch_marking?: string;
+  readonly observations?: string;
+}
+
+export interface BenchmarkRequest {
+  readonly project_id: string;
+  readonly attribute: string;
+  readonly gap_summary: string;
+  readonly competitor_value?: string;
+  readonly our_value?: string;
+  readonly formula_version_id?: string;
+  readonly test_id?: string;
+}
+
+export function fetchCompetitorProducts(
+  credentials: ApiCredentials,
+  signal?: AbortSignal,
+): Promise<CompetitorProduct[]> {
+  return apiRequest({ path: "/api/competitors", credentials, signal }, (payload) =>
+    z.array(competitorProductSchema).parse(payload),
+  );
+}
+
+export function fetchCompositionMatrix(
+  credentials: ApiCredentials,
+  productId: string,
+  signal?: AbortSignal,
+): Promise<CompositionMatrix> {
+  return apiRequest(
+    { path: `/api/competitors/${productId}/composition`, credentials, signal },
+    (payload) => compositionMatrixSchema.parse(payload),
+  );
+}
+
+export function fetchCompetitorDocuments(
+  credentials: ApiCredentials,
+  productId: string,
+  signal?: AbortSignal,
+): Promise<CompetitorDocument[]> {
+  return apiRequest(
+    { path: `/api/competitors/${productId}/documents`, credentials, signal },
+    (payload) => z.array(competitorDocumentSchema).parse(payload),
+  );
+}
+
+export function registerCompetitorProduct(
+  credentials: ApiCredentials,
+  request: ProductRequest,
+): Promise<{ id: string }> {
+  return apiRequest(
+    { path: "/api/competitors", method: "POST", credentials, body: request },
+    (payload) => z.object({ id: z.string() }).parse(payload),
+  );
+}
+
+export function recordCompetitorEvidence(
+  credentials: ApiCredentials,
+  productId: string,
+  request: EvidenceRequest,
+): Promise<{ id: string; confidence: string }> {
+  return apiRequest(
+    {
+      path: `/api/competitors/${productId}/evidence`,
+      method: "POST",
+      credentials,
+      body: request,
+    },
+    (payload) => z.object({ id: z.string(), confidence: z.string() }).parse(payload),
+  );
+}
+
+export function gradeCompetitorEvidence(
+  credentials: ApiCredentials,
+  evidenceId: string,
+  confidence: string,
+): Promise<{ id: string; confidence: string }> {
+  return apiRequest(
+    {
+      path: `/api/competitors/evidence/${evidenceId}/grade`,
+      method: "POST",
+      credentials,
+      body: { confidence },
+    },
+    (payload) => z.object({ id: z.string(), confidence: z.string() }).parse(payload),
+  );
+}
+
+/**
+ * Upload a label or a product photograph.
+ *
+ * 🔴 MULTIPART, AND IT DOES NOT GO THROUGH `apiRequest`.
+ *
+ * `apiRequest` JSON-encodes its body and sets `Content-Type: application/json`.
+ * A file needs `FormData` and the browser's own boundary — setting the header
+ * by hand omits the boundary and the server cannot parse the parts. So this is
+ * a deliberate exception, and it still carries the same credentials and
+ * organization header every other call does.
+ */
+export async function uploadCompetitorDocument(
+  credentials: ApiCredentials,
+  productId: string,
+  file: File,
+  documentType: string,
+  title: string,
+): Promise<{ id: string }> {
+  const body = new FormData();
+  body.append("file", file);
+  body.append("document_type", documentType);
+  body.append("title", title);
+
+  if (API_BASE_URL === null) {
+    // The same absence `apiRequest` distinguishes: this build has nothing to
+    // call, which is not a failure and must not read as one.
+    throw new Error("this build is not pointed at an API, so nothing can be uploaded");
+  }
+  const response = await fetch(`${API_BASE_URL}/api/competitors/${productId}/documents`, {
+    method: "POST",
+    headers: {
+      Authorization: `Bearer ${credentials.token}`,
+      "X-Organization-Id": credentials.organizationId,
+      // NO Content-Type: the browser sets it, WITH the multipart boundary.
+    },
+    body,
+  });
+
+  if (!response.ok) {
+    let detail = `the upload failed (${response.status})`;
+    try {
+      const parsed = (await response.json()) as { detail?: unknown };
+      if (typeof parsed.detail === "string") detail = parsed.detail;
+    } catch {
+      // A non-JSON error body. The status alone is what we have.
+    }
+    throw new Error(detail);
+  }
+  return z.object({ id: z.string() }).parse(await response.json());
+}
+
+
+export function fetchCompetitorSamples(
+  credentials: ApiCredentials,
+  productId: string,
+  signal?: AbortSignal,
+): Promise<CompetitorSample[]> {
+  return apiRequest(
+    { path: `/api/competitors/${productId}/samples`, credentials, signal },
+    (payload) => z.array(competitorSampleSchema).parse(payload),
+  );
+}
+
+export function fetchCompetitorBenchmarks(
+  credentials: ApiCredentials,
+  productId: string,
+  signal?: AbortSignal,
+): Promise<CompetitorBenchmark[]> {
+  return apiRequest(
+    { path: `/api/competitors/${productId}/benchmarks`, credentials, signal },
+    (payload) => z.array(competitorBenchmarkSchema).parse(payload),
+  );
+}
+
+export function registerCompetitorSample(
+  credentials: ApiCredentials,
+  productId: string,
+  request: SampleRequest,
+): Promise<{ id: string }> {
+  return apiRequest(
+    {
+      path: `/api/competitors/${productId}/samples`,
+      method: "POST",
+      credentials,
+      body: request,
+    },
+    (payload) => z.object({ id: z.string() }).parse(payload),
+  );
+}
+
+export function recordCompetitorBenchmark(
+  credentials: ApiCredentials,
+  productId: string,
+  request: BenchmarkRequest,
+): Promise<{ id: string }> {
+  return apiRequest(
+    {
+      path: `/api/competitors/${productId}/benchmarks`,
+      method: "POST",
+      credentials,
+      body: request,
+    },
+    (payload) => z.object({ id: z.string() }).parse(payload),
+  );
+}
diff --git a/apps/web/lib/api/hooks.ts b/apps/web/lib/api/hooks.ts
index ea457f7..f041302 100644
--- a/apps/web/lib/api/hooks.ts
+++ b/apps/web/lib/api/hooks.ts
@@ -205,6 +205,30 @@ import {
   useAuth,
   type OrganizationChoice,
 } from "@/components/providers/auth-provider";
+import {
+  fetchCompetitorBenchmarks,
+  fetchCompetitorDocuments,
+  fetchCompetitorProducts,
+  fetchCompetitorSamples,
+  fetchCompositionMatrix,
+  gradeCompetitorEvidence,
+  recordCompetitorBenchmark,
+  recordCompetitorEvidence,
+  registerCompetitorProduct,
+  registerCompetitorSample,
+  uploadCompetitorDocument,
+  type BenchmarkRequest,
+  type CompetitorBenchmark,
+  type CompetitorDocument,
+  type CompetitorProduct,
+  type CompetitorSample,
+  type CompositionMatrix,
+  type EvidenceRequest as CompetitorEvidenceRequest,
+  type ProductRequest,
+  // Aliased: laboratory.ts already exports a SampleRequest, and that one is a
+  // BATCH sample of our own. Two different things with one name in one file.
+  type SampleRequest as CompetitorSampleRequest,
+} from "./competitors";
 import {
   dashboardForRoles,
   fetchRoleDashboard,
@@ -2532,3 +2556,193 @@ export function useRoleDashboard(role: DashboardRole | null): LiveOnly<RoleDashb
     fetchRoleDashboard(credentials, role ?? "", signal),
   );
 }
+
+// ---------------------------------------------------------------------------
+// Competitor intelligence
+// ---------------------------------------------------------------------------
+
+export function useCompetitorProducts<TShown = CompetitorProduct[]>(
+  project: (live: CompetitorProduct[]) => TShown = (live) => live as unknown as TShown,
+): LiveOnly<TShown> {
+  return useLiveOnlyList("competitor-products", project, fetchCompetitorProducts);
+}
+
+/** The Composition Evidence Matrix for one product. */
+export function useCompositionMatrix(productId: string): LiveOnly<CompositionMatrix> {
+  return useLiveOnlyRecord("competitor-composition", productId, (credentials, signal) =>
+    fetchCompositionMatrix(credentials, productId, signal),
+  );
+}
+
+/** Labels, photographs and literature on file for one product. */
+export function useCompetitorDocuments(productId: string): LiveOnly<CompetitorDocument[]> {
+  return useLiveOnlyRecord("competitor-documents", productId, (credentials, signal) =>
+    fetchCompetitorDocuments(credentials, productId, signal),
+  );
+}
+
+/**
+ * Physical samples held for one competitor product.
+ *
+ * 🔴 THE LIST EXISTS SO A CLAIM CAN CITE ONE. `manual_observation` means a
+ * person read a tin; the matrix stores WHICH tin in `sample_id`, and until
+ * this hook existed no screen could offer the choice, so every observation
+ * was recorded unattributable.
+ */
+export function useCompetitorSamples(productId: string): LiveOnly<CompetitorSample[]> {
+  return useLiveOnlyRecord("competitor-samples", productId, (credentials, signal) =>
+    fetchCompetitorSamples(credentials, productId, signal),
+  );
+}
+
+/** Measured comparisons recorded against one competitor product. */
+export function useCompetitorBenchmarks(productId: string): LiveOnly<CompetitorBenchmark[]> {
+  return useLiveOnlyRecord("competitor-benchmarks", productId, (credentials, signal) =>
+    fetchCompetitorBenchmarks(credentials, productId, signal),
+  );
+}
+
+/**
+ * Every write in competitor intelligence, including the file upload.
+ *
+ * 🔴 THE UPLOAD IS IN THE SAME HOOK AS THE REST, so the screen has one
+ * `isPending` and one error. A separate upload hook would let a form show
+ * "saved" while a file was still in flight.
+ */
+export function useCompetitorWrites(): {
+  readonly registerProduct: (request: ProductRequest, after?: () => void) => void;
+  readonly upload: (
+    productId: string,
+    file: File,
+    documentType: string,
+    title: string,
+    after?: () => void,
+  ) => void;
+  readonly recordEvidence: (
+    productId: string,
+    request: CompetitorEvidenceRequest,
+    after?: () => void,
+  ) => void;
+  readonly grade: (evidenceId: string, confidence: string) => void;
+  readonly registerSample: (
+    productId: string,
+    request: CompetitorSampleRequest,
+    after?: () => void,
+  ) => void;
+  readonly recordBenchmark: (
+    productId: string,
+    request: BenchmarkRequest,
+    after?: () => void,
+  ) => void;
+  readonly isPending: boolean;
+  readonly error: Error | null;
+  readonly lastAction: string | null;
+  readonly unavailable: string | null;
+} {
+  const resolved = useCredentials();
+  const queryClient = useQueryClient();
+
+  const credentials = () => {
+    if (!resolved.ok) {
+      throw isApiConfigured
+        ? new ApiNoSessionError(resolved.reason)
+        : new ApiNotConfiguredError();
+    }
+    return resolved.credentials;
+  };
+
+  const mutation = useMutation({
+    mutationFn: async (
+      job:
+        | { readonly kind: "product"; readonly request: ProductRequest; readonly after?: () => void }
+        | {
+            readonly kind: "upload";
+            readonly productId: string;
+            readonly file: File;
+            readonly documentType: string;
+            readonly title: string;
+            readonly after?: () => void;
+          }
+        | {
+            readonly kind: "evidence";
+            readonly productId: string;
+            readonly request: CompetitorEvidenceRequest;
+            readonly after?: () => void;
+          }
+        | {
+            readonly kind: "sample";
+            readonly productId: string;
+            readonly request: CompetitorSampleRequest;
+            readonly after?: () => void;
+          }
+        | {
+            readonly kind: "benchmark";
+            readonly productId: string;
+            readonly request: BenchmarkRequest;
+            readonly after?: () => void;
+          }
+        | { readonly kind: "grade"; readonly evidenceId: string; readonly confidence: string },
+    ) => {
+      if (job.kind === "product") {
+        await registerCompetitorProduct(credentials(), job.request);
+        return "product registered";
+      }
+      if (job.kind === "upload") {
+        await uploadCompetitorDocument(
+          credentials(),
+          job.productId,
+          job.file,
+          job.documentType,
+          job.title,
+        );
+        return "uploaded";
+      }
+      if (job.kind === "evidence") {
+        await recordCompetitorEvidence(credentials(), job.productId, job.request);
+        return "evidence recorded";
+      }
+      if (job.kind === "sample") {
+        await registerCompetitorSample(credentials(), job.productId, job.request);
+        return "sample registered";
+      }
+      if (job.kind === "benchmark") {
+        await recordCompetitorBenchmark(credentials(), job.productId, job.request);
+        return "benchmark recorded";
+      }
+      const graded = await gradeCompetitorEvidence(
+        credentials(),
+        job.evidenceId,
+        job.confidence,
+      );
+      return graded.confidence;
+    },
+    onSuccess: (_data, job) => {
+      void queryClient.invalidateQueries({ queryKey: ["competitor-products"] });
+      void queryClient.invalidateQueries({ queryKey: ["competitor-composition"] });
+      void queryClient.invalidateQueries({ queryKey: ["competitor-documents"] });
+      // A new sample changes what an observation may cite, so the sample list
+      // is invalidated by EVERY write here, not only by "sample".
+      void queryClient.invalidateQueries({ queryKey: ["competitor-samples"] });
+      void queryClient.invalidateQueries({ queryKey: ["competitor-benchmarks"] });
+      if (job.kind !== "grade") job.after?.();
+    },
+  });
+
+  return {
+    registerProduct: (request, after) => mutation.mutate({ kind: "product", request, after }),
+    upload: (productId, file, documentType, title, after) =>
+      mutation.mutate({ kind: "upload", productId, file, documentType, title, after }),
+    recordEvidence: (productId, request, after) =>
+      mutation.mutate({ kind: "evidence", productId, request, after }),
+    grade: (evidenceId, confidence) =>
+      mutation.mutate({ kind: "grade", evidenceId, confidence }),
+    registerSample: (productId, request, after) =>
+      mutation.mutate({ kind: "sample", productId, request, after }),
+    recordBenchmark: (productId, request, after) =>
+      mutation.mutate({ kind: "benchmark", productId, request, after }),
+    isPending: mutation.isPending,
+    error: (mutation.error as Error | null) ?? null,
+    lastAction: mutation.data ?? null,
+    unavailable: resolved.ok ? null : resolved.failed ? null : resolved.reason,
+  };
+}
diff --git a/apps/web/lib/navigation.ts b/apps/web/lib/navigation.ts
index c9d774a..5b006e9 100644
--- a/apps/web/lib/navigation.ts
+++ b/apps/web/lib/navigation.ts
@@ -119,6 +119,16 @@ export const NAVIGATION: readonly NavGroup[] = [
         permission: "material.view",
         slice: 7,
       },
+      // Competitor intelligence sits under the Center it belongs to, and is
+      // reachable in its own right: the operator went looking for "where do I
+      // load the picture of the label" and there was nowhere to go.
+      {
+        id: "competitors",
+        label: "Competitor Intelligence",
+        href: "/material-safety/competitors",
+        permission: "material.view",
+        slice: 7,
+      },
       { id: "knowledge", label: "Knowledge Library", href: "/knowledge", permission: "knowledge.view", slice: 8 },
     ],
   },
@@ -323,6 +333,7 @@ export const BUILT_AHEAD: ReadonlySet<string> = new Set([
   // `page.tsx` and `navigation.test.ts` reads the filesystem and would fail
   // the build for putting a live link in front of a 404.
   "material-safety",
+  "competitors",
 ]);
 
 export function isAvailable(item: NavItem): boolean {
diff --git a/tests/e2e/shell/accessibility.spec.ts b/tests/e2e/shell/accessibility.spec.ts
index 275bbcd..bfc9ab1 100644
--- a/tests/e2e/shell/accessibility.spec.ts
+++ b/tests/e2e/shell/accessibility.spec.ts
@@ -94,6 +94,7 @@ const PAGES = [
   // live suite on 2026-08-27, which is why
   // `lib/accessibility-coverage.test.ts` now asserts uniqueness too.
   { name: "material safety data", path: "/material-safety" },
+  { name: "competitor intelligence", path: "/material-safety/competitors" },
   { name: "reports", path: "/reports" },
   // The workspace routes, with no record named. That is a REAL state — it is
   // what a bookmarked link without its query string renders — and it is the

2026-08-28T21:55:24.245905Z ERROR codex_core::tools::router: error=`"C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command 'git diff c98420a''^ c98420a --unified=35 -- apps/api/app/api/competitors.py apps/api/app/domains/competitor_intelligence/service.py apps/api/tests/db/test_056_competitor_intelligence.py apps/web/app/material-safety/competitors/page.tsx | Select-String -Pattern '"'get_benchmarks|list_benchmarks|list_samples|record_evidence|sample_id|evidence_source|manual_observation|benchmark|project|test.view|material.view|disclaimer' -Context 15,25"` rejected: blocked by policy
exec
"C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command 'git diff c98420a''^ c98420a --unified=35 -- apps/api/app/api/competitors.py apps/api/app/domains/competitor_intelligence/service.py apps/api/tests/db/test_056_competitor_intelligence.py apps/web/app/material-safety/competitors/page.tsx | Select-String -Pattern '"'get_benchmarks|list_benchmarks|list_samples|record_evidence|sample_id|evidence_source|manual_observation|benchmark|project|test.view|material.view|disclaimer' -Context 15,25" in C:\Users\USER\Documents\evercoat-itw-rd-workspace\EvercoatITWRD APP
 declined in 0ms:
`"C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command 'git diff c98420a''^ c98420a --unified=35 -- apps/api/app/api/competitors.py apps/api/app/domains/competitor_intelligence/service.py apps/api/tests/db/test_056_competitor_intelligence.py apps/web/app/material-safety/competitors/page.tsx | Select-String -Pattern '"'get_benchmarks|list_benchmarks|list_samples|record_evidence|sample_id|evidence_source|manual_observation|benchmark|project|test.view|material.view|disclaimer' -Context 15,25"` rejected: blocked by policy
2026-08-28T21:55:30.949725Z ERROR codex_core::tools::router: error=`"C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command "git diff c98420a~1 c98420a --unified=25 -- apps/api/app/api/competitors.py apps/api/app/domains/competitor_intelligence/service.py apps/api/tests/db/test_056_competitor_intelligence.py apps/web/app/material-safety/competitors/page.tsx | Select-String -Pattern 'get_benchmarks|list_benchmarks|list_samples|record_evidence|sample_id|evidence_source|manual_observation|benchmark|project|test.view|material.view|disclaimer' -Context 12,20"` rejected: blocked by policy
exec
"C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command "git diff c98420a~1 c98420a --unified=25 -- apps/api/app/api/competitors.py apps/api/app/domains/competitor_intelligence/service.py apps/api/tests/db/test_056_competitor_intelligence.py apps/web/app/material-safety/competitors/page.tsx | Select-String -Pattern 'get_benchmarks|list_benchmarks|list_samples|record_evidence|sample_id|evidence_source|manual_observation|benchmark|project|test.view|material.view|disclaimer' -Context 12,20" in C:\Users\USER\Documents\evercoat-itw-rd-workspace\EvercoatITWRD APP
 declined in 0ms:
`"C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command "git diff c98420a~1 c98420a --unified=25 -- apps/api/app/api/competitors.py apps/api/app/domains/competitor_intelligence/service.py apps/api/tests/db/test_056_competitor_intelligence.py apps/web/app/material-safety/competitors/page.tsx | Select-String -Pattern 'get_benchmarks|list_benchmarks|list_samples|record_evidence|sample_id|evidence_source|manual_observation|benchmark|project|test.view|material.view|disclaimer' -Context 12,20"` rejected: blocked by policy
exec
"C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command 'git show c98420a:apps/api/app/domains/competitor_intelligence/service.py | rg -n -C 18 "def list_samples|def list_benchmarks|def record_evidence|sample_id|project_access|test_id"' in C:\Users\USER\Documents\evercoat-itw-rd-workspace\EvercoatITWRD APP
 succeeded in 2043ms:
235-        ).mappings()
236-    ]
237-
238-
239-def register_sample(
240-    session: Session,
241-    *,
242-    organization_id: uuid.UUID,
243-    actor_id: uuid.UUID,
244-    competitor_product_id: uuid.UUID,
245-    sample_reference: str,
246-    acquired_on: str | None = None,
247-    batch_marking: str | None = None,
248-    observations: str | None = None,
249-) -> dict[str, Any]:
250-    """Register a physical sample of a competitor product."""
251-    try:
252-        with guarded_write(session):
253:            sample_id = session.execute(
254-                text(
255-                    """
256-                    INSERT INTO competitors.samples
257-                        (organization_id, competitor_product_id, sample_reference,
258-                         acquired_on, batch_marking, observations, registered_by)
259-                    VALUES (:org, :product, :ref, CAST(:acquired AS DATE), :batch,
260-                            :observations, :actor)
261-                    RETURNING id
262-                    """
263-                ),
264-                {
265-                    "org": organization_id,
266-                    "product": competitor_product_id,
267-                    "ref": sample_reference,
268-                    "acquired": acquired_on,
269-                    "batch": batch_marking,
270-                    "observations": observations,
271-                    "actor": actor_id,
272-                },
273-            ).scalar_one()
274-    except DBAPIError as exc:
275-        raise _translate(exc) from exc
276-
277-    write_audit(
278-        session,
279-        AuditEvent(
280-            action="COMPETITOR_SAMPLE_REGISTERED",
281-            entity_type="competitor_sample",
282:            entity_id=str(sample_id),
283-            organization_id=organization_id,
284-            user_id=actor_id,
285-            new_state={"sample_reference": sample_reference},
286-        ),
287-    )
288:    return {"id": sample_id}
289-
290-
291:def list_samples(
292-    session: Session, *, organization_id: uuid.UUID, competitor_product_id: uuid.UUID
293-) -> list[dict[str, Any]]:
294-    """Physical samples on file for one competitor product, newest first.
295-
296-    ?? WRITTEN BECAUSE `register_sample` HAD NO READER, AND A SAMPLE NOBODY
297:    CAN LIST IS A ROW THAT CANNOT BE CITED. `composition_evidence.sample_id`
298-    exists precisely so a `manual_observation` claim can name the tin it was
299-    read from -- and naming one requires being shown which ones exist. A
300-    writer without its reader is the same defect as a route without its
301-    control, one tier down.
302-
303-    RLS supplies the organization and project predicate; the explicit
304-    `organization_id` here is the same belt-and-braces every reader in this
305-    module uses, not a substitute for it.
306-    """
307-    return [
308-        dict(r)
309-        for r in session.execute(
310-            text(
311-                """
312-                SELECT s.id, s.sample_reference, s.acquired_on, s.batch_marking,
313-                       s.observations, s.registered_by, s.created_at,
314-                       (SELECT count(*) FROM competitors.composition_evidence e
315:                         WHERE e.sample_id = s.id
316-                           AND e.organization_id = s.organization_id) AS evidence_count
317-                  FROM competitors.samples s
318-                 WHERE s.organization_id = :org
319-                   AND s.competitor_product_id = :product
320-                 ORDER BY s.acquired_on DESC NULLS LAST, s.created_at DESC
321-                """
322-            ),
323-            {"org": organization_id, "product": competitor_product_id},
324-        ).mappings()
325-    ]
326-
327-
328-# ---------------------------------------------------------------------------
329-# The Composition Evidence Matrix
330-# ---------------------------------------------------------------------------
331-
332-
333-@dataclass(frozen=True, slots=True)
334-class EvidenceInput:
335-    component_name: str
336-    evidence_source: str
337-    evidence_grade: str
338-    cas_number: str | None = None
339-    component_function: str | None = None
340-    # Strings, not floats. NUMERIC(7,4) in PostgreSQL, and a float would round
341-    # the disclosed range before the database saw it.
342-    concentration_low: str | None = None
343-    concentration_high: str | None = None
344-    is_balance: bool = False
345-    source_document_id: uuid.UUID | None = None
346:    sample_id: uuid.UUID | None = None
347:    test_id: uuid.UUID | None = None
348-    source_locator: str | None = None
349-    rationale: str | None = None
350-
351-
352:def record_evidence(
353-    session: Session,
354-    *,
355-    organization_id: uuid.UUID,
356-    actor_id: uuid.UUID,
357-    competitor_product_id: uuid.UUID,
358-    spec: EvidenceInput,
359-) -> dict[str, Any]:
360-    """Record one claim about what a competitor product contains.
361-
362-    ?? IT IS RECORDED AT `possible`, NEVER AT `verified`.
363-
364-    `confidence` is not an argument. A claim arrives as something somebody
365-    noticed; it becomes verified only through `verify_evidence`, which is a
366-    separate act by somebody holding `compliance.review_sds` ? the same shape
367-    as a root cause, where ?3 rule 4 says only a human moves a hypothesis to
368-    accepted. Letting the writer set `verified` would make the matrix's
369-    central distinction a matter of what the caller typed.
370-
371-    `observed_by` is the actor for a manual observation: the person recording
372-    what they saw is the person who saw it, and the database requires a name.
373-    """
374-    try:
375-        with guarded_write(session):
376-            evidence_id = session.execute(
377-                text(
378-                    """
379-                    INSERT INTO competitors.composition_evidence
380-                        (organization_id, competitor_product_id, component_name,
381-                         cas_number, component_function, concentration_low,
382-                         concentration_high, is_balance, evidence_source,
383:                         evidence_grade, confidence, source_document_id, sample_id,
384:                         test_id, source_locator, rationale, observed_by, recorded_by)
385-                    VALUES (:org, :product, :name, :cas, :function,
386-                            CAST(:low AS NUMERIC), CAST(:high AS NUMERIC), :balance,
387-                            :source, :grade, 'possible', :doc, :sample, :test,
388-                            :locator, :rationale, :observed, :actor)
389-                    RETURNING id
390-                    """
391-                ),
392-                {
393-                    "org": organization_id,
394-                    "product": competitor_product_id,
395-                    "name": spec.component_name,
396-                    "cas": spec.cas_number,
397-                    "function": spec.component_function,
398-                    "low": spec.concentration_low,
399-                    "high": spec.concentration_high,
400-                    "balance": spec.is_balance,
401-                    "source": spec.evidence_source,
402-                    "grade": spec.evidence_grade,
403-                    "doc": spec.source_document_id,
404:                    "sample": spec.sample_id,
405:                    "test": spec.test_id,
406-                    "locator": spec.source_locator,
407-                    "rationale": spec.rationale,
408-                    "observed": actor_id if spec.evidence_source == "manual_observation" else None,
409-                    "actor": actor_id,
410-                },
411-            ).scalar_one()
412-    except DBAPIError as exc:
413-        raise _translate(exc) from exc
414-
415-    write_audit(
416-        session,
417-        AuditEvent(
418-            action="COMPETITOR_EVIDENCE_RECORDED",
419-            entity_type="composition_evidence",
420-            entity_id=str(evidence_id),
421-            organization_id=organization_id,
422-            user_id=actor_id,
423-            # The component name is not a payload to withhold -- it is the
--
507-    deliberately not shaped like a formula. It is the claims, strongest
508-    evidence first, each with its source, its grade, its confidence and the
509-    locator somebody else can use to re-check it.
510-
511-    The summary counts exist so a reader can see at a glance how much of the
512-    picture is actually established: "3 verified, 2 supported, 6 inferred" is a
513-    different product understanding from "11 verified", and a bare list makes
514-    them look alike.
515-    """
516-    rows = [
517-        _decimal_strings(r)
518-        for r in session.execute(
519-            text(
520-                """
521-                SELECT e.id, e.component_name, e.cas_number, e.component_function,
522-                       e.concentration_low, e.concentration_high, e.is_balance,
523-                       e.evidence_source, e.evidence_grade, e.confidence,
524-                       e.source_locator, e.rationale, e.verified_at,
525:                       e.source_document_id, e.sample_id, e.test_id,
526-                       d.title AS source_document_title,
527-                       d.document_type AS source_document_type
528-                  FROM competitors.composition_evidence e
529-                  LEFT JOIN materials.material_documents d
530-                    ON d.id = e.source_document_id AND d.organization_id = e.organization_id
531-                 WHERE e.organization_id = :org AND e.competitor_product_id = :product
532-                 ORDER BY
533-                   -- Strongest first: a reader scanning the top of this list
534-                   -- should be reading the best-established claims.
535-                   CASE e.confidence WHEN 'verified'  THEN 0
536-                                     WHEN 'supported' THEN 1
537-                                     WHEN 'probable'  THEN 2
538-                                     WHEN 'possible'  THEN 3
539-                                     ELSE 4 END,
540-                   e.evidence_grade,
541-                   e.concentration_high DESC NULLS LAST,
542-                   e.component_name
543-                """
--
563-            "differing strength. It is not a known or verified formula, and "
564-            "rows that are not marked verified have not been confirmed."
565-        ),
566-    }
567-
568-
569-def record_benchmark(
570-    session: Session,
571-    *,
572-    organization_id: uuid.UUID,
573-    actor_id: uuid.UUID,
574-    competitor_product_id: uuid.UUID,
575-    project_id: uuid.UUID,
576-    attribute: str,
577-    gap_summary: str,
578-    competitor_value: str | None = None,
579-    our_value: str | None = None,
580-    formula_version_id: uuid.UUID | None = None,
581:    test_id: uuid.UUID | None = None,
582-) -> dict[str, Any]:
583-    """Record a measured comparison against our own work.
584-
585-    ?? IT CITES A TEST; IT DOES NOT GRADE ONE. Testing owns GREEN/YELLOW/RED
586-    (CLAUDE.md ?10) and this module must not produce a second disposition. The
587-    gap is stated in words for the same reason: the arithmetic belongs to the
588-    engine (?3 rule 2), and a delta computed here would be a second answer to a
589-    question Testing already answers.
590-    """
591-    try:
592-        with guarded_write(session):
593-            benchmark_id = session.execute(
594-                text(
595-                    """
596-                    INSERT INTO competitors.benchmarks
597-                        (organization_id, competitor_product_id, project_id,
598:                         formula_version_id, test_id, attribute, competitor_value,
599-                         our_value, gap_summary, recorded_by)
600-                    VALUES (:org, :product, :project, :version, :test, :attribute,
601-                            :theirs, :ours, :gap, :actor)
602-                    RETURNING id
603-                    """
604-                ),
605-                {
606-                    "org": organization_id,
607-                    "product": competitor_product_id,
608-                    "project": project_id,
609-                    "version": formula_version_id,
610:                    "test": test_id,
611-                    "attribute": attribute,
612-                    "theirs": competitor_value,
613-                    "ours": our_value,
614-                    "gap": gap_summary,
615-                    "actor": actor_id,
616-                },
617-            ).scalar_one()
618-    except DBAPIError as exc:
619-        raise _translate(exc) from exc
620-
621-    write_audit(
622-        session,
623-        AuditEvent(
624-            action="COMPETITOR_BENCHMARK_RECORDED",
625-            entity_type="competitor_benchmark",
626-            entity_id=str(benchmark_id),
627-            organization_id=organization_id,
628-            user_id=actor_id,
629-            new_state={"attribute": attribute},
630-        ),
631-    )
632-    return {"id": benchmark_id}
633-
634-
635:def list_benchmarks(
636-    session: Session, *, organization_id: uuid.UUID, competitor_product_id: uuid.UUID
637-) -> list[dict[str, Any]]:
638-    """Measured comparisons recorded against one competitor product.
639-
640-    ?? WRITTEN BECAUSE `record_benchmark` HAD NO READER EITHER. The whole
641-    point of a benchmark is that somebody later reads it beside the gap it
642-    describes; a write-only benchmark table is an audit trail nobody can
643-    consult.
644-
645-    ?? IT REPORTS THE CITED TEST, IT DOES NOT REPORT A DISPOSITION. Testing
646-    owns GREEN/YELLOW/RED (`CLAUDE.md` ?10) and this query deliberately does
647-    not join one in: a colour surfaced here would be a second answer to a
648-    question Testing already answers, and the two would drift.
649-
650-    The project name is joined because `project_id` alone is a UUID a reader
651-    cannot act on -- the same reason `list_products` carries its counts.
652-    """
653-    return [
654-        dict(r)
655-        for r in session.execute(
656-            text(
657-                """
658-                SELECT b.id, b.attribute, b.competitor_value, b.our_value,
659-                       b.gap_summary, b.project_id, b.formula_version_id,
660:                       b.test_id, b.recorded_by, b.created_at,
661-                       p.name AS project_name, p.project_code
662-                  FROM competitors.benchmarks b
663-                  LEFT JOIN projects.projects p
664-                    ON p.id = b.project_id AND p.organization_id = b.organization_id
665-                 WHERE b.organization_id = :org
666-                   AND b.competitor_product_id = :product
667-                 ORDER BY b.created_at DESC
668-                """
669-            ),
670-            {"org": organization_id, "product": competitor_product_id},
671-        ).mappings()
672-    ]

exec
"C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command 'git show c98420a:apps/api/app/api/competitors.py | rg -n -C 16 "get_benchmarks|post_benchmark|EvidenceCreate|sample_id|test_id"; git show c98420a:apps/web/app/material-safety/competitors/page.tsx | rg -n -C 18 "sample_id|manual_observation|benchmarks|competitor_value|confidence|disclaimer|test.view|canViewTests"' in C:\Users\USER\Documents\evercoat-itw-rd-workspace\EvercoatITWRD APP
 succeeded in 604ms:
74-    product_name: str = Field(min_length=1, max_length=300)
75-    product_code: str | None = Field(default=None, max_length=100)
76-    market_segment: str | None = Field(default=None, max_length=200)
77-    # Optional by design: most competitor products are public and belong to the
78-    # organization rather than to one project.
79-    project_id: uuid.UUID | None = None
80-    notes: str | None = Field(default=None, max_length=4000)
81-
82-
83-class SampleCreate(BaseModel):
84-    sample_reference: str = Field(min_length=1, max_length=100)
85-    acquired_on: dt.date | None = None
86-    batch_marking: str | None = Field(default=None, max_length=200)
87-    observations: str | None = Field(default=None, max_length=4000)
88-
89-
90:class EvidenceCreate(BaseModel):
91-    component_name: str = Field(min_length=1, max_length=300)
92-    # ?? NO `confidence` FIELD. A claim is recorded as `possible` and promoted
93-    # only by a reviewer. Accepting it here would let the caller decide whether
94-    # their own guess counts as verified.
95-    evidence_source: str = Field(
96-        pattern="^(document|manual_observation|laboratory|literature|patent|inference|model)$"
97-    )
98-    evidence_grade: str = Field(pattern="^[ABCDX]$")
99-    cas_number: str | None = Field(default=None, pattern=r"^[0-9]{2,7}-[0-9]{2}-[0-9]$")
100-    component_function: str | None = Field(default=None, max_length=200)
101-    # Strings all the way to PostgreSQL's NUMERIC. A float here would round the
102-    # disclosed range before the database ever saw it (CLAUDE.md ?5).
103-    concentration_low: str | None = Field(default=None, pattern=r"^[0-9]{1,3}(\.[0-9]{1,4})?$")
104-    concentration_high: str | None = Field(default=None, pattern=r"^[0-9]{1,3}(\.[0-9]{1,4})?$")
105-    is_balance: bool = False
106-    source_document_id: uuid.UUID | None = None
107:    sample_id: uuid.UUID | None = None
108:    test_id: uuid.UUID | None = None
109-    source_locator: str | None = Field(default=None, max_length=500)
110-    rationale: str | None = Field(default=None, max_length=4000)
111-
112-
113-class EvidenceGrade(BaseModel):
114-    confidence: str = Field(pattern="^(verified|supported|probable|possible|unknown)$")
115-
116-
117-class BenchmarkCreate(BaseModel):
118-    project_id: uuid.UUID
119-    attribute: str = Field(min_length=1, max_length=200)
120-    gap_summary: str = Field(min_length=1, max_length=2000)
121-    competitor_value: str | None = Field(default=None, max_length=200)
122-    our_value: str | None = Field(default=None, max_length=200)
123-    formula_version_id: uuid.UUID | None = None
124:    test_id: uuid.UUID | None = None
125-
126-
127-def _refuse(exc: CompetitorError) -> HTTPException:
128-    if isinstance(exc, CompetitorNotFoundError):
129-        return HTTPException(status.HTTP_404_NOT_FOUND, str(exc))
130-    if isinstance(exc, CompetitorStateError):
131-        return HTTPException(status.HTTP_409_CONFLICT, str(exc))
132-    return HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc))
133-
134-
135-@router.get("", summary="Competitor products this caller can reach")
136-def get_products(
137-    principal: Principal = Depends(require_permission("material.view")),
138-    session: Session = Depends(get_db),
139-    limit: int = Query(default=200, ge=1, le=500),
140-) -> list[dict[str, Any]]:
--
340-    outright ? so the words travel with the data.
341-    """
342-    return composition_matrix(
343-        session,
344-        organization_id=principal.organization_id,
345-        competitor_product_id=competitor_product_id,
346-    )
347-
348-
349-@router.post(
350-    "/{competitor_product_id}/evidence",
351-    status_code=status.HTTP_201_CREATED,
352-    summary="Record one claim about what the product contains",
353-)
354-def post_evidence(
355-    competitor_product_id: uuid.UUID,
356:    payload: EvidenceCreate,
357-    principal: Principal = Depends(require_permission("material.edit")),
358-    session: Session = Depends(get_db),
359-) -> dict[str, Any]:
360-    """Recorded at `possible`. Promotion is a separate, permissioned act."""
361-    try:
362-        result = record_evidence(
363-            session,
364-            organization_id=principal.organization_id,
365-            actor_id=principal.user_id,
366-            competitor_product_id=competitor_product_id,
367-            spec=EvidenceInput(
368-                component_name=payload.component_name,
369-                evidence_source=payload.evidence_source,
370-                evidence_grade=payload.evidence_grade,
371-                cas_number=payload.cas_number,
372-                component_function=payload.component_function,
373-                concentration_low=payload.concentration_low,
374-                concentration_high=payload.concentration_high,
375-                is_balance=payload.is_balance,
376-                source_document_id=payload.source_document_id,
377:                sample_id=payload.sample_id,
378:                test_id=payload.test_id,
379-                source_locator=payload.source_locator,
380-                rationale=payload.rationale,
381-            ),
382-        )
383-    except CompetitorError as exc:
384-        raise _refuse(exc) from exc
385-    session.commit()
386-    return result
387-
388-
389-@router.post("/evidence/{evidence_id}/grade", summary="Change a claim's confidence")
390-def post_grade(
391-    evidence_id: uuid.UUID,
392-    payload: EvidenceGrade,
393-    principal: Principal = Depends(require_permission("compliance.review_sds")),
394-    session: Session = Depends(get_db),
--
407-            organization_id=principal.organization_id,
408-            reviewer_id=principal.user_id,
409-            evidence_id=evidence_id,
410-            confidence=payload.confidence,
411-        )
412-    except CompetitorError as exc:
413-        raise _refuse(exc) from exc
414-    session.commit()
415-    return result
416-
417-
418-@router.post(
419-    "/{competitor_product_id}/benchmarks",
420-    status_code=status.HTTP_201_CREATED,
421-    summary="Record a measured comparison against our own work",
422-)
423:def post_benchmark(
424-    competitor_product_id: uuid.UUID,
425-    payload: BenchmarkCreate,
426-    principal: Principal = Depends(require_permission("test.view")),
427-    session: Session = Depends(get_db),
428-) -> dict[str, Any]:
429-    """It cites a test; it does not grade one. Testing owns GREEN/YELLOW/RED."""
430-    try:
431-        result = record_benchmark(
432-            session,
433-            organization_id=principal.organization_id,
434-            actor_id=principal.user_id,
435-            competitor_product_id=competitor_product_id,
436-            project_id=payload.project_id,
437-            attribute=payload.attribute,
438-            gap_summary=payload.gap_summary,
439-            competitor_value=payload.competitor_value,
440-            our_value=payload.our_value,
441-            formula_version_id=payload.formula_version_id,
442:            test_id=payload.test_id,
443-        )
444-    except CompetitorError as exc:
445-        raise _refuse(exc) from exc
446-    session.commit()
447-    return result
448-
449-
450-@router.get("/{competitor_product_id}/benchmarks", summary="Measured comparisons on file")
451:def get_benchmarks(
452-    competitor_product_id: uuid.UUID,
453-    principal: Principal = Depends(require_permission("test.view")),
454-    session: Session = Depends(get_db),
455-) -> list[dict[str, Any]]:
456-    """?? `test.view`, MATCHING ITS WRITER ? a benchmark is testing output.
457-
458-    A reader who may not see tests may not see comparisons drawn from them,
459-    which would otherwise be a way to read test results through a side door.
460-    """
461-    return list_benchmarks(
462-        session,
463-        organization_id=principal.organization_id,
464-        competitor_product_id=competitor_product_id,
465-    )
1-"use client";
2-
3-/**
4- * Competitor intelligence ? register a product, upload its label or a
5- * photograph, and build the Composition Evidence Matrix from them.
6- *
7- * ?? THIS SCREEN NEVER SHOWS A COMPETITOR RECIPE.
8- *
9- * The specification is explicit that the application *"shall NEVER
10- * automatically present an inferred competitor recipe as a known or verified
11- * formula"*. What it shows is a matrix of CLAIMS, strongest first, each
12- * carrying how it is known and how far it can be trusted ? and the server's
13: * own disclaimer rendered verbatim above it. Reading the matrix gives a
14- * candidate composition, which is what was asked for; no line of it pretends
15- * to be more than it is.
16- *
17- * ?? THREE ENTRY MODES, AS PEERS.
18- *
19- *   1. Upload the LABEL.
20- *   2. Upload a PHOTOGRAPH of the product.
21- *   3. Type what you read, with no document at all.
22- *
23: * All three land in the same matrix. The third is `manual_observation` ? not
24- * `inference`, because a person reading a tin is observing, not reasoning.
25- * What it cannot be is `verified`, since there is nothing anybody else can
26- * re-check, and the database refuses that combination outright.
27- *
28- * ?? UPLOADING DOES NOT FILL THE MATRIX IN. There is no automatic extraction:
29- * that was a deliberate choice on 2026-08-28 (no OCR dependency, and neither
30- * installed Ollama model reads images). The file is stored as evidence a claim
31- * can CITE, and a person records what it says. A screen that implied otherwise
32- * would be inventing components on somebody's product.
33- */
34-
35-import { useState } from "react";
36-
37-import { DataSourceError, LiveOnlyPage } from "@/components/ui/data-source-banner";
38-import { serverMessage } from "@/lib/api/client";
39-import {
40-  useCompetitorBenchmarks,
41-  useCompetitorDocuments,
--
58-  "disabled:cursor-not-allowed disabled:bg-slate-300";
59-const SECONDARY =
60-  "rounded border border-slate-300 px-3 py-1.5 text-sm font-medium text-slate-800 " +
61-  "hover:bg-slate-100 disabled:cursor-not-allowed disabled:text-slate-400";
62-const INPUT =
63-  "mt-1 w-full rounded border border-slate-300 px-2 py-1.5 text-sm text-slate-900 " +
64-  "focus:border-slate-500 focus:outline-none focus:ring-1 focus:ring-slate-500";
65-const LABEL = "block text-xs font-medium text-slate-700";
66-
67-/**
68- * Confidence, as colour AND icon AND word.
69- *
70- * CLAUDE.md ?11 forbids colour-only status, and here it matters more than
71- * usual: the difference between a verified disclosure and a model's guess is
72- * the entire point of the matrix, and a reader who cannot see colour must get
73- * the same answer.
74- */
75-const CONFIDENCE: Record<
76:  EvidenceRow["confidence"],
77-  { icon: string; label: string; className: string }
78-> = {
79-  verified: {
80-    icon: "?",
81-    label: "Verified",
82-    className: "border-emerald-300 bg-emerald-50 text-emerald-900",
83-  },
84-  supported: {
85-    icon: "+",
86-    label: "Supported",
87-    className: "border-sky-300 bg-sky-50 text-sky-900",
88-  },
89-  probable: {
90-    icon: "~",
91-    label: "Probable",
92-    className: "border-amber-300 bg-amber-50 text-amber-900",
93-  },
94-  possible: {
--
97-    className: "border-slate-300 bg-slate-50 text-slate-800",
98-  },
99-  unknown: {
100-    icon: "?",
101-    label: "Unknown",
102-    className: "border-slate-300 bg-white text-slate-600",
103-  },
104-};
105-
106-function concentration(row: EvidenceRow): string {
107-  if (row.is_balance) return "the balance";
108-  const { concentration_low: low, concentration_high: high } = row;
109-  if (low === null && high === null) return "not disclosed";
110-  if (low !== null && high !== null) return low === high ? `${low}%` : `${low}?${high}%`;
111-  return `${low ?? high}%`;
112-}
113-
114-function MatrixRow({ row }: { row: EvidenceRow }) {
115:  const confidence = CONFIDENCE[row.confidence];
116-  const source = EVIDENCE_SOURCES.find((s) => s.id === row.evidence_source);
117-  return (
118-    <li className="rounded border border-slate-200 bg-white p-3">
119-      <div className="flex flex-wrap items-baseline gap-2">
120-        <span
121:          className={`rounded border px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide ${confidence.className}`}
122-        >
123:          <span aria-hidden="true">{confidence.icon}</span> {confidence.label}
124-        </span>
125-        <h3 className="flex-1 text-sm font-semibold text-slate-900">{row.component_name}</h3>
126-        <span className="text-sm tabular-nums text-slate-800">{concentration(row)}</span>
127-      </div>
128-      <p className="mt-1 text-xs text-slate-600">
129-        {source?.label ?? row.evidence_source} ? grade {row.evidence_grade}
130-        {row.cas_number !== null ? ` ? CAS ${row.cas_number}` : ""}
131-        {row.component_function !== null ? ` ? ${row.component_function}` : ""}
132-      </p>
133-      {row.source_document_title !== null && (
134-        <p className="mt-1 text-xs text-slate-600">
135-          From {row.source_document_type}: {row.source_document_title}
136-          {row.source_locator !== null ? ` (${row.source_locator})` : ""}
137-        </p>
138-      )}
139-      {row.rationale !== null && (
140-        <p className="mt-1 text-xs text-slate-700">{row.rationale}</p>
141-      )}
142-    </li>
143-  );
144-}
145-
146-function ProductWorkspace({ product }: { product: CompetitorProduct }) {
147-  const matrix = useCompositionMatrix(product.id);
148-  const documents = useCompetitorDocuments(product.id);
149-  const samples = useCompetitorSamples(product.id);
150:  const benchmarks = useCompetitorBenchmarks(product.id);
151-  // ?? A BENCHMARK NEEDS A PROJECT, AND ASKING FOR A UUID IS NOT ASKING.
152-  // The register-a-member form on Projects still demands one typed by hand
153-  // and it is a standing complaint; this form does not repeat it.
154-  const projectList = useProjects<Project[]>([], (live) => live);
155-  const writes = useCompetitorWrites();
156-
157-  const [file, setFile] = useState<File | null>(null);
158-  const [documentType, setDocumentType] = useState("label");
159-  const [docTitle, setDocTitle] = useState("");
160-
161-  const [component, setComponent] = useState("");
162-  const [cas, setCas] = useState("");
163-  const [low, setLow] = useState("");
164-  const [high, setHigh] = useState("");
165:  const [evidenceSource, setEvidenceSource] = useState("manual_observation");
166-  const [grade, setGrade] = useState("C");
167-  const [sourceDocumentId, setSourceDocumentId] = useState("");
168-  const [sampleId, setSampleId] = useState("");
169-  const [locator, setLocator] = useState("");
170-  const [rationale, setRationale] = useState("");
171-
172-  const [sampleReference, setSampleReference] = useState("");
173-  const [acquiredOn, setAcquiredOn] = useState("");
174-  const [batchMarking, setBatchMarking] = useState("");
175-  const [sampleNotes, setSampleNotes] = useState("");
176-
177-  const [benchProject, setBenchProject] = useState("");
178-  const [benchAttribute, setBenchAttribute] = useState("");
179-  const [benchTheirs, setBenchTheirs] = useState("");
180-  const [benchOurs, setBenchOurs] = useState("");
181-  const [benchGap, setBenchGap] = useState("");
182-
183-  const needsDocument = evidenceSource === "document";
184-  // An observation was made ON something. Until this screen could name the
185:  // tin, every `manual_observation` was recorded with a null `sample_id`
186-  // that the server had always accepted and no client had ever sent.
187:  const isObservation = evidenceSource === "manual_observation";
188-  const docs = documents.data ?? [];
189-  const tins = samples.data ?? [];
190:  const comparisons = benchmarks.data ?? [];
191-  const projects = projectList.data ?? [];
192-
193-  return (
194-    <div className="grid gap-6">
195-      <section aria-labelledby="upload-heading">
196-        <h3 id="upload-heading" className="text-sm font-semibold text-slate-900">
197-          Upload a label or a photograph
198-        </h3>
199-        <p className="mt-1 text-xs text-slate-600">
200-          Stored through the same controlled document register a Safety Data Sheet
201-          goes through: validated against its real bytes, malware-scanned,
202-          checksummed. It is kept as evidence a claim can <em>cite</em> ? it does
203-          not fill the matrix in by itself.
204-        </p>
205-        <div className="mt-3 grid gap-3 rounded border border-slate-200 bg-white p-4 sm:grid-cols-2">
206-          <div>
207-            <label className={LABEL} htmlFor="doc-kind">
208-              What is it
--
557-              className={INPUT}
558-              rows={2}
559-              value={rationale}
560-              onChange={(event) => setRationale(event.target.value)}
561-            />
562-          </div>
563-
564-          <div className="sm:col-span-2">
565-            <button
566-              type="button"
567-              className={BUTTON}
568-              disabled={
569-                writes.isPending ||
570-                component.trim() === "" ||
571-                (needsDocument && sourceDocumentId === "") ||
572-                /* An observation or an inference must say what it rests on --
573-                   the database refuses it otherwise, so the form should too
574-                   rather than sending a request that cannot succeed. */
575:                (["manual_observation", "inference", "model"].includes(evidenceSource) &&
576-                  rationale.trim() === "")
577-              }
578-              onClick={() =>
579-                writes.recordEvidence(
580-                  product.id,
581-                  {
582-                    component_name: component.trim(),
583-                    evidence_source: evidenceSource,
584-                    evidence_grade: grade,
585-                    ...(cas.trim() ? { cas_number: cas.trim() } : {}),
586-                    ...(low.trim() ? { concentration_low: low.trim() } : {}),
587-                    ...(high.trim() ? { concentration_high: high.trim() } : {}),
588-                    ...(needsDocument ? { source_document_id: sourceDocumentId } : {}),
589:                    ...(isObservation && sampleId !== "" ? { sample_id: sampleId } : {}),
590-                    ...(locator.trim() ? { source_locator: locator.trim() } : {}),
591-                    ...(rationale.trim() ? { rationale: rationale.trim() } : {}),
592-                  },
593-                  () => {
594-                    setComponent("");
595-                    setSampleId("");
596-                    setCas("");
597-                    setLow("");
598-                    setHigh("");
599-                    setLocator("");
600-                    setRationale("");
601-                  },
602-                )
603-              }
604-            >
605-              Add to the evidence matrix
606-            </button>
607-          </div>
--
609-      </section>
610-
611-      <section aria-labelledby="matrix-heading">
612-        <h3 id="matrix-heading" className="text-sm font-semibold text-slate-900">
613-          Composition Evidence Matrix
614-        </h3>
615-        {matrix.error !== null ? (
616-          <DataSourceError error={matrix.error} />
617-        ) : matrix.data === undefined ? (
618-          <p className="mt-2 text-sm text-slate-600">
619-            {matrix.isLoading ? "Loading the matrix?" : ""}
620-          </p>
621-        ) : (
622-          <>
623-            {/* ?? THE SERVER'S OWN WORDS, RENDERED VERBATIM. Not a sentence
624-                this screen composes: a screen that forgot it would be
625-                presenting an inferred recipe as a known one. */}
626-            <p className="mt-2 rounded border border-amber-300 bg-amber-50 px-3 py-2 text-xs text-amber-900">
627:              {matrix.data.disclaimer}
628-            </p>
629-
630-            {Object.keys(matrix.data.summary).length > 0 && (
631-              <p className="mt-2 text-xs text-slate-700">
632-                {Object.entries(matrix.data.summary)
633-                  .map(([key, count]) => `${count} ${key}`)
634-                  .join(" ? ")}
635-              </p>
636-            )}
637-
638-            {matrix.data.rows.length === 0 ? (
639-              <p className="mt-3 text-sm text-slate-600">
640-                Nothing recorded yet. Upload a label or type what you can read,
641-                above.
642-              </p>
643-            ) : (
644-              <ul className="mt-3 grid gap-2">
645-                {matrix.data.rows.map((row) => (
--
730-          </div>
731-          <div className="sm:col-span-2">
732-            <button
733-              type="button"
734-              className={BUTTON}
735-              disabled={
736-                writes.isPending ||
737-                benchProject === "" ||
738-                benchAttribute.trim() === "" ||
739-                benchGap.trim() === ""
740-              }
741-              onClick={() =>
742-                writes.recordBenchmark(
743-                  product.id,
744-                  {
745-                    project_id: benchProject,
746-                    attribute: benchAttribute.trim(),
747-                    gap_summary: benchGap.trim(),
748:                    ...(benchTheirs.trim() ? { competitor_value: benchTheirs.trim() } : {}),
749-                    ...(benchOurs.trim() ? { our_value: benchOurs.trim() } : {}),
750-                  },
751-                  () => {
752-                    setBenchAttribute("");
753-                    setBenchTheirs("");
754-                    setBenchOurs("");
755-                    setBenchGap("");
756-                  },
757-                )
758-              }
759-            >
760-              Record the comparison
761-            </button>
762-          </div>
763-        </div>
764-
765:        {benchmarks.error !== null ? (
766:          <DataSourceError error={benchmarks.error} />
767-        ) : comparisons.length === 0 ? (
768-          <p className="mt-3 text-sm text-slate-600">No comparisons recorded yet.</p>
769-        ) : (
770-          <ul className="mt-3 grid gap-2">
771-            {comparisons.map((row) => (
772-              <li
773-                key={row.id}
774-                className="rounded border border-slate-200 bg-white px-3 py-2 text-xs text-slate-700"
775-              >
776-                <span className="font-medium text-slate-900">{row.attribute}</span>
777-                {row.project_code !== null && <> ? {row.project_code}</>}
778-                <span className="mt-1 block">
779:                  Theirs {row.competitor_value ?? "not stated"} ? ours{" "}
780-                  {row.our_value ?? "not stated"}
781-                </span>
782-                <span className="mt-1 block text-slate-600">{row.gap_summary}</span>
783-              </li>
784-            ))}
785-          </ul>
786-        )}
787-      </section>
788-    </div>
789-  );
790-}
791-
792-export default function CompetitorsPage() {
793-  const products = useCompetitorProducts();
794-  const writes = useCompetitorWrites();
795-  const [openId, setOpenId] = useState<string | null>(null);
796-  const [manufacturer, setManufacturer] = useState("");
797-  const [productName, setProductName] = useState("");

exec
"C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command 'git show c98420a:apps/api/tests/db/test_056_competitor_intelligence.py | rg -n -C 14 "manual_observation|sample_id|evidence_source|constraint|DROP|FORCE|cross.tenant|restricted|benchmark|usable_documents|supersedes|security_invoker"' in C:\Users\USER\Documents\evercoat-itw-rd-workspace\EvercoatITWRD APP
 succeeded in 866ms:
1-"""Migration 056 ? the competitor register and the Composition Evidence Matrix.
2-
3-?? WRITTEN BECAUSE `4e32a54` CLAIMED THREE HOLES CLOSED AND ASSERTED NONE OF THEM.
4-
5-The commit message states that the review found, before any of it was written:
6-
7:  1. `supersedes_id` constrained the tenant but not the OWNER, so a competitor
8-     label could supersede a material's Safety Data Sheet ? removing that SDS
9:     from `materials.usable_documents`, which decides whether a formula may be
10-     submitted.
11-  2. The write-once set protected the BYTES but not the OWNER, so an approved,
12-     scan-clean label could be re-pointed at a different product and carry its
13-     clean verdict there.
14-  3. The product-bound composite foreign key on evidence needed a unique key
15-     that did not exist, without which a label for product A could back a claim
16-     about product B.
17-
18-All three were fixed in the migration. None was exercised by a test, so all
19-three were claims rather than measurements. This project's standing lesson is
20-that **a test which has only ever PASSED has not been shown to detect
21-anything**, so every guard below is exercised in BOTH directions: the legal
22-case must succeed and the illegal case must be refused, for the stated reason.
23-
--
86-            RETURNING id
87-            """
88-        ),
89-        {"o": org_id, "code": f"RM-{suffix}", "u": user_id},
90-    ).scalar_one()
91-
92-    project_id = owner_session.execute(
93-        text(
94-            "INSERT INTO projects.projects (organization_id, project_code, name) "
95-            "VALUES (:o, :c, 'Benchmark project') RETURNING id"
96-        ),
97-        {"o": org_id, "c": f"PRJ-{suffix}"},
98-    ).scalar_one()
99-
100:    # FORCE RLS binds the table owner too, so even this session must declare
101-    # its tenant. Without it the INSERTs below fail with "new row violates
102-    # row-level security policy" -- the guard working, not a defect.
103-    owner_session.execute(
104-        text("SELECT set_config('app.current_org', :o, true)"), {"o": str(org_id)}
105-    )
106-    owner_session.execute(
107-        text("SELECT set_config('app.current_user_id', :u, true)"), {"u": str(user_id)}
108-    )
109-
110-    product_a = _make_product(owner_session, org_id, user_id, f"A-{suffix}")
111-    product_b = _make_product(owner_session, org_id, user_id, f"B-{suffix}")
112-
113-    sds_id = _make_document(owner_session, org_id, user_id, suffix, "SDS", material_id=material_id)
114-    label_a = _make_document(
--
140-        ),
141-        {"o": org_id, "n": name, "u": user_id},
142-    ).scalar_one()
143-
144-
145-def _make_document(
146-    session: Session,
147-    org_id: uuid.UUID,
148-    user_id: uuid.UUID,
149-    suffix: str,
150-    document_type: str,
151-    *,
152-    material_id: uuid.UUID | None = None,
153-    competitor_product_id: uuid.UUID | None = None,
154:    supersedes_id: uuid.UUID | None = None,
155-) -> uuid.UUID:
156-    """An APPROVED, scan-clean, unexpired document owned by exactly one thing.
157-
158-    Every column 036's `material_documents_approved_has_evidence` demands is
159:    supplied, so the row genuinely appears in `materials.usable_documents`.
160-    A quarantined fixture row would make the refusals pass for the wrong reason.
161-    """
162-    return session.execute(  # type: ignore[no-any-return]
163-        text(
164-            """
165-            INSERT INTO materials.material_documents
166-                (organization_id, material_id, competitor_product_id, document_type,
167-                 title, storage_key, content_type, byte_size, checksum_sha256,
168-                 status, scan_status, scanner_name, scanner_version, scanned_at,
169:                 supersedes_id, uploaded_by)
170-            VALUES (:o, :m, :cp, :dt, :title, :key, 'application/pdf', 2048,
171-                    :checksum, 'approved', 'clean', 'test-scanner', '1.0', now(),
172-                    :sup, :u)
173-            RETURNING id
174-            """
175-        ),
176-        {
177-            "o": org_id,
178-            "m": material_id,
179-            "cp": competitor_product_id,
180-            "dt": document_type,
181-            "title": f"{document_type} for testing",
182-            "key": f"test/{document_type}-{suffix}-{uuid.uuid4().hex[:6]}",
183-            "checksum": uuid.uuid4().hex + uuid.uuid4().hex,
184:            "sup": supersedes_id,
185-            "u": user_id,
186-        },
187-    ).scalar_one()
188-
189-
190-def _claim(session: Session, fx: dict[str, uuid.UUID], **overrides: object) -> uuid.UUID:
191-    """A document-sourced claim on product A, which is the legal shape."""
192-    params: dict[str, object] = {
193-        "o": fx["org_id"],
194-        "p": overrides.get("competitor_product_id", fx["product_a"]),
195-        "d": overrides.get("source_document_id", fx["label_a"]),
196:        "src": overrides.get("evidence_source", "document"),
197-        "conf": overrides.get("confidence", "possible"),
198-        "vby": overrides.get("verified_by"),
199-        "vat": overrides.get("verified_at"),
200-        "u": fx["user_id"],
201-        "name": overrides.get("component_name", "Styrene"),
202-    }
203-    return session.execute(  # type: ignore[no-any-return]
204-        text(
205-            """
206-            INSERT INTO competitors.composition_evidence
207-                (organization_id, competitor_product_id, component_name,
208:                 evidence_source, evidence_grade, confidence, source_document_id,
209-                 source_locator, verified_by, verified_at, recorded_by)
210-            VALUES (:o, :p, :name, :src, 'A', :conf, :d,
211-                    'Section 3, ingredient table', :vby, CAST(:vat AS TIMESTAMPTZ), :u)
212-            RETURNING id
213-            """
214-        ),
215-        params,
216-    ).scalar_one()
217-
218-
219-def _grant_review_sds(session: Session, fx: dict[str, uuid.UUID]) -> None:
220-    """Give the fixture's member a role actually carrying `compliance.review_sds`.
221-
222-    Built rather than looked up: a test that depended on a seeded role holding
--
251-
252-
253-def test_a_document_may_supersede_one_with_the_same_owner(
254-    owner_session: Session, competitor_fixture
255-) -> None:
256-    """The legal case. Without it the refusal below proves only that something broke."""
257-    fx = competitor_fixture
258-    revision = _make_document(
259-        owner_session,
260-        fx["org_id"],
261-        fx["user_id"],
262-        "rev",
263-        "label",
264-        competitor_product_id=fx["product_a"],
265:        supersedes_id=fx["label_a"],
266-    )
267-    assert revision is not None
268-
269-
270-def test_a_competitor_label_cannot_supersede_a_materials_sds(
271-    owner_session: Session, competitor_fixture
272-) -> None:
273-    """?? THE HOLE THAT REACHED THE FORMULA-SUBMISSION GATE.
274-
275:    `materials.usable_documents` excludes a document a newer approved revision
276:    supersedes, and the formula-submission gate reads that view. So superseding
277-    ACROSS owners would have let an upload against a competitor product remove a
278-    material's SDS from the view -- changing whether a formula may be submitted,
279-    on the strength of an unrelated file.
280-    """
281-    fx = competitor_fixture
282-    with pytest.raises(DBAPIError) as caught:
283-        _make_document(
284-            owner_session,
285-            fx["org_id"],
286-            fx["user_id"],
287-            "cross",
288-            "label",
289-            competitor_product_id=fx["product_a"],
290:            supersedes_id=fx["sds_id"],  # a MATERIAL's document
291-        )
292-    assert "SAME owner" in str(caught.value)
293-
294-
295-def test_the_superseded_sds_is_still_usable_after_the_refusal(
296-    owner_session: Session, competitor_fixture
297-) -> None:
298-    """?? THE POINT OF THE GUARD, ASSERTED AS AN OUTCOME RATHER THAN A MESSAGE.
299-
300-    Checking only that an exception was raised would leave the actual claim --
301-    that the SDS remains submittable -- unmeasured. This asserts the CONSEQUENCE.
302-    """
303-    fx = competitor_fixture
304-    owner_session.execute(text("SAVEPOINT before_cross_owner"))
305-    with pytest.raises(DBAPIError):
306-        _make_document(
307-            owner_session,
308-            fx["org_id"],
309-            fx["user_id"],
310-            "cross2",
311-            "label",
312-            competitor_product_id=fx["product_a"],
313:            supersedes_id=fx["sds_id"],
314-        )
315-    owner_session.execute(text("ROLLBACK TO SAVEPOINT before_cross_owner"))
316-
317-    still_usable = owner_session.execute(
318:        text("SELECT count(*) FROM materials.usable_documents WHERE id = :d"),
319-        {"d": fx["sds_id"]},
320-    ).scalar_one()
321:    assert still_usable == 1, "the SDS left usable_documents despite the refusal"
322-
323-
324-# ---------------------------------------------------------------------------
325-# HOLE 2 ? the owner is write-once
326-# ---------------------------------------------------------------------------
327-
328-
329-def test_a_scanned_label_cannot_be_re_pointed_at_another_product(
330-    owner_session: Session, competitor_fixture
331-) -> None:
332-    """An approved, scan-clean label must not carry its verdict to a different product."""
333-    fx = competitor_fixture
334-    with pytest.raises(DBAPIError) as caught:
335-        owner_session.execute(
336-            text(
337-                "UPDATE materials.material_documents SET competitor_product_id = :b "
338-                "WHERE id = :d"
339-            ),
340-            {"b": fx["product_b"], "d": fx["label_a"]},
341-        )
342-    assert "write-once" in str(caught.value)
343-
344-
345-def test_a_document_cannot_be_re_owned_from_a_competitor_to_a_material(
346-    owner_session: Session, competitor_fixture
347-) -> None:
348:    """The other half of the rule ? and ?? A DIFFERENT TRIGGER ENFORCES IT.
349-
350-    MEASURED, not assumed. Triggers fire in NAME order, and
351-    `material_documents_evidence_write_once` (038) sorts before
352-    `material_documents_owner_write_once` (056). 038 already refuses a move to
353-    another material, so on this path it fires first and 056's `material_id`
354-    branch never executes ? it is unreachable defence-in-depth.
355-
356-    056's `competitor_product_id` branch IS load-bearing: 038 checks material,
357-    organization and document type only, so nothing but 056 stops a label being
358-    re-pointed at another product. The preceding test is the one that measures
359-    the new guard; this one measures that the OUTCOME holds either way.
360-
361-    Asserting the refusal message here would tie the test to whichever trigger
362-    happens to sort first, so it asserts the consequence: the document still
--
408-# ---------------------------------------------------------------------------
409-
410-
411-def test_a_document_can_back_a_claim_about_its_own_product(
412-    owner_session: Session, competitor_fixture
413-) -> None:
414-    """The legal case for the composite foreign key."""
415-    fx = competitor_fixture
416-    assert _claim(owner_session, fx) is not None
417-
418-
419-def test_a_label_for_product_a_cannot_back_a_claim_about_product_b(
420-    owner_session: Session, competitor_fixture
421-) -> None:
422:    """?? T2b. The composite FK is the mechanism; every other constraint holds."""
423-    fx = competitor_fixture
424-    with pytest.raises(IntegrityError) as caught:
425-        _claim(owner_session, fx, competitor_product_id=fx["product_b"])
426-    assert "composition_evidence_document_fk" in str(caught.value)
427-
428-
429-def test_the_unique_key_the_composite_foreign_key_needs_exists(
430-    owner_session: Session, competitor_fixture
431-) -> None:
432-    """?? ASSERT THE THING EXISTS BEFORE TRUSTING A PROPERTY OF IT.
433-
434-    The FK above is only expressible because 056 added
435:    `material_documents_id_competitor_org_key`. Reading it from `pg_constraint`
436-    rather than from the migration text: the file existing is not the schema.
437-    """
438-    kind = owner_session.execute(
439-        text(
440:            "SELECT contype FROM pg_constraint "
441-            "WHERE conname = 'material_documents_id_competitor_org_key'"
442-        )
443-    ).scalar_one_or_none()
444-    assert kind == "u", "the unique key the evidence FK depends on is missing"
445-
446-
447-# ---------------------------------------------------------------------------
448-# T2a / T2c ? `verified` is not something a writer may assert about itself
449-# ---------------------------------------------------------------------------
450-
451-
452-def test_verified_requires_both_a_verifier_and_a_time(
453-    owner_session: Session, competitor_fixture
454-) -> None:
455-    """T2c. `verified_by` alone is not verification, and neither is a bare flag.
456-
457-    ?? THE PERMISSION MUST BE GRANTED FIRST TO REACH THE CONSTRAINT AT ALL.
458:    A `BEFORE INSERT` trigger runs before row constraints are evaluated, so
459-    without the grant this refusal comes from `verification_names_a_reviewer`
460-    and the CHECK is never exercised ? the test would pass while measuring a
461-    different mechanism entirely.
462-    """
463-    fx = competitor_fixture
464-    _grant_review_sds(owner_session, fx)
465-    with pytest.raises(IntegrityError) as caught:
466-        _claim(owner_session, fx, confidence="verified", verified_by=fx["user_id"])
467-    assert "composition_evidence_verification_complete" in str(caught.value)
468-
469-
470-def test_a_verifier_and_a_time_without_verified_is_also_refused(
471-    owner_session: Session, competitor_fixture
472-) -> None:
473:    """?? BOTH DIRECTIONS. The constraint is an equivalence, not an implication.
474-
475-    A row carrying a verifier and a timestamp while claiming `possible` would
476-    read, to anybody scanning the table, as a verified claim that had been
477-    quietly downgraded.
478-    """
479-    fx = competitor_fixture
480-    with pytest.raises(IntegrityError) as caught:
481-        _claim(
482-            owner_session,
483-            fx,
484-            confidence="possible",
485-            verified_by=fx["user_id"],
486-            verified_at="2026-08-28T00:00:00Z",
487-        )
--
494-    """T2a. There is nothing anybody else can re-check, so the grade is unearnable.
495-
496-    A person reading the back of a tin is making an honest observation. What
497-    they cannot do is certify it, and the database ? not the screen ? is what
498-    says so.
499-    """
500-    fx = competitor_fixture
501-    _grant_review_sds(owner_session, fx)
502-    with pytest.raises(IntegrityError) as caught:
503-        owner_session.execute(
504-            text(
505-                """
506-                INSERT INTO competitors.composition_evidence
507-                    (organization_id, competitor_product_id, component_name,
508:                     evidence_source, evidence_grade, confidence, rationale,
509-                     observed_by, verified_by, verified_at, recorded_by)
510:                VALUES (:o, :p, 'Talc', 'manual_observation', 'C', 'verified',
511-                        'Read from the back of the tin', :u, :u, now(), :u)
512-                """
513-            ),
514-            {"o": fx["org_id"], "p": fx["product_a"], "u": fx["user_id"]},
515-        )
516-    assert "composition_evidence_verifiable_source" in str(caught.value)
517-
518-
519-def test_the_named_verifier_must_actually_hold_the_permission(
520-    owner_session: Session, competitor_fixture
521-) -> None:
522-    """?? THE TRIGGER, AND IT IS A MISUSE BARRIER RATHER THAN A BOUNDARY.
523-
524-    Anybody who can already run SQL as this role can grant themselves the role
--
553-        fx,
554-        confidence="verified",
555-        verified_by=fx["user_id"],
556-        verified_at="2026-08-28T00:00:00Z",
557-    )
558-    assert claim_id is not None
559-
560-
561-# ---------------------------------------------------------------------------
562-# T3a / T8 ? reach, counted as what a user can reach
563-# ---------------------------------------------------------------------------
564-
565-
566-def test_every_competitor_table_forces_row_level_security(owner_session: Session) -> None:
567:    """T8. FORCE from birth: the policies bind the table OWNER too.
568-
569-    Read from `pg_class`, not from the migration text ? the database in front
570-    of you is not the schema, and a migration is not applied because a file
571-    exists.
572-    """
573-    rows = owner_session.execute(
574-        text(
575-            "SELECT c.relname, c.relrowsecurity, c.relforcerowsecurity "
576-            "  FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace "
577-            " WHERE n.nspname = 'competitors' AND c.relkind = 'r' ORDER BY c.relname"
578-        )
579-    ).all()
580-    assert len(rows) == 4, f"expected four competitor tables, found {len(rows)}"
581-    unforced = [r[0] for r in rows if not (r[1] and r[2])]
582:    assert not unforced, f"these competitor tables are not FORCE RLS: {unforced}"
583-
584-
585-def test_another_organization_reaches_none_of_it(
586-    owner_session: Session, app_session: Session, competitor_fixture
587-) -> None:
588-    """?? T3a ? COUNTED AS WHAT A USER CAN REACH, NOT BY READING A POLICY.
589-
590-    A policy can be present and still not apply. This asks the runtime role,
591-    under a different tenant, how many rows it can actually see.
592-    """
593-    fx = competitor_fixture
594-    owner_session.commit()
595-
596-    other_org = uuid.uuid4()
597-    app_session.execute(
598-        text("SELECT set_config('app.current_org', :o, true)"), {"o": str(other_org)}
599-    )
600-
601-    for table in (
602-        "competitors.products",
603-        "competitors.samples",
604-        "competitors.composition_evidence",
605:        "competitors.benchmarks",
606-    ):
607-        reachable = app_session.execute(
608-            text(f"SELECT count(*) FROM {table} WHERE organization_id = :o"),
609-            {"o": fx["org_id"]},
610-        ).scalar_one()
611-        assert reachable == 0, f"another organization reached {reachable} rows of {table}"
612-
613-
614-def test_the_owning_organization_does_reach_its_own_product(
615-    owner_session: Session, app_session: Session, competitor_fixture
616-) -> None:
617-    """?? THE OTHER DIRECTION OF T3a.
618-
619-    Without it, the zeros above would also be produced by a policy that hides
--
641-
642-
643-def test_there_is_no_second_document_table(owner_session: Session) -> None:
644-    """?14: *"do not build a second document repository"*, asserted rather than intended."""
645-    forked = owner_session.execute(
646-        text(
647-            "SELECT count(*) FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace "
648-            " WHERE n.nspname = 'competitors' AND c.relkind = 'r' "
649-            "   AND c.relname LIKE '%document%'"
650-        )
651-    ).scalar_one()
652-    assert forked == 0, "a second document repository exists in the competitors schema"
653-
654-
655:def test_usable_documents_kept_security_invoker(owner_session: Session) -> None:
656-    """?? 056 RECREATED THE VIEW THE FORMULA-SUBMISSION GATE READS.
657-
658:    `security_invoker = true` is what makes the view honour the CALLER's RLS.
659-    Recreating a view silently drops its options, and the loss would be
660-    invisible: every query would keep working, and would return more rows.
661-    """
662-    options = owner_session.execute(
663-        text(
664-            "SELECT c.reloptions FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace "
665:            " WHERE n.nspname = 'materials' AND c.relname = 'usable_documents'"
666-        )
667-    ).scalar_one()
668-    assert options is not None and any(
669:        "security_invoker=true" in str(opt) for opt in options
670:    ), f"usable_documents lost security_invoker; reloptions = {options}"

exec
"C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command 'git show c98420a:apps/web/app/material-safety/competitors/page.tsx | Select-Object -Skip 390 -First 180; git show c98420a:apps/api/tests/db/test_056_competitor_intelligence.py | Select-Object -Skip 560 -First 90; git show c98420a:apps/api/app/domains/competitor_intelligence/service.py | Select-Object -First 240' in C:\Users\USER\Documents\evercoat-itw-rd-workspace\EvercoatITWRD APP
2026-08-28T21:56:00.493229Z ERROR codex_core::tools::router: error=Exit code: 1
Wall time: 1.2 seconds
Output:
      </section>

      <section aria-labelledby="claim-heading">
        <h3 id="claim-heading" className="text-sm font-semibold text-slate-900">
          Record what it contains
        </h3>
        <p className="mt-1 text-xs text-slate-600">
          Every claim is recorded as <strong>possible</strong>. Only a reviewer
          holding <code className="text-[11px]">compliance.review_sds</code> can
          raise one to verified, and only when it cites a document or a
          laboratory result.
        </p>
        <div className="mt-3 grid gap-3 rounded border border-slate-200 bg-white p-4 sm:grid-cols-2">
          <div>
            <label className={LABEL} htmlFor="ev-component">
              Component
            </label>
            <input
              id="ev-component"
              className={INPUT}
              value={component}
              onChange={(event) => setComponent(event.target.value)}
              placeholder="Styrene"
            />
          </div>
          <div>
            <label className={LABEL} htmlFor="ev-cas">
              CAS number
            </label>
            <input
              id="ev-cas"
              className={INPUT}
              value={cas}
              onChange={(event) => setCas(event.target.value)}
              placeholder="100-42-5"
            />
          </div>
          <div>
            <label className={LABEL} htmlFor="ev-low">
              From (%)
            </label>
            {/* Text, not number: a float would round the disclosed range. */}
            <input
              id="ev-low"
              className={INPUT}
              inputMode="decimal"
              value={low}
              onChange={(event) => setLow(event.target.value)}
            />
          </div>
          <div>
            <label className={LABEL} htmlFor="ev-high">
              To (%)
            </label>
            <input
              id="ev-high"
              className={INPUT}
              inputMode="decimal"
              value={high}
              onChange={(event) => setHigh(event.target.value)}
            />
          </div>
          <div>
            <label className={LABEL} htmlFor="ev-source">
              How is this known
            </label>
            <select
              id="ev-source"
              className={INPUT}
              value={evidenceSource}
              onChange={(event) => setEvidenceSource(event.target.value)}
            >
              {EVIDENCE_SOURCES.map((source) => (
                <option key={source.id} value={source.id}>
                  {source.label}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label className={LABEL} htmlFor="ev-grade">
              Evidence grade
            </label>
            <select
              id="ev-grade"
              className={INPUT}
              value={grade}
              onChange={(event) => setGrade(event.target.value)}
            >
              {EVIDENCE_GRADES.map((g) => (
                <option key={g.id} value={g.id}>
                  {g.label}
                </option>
              ))}
            </select>
          </div>

          {needsDocument && (
            <div className="sm:col-span-2">
              <label className={LABEL} htmlFor="ev-doc">
                Which document
              </label>
              <select
                id="ev-doc"
                className={INPUT}
                value={sourceDocumentId}
                onChange={(event) => setSourceDocumentId(event.target.value)}
              >
                <option value="">Choose one of the uploads above…</option>
                {docs.map((doc) => (
                  <option key={doc.id} value={doc.id}>
                    {doc.document_type} — {doc.title}
                  </option>
                ))}
              </select>
              {docs.length === 0 && (
                <p className="mt-1 text-xs text-slate-600">
                  Nothing is uploaded yet, so no claim can cite a document.
                </p>
              )}
            </div>
          )}

          {isObservation && (
            <div className="sm:col-span-2">
              <label className={LABEL} htmlFor="ev-sample">
                Which sample did you read
              </label>
              <select
                id="ev-sample"
                className={INPUT}
                value={sampleId}
                onChange={(event) => setSampleId(event.target.value)}
              >
                <option value="">
                  {tins.length === 0
                    ? "No samples registered yet"
                    : "Not recorded against a sample"}
                </option>
                {tins.map((tin) => (
                  <option key={tin.id} value={tin.id}>
                    {tin.sample_reference}
                    {tin.batch_marking !== null ? ` — batch ${tin.batch_marking}` : ""}
                  </option>
                ))}
              </select>
            </div>
          )}
          <div className="sm:col-span-2">
            <label className={LABEL} htmlFor="ev-locator">
              Where exactly {needsDocument ? "in the document" : "on the product"}
            </label>
            <input
              id="ev-locator"
              className={INPUT}
              value={locator}
              onChange={(event) => setLocator(event.target.value)}
              placeholder="Section 3, ingredient table / back of tin, small print"
            />
          </div>
          <div className="sm:col-span-2">
            <label className={LABEL} htmlFor="ev-rationale">
              What you saw, or what you reasoned from
            </label>
            <textarea
              id="ev-rationale"
              className={INPUT}
              rows={2}
              value={rationale}
              onChange={(event) => setRationale(event.target.value)}
            />
          </div>

          <div className="sm:col-span-2">
            <button
              type="button"
              className={BUTTON}
              disabled={
                writes.isPending ||
                component.trim() === "" ||
# ---------------------------------------------------------------------------
# T3a / T8 — reach, counted as what a user can reach
# ---------------------------------------------------------------------------


def test_every_competitor_table_forces_row_level_security(owner_session: Session) -> None:
    """T8. FORCE from birth: the policies bind the table OWNER too.

    Read from `pg_class`, not from the migration text — the database in front
    of you is not the schema, and a migration is not applied because a file
    exists.
    """
    rows = owner_session.execute(
        text(
            "SELECT c.relname, c.relrowsecurity, c.relforcerowsecurity "
            "  FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace "
            " WHERE n.nspname = 'competitors' AND c.relkind = 'r' ORDER BY c.relname"
        )
    ).all()
    assert len(rows) == 4, f"expected four competitor tables, found {len(rows)}"
    unforced = [r[0] for r in rows if not (r[1] and r[2])]
    assert not unforced, f"these competitor tables are not FORCE RLS: {unforced}"


def test_another_organization_reaches_none_of_it(
    owner_session: Session, app_session: Session, competitor_fixture
) -> None:
    """🔴 T3a — COUNTED AS WHAT A USER CAN REACH, NOT BY READING A POLICY.

    A policy can be present and still not apply. This asks the runtime role,
    under a different tenant, how many rows it can actually see.
    """
    fx = competitor_fixture
    owner_session.commit()

    other_org = uuid.uuid4()
    app_session.execute(
        text("SELECT set_config('app.current_org', :o, true)"), {"o": str(other_org)}
    )

    for table in (
        "competitors.products",
        "competitors.samples",
        "competitors.composition_evidence",
        "competitors.benchmarks",
    ):
        reachable = app_session.execute(
            text(f"SELECT count(*) FROM {table} WHERE organization_id = :o"),
            {"o": fx["org_id"]},
        ).scalar_one()
        assert reachable == 0, f"another organization reached {reachable} rows of {table}"


def test_the_owning_organization_does_reach_its_own_product(
    owner_session: Session, app_session: Session, competitor_fixture
) -> None:
    """🔴 THE OTHER DIRECTION OF T3a.

    Without it, the zeros above would also be produced by a policy that hides
    the table from everybody — or by a fixture that never committed a row.
    """
    fx = competitor_fixture
    owner_session.commit()

    app_session.execute(
        text("SELECT set_config('app.current_org', :o, true)"), {"o": str(fx["org_id"])}
    )
    app_session.execute(
        text("SELECT set_config('app.current_user_id', :u, true)"), {"u": str(fx["user_id"])}
    )
    reachable = app_session.execute(
        text("SELECT count(*) FROM competitors.products WHERE organization_id = :o"),
        {"o": fx["org_id"]},
    ).scalar_one()
    assert reachable == 2, f"the owning organization reached {reachable} of its 2 products"


# ---------------------------------------------------------------------------
# The register was EXTENDED, not forked — §14
# ---------------------------------------------------------------------------


def test_there_is_no_second_document_table(owner_session: Session) -> None:
    """§14: *"do not build a second document repository"*, asserted rather than intended."""
    forked = owner_session.execute(
        text(
            "SELECT count(*) FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace "
            " WHERE n.nspname = 'competitors' AND c.relkind = 'r' "
            "   AND c.relname LIKE '%document%'"
        )
"""Competitor intelligence: products, samples, and the Composition Evidence Matrix.

🔴 THE ONE RULE THIS MODULE EXISTS TO KEEP

The specification, on competitor formulation analysis:

    "Safety Data Sheets often disclose only hazardous components or
     concentration ranges and normally do not reveal a complete proprietary
     formulation. The application shall therefore NEVER automatically present
     an inferred competitor recipe as a known or verified formula."

So there is no competitor formula anywhere in this module. There is a matrix of
CLAIMS, each carrying how it is known and how far it can be trusted. Reading the
matrix end to end gives a candidate composition — which is what the operator
asked for — and every line of it says what it rests on.

The purpose is stated in the same section and is worth keeping in view: this is
not for reconstructing somebody's proprietary information. It is for
understanding comparable chemistry, likely material functions, performance
characteristics and technology approaches, so that a technically superior
product can be developed. Lawful benchmarking, with evidence and inference kept
visibly apart.

🔴 THE THREE ENTRY MODES ARE PEERS

Label, product image, and manual entry. A person reading the back of a tin is
making an OBSERVATION, not an inference, and `manual_observation` says so —
an earlier design forced honest transcription into `inference`, which
misdescribed the person's work. What manual entry cannot do is reach
`verified`, because there is no document anybody else can re-check.

⚠️ DOCUMENTS BELONG TO THE ONE REGISTER. Uploading a label calls
`materials.store_document`, the same writer an SDS goes through, so a
competitor label gets the identical malware scan, checksum, expiry and
supersession rules. §14: do not build a second document repository.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from app.core.audit import AuditEvent, write_audit
from app.core.db import guarded_write

__all__ = [
    "CompetitorError",
    "CompetitorNotFoundError",
    "CompetitorStateError",
    "EvidenceInput",
    "composition_matrix",
    "list_benchmarks",
    "list_products",
    "list_samples",
    "record_benchmark",
    "record_evidence",
    "register_product",
    "register_sample",
    "verify_evidence",
]


class CompetitorError(RuntimeError):
    """A competitor record could not be written as asked."""


class CompetitorNotFoundError(CompetitorError):
    """It does not exist, or the caller cannot reach it."""


class CompetitorStateError(CompetitorError):
    """It exists but is not in a state that allows this."""


def _decimal_strings(row: Any) -> dict[str, Any]:
    """Every `Decimal` as a string; everything else untouched.

    🔴 WITHOUT THIS, `NUMERIC` LEAVES THE API AS A FLOAT. FastAPI's
    `jsonable_encoder` maps `Decimal` to float, so a disclosed range of
    10.0000-25.0000 arrives as 10.0-25.0: the manufacturer's stated precision
    destroyed, a float on a controlled record against CLAUDE.md §5, and the
    client's `z.string()` rejecting the response.

    This module is the FOURTH to need it — `formulations`, `laboratory`,
    `testing` and `material_safety` each carry a copy, because importing across
    domain services is the cross-domain dependency §0.3 forbids. Four copies is
    the point at which it should move to `core`; recorded here rather than done
    mid-slice, because moving it touches 36 existing call sites.
    """
    return {
        key: (str(value) if isinstance(value, Decimal) else value) for key, value in row.items()
    }


def _translate(exc: DBAPIError) -> CompetitorError:
    """A PostgreSQL refusal, as an answer a client can act on."""
    detail = str(getattr(exc, "orig", exc))

    if "products_org_name_key" in detail:
        return CompetitorStateError(
            "that manufacturer and product are already registered in this "
            "organization. Add evidence to the existing product rather than "
            "creating a second record of the same thing."
        )
    if "samples_org_reference_key" in detail:
        return CompetitorStateError("that sample reference is already used here")
    if "composition_evidence_document_fk" in detail:
        return CompetitorStateError(
            "that document does not belong to this competitor product. A label "
            "uploaded for one product cannot support a claim about another."
        )
    if "composition_evidence_verifiable_source" in detail:
        return CompetitorStateError(
            "only a document-backed or laboratory-backed claim can be verified. "
            "An observation, an inference or a model result can be supported, "
            "probable or possible -- never verified."
        )
    if "may only be marked verified by an active member holding" in detail:
        return CompetitorStateError(detail.strip().splitlines()[0])
    if "composition_evidence_observation_shape" in detail:
        return CompetitorError(
            "a manual observation must name who observed it and say what they saw"
        )
    if "composition_evidence_reasoned_shape" in detail:
        return CompetitorError("an inference must state what it was reasoned from")
    if "composition_evidence_document_shape" in detail:
        return CompetitorError("document-backed evidence must name the document")
    if "composition_evidence_balance_has_no_range" in detail:
        return CompetitorError("'the balance' is not also a concentration range")
    if "row-level security" in detail:
        return CompetitorStateError("this record names a project you cannot reach")
    return CompetitorError(detail)


# ---------------------------------------------------------------------------
# Products and samples
# ---------------------------------------------------------------------------


def register_product(
    session: Session,
    *,
    organization_id: uuid.UUID,
    actor_id: uuid.UUID,
    manufacturer: str,
    product_name: str,
    product_code: str | None = None,
    market_segment: str | None = None,
    project_id: uuid.UUID | None = None,
    notes: str | None = None,
) -> dict[str, Any]:
    """Register a competitor product.

    `project_id` is optional and that is the specification's own shape: a
    competitor product *may* be registered against a project. Most are public
    products the whole organization may see, and NULL says exactly that.
    """
    try:
        with guarded_write(session):
            product_id = session.execute(
                text(
                    """
                    INSERT INTO competitors.products
                        (organization_id, project_id, manufacturer, product_name,
                         product_code, market_segment, notes, registered_by)
                    VALUES (:org, :project, :manufacturer, :name, :code, :segment,
                            :notes, :actor)
                    RETURNING id
                    """
                ),
                {
                    "org": organization_id,
                    "project": project_id,
                    "manufacturer": manufacturer,
                    "name": product_name,
                    "code": product_code,
                    "segment": market_segment,
                    "notes": notes,
                    "actor": actor_id,
                },
            ).scalar_one()
    except DBAPIError as exc:
        raise _translate(exc) from exc

    write_audit(
        session,
        AuditEvent(
            action="COMPETITOR_CREATED",
            entity_type="competitor_product",
            entity_id=str(product_id),
            organization_id=organization_id,
            user_id=actor_id,
            new_state={"manufacturer": manufacturer, "product_name": product_name},
        ),
    )
    return {"id": product_id}


def list_products(
    session: Session, *, organization_id: uuid.UUID, limit: int = 200
) -> list[dict[str, Any]]:
    """Competitor products this caller can reach.

    RLS applies the project predicate, so a product registered against a
    restricted project is invisible to a non-member. Counts of documents and
    evidence come with it, because a product with neither is a stub somebody
    started and abandoned, and the screen should say so.
    """
    return [
        dict(r)
        for r in session.execute(
            text(
                """
                SELECT p.id, p.manufacturer, p.product_name, p.product_code,
                       p.market_segment, p.project_id, p.created_at,
                       (SELECT count(*) FROM materials.material_documents d
                         WHERE d.competitor_product_id = p.id
                           AND d.organization_id = p.organization_id) AS document_count,
                       (SELECT count(*) FROM competitors.composition_evidence e
                         WHERE e.competitor_product_id = p.id
                           AND e.organization_id = p.organization_id) AS evidence_count
                  FROM competitors.products p
                 WHERE p.organization_id = :org
                 ORDER BY p.manufacturer, p.product_name
                 LIMIT :limit
                """
            ),
            {"org": organization_id, "limit": limit},
        ).mappings()
    ]


def register_sample(
    session: Session,

 exited 1 in 1183ms:
      </section>

      <section aria-labelledby="claim-heading">
        <h3 id="claim-heading" className="text-sm font-semibold text-slate-900">
          Record what it contains
        </h3>
        <p className="mt-1 text-xs text-slate-600">
          Every claim is recorded as <strong>possible</strong>. Only a reviewer
          holding <code className="text-[11px]">compliance.review_sds</code> can
          raise one to verified, and only when it cites a document or a
          laboratory result.
        </p>
        <div className="mt-3 grid gap-3 rounded border border-slate-200 bg-white p-4 sm:grid-cols-2">
          <div>
            <label className={LABEL} htmlFor="ev-component">
              Component
            </label>
            <input
              id="ev-component"
              className={INPUT}
              value={component}
              onChange={(event) => setComponent(event.target.value)}
              placeholder="Styrene"
            />
          </div>
          <div>
            <label className={LABEL} htmlFor="ev-cas">
              CAS number
            </label>
            <input
              id="ev-cas"
              className={INPUT}
              value={cas}
              onChange={(event) => setCas(event.target.value)}
              placeholder="100-42-5"
            />
          </div>
          <div>
            <label className={LABEL} htmlFor="ev-low">
              From (%)
            </label>
            {/* Text, not number: a float would round the disclosed range. */}
            <input
              id="ev-low"
              className={INPUT}
              inputMode="decimal"
              value={low}
              onChange={(event) => setLow(event.target.value)}
            />
          </div>
          <div>
            <label className={LABEL} htmlFor="ev-high">
              To (%)
            </label>
            <input
              id="ev-high"
              className={INPUT}
              inputMode="decimal"
              value={high}
              onChange={(event) => setHigh(event.target.value)}
            />
          </div>
          <div>
            <label className={LABEL} htmlFor="ev-source">
              How is this known
            </label>
            <select
              id="ev-source"
              className={INPUT}
              value={evidenceSource}
              onChange={(event) => setEvidenceSource(event.target.value)}
            >
              {EVIDENCE_SOURCES.map((source) => (
                <option key={source.id} value={source.id}>
                  {source.label}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label className={LABEL} htmlFor="ev-grade">
              Evidence grade
            </label>
            <select
              id="ev-grade"
              className={INPUT}
              value={grade}
              onChange={(event) => setGrade(event.target.value)}
            >
              {EVIDENCE_GRADES.map((g) => (
                <option key={g.id} value={g.id}>
                  {g.label}
                </option>
              ))}
            </select>
          </div>

          {needsDocument && (
            <div className="sm:col-span-2">
              <label className={LABEL} htmlFor="ev-doc">
                Which document
              </label>
              <select
                id="ev-doc"
                className={INPUT}
                value={sourceDocumentId}
                onChange={(event) => setSourceDocumentId(event.target.value)}
              >
                <option value="">Choose one of the uploads above…</option>
                {docs.map((doc) => (
                  <option key={doc.id} value={doc.id}>
                    {doc.document_type} — {doc.title}
                  </option>
                ))}
              </select>
              {docs.length === 0 && (
                <p className="mt-1 text-xs text-slate-600">
                  Nothing is uploaded yet, so no claim can cite a document.
                </p>
              )}
            </div>
          )}

          {isObservation && (
            <div className="sm:col-span-2">
              <label className={LABEL} htmlFor="ev-sample">
                Which sample did you read
              </label>
              <select
                id="ev-sample"
                className={INPUT}
                value={sampleId}
                onChange={(event) => setSampleId(event.target.value)}
              >
                <option value="">
                  {tins.length === 0
                    ? "No samples registered yet"
                    : "Not recorded against a sample"}
                </option>
                {tins.map((tin) => (
                  <option key={tin.id} value={tin.id}>
                    {tin.sample_reference}
                    {tin.batch_marking !== null ? ` — batch ${tin.batch_marking}` : ""}
                  </option>
                ))}
              </select>
            </div>
          )}
          <div className="sm:col-span-2">
            <label className={LABEL} htmlFor="ev-locator">
              Where exactly {needsDocument ? "in the document" : "on the product"}
            </label>
            <input
              id="ev-locator"
              className={INPUT}
              value={locator}
              onChange={(event) => setLocator(event.target.value)}
              placeholder="Section 3, ingredient table / back of tin, small print"
            />
          </div>
          <div className="sm:col-span-2">
            <label className={LABEL} htmlFor="ev-rationale">
              What you saw, or what you reasoned from
            </label>
            <textarea
              id="ev-rationale"
              className={INPUT}
              rows={2}
              value={rationale}
              onChange={(event) => setRationale(event.target.value)}
            />
          </div>

          <div className="sm:col-span-2">
            <button
              type="button"
              className={BUTTON}
              disabled={
                writes.isPending ||
                component.trim() === "" ||
# ---------------------------------------------------------------------------
# T3a / T8 — reach, counted as what a user can reach
# ---------------------------------------------------------------------------


def test_every_competitor_table_forces_row_level_security(owner_session: Session) -> None:
    """T8. FORCE from birth: the policies bind the table OWNER too.

    Read from `pg_class`, not from the migration text — the database in front
    of you is not the schema, and a migration is not applied because a file
    exists.
    """
    rows = owner_session.execute(
        text(
            "SELECT c.relname, c.relrowsecurity, c.relforcerowsecurity "
            "  FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace "
            " WHERE n.nspname = 'competitors' AND c.relkind = 'r' ORDER BY c.relname"
        )
    ).all()
    assert len(rows) == 4, f"expected four competitor tables, found {len(rows)}"
    unforced = [r[0] for r in rows if not (r[1] and r[2])]
    assert not unforced, f"these competitor tables are not FORCE RLS: {unforced}"


def test_another_organization_reaches_none_of_it(
    owner_session: Session, app_session: Session, competitor_fixture
) -> None:
    """🔴 T3a — COUNTED AS WHAT A USER CAN REACH, NOT BY READING A POLICY.

    A policy can be present and still not apply. This asks the runtime role,
    under a different tenant, how many rows it can actually see.
    """
    fx = competitor_fixture
    owner_session.commit()

    other_org = uuid.uuid4()
    app_session.execute(
        text("SELECT set_config('app.current_org', :o, true)"), {"o": str(other_org)}
    )

    for table in (
        "competitors.products",
        "competitors.samples",
        "competitors.composition_evidence",
        "competitors.benchmarks",
    ):
        reachable = app_session.execute(
            text(f"SELECT count(*) FROM {table} WHERE organization_id = :o"),
            {"o": fx["org_id"]},
        ).scalar_one()
        assert reachable == 0, f"another organization reached {reachable} rows of {table}"


def test_the_owning_organization_does_reach_its_own_product(
    owner_session: Session, app_session: Session, competitor_fixture
) -> None:
    """🔴 THE OTHER DIRECTION OF T3a.

    Without it, the zeros above would also be produced by a policy that hides
    the table from everybody — or by a fixture that never committed a row.
    """
    fx = competitor_fixture
    owner_session.commit()

    app_session.execute(
        text("SELECT set_config('app.current_org', :o, true)"), {"o": str(fx["org_id"])}
    )
    app_session.execute(
        text("SELECT set_config('app.current_user_id', :u, true)"), {"u": str(fx["user_id"])}
    )
    reachable = app_session.execute(
        text("SELECT count(*) FROM competitors.products WHERE organization_id = :o"),
        {"o": fx["org_id"]},
    ).scalar_one()
    assert reachable == 2, f"the owning organization reached {reachable} of its 2 products"


# ---------------------------------------------------------------------------
# The register was EXTENDED, not forked — §14
# ---------------------------------------------------------------------------


def test_there_is_no_second_document_table(owner_session: Session) -> None:
    """§14: *"do not build a second document repository"*, asserted rather than intended."""
    forked = owner_session.execute(
        text(
            "SELECT count(*) FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace "
            " WHERE n.nspname = 'competitors' AND c.relkind = 'r' "
            "   AND c.relname LIKE '%document%'"
        )
"""Competitor intelligence: products, samples, and the Composition Evidence Matrix.

🔴 THE ONE RULE THIS MODULE EXISTS TO KEEP

The specification, on competitor formulation analysis:

    "Safety Data Sheets often disclose only hazardous components or
     concentration ranges and normally do not reveal a complete proprietary
     formulation. The application shall therefore NEVER automatically present
     an inferred competitor recipe as a known or verified formula."

So there is no competitor formula anywhere in this module. There is a matrix of
CLAIMS, each carrying how it is known and how far it can be trusted. Reading the
matrix end to end gives a candidate composition — which is what the operator
asked for — and every line of it says what it rests on.

The purpose is stated in the same section and is worth keeping in view: this is
not for reconstructing somebody's proprietary information. It is for
understanding comparable chemistry, likely material functions, performance
characteristics and technology approaches, so that a technically superior
product can be developed. Lawful benchmarking, with evidence and inference kept
visibly apart.

🔴 THE THREE ENTRY MODES ARE PEERS

Label, product image, and manual entry. A person reading the back of a tin is
making an OBSERVATION, not an inference, and `manual_observation` says so —
an earlier design forced honest transcription into `inference`, which
misdescribed the person's work. What manual entry cannot do is reach
`verified`, because there is no document anybody else can re-check.

⚠️ DOCUMENTS BELONG TO THE ONE REGISTER. Uploading a label calls
`materials.store_document`, the same writer an SDS goes through, so a
competitor label gets the identical malware scan, checksum, expiry and
supersession rules. §14: do not build a second document repository.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from app.core.audit import AuditEvent, write_audit
from app.core.db import guarded_write

__all__ = [
    "CompetitorError",
    "CompetitorNotFoundError",
    "CompetitorStateError",
    "EvidenceInput",
    "composition_matrix",
    "list_benchmarks",
    "list_products",
    "list_samples",
    "record_benchmark",
    "record_evidence",
    "register_product",
    "register_sample",
    "verify_evidence",
]


class CompetitorError(RuntimeError):
    """A competitor record could not be written as asked."""


class CompetitorNotFoundError(CompetitorError):
    """It does not exist, or the caller cannot reach it."""


class CompetitorStateError(CompetitorError):
    """It exists but is not in a state that allows this."""


def _decimal_strings(row: Any) -> dict[str, Any]:
    """Every `Decimal` as a string; everything else untouched.

    🔴 WITHOUT THIS, `NUMERIC` LEAVES THE API AS A FLOAT. FastAPI's
    `jsonable_encoder` maps `Decimal` to float, so a disclosed range of
    10.0000-25.0000 arrives as 10.0-25.0: the manufacturer's stated precision
    destroyed, a float on a controlled record against CLAUDE.md §5, and the
    client's `z.string()` rejecting the response.

    This module is the FOURTH to need it — `formulations`, `laboratory`,
    `testing` and `material_safety` each carry a copy, because importing across
    domain services is the cross-domain dependency §0.3 forbids. Four copies is
    the point at which it should move to `core`; recorded here rather than done
    mid-slice, because moving it touches 36 existing call sites.
    """
    return {
        key: (str(value) if isinstance(value, Decimal) else value) for key, value in row.items()
    }


def _translate(exc: DBAPIError) -> CompetitorError:
    """A PostgreSQL refusal, as an answer a client can act on."""
    detail = str(getattr(exc, "orig", exc))

    if "products_org_name_key" in detail:
        return CompetitorStateError(
            "that manufacturer and product are already registered in this "
            "organization. Add evidence to the existing product rather than "
            "creating a second record of the same thing."
        )
    if "samples_org_reference_key" in detail:
        return CompetitorStateError("that sample reference is already used here")
    if "composition_evidence_document_fk" in detail:
        return CompetitorStateError(
            "that document does not belong to this competitor product. A label "
            "uploaded for one product cannot support a claim about another."
        )
    if "composition_evidence_verifiable_source" in detail:
        return CompetitorStateError(
            "only a document-backed or laboratory-backed claim can be verified. "
            "An observation, an inference or a model result can be supported, "
            "probable or possible -- never verified."
        )
    if "may only be marked verified by an active member holding" in detail:
        return CompetitorStateError(detail.strip().splitlines()[0])
    if "composition_evidence_observation_shape" in detail:
        return CompetitorError(
            "a manual observation must name who observed it and say what they saw"
        )
    if "composition_evidence_reasoned_shape" in detail:
        return CompetitorError("an inference must state what it was reasoned from")
    if "composition_evidence_document_shape" in detail:
        return CompetitorError("document-backed evidence must name the document")
    if "composition_evidence_balance_has_no_range" in detail:
        return CompetitorError("'the balance' is not also a concentration range")
    if "row-level security" in detail:
        return CompetitorStateError("this record names a project you cannot reach")
    return CompetitorError(detail)


# ---------------------------------------------------------------------------
# Products and samples
# ---------------------------------------------------------------------------


def register_product(
    session: Session,
    *,
    organization_id: uuid.UUID,
    actor_id: uuid.UUID,
    manufacturer: str,
    product_name: str,
    product_code: str | None = None,
    market_segment: str | None = None,
    project_id: uuid.UUID | None = None,
    notes: str | None = None,
) -> dict[str, Any]:
    """Register a competitor product.

    `project_id` is optional and that is the specification's own shape: a
    competitor product *may* be registered against a project. Most are public
    products the whole organization may see, and NULL says exactly that.
    """
    try:
        with guarded_write(session):
            product_id = session.execute(
                text(
                    """
                    INSERT INTO competitors.products
                        (organization_id, project_id, manufacturer, product_name,
                         product_code, market_segment, notes, registered_by)
                    VALUES (:org, :project, :manufacturer, :name, :code, :segment,
                            :notes, :actor)
                    RETURNING id
                    """
                ),
                {
                    "org": organization_id,
                    "project": project_id,
                    "manufacturer": manufacturer,
                    "name": product_name,
                    "code": product_code,
                    "segment": market_segment,
                    "notes": notes,
                    "actor": actor_id,
                },
            ).scalar_one()
    except DBAPIError as exc:
        raise _translate(exc) from exc

    write_audit(
        session,
        AuditEvent(
            action="COMPETITOR_CREATED",
            entity_type="competitor_product",
            entity_id=str(product_id),
            organization_id=organization_id,
            user_id=actor_id,
            new_state={"manufacturer": manufacturer, "product_name": product_name},
        ),
    )
    return {"id": product_id}


def list_products(
    session: Session, *, organization_id: uuid.UUID, limit: int = 200
) -> list[dict[str, Any]]:
    """Competitor products this caller can reach.

    RLS applies the project predicate, so a product registered against a
    restricted project is invisible to a non-member. Counts of documents and
    evidence come with it, because a product with neither is a stub somebody
    started and abandoned, and the screen should say so.
    """
    return [
        dict(r)
        for r in session.execute(
            text(
                """
                SELECT p.id, p.manufacturer, p.product_name, p.product_code,
                       p.market_segment, p.project_id, p.created_at,
                       (SELECT count(*) FROM materials.material_documents d
                         WHERE d.competitor_product_id = p.id
                           AND d.organization_id = p.organization_id) AS document_count,
                       (SELECT count(*) FROM competitors.composition_evidence e
                         WHERE e.competitor_product_id = p.id
                           AND e.organization_id = p.organization_id) AS evidence_count
                  FROM competitors.products p
                 WHERE p.organization_id = :org
                 ORDER BY p.manufacturer, p.product_name
                 LIMIT :limit
                """
            ),
            {"org": organization_id, "limit": limit},
        ).mappings()
    ]


def register_sample(
    session: Session,

exec
"C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command 'git show c98420a:apps/web/app/material-safety/competitors/page.tsx | rg -n -C 5 "EVIDENCE_SOURCES|laboratory|patent|literature|model"; git show c98420a:apps/api/tests/db/test_056_competitor_intelligence.py | rg -n "def test_"' in C:\Users\USER\Documents\evercoat-itw-rd-workspace\EvercoatITWRD APP
 succeeded in 613ms:
25- * What it cannot be is `verified`, since there is nothing anybody else can
26- * re-check, and the database refuses that combination outright.
27- *
28- * ?? UPLOADING DOES NOT FILL THE MATRIX IN. There is no automatic extraction:
29- * that was a deliberate choice on 2026-08-28 (no OCR dependency, and neither
30: * installed Ollama model reads images). The file is stored as evidence a claim
31- * can CITE, and a person records what it says. A screen that implied otherwise
32- * would be inventing components on somebody's product.
33- */
34-
35-import { useState } from "react";
--
46-  useProjects,
47-} from "@/lib/api/hooks";
48-import type { Project } from "@/lib/api/projects";
49-import {
50-  EVIDENCE_GRADES,
51:  EVIDENCE_SOURCES,
52-  type CompetitorProduct,
53-  type EvidenceRow,
54-} from "@/lib/api/competitors";
55-
56-const BUTTON =
--
66-
67-/**
68- * Confidence, as colour AND icon AND word.
69- *
70- * CLAUDE.md ?11 forbids colour-only status, and here it matters more than
71: * usual: the difference between a verified disclosure and a model's guess is
72- * the entire point of the matrix, and a reader who cannot see colour must get
73- * the same answer.
74- */
75-const CONFIDENCE: Record<
76-  EvidenceRow["confidence"],
--
111-  return `${low ?? high}%`;
112-}
113-
114-function MatrixRow({ row }: { row: EvidenceRow }) {
115-  const confidence = CONFIDENCE[row.confidence];
116:  const source = EVIDENCE_SOURCES.find((s) => s.id === row.evidence_source);
117-  return (
118-    <li className="rounded border border-slate-200 bg-white p-3">
119-      <div className="flex flex-wrap items-baseline gap-2">
120-        <span
121-          className={`rounded border px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide ${confidence.className}`}
--
215-            >
216-              <option value="label">The product label</option>
217-              <option value="product_image">A photograph of the product</option>
218-              <option value="SDS">Their published Safety Data Sheet</option>
219-              <option value="TDS">Their technical data sheet</option>
220:              <option value="literature">Product literature</option>
221:              <option value="patent">A patent</option>
222-            </select>
223-          </div>
224-          <div>
225-            <label className={LABEL} htmlFor="doc-title">
226-              Title
--
396-        </h3>
397-        <p className="mt-1 text-xs text-slate-600">
398-          Every claim is recorded as <strong>possible</strong>. Only a reviewer
399-          holding <code className="text-[11px]">compliance.review_sds</code> can
400-          raise one to verified, and only when it cites a document or a
401:          laboratory result.
402-        </p>
403-        <div className="mt-3 grid gap-3 rounded border border-slate-200 bg-white p-4 sm:grid-cols-2">
404-          <div>
405-            <label className={LABEL} htmlFor="ev-component">
406-              Component
--
458-              id="ev-source"
459-              className={INPUT}
460-              value={evidenceSource}
461-              onChange={(event) => setEvidenceSource(event.target.value)}
462-            >
463:              {EVIDENCE_SOURCES.map((source) => (
464-                <option key={source.id} value={source.id}>
465-                  {source.label}
466-                </option>
467-              ))}
468-            </select>
--
570-                component.trim() === "" ||
571-                (needsDocument && sourceDocumentId === "") ||
572-                /* An observation or an inference must say what it rests on --
573-                   the database refuses it otherwise, so the form should too
574-                   rather than sending a request that cannot succeed. */
575:                (["manual_observation", "inference", "model"].includes(evidenceSource) &&
576-                  rationale.trim() === "")
577-              }
578-              onClick={() =>
579-                writes.recordEvidence(
580-                  product.id,
253:def test_a_document_may_supersede_one_with_the_same_owner(
270:def test_a_competitor_label_cannot_supersede_a_materials_sds(
295:def test_the_superseded_sds_is_still_usable_after_the_refusal(
329:def test_a_scanned_label_cannot_be_re_pointed_at_another_product(
345:def test_a_document_cannot_be_re_owned_from_a_competitor_to_a_material(
386:def test_a_harmless_update_to_the_same_document_still_succeeds(
411:def test_a_document_can_back_a_claim_about_its_own_product(
419:def test_a_label_for_product_a_cannot_back_a_claim_about_product_b(
429:def test_the_unique_key_the_composite_foreign_key_needs_exists(
452:def test_verified_requires_both_a_verifier_and_a_time(
470:def test_a_verifier_and_a_time_without_verified_is_also_refused(
491:def test_an_observation_can_never_be_verified(
519:def test_the_named_verifier_must_actually_hold_the_permission(
541:def test_a_holder_of_review_sds_can_verify(
566:def test_every_competitor_table_forces_row_level_security(owner_session: Session) -> None:
585:def test_another_organization_reaches_none_of_it(
614:def test_the_owning_organization_does_reach_its_own_product(
643:def test_there_is_no_second_document_table(owner_session: Session) -> None:
655:def test_usable_documents_kept_security_invoker(owner_session: Session) -> None:

exec
"C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -Command 'git show c98420a:apps/web/lib/api/competitors.ts | Select-Object -First 100; git show c98420a:apps/api/tests/db/test_056_competitor_intelligence.py | Select-Object -Skip 40 -First 105' in C:\Users\USER\Documents\evercoat-itw-rd-workspace\EvercoatITWRD APP
2026-08-28T21:56:17.327011Z ERROR codex_core::tools::router: error=Exit code: 1
Wall time: 0.6 seconds
Output:
/**
 * Competitor intelligence, over HTTP.
 *
 * 🔴 THE MATRIX IS NOT A RECIPE, AND THIS MODULE MUST NOT LET IT LOOK LIKE ONE.
 *
 * The specification forbids presenting an inferred competitor composition as a
 * known or verified formula. So `compositionMatrixSchema` carries a
 * `disclaimer` the SERVER supplies and the screen renders — not a sentence the
 * screen remembers to add, because a screen that forgets it would be doing the
 * one thing the specification rules out.
 *
 * ⚠️ CONCENTRATIONS ARE STRINGS. `NUMERIC(7,4)` in PostgreSQL, and the server
 * stringifies them at the boundary. Parsing to `number` here would reintroduce
 * the float CLAUDE.md §5 forbids on a controlled record, and would render
 * "10.0000" — a range disclosed to four decimal places — as "10".
 */

import { z } from "zod";

import { apiRequest, type ApiCredentials } from "./client";
import { API_BASE_URL } from "./config";

export const competitorProductSchema = z.object({
  id: z.string(),
  manufacturer: z.string(),
  product_name: z.string(),
  product_code: z.string().nullable(),
  market_segment: z.string().nullable(),
  project_id: z.string().nullable(),
  created_at: z.string(),
  document_count: z.number(),
  evidence_count: z.number(),
});

/**
 * How a claim is known. SEPARATE from the document's type: a person reading a
 * tin is making an observation, not an inference, and the two must not collapse
 * into one field.
 */
export const EVIDENCE_SOURCES = [
  { id: "document", label: "A document on file", needsDocument: true },
  { id: "manual_observation", label: "Read from the product myself", needsDocument: false },
  { id: "laboratory", label: "Our own laboratory result", needsDocument: false },
  { id: "literature", label: "Published literature", needsDocument: false },
  { id: "patent", label: "A patent", needsDocument: false },
  { id: "inference", label: "Inferred from the above", needsDocument: false },
  { id: "model", label: "Model hypothesis", needsDocument: false },
] as const;

/** The A–X ranking from the research source document. */
export const EVIDENCE_GRADES = [
  { id: "A", label: "A — validated internal evidence, a standard, or manufacturer documentation" },
  { id: "B", label: "B — peer-reviewed literature, a patent, or a recognised institution" },
  { id: "C", label: "C — supplier literature or a conference paper" },
  { id: "D", label: "D — a general web source" },
  { id: "X", label: "X — unverified or unreliable" },
] as const;

export const evidenceRowSchema = z.object({
  id: z.string(),
  component_name: z.string(),
  cas_number: z.string().nullable(),
  component_function: z.string().nullable(),
  // Strings. See the header.
  concentration_low: z.string().nullable(),
  concentration_high: z.string().nullable(),
  is_balance: z.boolean(),
  evidence_source: z.string(),
  evidence_grade: z.string(),
  confidence: z.enum(["verified", "supported", "probable", "possible", "unknown"]),
  source_locator: z.string().nullable(),
  rationale: z.string().nullable(),
  verified_at: z.string().nullable(),
  source_document_id: z.string().nullable(),
  sample_id: z.string().nullable(),
  test_id: z.string().nullable(),
  source_document_title: z.string().nullable(),
  source_document_type: z.string().nullable(),
});

export const compositionMatrixSchema = z.object({
  rows: z.array(evidenceRowSchema),
  summary: z.record(z.string(), z.number()),
  // 🔴 SUPPLIED BY THE SERVER AND RENDERED VERBATIM.
  disclaimer: z.string(),
});

export const competitorDocumentSchema = z.object({
  id: z.string(),
  document_type: z.string(),
  title: z.string(),
  content_type: z.string().nullable(),
  byte_size: z.number().nullable(),
  issued_on: z.string().nullable(),
  expires_on: z.string().nullable(),
  created_at: z.string(),
});

export const competitorSampleSchema = z.object({
  id: z.string(),


# ---------------------------------------------------------------------------
# Fixture — one organization, one material with an approved SDS, and two
# competitor products, so "the other product" is a real row and not a UUID
# that simply does not exist.
# ---------------------------------------------------------------------------


@pytest.fixture
def competitor_fixture(owner_session: Session) -> dict[str, uuid.UUID]:
    suffix = uuid.uuid4().hex[:8]

    org_id = owner_session.execute(
        text("INSERT INTO core.organizations (code, name) VALUES (:c, :n) RETURNING id"),
        {"c": f"COMP-{suffix}", "n": "Competitor Test Org"},
    ).scalar_one()

    user_id = owner_session.execute(
        text(
            "INSERT INTO core.users (keycloak_sub, email, display_name) "
            "VALUES (:s, :e, :n) RETURNING id"
        ),
        {"s": f"comp-{suffix}", "e": f"comp-{suffix}@example.test", "n": "Competitor Tester"},
    ).scalar_one()
    member_id = owner_session.execute(
        text(
            "INSERT INTO core.organization_members "
            "(organization_id, user_id, status, email, display_name) "
            "VALUES (:o, :u, 'active', :e, :n) RETURNING id"
        ),
        {
            "o": org_id,
            "u": user_id,
            "e": f"comp-{suffix}@example.test",
            "n": "Competitor Tester",
        },
    ).scalar_one()

    material_id = owner_session.execute(
        text(
            """
            INSERT INTO materials.materials
                (organization_id, material_code, name, category, role, status, created_by)
            VALUES (:o, :code, 'Test resin', 'Resin', 'resin', 'approved', :u)
            RETURNING id
            """
        ),
        {"o": org_id, "code": f"RM-{suffix}", "u": user_id},
    ).scalar_one()

    project_id = owner_session.execute(
        text(
            "INSERT INTO projects.projects (organization_id, project_code, name) "
            "VALUES (:o, :c, 'Benchmark project') RETURNING id"
        ),
        {"o": org_id, "c": f"PRJ-{suffix}"},
    ).scalar_one()

    # FORCE RLS binds the table owner too, so even this session must declare
    # its tenant. Without it the INSERTs below fail with "new row violates
    # row-level security policy" -- the guard working, not a defect.
    owner_session.execute(
        text("SELECT set_config('app.current_org', :o, true)"), {"o": str(org_id)}
    )
    owner_session.execute(
        text("SELECT set_config('app.current_user_id', :u, true)"), {"u": str(user_id)}
    )

    product_a = _make_product(owner_session, org_id, user_id, f"A-{suffix}")
    product_b = _make_product(owner_session, org_id, user_id, f"B-{suffix}")

    sds_id = _make_document(owner_session, org_id, user_id, suffix, "SDS", material_id=material_id)
    label_a = _make_document(
        owner_session, org_id, user_id, suffix, "label", competitor_product_id=product_a
    )
    owner_session.flush()

    return {
        "org_id": org_id,
        "user_id": user_id,
        "member_id": member_id,
        "material_id": material_id,
        "project_id": project_id,
        "product_a": product_a,
        "product_b": product_b,
        "sds_id": sds_id,
        "label_a": label_a,
    }


def _make_product(
    session: Session, org_id: uuid.UUID, user_id: uuid.UUID, name: str
) -> uuid.UUID:
    return session.execute(  # type: ignore[no-any-return]
        text(
            "INSERT INTO competitors.products "
            "(organization_id, manufacturer, product_name, registered_by) "
            "VALUES (:o, 'Rival Chemicals', :n, :u) RETURNING id"
        ),
        {"o": org_id, "n": name, "u": user_id},
    ).scalar_one()


def _make_document(

 exited 1 in 613ms:
/**
 * Competitor intelligence, over HTTP.
 *
 * 🔴 THE MATRIX IS NOT A RECIPE, AND THIS MODULE MUST NOT LET IT LOOK LIKE ONE.
 *
 * The specification forbids presenting an inferred competitor composition as a
 * known or verified formula. So `compositionMatrixSchema` carries a
 * `disclaimer` the SERVER supplies and the screen renders — not a sentence the
 * screen remembers to add, because a screen that forgets it would be doing the
 * one thing the specification rules out.
 *
 * ⚠️ CONCENTRATIONS ARE STRINGS. `NUMERIC(7,4)` in PostgreSQL, and the server
 * stringifies them at the boundary. Parsing to `number` here would reintroduce
 * the float CLAUDE.md §5 forbids on a controlled record, and would render
 * "10.0000" — a range disclosed to four decimal places — as "10".
 */

import { z } from "zod";

import { apiRequest, type ApiCredentials } from "./client";
import { API_BASE_URL } from "./config";

export const competitorProductSchema = z.object({
  id: z.string(),
  manufacturer: z.string(),
  product_name: z.string(),
  product_code: z.string().nullable(),
  market_segment: z.string().nullable(),
  project_id: z.string().nullable(),
  created_at: z.string(),
  document_count: z.number(),
  evidence_count: z.number(),
});

/**
 * How a claim is known. SEPARATE from the document's type: a person reading a
 * tin is making an observation, not an inference, and the two must not collapse
 * into one field.
 */
export const EVIDENCE_SOURCES = [
  { id: "document", label: "A document on file", needsDocument: true },
  { id: "manual_observation", label: "Read from the product myself", needsDocument: false },
  { id: "laboratory", label: "Our own laboratory result", needsDocument: false },
  { id: "literature", label: "Published literature", needsDocument: false },
  { id: "patent", label: "A patent", needsDocument: false },
  { id: "inference", label: "Inferred from the above", needsDocument: false },
  { id: "model", label: "Model hypothesis", needsDocument: false },
] as const;

/** The A–X ranking from the research source document. */
export const EVIDENCE_GRADES = [
  { id: "A", label: "A — validated internal evidence, a standard, or manufacturer documentation" },
  { id: "B", label: "B — peer-reviewed literature, a patent, or a recognised institution" },
  { id: "C", label: "C — supplier literature or a conference paper" },
  { id: "D", label: "D — a general web source" },
  { id: "X", label: "X — unverified or unreliable" },
] as const;

export const evidenceRowSchema = z.object({
  id: z.string(),
  component_name: z.string(),
  cas_number: z.string().nullable(),
  component_function: z.string().nullable(),
  // Strings. See the header.
  concentration_low: z.string().nullable(),
  concentration_high: z.string().nullable(),
  is_balance: z.boolean(),
  evidence_source: z.string(),
  evidence_grade: z.string(),
  confidence: z.enum(["verified", "supported", "probable", "possible", "unknown"]),
  source_locator: z.string().nullable(),
  rationale: z.string().nullable(),
  verified_at: z.string().nullable(),
  source_document_id: z.string().nullable(),
  sample_id: z.string().nullable(),
  test_id: z.string().nullable(),
  source_document_title: z.string().nullable(),
  source_document_type: z.string().nullable(),
});

export const compositionMatrixSchema = z.object({
  rows: z.array(evidenceRowSchema),
  summary: z.record(z.string(), z.number()),
  // 🔴 SUPPLIED BY THE SERVER AND RENDERED VERBATIM.
  disclaimer: z.string(),
});

export const competitorDocumentSchema = z.object({
  id: z.string(),
  document_type: z.string(),
  title: z.string(),
  content_type: z.string().nullable(),
  byte_size: z.number().nullable(),
  issued_on: z.string().nullable(),
  expires_on: z.string().nullable(),
  created_at: z.string(),
});

export const competitorSampleSchema = z.object({
  id: z.string(),


# ---------------------------------------------------------------------------
# Fixture — one organization, one material with an approved SDS, and two
# competitor products, so "the other product" is a real row and not a UUID
# that simply does not exist.
# ---------------------------------------------------------------------------


@pytest.fixture
def competitor_fixture(owner_session: Session) -> dict[str, uuid.UUID]:
    suffix = uuid.uuid4().hex[:8]

    org_id = owner_session.execute(
        text("INSERT INTO core.organizations (code, name) VALUES (:c, :n) RETURNING id"),
        {"c": f"COMP-{suffix}", "n": "Competitor Test Org"},
    ).scalar_one()

    user_id = owner_session.execute(
        text(
            "INSERT INTO core.users (keycloak_sub, email, display_name) "
            "VALUES (:s, :e, :n) RETURNING id"
        ),
        {"s": f"comp-{suffix}", "e": f"comp-{suffix}@example.test", "n": "Competitor Tester"},
    ).scalar_one()
    member_id = owner_session.execute(
        text(
            "INSERT INTO core.organization_members "
            "(organization_id, user_id, status, email, display_name) "
            "VALUES (:o, :u, 'active', :e, :n) RETURNING id"
        ),
        {
            "o": org_id,
            "u": user_id,
            "e": f"comp-{suffix}@example.test",
            "n": "Competitor Tester",
        },
    ).scalar_one()

    material_id = owner_session.execute(
        text(
            """
            INSERT INTO materials.materials
                (organization_id, material_code, name, category, role, status, created_by)
            VALUES (:o, :code, 'Test resin', 'Resin', 'resin', 'approved', :u)
            RETURNING id
            """
        ),
        {"o": org_id, "code": f"RM-{suffix}", "u": user_id},
    ).scalar_one()

    project_id = owner_session.execute(
        text(
            "INSERT INTO projects.projects (organization_id, project_code, name) "
            "VALUES (:o, :c, 'Benchmark project') RETURNING id"
        ),
        {"o": org_id, "c": f"PRJ-{suffix}"},
    ).scalar_one()

    # FORCE RLS binds the table owner too, so even this session must declare
    # its tenant. Without it the INSERTs below fail with "new row violates
    # row-level security policy" -- the guard working, not a defect.
    owner_session.execute(
        text("SELECT set_config('app.current_org', :o, true)"), {"o": str(org_id)}
    )
    owner_session.execute(
        text("SELECT set_config('app.current_user_id', :u, true)"), {"u": str(user_id)}
    )

    product_a = _make_product(owner_session, org_id, user_id, f"A-{suffix}")
    product_b = _make_product(owner_session, org_id, user_id, f"B-{suffix}")

    sds_id = _make_document(owner_session, org_id, user_id, suffix, "SDS", material_id=material_id)
    label_a = _make_document(
        owner_session, org_id, user_id, suffix, "label", competitor_product_id=product_a
    )
    owner_session.flush()

    return {
        "org_id": org_id,
        "user_id": user_id,
        "member_id": member_id,
        "material_id": material_id,
        "project_id": project_id,
        "product_a": product_a,
        "product_b": product_b,
        "sds_id": sds_id,
        "label_a": label_a,
    }


def _make_product(
    session: Session, org_id: uuid.UUID, user_id: uuid.UUID, name: str
) -> uuid.UUID:
    return session.execute(  # type: ignore[no-any-return]
        text(
            "INSERT INTO competitors.products "
            "(organization_id, manufacturer, product_name, registered_by) "
            "VALUES (:o, 'Rival Chemicals', :n, :u) RETURNING id"
        ),
        {"o": org_id, "n": name, "u": user_id},
    ).scalar_one()


def _make_document(

codex
- **P1** — [apps/api/app/api/competitors.py:426](C:/Users/USER/Documents/evercoat-itw-rd-workspace/EvercoatITWRD%20APP/apps/api/app/api/competitors.py:426): `POST /benchmarks` requires only `test.view`. A read-only testing user can therefore create arbitrary competitor comparisons and gap summaries. Server-side RLS cannot prevent this because the user is writing into a project they legitimately reach; the mutation needs an actual edit/record permission.

- **P2** — [apps/web/app/material-safety/competitors/page.tsx:568](C:/Users/USER/Documents/evercoat-itw-rd-workspace/EvercoatITWRD%20APP/apps/web/app/material-safety/competitors/page.tsx:568): the manual-observation form does not require a sample selection, and [line 589](C:/Users/USER/Documents/evercoat-itw-rd-workspace/EvercoatITWRD%20APP/apps/web/app/material-safety/competitors/page.tsx:589) omits `sample_id` when the default “Not recorded against a sample” option remains selected. A user can still submit the observation with only a rationale, producing exactly the unattributable row this change claims to eliminate.

- **P2** — [apps/web/lib/api/competitors.ts:42](C:/Users/USER/Documents/evercoat-itw-rd-workspace/EvercoatITWRD%20APP/apps/web/lib/api/competitors.ts:42): “Our own laboratory result” is offered as an evidence source, but the form has no test selector and its request at [page.tsx:581](C:/Users/USER/Documents/evercoat-itw-rd-workspace/EvercoatITWRD%20APP/apps/web/app/material-safety/competitors/page.tsx:581) never sends `test_id`. The API nevertheless treats `laboratory` as a verifiable source. Consequently, a user can create an uncited “laboratory” claim which a reviewer can later promote to verified without any laboratory record establishing it.

- **P2** — [apps/api/tests/db/test_056_competitor_intelligence.py:601](C:/Users/USER/Documents/evercoat-itw-rd-workspace/EvercoatITWRD%20APP/apps/api/tests/db/test_056_competitor_intelligence.py:601): the cross-tenant loop claims to exercise all four competitor tables, but the fixture creates rows only in `competitors.products`; it creates no sample, composition-evidence, or benchmark rows. Counts for those three tables are therefore zero even if their RLS policies expose every row. The positive control at [line 628](C:/Users/USER/Documents/evercoat-itw-rd-workspace/EvercoatITWRD%20APP/apps/api/tests/db/test_056_competitor_intelligence.py:628) validates only products, so it does not repair the false-positive test.

VERDICT: FAIL
tokens used
74,367
- **P1** — [apps/api/app/api/competitors.py:426](C:/Users/USER/Documents/evercoat-itw-rd-workspace/EvercoatITWRD%20APP/apps/api/app/api/competitors.py:426): `POST /benchmarks` requires only `test.view`. A read-only testing user can therefore create arbitrary competitor comparisons and gap summaries. Server-side RLS cannot prevent this because the user is writing into a project they legitimately reach; the mutation needs an actual edit/record permission.

- **P2** — [apps/web/app/material-safety/competitors/page.tsx:568](C:/Users/USER/Documents/evercoat-itw-rd-workspace/EvercoatITWRD%20APP/apps/web/app/material-safety/competitors/page.tsx:568): the manual-observation form does not require a sample selection, and [line 589](C:/Users/USER/Documents/evercoat-itw-rd-workspace/EvercoatITWRD%20APP/apps/web/app/material-safety/competitors/page.tsx:589) omits `sample_id` when the default “Not recorded against a sample” option remains selected. A user can still submit the observation with only a rationale, producing exactly the unattributable row this change claims to eliminate.

- **P2** — [apps/web/lib/api/competitors.ts:42](C:/Users/USER/Documents/evercoat-itw-rd-workspace/EvercoatITWRD%20APP/apps/web/lib/api/competitors.ts:42): “Our own laboratory result” is offered as an evidence source, but the form has no test selector and its request at [page.tsx:581](C:/Users/USER/Documents/evercoat-itw-rd-workspace/EvercoatITWRD%20APP/apps/web/app/material-safety/competitors/page.tsx:581) never sends `test_id`. The API nevertheless treats `laboratory` as a verifiable source. Consequently, a user can create an uncited “laboratory” claim which a reviewer can later promote to verified without any laboratory record establishing it.

- **P2** — [apps/api/tests/db/test_056_competitor_intelligence.py:601](C:/Users/USER/Documents/evercoat-itw-rd-workspace/EvercoatITWRD%20APP/apps/api/tests/db/test_056_competitor_intelligence.py:601): the cross-tenant loop claims to exercise all four competitor tables, but the fixture creates rows only in `competitors.products`; it creates no sample, composition-evidence, or benchmark rows. Counts for those three tables are therefore zero even if their RLS policies expose every row. The positive control at [line 628](C:/Users/USER/Documents/evercoat-itw-rd-workspace/EvercoatITWRD%20APP/apps/api/tests/db/test_056_competitor_intelligence.py:628) validates only products, so it does not repair the false-positive test.

VERDICT: FAIL
