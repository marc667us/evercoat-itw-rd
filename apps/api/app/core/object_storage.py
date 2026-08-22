"""The port bytes are stored through, and its two adapters.

🔴 WHY THIS FILE EXISTS AT ALL — I41.

`materials.material_documents` has carried a `storage_key`, a `checksum_sha256`
and a `byte_size` since migration 015. `POST /api/materials/{id}/documents`
writes those rows and is permission-gated. **Nothing has ever written the
bytes.** `boto3` was declared in `pyproject.toml` at Slice 1 and never
imported; Garage runs in the compose stack serving nobody.

That is not a missing feature. It is a safety control that reports success:
`formulations/service.py` and `msd_conductor.py` both block formula submission
on `requires_sds AND sds_count == 0`, and they **count rows**. So any holder of
`material.edit` satisfies the SDS control the golden scenario exists to
demonstrate by registering `storage_key = "sds/anything.pdf"`, and no Safety
Data Sheet need exist anywhere.

THE RULE THIS PORT ENFORCES
---------------------------
**A stored object's checksum is computed from the bytes actually written, by
the store, and returned to the caller.** The caller does not supply it. A row
therefore cannot claim a file the store does not hold, because the value that
proves the file is only obtainable by storing it.

WHY TWO ADAPTERS AND NOT JUST S3
--------------------------------
`FilesystemObjectStore` is not a test double. It is the supported
configuration for local development and CI, where running Garage would cost
memory this host does not have (measured 2026-08-22: 1.8 GB free of 7.9 GB).
`S3ObjectStore` speaks to Garage locally and to Oracle Object Storage in
production — the same API, which is why ADR-004 chose an S3-compatible store.

⚠️ ADR-004's caveat stands: **not drop-in**. Multipart, signing, versioning and
retention differ between Garage and Oracle. This port exposes none of those, so
the difference cannot leak into a domain service; when one is needed it is
added here deliberately, with an adapter test for each backend.
"""

from __future__ import annotations

import hashlib
import shutil
import uuid
from pathlib import Path
from typing import BinaryIO, Protocol

__all__ = [
    "FilesystemObjectStore",
    "ObjectStorageError",
    "ObjectStoragePort",
    "S3ObjectStore",
    "StoredObject",
    "default_object_store_root",
    "new_object_key",
]


def default_object_store_root() -> Path:
    """Where documents live when nothing configures it. ONE definition.

    Inside the application's own tree, deliberately:

    * NOT `/var/lib/evercoat/documents` -- unwritable on every CI runner and
      developer machine, and because the store no longer creates its root
      eagerly the failure surfaced at dependency resolution.
    * NOT the shared temp directory -- swept on reboot, which leaves rows
      claiming `approved` with a checksum for bytes that are gone (I41's shape,
      restored by omission), and on a shared Linux host it is a world-writable
      directory at a predictable name that an unprivileged user can create or
      symlink first.

    A container deployment mounts a volume over this path.
    """
    return Path(__file__).resolve().parents[2] / "var" / "documents"


class ObjectStorageError(RuntimeError):
    """The store could not satisfy the request.

    Deliberately distinct from a domain error: a caller must never map this to
    "the document is absent". A store that is unreachable is an outage, and
    treating it as absence would let a safety gate that depends on document
    presence silently open.
    """


class StoredObject:
    """What the store observed while writing. Not what the caller claimed."""

    __slots__ = ("byte_size", "checksum_sha256", "key")

    def __init__(self, key: str, checksum_sha256: str, byte_size: int) -> None:
        self.key = key
        self.checksum_sha256 = checksum_sha256
        self.byte_size = byte_size

    def __repr__(self) -> str:  # pragma: no cover - diagnostic only
        return (
            f"StoredObject(key={self.key!r}, "
            f"checksum_sha256={self.checksum_sha256!r}, byte_size={self.byte_size})"
        )


def new_object_key(organization_id: uuid.UUID, kind: str) -> str:
    """An application-generated key. The user's filename is never a path.

    🔴 §23 of the security source: *"Never use a user's raw filename directly
    as a filesystem path"* — `../../../etc/passwd`, control characters,
    Unicode look-alikes, and names that collide on a case-insensitive
    filesystem are all reachable from an upload form. The original filename is
    kept as metadata on the row and is never resolved against anything.

    The organization prefix is for operability (per-tenant listing, lifecycle
    rules), NOT for authorization. Authorization is the database's job; a key
    that merely *looks* scoped would be an invitation to check the string
    instead of the row.
    """
    safe_kind = "".join(c for c in kind.lower() if c.isalnum() or c == "-") or "document"
    return f"{organization_id}/{safe_kind}/{uuid.uuid4()}"


class ObjectStoragePort(Protocol):
    """Bytes in, bytes out, and proof of what was written."""

    def put(self, key: str, stream: BinaryIO, content_type: str) -> StoredObject:
        """Store `stream` at `key`; return what was actually written."""
        ...

    def get(self, key: str) -> bytes:
        """Retrieve the object. Raises `ObjectStorageError` if absent."""
        ...

    def exists(self, key: str) -> bool:
        """Whether the object is retrievable **now**."""
        ...

    def delete(self, key: str) -> None:
        """Remove the object. Idempotent."""
        ...


def _digest(stream: BinaryIO, sink: BinaryIO | None) -> tuple[str, int]:
    """Hash and optionally copy in one pass, without loading the whole file.

    Chunked because an SDS is small and a lab photograph or an instrument
    export is not, and a document pipeline that reads whole files into memory
    fails first on the machine with least of it.
    """
    hasher = hashlib.sha256()
    size = 0
    while True:
        chunk = stream.read(1024 * 1024)
        if not chunk:
            break
        hasher.update(chunk)
        size += len(chunk)
        if sink is not None:
            sink.write(chunk)
    return hasher.hexdigest(), size


