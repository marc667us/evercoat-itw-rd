# -*- coding: utf-8 -*-
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

from pydantic import Field, PostgresDsn, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

__all__ = ["Settings", "settings", "get_settings"]


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
