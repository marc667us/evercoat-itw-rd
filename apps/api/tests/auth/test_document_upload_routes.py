"""I41 over real HTTP — the SDS gate counts FILES, not rows.

🔴 WHY THESE ARE ROUTE TESTS AND NOT SERVICE TESTS.

I40 recorded this project's own lesson four days ago: *"a service-level test
cannot see a permission floor that is too low, nor a gate naming a permission
nobody holds"* — because a service test hands itself whatever it likes. Here
the equivalent is the store and the scanner: a service test passes in an
`AlwaysCleanScanner` and proves nothing about what the DEPLOYED application
does when no scanner is configured.

So these drive the route, through FastAPI's dependency graph, with the real
`get_scanner` / `get_object_store` providers overridden the way a deployment's
configuration would set them. The 503 test in particular is only meaningful
here: it asserts that a missing scanner produces a REFUSAL rather than a
silently unscanned document, which is the failure mode `MalwareScannerPort`
exists to prevent and which no service test can observe.
"""

from __future__ import annotations

import pathlib
import uuid

import pytest
from sqlalchemy import text

from app.core.documents import get_object_store, get_scanner
from app.core.malware import AlwaysCleanScanner, ScannerUnavailable, ScanResult
from app.core.object_storage import FilesystemObjectStore
from app.main import app

PDF = b"%PDF-1.4\n% a synthetic safety data sheet\n" + b"x" * 128
ELF = b"\x7fELF\x02\x01\x01\x00" + b"\x00" * 128


class _FindsEverything:
    """A scanner that condemns whatever it is given."""

    def scan(self, data: bytes) -> ScanResult:
        return ScanResult(
            clean=False, scanner="test", version="1", signature="Eicar-Test-Signature"
        )


@pytest.fixture
def client():
    from fastapi.testclient import TestClient

    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture
def may_upload(owner_session, lead_ctx):
    """Grant the caller a role that actually holds `material.edit`.

    🔴 `lead_ctx` is a product_development_lead, and a Lead holds NEITHER
    `material.edit` NOR `supplier.manage` -- measured, not assumed. The first
    draft of this file used it directly and every upload returned 403, which
    was the authorization chain working correctly and my fixture being wrong.

    Granting the chemist role explicitly keeps that visible: the tests below
    are about the document pipeline, and
    `test_a_lead_alone_may_not_upload_a_document` is where the permission
    itself is asserted.
    """
    owner_session.execute(
        text(
            """
            INSERT INTO core.member_roles (member_id, role_id)
            SELECT m.id, r.id
            FROM core.organization_members m, core.roles r
            WHERE m.user_id = :u AND m.organization_id = :o
              AND r.code = 'product_development_chemist'
            ON CONFLICT DO NOTHING
            """
        ),
        {"u": lead_ctx["user_id"], "o": lead_ctx["org_id"]},
    )
    owner_session.commit()

    yield

    owner_session.rollback()
    owner_session.execute(
        text(
            """
            DELETE FROM core.member_roles
            WHERE member_id IN (
                SELECT id FROM core.organization_members
                WHERE user_id = :u AND organization_id = :o
            )
            AND role_id = (SELECT id FROM core.roles WHERE code='product_development_chemist')
            """
        ),
        {"u": lead_ctx["user_id"], "o": lead_ctx["org_id"]},
    )
    owner_session.commit()


@pytest.fixture
def store(tmp_path: pathlib.Path) -> FilesystemObjectStore:
    return FilesystemObjectStore(tmp_path / "documents")


@pytest.fixture
def material(owner_session, lead_ctx):
    """A material that REQUIRES an SDS, in the caller's organization.

    COMMITS, because the route runs on its own connection and cannot see an
    uncommitted row -- and therefore CLEANS UP, because `lead_ctx` deletes its
    organization on teardown and `materials_organization_id_fkey` is RESTRICT.
    Fixture teardown runs in reverse dependency order, so this finalizer is
    guaranteed to run first.
    """
    mid = owner_session.execute(
        text(
            """
            INSERT INTO materials.materials
                (organization_id, material_code, name, category, requires_sds, created_by)
            VALUES (:o, :c, 'Styrene-bearing resin', 'Resin', TRUE, :u)
            RETURNING id
            """
        ),
        {
            "o": lead_ctx["org_id"],
            "c": f"RM-{uuid.uuid4().hex[:6]}",
            "u": lead_ctx["user_id"],
        },
    ).scalar_one()
    owner_session.commit()

    yield mid

    owner_session.rollback()
    owner_session.execute(
        text("DELETE FROM materials.material_documents WHERE material_id = :m"), {"m": mid}
    )
    owner_session.execute(text("DELETE FROM materials.materials WHERE id = :m"), {"m": mid})
    owner_session.commit()


