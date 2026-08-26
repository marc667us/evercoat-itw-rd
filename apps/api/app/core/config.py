"""Application settings.

Every value is read from the environment. Nothing sensitive has a default
-- a missing database password should stop the process at startup, not
silently connect somewhere unintended.

Secrets reach the environment through SOPS + age (SECURITY.md §12), never
from a committed file. Note for anyone writing a secrets file on this
host: PowerShell pipelines add a UTF-16 BOM, which makes the first key
unparseable in a way that looks like a wrong password. Write UTF-8
explicitly.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

__all__ = ["Settings", "get_settings", "settings"]


from app.core.object_storage import default_object_store_root


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # --- Identity -------------------------------------------------------
    app_name: str = "EvercoatITWRD APP"
    app_slug: str = "evercoat-itw-rd"
    app_env: Literal["development", "staging", "production"] = "development"

    # --- Database -------------------------------------------------------
    # No default. The app must never guess a connection string.
    database_url: str = Field(..., description="SQLAlchemy URL for the runtime app role")
    db_pool_size: int = 10
    db_max_overflow: int = 5
    db_echo: bool = False

    # 🔴 A SECOND CONNECTION, FOR SIGN-IN ONLY (I109, migration 053).
    #
    # `core.principal_for_subject` and `core.memberships_for_subject` take a
    # SUBJECT AS AN ARGUMENT and cannot check their caller -- they exist to
    # answer before a session has an organization, so there is nothing yet to
    # compare against. On the runtime connection that made them an
    # identity-enumeration primitive: an ordinary member could read any named
    # subject's address and every organization it belongs to.
    #
    # Neither a GUC nor `SET ROLE` closes that, because anything able to run
    # SQL as `evercoat_app` can set either. Privilege has to follow the
    # CONNECTION. `evercoat_auth` holds EXECUTE on exactly those two functions
    # and no table privilege at all.
    #
    # ⚠️ OPTIONAL HERE, AND ENFORCED BY THE DATABASE INSTEAD. Making it
    # required would turn every unconfigured tool that imports `settings` --
    # seed scripts, one-off maintenance, `alembic` -- into an import error for
    # a connection it never opens. Migration 053 has already revoked EXECUTE
    # from `evercoat_app`, so an environment that omits this cannot sign
    # anybody in whatever this field says: there is no configuration in which
    # the fix reads as applied and the old privilege still works. The failure
    # is surfaced early by `/health/ready`, which reports this connection.
    auth_database_url: str | None = Field(
        default=None,
        description="SQLAlchemy URL for the sign-in role (evercoat_auth). I109.",
    )

    # --- Keycloak -------------------------------------------------------
    keycloak_issuer: str = Field(..., description="Realm issuer URL")
    keycloak_audience: str = Field(default="evercoat-api")
    # JWKS is cached; this bounds how long a revoked signing key stays
    # trusted after a realm key rotation.
    jwks_cache_seconds: int = 300

    # --- Cache / worker -------------------------------------------------
    valkey_url: str = "redis://valkey:6379/0"

    # --- Object storage -------------------------------------------------
    garage_endpoint: str = "http://garage:3900"
    garage_bucket: str = "evercoat-documents"
    garage_access_key: str | None = None
    garage_secret_key: str | None = None
    # Short by design. A signed URL outlives access revocation (Codex F38),
    # so the window is kept small and sensitive formulation documents go
    # through an authorization-checking proxy instead.
    signed_url_ttl_seconds: int = 120

    # Which ObjectStoragePort adapter to build. "filesystem" is the supported
    # configuration for development and CI -- not a test double: running Garage
    # costs memory this host does not have (measured 1.8 GB free of 7.9 GB on
    # 2026-08-22). "s3" reaches Garage locally and Oracle Object Storage in
    # production, which is the same API by ADR-004.
    object_store_backend: str = "filesystem"
    # 🔴 NEITHER AN UNWRITABLE SYSTEM PATH NOR THE SHARED TEMP DIRECTORY.
    #
    # First draft: `/var/lib/evercoat/documents` -- which no CI runner and no
    # developer machine can create, so the API failed at dependency resolution
    # rather than at upload.
    #
    # Second draft: `<tempdir>/evercoat-documents`. Worse, in two ways the
    # Supervisor named. (a) LOSSY -- a temp directory is swept on reboot, and
    # the rows survive still claiming `approved` with a checksum, which is
    # I41's exact shape restored by omission. (b) On a shared Linux host `/tmp`
    # is world-writable and the name is fixed and predictable, and since
    # `FilesystemObjectStore.__init__` no longer creates the root, an
    # unprivileged local user can create it first -- or symlink it -- and then
    # read every stored Safety Data Sheet, or make every upload 503 because
    # `_resolve` rejects the symlinked path.
    #
    # So: a path inside the application's own tree, created with the process
    # umask under a directory only it uses. A container deployment mounts a
    # volume here; `infrastructure/compose/docker-compose.yml` does.
    object_store_root: str = str(default_object_store_root())

    # --- Malware scanning ------------------------------------------------
    # 🔴 THE DEFAULT REFUSES. There is deliberately no "scanning disabled"
    # value: a deployment that has not configured a scanner gets a 503 on
    # upload rather than a document store quietly filling with unscanned
    # files. See app/core/malware.py.
    malware_scanner_backend: str = "unavailable"
    clamav_host: str = "clamav"
    clamav_port: int = 3310
    # Gates the AlwaysCleanScanner, which admits every file. Separate from the
    # backend name so "always-clean" cannot be reached by setting one variable
    # on a real deployment.
    allow_test_scanner: bool = False

    # --- AI (Slice 7 onward) --------------------------------------------
    # Local runtime only. The zero-cost rule forbids an essential paid AI
    # API, and proprietary formulations must not leave the organization's
    # infrastructure -- that is a security property first, cost second.
    ollama_base_url: str = "http://ollama:11434"
    ollama_model: str | None = None  # chosen from measured memory headroom

    # --- Observability --------------------------------------------------
    log_format: Literal["json", "console"] = "json"
    log_level: str = "INFO"
    metrics_enabled: bool = True

    # --- Security -------------------------------------------------------
    cors_allowed_origins: list[str] = Field(default_factory=list)

    @field_validator("database_url")
    @classmethod
    def _reject_superuser(cls, v: str) -> str:
        """Refuse to start as a database superuser.

        Superuser bypasses Row Level Security. Running the application as
        one hides exactly the defects RLS exists to catch, and they would
        only surface in production (ADR-017). This is a cheap guard
        against a mistake that is expensive and silent.
        """
        lowered = v.lower()
        for forbidden in ("://postgres:", "://postgres@", "user=postgres"):
            if forbidden in lowered:
                raise ValueError(
                    "the application must not connect as a database superuser; "
                    "use the evercoat_app role, which is subject to FORCE RLS"
                )
        return v

    @field_validator("cors_allowed_origins")
    @classmethod
    def _no_wildcard_in_prod(cls, v: list[str], info) -> list[str]:  # type: ignore[no-untyped-def]
        if "*" in v and info.data.get("app_env") == "production":
            raise ValueError("wildcard CORS origin is not permitted in production")
        return v

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]


settings = get_settings()
