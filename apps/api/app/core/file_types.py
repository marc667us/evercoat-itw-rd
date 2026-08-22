"""What an uploaded file is ALLOWED to be, decided from its bytes.

🔴 THE EXTENSION AND THE DECLARED CONTENT-TYPE ARE BOTH CLAIMS BY THE UPLOADER.
Security source §21: *"Do not trust only .pdf, .docx, etc. Check the actual
MIME/file signature."*

So three things must agree before a file is accepted: the **magic bytes**, the
**extension**, and the declared **content type**. Any disagreement is a
refusal, not a correction — silently "fixing" a mislabelled file would mean the
store's metadata describes something the uploader did not send, and the
downstream RAG ingestion (E7/E10) parses by declared type.

WHY NOT python-magic / libmagic
-------------------------------
`libmagic` is a system package, and the allow-list here is nine formats whose
signatures are short and stable. Sniffing them directly costs no dependency, no
container layer and no version skew between the developer's machine, CI and
Oracle — and it is auditable in one screen, which a 5 MB magic database is not.
If the allow-list ever needs to be broad, that trade changes; today breadth is
the opposite of what is wanted.

⚠️ THE ALLOW-LIST IS THE CONTROL. Nothing executable is on it, and nothing is
added to it without a stated R&D use case. Security source §51: *"Do not allow
executable file types unless a legitimate R&D use case later requires them."*
"""

from __future__ import annotations

import re
from dataclasses import dataclass

__all__ = [
    "ALLOWED_TYPES",
    "MAX_UPLOAD_BYTES",
    "AllowedType",
    "FileTypeRejectedError",
    "safe_display_filename",
    "validate_upload",
]

# 25 MB. An SDS is tens of kilobytes; a lab photograph or an instrument export
# is the reason this is not 1 MB. It is a DoS bound as much as a storage one:
# every accepted byte is hashed, held in memory for the scanner, and streamed
# to clamd.
MAX_UPLOAD_BYTES = 25 * 1024 * 1024


class FileTypeRejectedError(ValueError):
    """The upload is not an allowed type, or its claims disagree."""


@dataclass(frozen=True, slots=True)
class AllowedType:
    content_type: str
    extensions: tuple[str, ...]
    # Each entry is (offset, signature). A type matches if ANY entry matches.
    signatures: tuple[tuple[int, bytes], ...]
    description: str


# ZIP-container formats (docx, xlsx) share the PK signature, so the magic alone
# cannot separate them from each other or from a plain .zip. That is accepted
# deliberately: the extension and declared type disambiguate WITHIN the
# container family, while the magic still refuses anything that is not a ZIP at
# all. What it stops is the case that matters — a .docx that is really a PDF,
# an ELF, or a script.
_ZIP = ((0, b"PK\x03\x04"), (0, b"PK\x05\x06"), (0, b"PK\x07\x08"))

ALLOWED_TYPES: tuple[AllowedType, ...] = (
    AllowedType("application/pdf", (".pdf",), ((0, b"%PDF-"),), "SDS, TDS, CoA, reports"),
    AllowedType("image/png", (".png",), ((0, b"\x89PNG\r\n\x1a\n"),), "lab photographs"),
    AllowedType("image/jpeg", (".jpg", ".jpeg"), ((0, b"\xff\xd8\xff"),), "lab photographs"),
    AllowedType("image/tiff", (".tif", ".tiff"), ((0, b"II*\x00"), (0, b"MM\x00*")), "microscopy"),
    AllowedType(
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        (".docx",),
        _ZIP,
        "technical documents",
    ),
    AllowedType(
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        (".xlsx",),
        _ZIP,
        "instrument exports, test data",
    ),
)

# Text formats have no magic bytes at all. They are validated by DECODING
# rather than by signature: a file that is not valid UTF-8, or that contains
# NUL, is not text whatever it is named.
_TEXT_TYPES: dict[str, tuple[str, ...]] = {
    "text/csv": (".csv",),
    "text/plain": (".txt",),
}

_SAFE_DISPLAY = re.compile(r"[^A-Za-z0-9 ._()\-]+")


def safe_display_filename(raw: str) -> str:
    """Reduce a user's filename to something safe to STORE AND SHOW.

    It is never a path — the object key is a generated UUID (see
    `new_object_key`). This value exists so a chemist recognises the document
    in a list, so the requirement is only that it cannot carry traversal,
    control characters, or markup into a UI or a report.
    """
    name = raw.replace("\\", "/").rsplit("/", 1)[-1]
    name = _SAFE_DISPLAY.sub("_", name).strip(" ._")
    name = re.sub(r"_{2,}", "_", name)
    return name[:200] or "document"


def _matches_signature(data: bytes, allowed: AllowedType) -> bool:
    return any(data[offset : offset + len(sig)] == sig for offset, sig in allowed.signatures)


def validate_upload(
    *, data: bytes, filename: str, declared_content_type: str | None
) -> tuple[str, str]:
    """Return `(canonical_content_type, safe_display_name)` or raise.

    Order matters. Size is checked first because everything after it costs
    time proportional to the content, and an unbounded upload should be
    refused before it is hashed, decoded or streamed to a scanner.
    """
    if not data:
        raise FileTypeRejectedError("the uploaded file is empty")
    if len(data) > MAX_UPLOAD_BYTES:
        raise FileTypeRejectedError(
            f"the file is {len(data)} bytes; the limit is {MAX_UPLOAD_BYTES}"
        )

    display = safe_display_filename(filename)
    suffix = ("." + display.rsplit(".", 1)[-1].lower()) if "." in display else ""
    declared = (declared_content_type or "").split(";")[0].strip().lower()

    for allowed in ALLOWED_TYPES:
        if suffix not in allowed.extensions:
            continue
        if not _matches_signature(data, allowed):
            raise FileTypeRejectedError(
                f"the file is named {suffix} but its contents are not "
                f"{allowed.content_type}. The extension is a claim; the bytes "
                f"are not."
            )
        if declared and declared != allowed.content_type:
            raise FileTypeRejectedError(
                f"the declared content type {declared!r} disagrees with the "
                f"file's extension and contents ({allowed.content_type})"
            )
        return allowed.content_type, display

    for content_type, extensions in _TEXT_TYPES.items():
        if suffix not in extensions:
            continue
        if b"\x00" in data:
            raise FileTypeRejectedError(f"a {suffix} file contains NUL bytes, so it is not text")
        try:
            data.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise FileTypeRejectedError(
                f"a {suffix} file is not valid UTF-8, so it is not text"
            ) from exc
        if declared and declared != content_type:
            raise FileTypeRejectedError(
                f"the declared content type {declared!r} disagrees with {suffix}"
            )
        return content_type, display

    permitted = ", ".join(
        sorted(
            {ext for a in ALLOWED_TYPES for ext in a.extensions}
            | {e for v in _TEXT_TYPES.values() for e in v}
        )
    )
    raise FileTypeRejectedError(
        f"{suffix or 'a file with no extension'} is not an accepted document "
        f"type. Accepted: {permitted}"
    )