@pytest.fixture
def wire(store):
    """Override the two ports the way a deployment's configuration would.

    Yields a function so each test names the scanner it is asserting about;
    the store is always the temporary one, because a test must never write
    into whatever store a developer's API happens to point at.
    """

    def _wire(scanner):
        app.dependency_overrides[get_object_store] = lambda: store
        app.dependency_overrides[get_scanner] = lambda: scanner

    yield _wire
    app.dependency_overrides.pop(get_object_store, None)
    app.dependency_overrides.pop(get_scanner, None)


def _upload(
    client, auth, material, *, data=PDF, filename="SDS.pdf", content_type="application/pdf"
):
    return client.post(
        f"/api/materials/{material}/documents",
        headers=auth,
        files={"file": (filename, data, content_type)},
        data={"document_type": "SDS", "title": "Safety data sheet rev 4"},
    )


def _usable(owner_session, material) -> int:
    return owner_session.execute(
        text(
            "SELECT count(*) FROM materials.usable_documents "
            "WHERE material_id = :m AND document_type = 'SDS'"
        ),
        {"m": material},
    ).scalar_one()


def test_a_real_file_is_stored_and_counts_as_evidence(
    client, auth, owner_session, material, store, wire, may_upload
) -> None:
    """The happy path, asserted through the view the SAFETY GATE reads."""
    wire(AlwaysCleanScanner())

    response = _upload(client, auth, material)
    assert response.status_code == 201, response.text

    row = (
        owner_session.execute(
            text(
                "SELECT storage_key, checksum_sha256, byte_size, status, scan_status, "
                "scanner_name, original_filename "
                "FROM materials.material_documents WHERE id = :i"
            ),
            {"i": uuid.UUID(response.json()["id"])},
        )
        .mappings()
        .one()
    )

    assert row["status"] == "approved"
    assert row["scan_status"] == "clean"
    assert row["scanner_name"] == "always-clean"
    assert row["byte_size"] == len(PDF)

    # 🔴 THE BYTES ARE REALLY THERE, AND THE CHECKSUM DESCRIBES THEM.
    # This is the assertion the whole of I41 comes down to: before this
    # change the row existed and the file did not.
    assert store.exists(row["storage_key"])
    assert store.get(row["storage_key"]) == PDF

    import hashlib

    assert row["checksum_sha256"] == hashlib.sha256(PDF).hexdigest()
    assert _usable(owner_session, material) == 1


def test_a_row_without_bytes_does_not_satisfy_the_gate(owner_session, material, lead_ctx) -> None:
    """🔴 I41 STATED DIRECTLY, AND PROVED BY FALSIFICATION.

    This inserts precisely what the old route produced -- a row naming a
    storage key with nothing behind it -- and asserts the safety gate does NOT
    count it. Against the code as it stood four days ago this assertion fails,
    because `usable_documents` did not exist and the gate counted
    `material_documents` rows.
    """
    owner_session.execute(
        text(
            """
            INSERT INTO materials.material_documents
                (organization_id, material_id, document_type, title, storage_key,
                 uploaded_by, status, scan_status)
            VALUES (:o, :m, 'SDS', 'A claim with no file', :k, :u,
                    'legacy_unverified', 'not_scanned')
            """
        ),
        {
            "o": lead_ctx["org_id"],
            "m": material,
            "k": f"sds/{uuid.uuid4().hex}.pdf",
            "u": lead_ctx["user_id"],
        },
    )
    owner_session.commit()

    assert _usable(owner_session, material) == 0, (
        "a document row carrying no bytes counted as hazard documentation -- "
        "that is I41, the defect this whole slice exists to close"
    )


def test_an_executable_renamed_to_pdf_is_refused(
    client, auth, material, store, wire, may_upload
) -> None:
    """The extension is a claim. The magic bytes are not."""
    wire(AlwaysCleanScanner())

    response = _upload(client, auth, material, data=ELF)

    assert response.status_code == 400, response.text
    assert "bytes" in response.json()["detail"].lower()


def test_malware_is_refused_and_never_stored(
    client, auth, owner_session, material, store, wire, may_upload
) -> None:
    """422, and nothing reaches the store.

    The scan happens BEFORE `store.put`, so a condemned file is not written and
    there is nothing to quarantine or clean up.
    """
    wire(_FindsEverything())

    # A VALID PDF. The first draft sent EICAR followed by a PDF header, and
    # the TYPE check refused it before the scanner ever ran -- correct
    # behaviour, and it meant this test proved the magic-byte check twice and
    # the malware path never. What is under test here is the scanner's
    # verdict, so the file has to be one that reaches it.
    response = _upload(client, auth, material, data=PDF)

    assert response.status_code == 422, response.text
    assert "Eicar-Test-Signature" in response.json()["detail"]
    assert _usable(owner_session, material) == 0

    written = list(pathlib.Path(store._root).rglob("*")) if store._root.exists() else []
    assert [p for p in written if p.is_file()] == [], (
        "a file the scanner condemned was written to the object store"
    )