class FilesystemObjectStore:
    """Local disk. The supported store for development and CI.

    Keys contain `/`, so they nest as directories. `_resolve` refuses any key
    that escapes the root even though keys are application-generated — the
    check costs nothing and the day someone passes a user-influenced key
    through is the day it matters.
    """

    def __init__(self, root: Path | str) -> None:
        # 🔴 DOES NOT CREATE THE ROOT. Constructing a store must not touch the
        # filesystem.
        #
        # The first version called `mkdir(parents=True)` here, so building the
        # object simply FAILED on an unwritable path -- and because
        # `get_object_store()` is a FastAPI dependency, that took down
        # dependency resolution for the route rather than producing a handled
        # error. CI found it: the default root is an absolute system path
        # (`/var/lib/evercoat/documents`) and the runner is not root, so the
        # Auth job died with PermissionError before any request was served.
        #
        # The directory is created on the first `put` instead, where a failure
        # is an `ObjectStorageError` the route maps to 503.
        self._root = Path(root).resolve()

    def _resolve(self, key: str) -> Path:
        candidate = (self._root / key).resolve()
        if not candidate.is_relative_to(self._root):
            raise ObjectStorageError(f"key escapes the storage root: {key!r}")
        return candidate

    def put(self, key: str, stream: BinaryIO, content_type: str) -> StoredObject:
        path = self._resolve(key)
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            raise ObjectStorageError(
                f"could not create the storage directory for {key!r}: {exc}"
            ) from exc
        # Write to a sibling temporary file and rename, so a crash mid-write
        # cannot leave a short file that hashes to nothing anyone expects but
        # still satisfies `exists()`.
        staging = path.with_suffix(path.suffix + f".part-{uuid.uuid4().hex[:8]}")
        try:
            with staging.open("wb") as sink:
                checksum, size = _digest(stream, sink)
            staging.replace(path)
        except OSError as exc:
            staging.unlink(missing_ok=True)
            raise ObjectStorageError(f"could not write {key!r}: {exc}") from exc
        return StoredObject(key=key, checksum_sha256=checksum, byte_size=size)

    def get(self, key: str) -> bytes:
        path = self._resolve(key)
        try:
            return path.read_bytes()
        except OSError as exc:
            raise ObjectStorageError(f"could not read {key!r}: {exc}") from exc

    def exists(self, key: str) -> bool:
        try:
            return self._resolve(key).is_file()
        except ObjectStorageError:
            return False

    def delete(self, key: str) -> None:
        try:
            self._resolve(key).unlink(missing_ok=True)
        except OSError as exc:  # pragma: no cover - filesystem-specific
            raise ObjectStorageError(f"could not delete {key!r}: {exc}") from exc

    def clear(self) -> None:
        """Test helper. Present so a test never reaches for `shutil` itself."""
        shutil.rmtree(self._root, ignore_errors=True)


class S3ObjectStore:
    """Garage locally, Oracle Object Storage in production.

    `boto3` is imported inside `__init__` rather than at module scope so the
    filesystem adapter — the one CI uses — never pays for it, and so a missing
    optional dependency surfaces when this adapter is *chosen* rather than when
    the module is merely imported.
    """

    def __init__(
        self,
        *,
        endpoint_url: str,
        bucket: str,
        access_key: str,
        secret_key: str,
        region: str = "garage",
    ) -> None:
        try:
            import boto3
        except ImportError as exc:  # pragma: no cover - dependency is declared
            raise ObjectStorageError(
                "boto3 is required for S3ObjectStore but is not installed"
            ) from exc

        self._bucket = bucket
        self._client = boto3.client(
            "s3",
            endpoint_url=endpoint_url,
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            region_name=region,
        )

    def put(self, key: str, stream: BinaryIO, content_type: str) -> StoredObject:
        # Hash first, then upload from the rewound stream. Two passes, but the
        # checksum must describe the bytes that were sent, and computing it
        # from a response header would trust the server to describe its own
        # write — some S3 implementations return an ETag that is not SHA-256
        # and, for multipart, not a hash of the content at all.
        checksum, size = _digest(stream, None)
        try:
            stream.seek(0)
        except (OSError, AttributeError) as exc:
            raise ObjectStorageError(
                "S3ObjectStore needs a seekable stream so the checksum can "
                "describe the bytes that were uploaded"
            ) from exc
        try:
            self._client.put_object(
                Bucket=self._bucket,
                Key=key,
                Body=stream,
                ContentType=content_type,
            )
        except Exception as exc:
            raise ObjectStorageError(f"could not write {key!r}: {exc}") from exc
        return StoredObject(key=key, checksum_sha256=checksum, byte_size=size)

    def get(self, key: str) -> bytes:
        try:
            response = self._client.get_object(Bucket=self._bucket, Key=key)
            return bytes(response["Body"].read())
        except Exception as exc:
            raise ObjectStorageError(f"could not read {key!r}: {exc}") from exc

    def exists(self, key: str) -> bool:
        try:
            self._client.head_object(Bucket=self._bucket, Key=key)
        except Exception:  # noqa: BLE001 - a 404 is an ordinary answer here
            return False
        return True

    def delete(self, key: str) -> None:
        try:
            self._client.delete_object(Bucket=self._bucket, Key=key)
        except Exception as exc:
            raise ObjectStorageError(f"could not delete {key!r}: {exc}") from exc
