"""The three units the document pipeline is built from — I41.

No database, no containers. These prove the properties the rest of E3 rests on:
the store reports what it actually wrote, an unavailable scanner refuses rather
than passes, and a file's TYPE comes from its bytes rather than its name.
"""

from __future__ import annotations

import io

import pytest

from app.core.file_types import (
    MAX_UPLOAD_BYTES,
    FileTypeRejectedError,
    safe_display_filename,
    validate_upload,
)
from app.core.malware import (
    EICAR,
    AlwaysCleanScanner,
    MalwareScanUnavailableError,
    ScannerUnavailable,
    build_scanner,
)
from app.core.object_storage import (
    FilesystemObjectStore,
    ObjectStorageError,
    new_object_key,
)

PDF = b"%PDF-1.7\n" + b"x" * 64
PNG = b"\x89PNG\r\n\x1a\n" + b"x" * 64


# ---------------------------------------------------------------------------
# Object storage
# ---------------------------------------------------------------------------


def test_the_store_reports_the_checksum_of_what_it_wrote(tmp_path) -> None:
    """🔴 The property the whole of I41 turns on.

    The caller cannot supply a checksum, so a row cannot claim a file the store
    does not hold: the value that proves the file exists is only obtainable by
    storing it.
    """
    import hashlib

    store = FilesystemObjectStore(tmp_path)
    key = "org/sds/one"

    stored = store.put(key, io.BytesIO(PDF), "application/pdf")

    assert stored.checksum_sha256 == hashlib.sha256(PDF).hexdigest()
    assert stored.byte_size == len(PDF)
    assert store.get(key) == PDF
    assert store.exists(key)


def test_a_key_cannot_escape_the_storage_root(tmp_path) -> None:
    """Keys are application-generated today; this costs nothing and outlives that."""
    store = FilesystemObjectStore(tmp_path / "root")
    with pytest.raises(ObjectStorageError, match="escapes"):
        store.put("../../escaped", io.BytesIO(PDF), "application/pdf")


def test_a_missing_object_is_an_error_not_an_empty_answer(tmp_path) -> None:
    """🔴 Absence must not be indistinguishable from an outage.

    A caller that reads b"" for a missing SDS and for an unreachable store
    cannot tell "no document" from "the store is down" -- and the SDS gate
    turns on exactly that distinction.
    """
    store = FilesystemObjectStore(tmp_path)
    assert store.exists("nothing/here") is False
    with pytest.raises(ObjectStorageError):
        store.get("nothing/here")


def test_object_keys_are_unique_and_carry_no_user_input() -> None:
    import uuid

    org = uuid.uuid4()
    a = new_object_key(org, "SDS")
    b = new_object_key(org, "SDS")
    assert a != b
    assert a.startswith(f"{org}/sds/")
    # A hostile "kind" cannot introduce path segments.
    assert "/" not in new_object_key(org, "../../etc").removeprefix(f"{org}/").rsplit("/", 1)[-1]


# ---------------------------------------------------------------------------
# Malware scanning
# ---------------------------------------------------------------------------


def test_an_unavailable_scanner_raises_rather_than_passing() -> None:
    """🔴 The single most important assertion in this file.

    The natural implementation of "scan if a scanner is configured" is a
    control that stops existing when the scanner does. This one refuses.
    """
    with pytest.raises(MalwareScanUnavailableError):
        ScannerUnavailable().scan(PDF)


def test_the_default_backend_is_unavailable_not_permissive() -> None:
    scanner = build_scanner(backend="not-configured")
    with pytest.raises(MalwareScanUnavailableError):
        scanner.scan(PDF)


def test_the_always_clean_scanner_is_refused_unless_explicitly_allowed() -> None:
    """It admits every file, so reaching it must take more than a config value."""
    with pytest.raises(MalwareScanUnavailableError, match="TEST fixture"):
        build_scanner(backend="always-clean")

    scanner = build_scanner(backend="always-clean", allow_test_scanner=True)
    assert scanner.scan(EICAR).clean is True  # which is why it is refused above


