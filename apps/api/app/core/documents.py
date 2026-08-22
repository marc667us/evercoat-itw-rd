"""Building the document pipeline's two ports from configuration.

Kept out of `app/api/` because a route must not decide which scanner it gets,
and out of the port modules because those must stay importable without
settings — `tests/test_upload_pipeline_units.py` builds both directly.

🔴 THE SCANNER IS BUILT ONCE PER PROCESS AND THE FAILURE IS DEFERRED.

`build_scanner()` raises when a backend is misconfigured. If that happened at
import time the API would refuse to start because of a *document upload*
setting, taking down formulation, testing and approvals with it. So the error
is captured and re-raised at `scan()`, which means the blast radius of "no
scanner configured" is exactly the uploads — and it is still impossible to
upload without one.
"""

from __future__ import annotations

from functools import lru_cache

from app.core.config import settings
from app.core.malware import (
    MalwareScannerPort,
    MalwareScanUnavailableError,
    ScannerUnavailable,
    build_scanner,
)
from app.core.object_storage import (
    FilesystemObjectStore,
    ObjectStorageError,
    ObjectStoragePort,
    S3ObjectStore,
)

__all__ = ["get_object_store", "get_scanner"]


@lru_cache(maxsize=1)
def get_object_store() -> ObjectStoragePort:
    backend = settings.object_store_backend.lower()
    if backend == "filesystem":
        return FilesystemObjectStore(settings.object_store_root)
    if backend == "s3":
        if not settings.garage_access_key or not settings.garage_secret_key:
            raise ObjectStorageError(
                "the s3 object store backend needs garage_access_key and garage_secret_key"
            )
        return S3ObjectStore(
            endpoint_url=settings.garage_endpoint,
            bucket=settings.garage_bucket,
            access_key=settings.garage_access_key,
            secret_key=settings.garage_secret_key,
        )
    raise ObjectStorageError(f"unknown object store backend: {backend!r}")


@lru_cache(maxsize=1)
def get_scanner() -> MalwareScannerPort:
    """The scanner, or one that refuses and says why.

    A configuration error becomes a `ScannerUnavailable` carrying the reason
    rather than an exception here, so the process starts and only uploads are
    refused. `ScannerUnavailable` raises on `scan()`, so nothing is admitted
    unscanned — the deferral changes WHEN the failure is seen, never whether.
    """
    try:
        return build_scanner(
            backend=settings.malware_scanner_backend,
            host=settings.clamav_host,
            port=settings.clamav_port,
            allow_test_scanner=settings.allow_test_scanner,
        )
    except MalwareScanUnavailableError as exc:
        return ScannerUnavailable(str(exc))
