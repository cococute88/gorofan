"""Application configuration (design 8.10).

Pydantic Settings loads from environment / .env. A single ``DATABASE_URL`` switch
governs SQLite <-> PostgreSQL (design 4.4 / 8.6). Secrets use ``SecretStr``.
"""
from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_nested_delimiter="__",
        extra="ignore",
    )

    # --- core ---
    APP_ENV: Literal["local", "dev", "prod"] = "local"
    APP_SECRET_KEY: SecretStr = SecretStr("change-me-dev-only-secret-key-0123456789")
    DATABASE_URL: str = "sqlite+aiosqlite:///./data/app.db"

    # --- auth (FR-AUTH-2) ---
    AUTH_ENABLED: bool = False
    JWT_ALG: str = "HS256"
    JWT_TTL_SECONDS: int = 60 * 60 * 24 * 30
    REFRESH_TTL_SECONDS: int = 60 * 60 * 24 * 60
    GOOGLE_CLIENT_ID: str | None = None
    GOOGLE_CLIENT_SECRET: SecretStr | None = None
    OAUTH_REDIRECT_BASE: str = "http://localhost:8000"

    # --- providers / runtime ---
    PROVIDER_MAX_CONCURRENCY: int = 4
    PROVIDER_TIMEOUT_SECONDS: int = 60

    # --- storage / jobs ---
    MEDIA_ROOT: str = "./data/media"
    STORAGE_BACKEND: Literal["local", "s3"] = "local"
    JOB_BACKEND: Literal["inproc", "celery", "arq"] = "inproc"
    MAX_UPLOAD_BYTES: int = 5 * 1024 * 1024

    # --- feature flags (design 7.15 / 8.10) ---
    FEATURES: dict[str, bool] = {}

    # --- cors ---
    CORS_ORIGINS: str = "http://localhost:3000"

    # Fixed default-user id for local single-user mode (design 14.2)
    DEFAULT_USER_ID: str = "00000000-0000-0000-0000-000000000001"

    @property
    def cors_origins(self) -> list[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]

    @property
    def is_sqlite(self) -> bool:
        return self.DATABASE_URL.startswith("sqlite")


@lru_cache
def get_settings() -> Settings:
    """Singleton settings accessor (design 8.4.1)."""
    return Settings()