def test_clamav_without_a_host_is_unavailable_not_silently_skipped() -> None:
    with pytest.raises(MalwareScanUnavailableError, match="host and a port"):
        build_scanner(backend="clamav")


def test_a_scan_result_carries_the_scanner_and_version() -> None:
    """A regulated audit must be able to say WHICH scanner cleared a document."""
    result = AlwaysCleanScanner().scan(PDF)
    assert result.scanner
    assert result.version


# ---------------------------------------------------------------------------
# File types
# ---------------------------------------------------------------------------


def test_a_pdf_is_accepted() -> None:
    content_type, name = validate_upload(
        data=PDF, filename="Safety Data Sheet.pdf", declared_content_type="application/pdf"
    )
    assert content_type == "application/pdf"
    assert name == "Safety Data Sheet.pdf"


def test_an_executable_renamed_to_pdf_is_refused() -> None:
    """🔴 The attack the extension check alone cannot see."""
    elf = b"\x7fELF\x02\x01\x01\x00" + b"\x00" * 64
    with pytest.raises(FileTypeRejectedError, match="the bytes are not"):
        validate_upload(data=elf, filename="sds.pdf", declared_content_type="application/pdf")


def test_a_declared_type_that_disagrees_with_the_bytes_is_refused() -> None:
    with pytest.raises(FileTypeRejectedError, match="disagrees"):
        validate_upload(data=PNG, filename="photo.png", declared_content_type="application/pdf")


def test_an_unlisted_type_is_refused() -> None:
    with pytest.raises(FileTypeRejectedError, match="not an accepted document type"):
        validate_upload(
            data=b"#!/bin/sh\necho hi\n",
            filename="run.sh",
            declared_content_type="text/x-shellscript",
        )


def test_an_empty_file_is_refused() -> None:
    with pytest.raises(FileTypeRejectedError, match="empty"):
        validate_upload(data=b"", filename="sds.pdf", declared_content_type="application/pdf")


def test_a_file_over_the_limit_is_refused_before_anything_else() -> None:
    oversized = b"%PDF-" + b"x" * MAX_UPLOAD_BYTES
    with pytest.raises(FileTypeRejectedError, match="the limit is"):
        validate_upload(
            data=oversized, filename="huge.pdf", declared_content_type="application/pdf"
        )


def test_text_is_validated_by_decoding_because_it_has_no_magic() -> None:
    ct, _ = validate_upload(
        data=b"temp,visc\n25,1200\n", filename="run.csv", declared_content_type="text/csv"
    )
    assert ct == "text/csv"

    with pytest.raises(FileTypeRejectedError, match="NUL"):
        validate_upload(data=b"a,b\n\x00\n", filename="run.csv", declared_content_type="text/csv")

    # Deliberately WITHOUT a NUL. The first draft used b"\xff\xfe\x00bad", which
    # tripped the NUL branch instead -- so it proved that branch twice and the
    # decode branch never. 0xFF is not a valid UTF-8 lead byte on its own.
    with pytest.raises(FileTypeRejectedError, match="not valid UTF-8"):
        validate_upload(data=b"\xff\xfe bad", filename="run.csv", declared_content_type="text/csv")


def test_a_traversal_filename_cannot_survive_as_a_display_name() -> None:
    assert "/" not in safe_display_filename("../../../etc/passwd")
    assert ".." not in safe_display_filename("../../../etc/passwd")
    assert safe_display_filename("../../../etc/passwd") == "passwd"


def test_a_filename_cannot_carry_markup_into_a_report() -> None:
    cleaned = safe_display_filename("<script>alert(1)</script>.pdf")
    assert "<" not in cleaned
    assert ">" not in cleaned


def test_a_nameless_file_still_gets_a_display_name() -> None:
    assert safe_display_filename("///") == "document"