def test_an_unavailable_scanner_returns_503_and_stores_nothing(
    client, auth, owner_session, material, wire, may_upload
) -> None:
    """🔴 THE MOST IMPORTANT TEST IN THIS FILE.

    A deployment with no scanner configured must REFUSE uploads. The tempting
    implementation -- scan when a scanner exists, otherwise proceed -- gives
    201 here, admits every file unscanned, logs nothing, and looks perfectly
    healthy. That is the failure `MalwareScannerPort` is shaped to prevent, and
    503 rather than 201 is the whole of the difference.
    """
    wire(ScannerUnavailable("clamd is not reachable"))

    response = _upload(client, auth, material)

    assert response.status_code == 503, response.text
    assert "scan" in response.json()["detail"].lower()
    assert _usable(owner_session, material) == 0


def test_an_unauthenticated_upload_is_refused(client, material) -> None:
    response = client.post(
        f"/api/materials/{material}/documents",
        files={"file": ("SDS.pdf", PDF, "application/pdf")},
        data={"document_type": "SDS", "title": "no token"},
    )
    assert response.status_code in (401, 403), response.text


def test_a_material_in_another_organization_is_not_found(
    client, auth, owner_session, wire, may_upload
) -> None:
    """Resource scope, at the upload boundary.

    A material id from elsewhere must 404, not store a file against it. The
    store is checked too: a 404 that had already written bytes would leave an
    object no row references -- invisible to every quota, retention and
    deletion path (I49).
    """
    wire(AlwaysCleanScanner())

    other_org = owner_session.execute(
        text("INSERT INTO core.organizations (code,name) VALUES (:c,'Other') RETURNING id"),
        {"c": f"OTH-{uuid.uuid4().hex[:8]}"},
    ).scalar_one()
    user = owner_session.execute(
        text(
            "INSERT INTO core.users (keycloak_sub,email,display_name) "
            "VALUES (:s,:e,'Other') RETURNING id"
        ),
        {"s": str(uuid.uuid4()), "e": f"{uuid.uuid4().hex[:8]}@example.test"},
    ).scalar_one()
    foreign_material = owner_session.execute(
        text(
            """
            INSERT INTO materials.materials
                (organization_id, material_code, name, category, created_by)
            VALUES (:o, :c, 'Elsewhere', 'Resin', :u) RETURNING id
            """
        ),
        {"o": other_org, "c": f"RM-{uuid.uuid4().hex[:6]}", "u": user},
    ).scalar_one()
    owner_session.commit()

    try:
        response = _upload(client, auth, foreign_material)
        assert response.status_code == 404, response.text
        assert _usable(owner_session, foreign_material) == 0
    finally:
        # Committed above so the route's own connection can see it, so it has
        # to be removed here or it outlives the test.
        owner_session.rollback()
        owner_session.execute(
            text("DELETE FROM materials.materials WHERE id = :m"), {"m": foreign_material}
        )
        owner_session.execute(
            text("DELETE FROM core.organization_members WHERE user_id = :u"), {"u": user}
        )
        owner_session.execute(text("DELETE FROM core.users WHERE id = :u"), {"u": user})
        owner_session.execute(
            text("DELETE FROM core.organizations WHERE id = :o"), {"o": other_org}
        )
        owner_session.commit()


def test_the_temporary_store_is_used_rather_than_the_configured_one(store, wire) -> None:
    """A guard on this file's own fixtures.

    If `wire` ever stopped overriding `get_object_store`, every test above
    would still pass while writing into the deployment's real document store.
    """
    wire(AlwaysCleanScanner())
    assert app.dependency_overrides[get_object_store]() is store
    assert isinstance(app.dependency_overrides[get_object_store](), FilesystemObjectStore)


def test_a_lead_alone_may_not_upload_a_document(client, auth, material, store, wire) -> None:
    """The permission itself, asserted rather than assumed.

    Deliberately does NOT request `may_upload`. A product_development_lead
    holds neither `material.edit` nor `supplier.manage`, so hazard
    documentation is not theirs to file -- and every other test in this file
    would pass just as well if the route had no permission requirement at all.
    """
    wire(AlwaysCleanScanner())

    response = _upload(client, auth, material)

    assert response.status_code == 403, response.text
