"""Application settings, loaded from environment variables."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Always load backend/.env by absolute path so the app behaves the same whether
# uvicorn is launched from backend/ or the repo root. Real environment variables
# (e.g. those injected by docker compose) still take precedence over this file.
_BACKEND_DIR = Path(__file__).resolve().parents[2]
_ENV_FILE = _BACKEND_DIR / ".env"

KNOWN_FRONTEND_ORIGINS = {
    "https://biolympics-live.vercel.app",
    "https://usf26.pxxl.run",
}


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(_ENV_FILE), env_file_encoding="utf-8", extra="ignore"
    )

    # --- App ---
    app_env: str = Field("development", alias="APP_ENV")
    app_name: str = Field("BIOLYMPICS LIVE", alias="APP_NAME")
    app_url: str = Field("http://localhost:5173", alias="APP_URL")
    api_base_url: str = Field("http://localhost:8000", alias="API_BASE_URL")
    log_level: str = Field("INFO", alias="LOG_LEVEL")
    timezone: str = Field("Africa/Lagos", alias="TZ")

    # --- Security ---
    secret_key: str = Field("dev-insecure-secret-change-me", alias="SECRET_KEY")
    access_token_ttl_minutes: int = Field(15, alias="ACCESS_TOKEN_TTL_MINUTES")
    refresh_token_ttl_days: int = Field(14, alias="REFRESH_TOKEN_TTL_DAYS")
    cors_origins: str = Field("http://localhost:5173", alias="CORS_ORIGINS")
    trusted_hosts: str = Field("localhost,127.0.0.1", alias="TRUSTED_HOSTS")

    # --- Data stores ---
    database_url: str = Field(
        "postgresql+asyncpg://biolympics:biolympics@localhost:5432/biolympics",
        alias="DATABASE_URL",
    )
    redis_url: str = Field("redis://localhost:6379/0", alias="REDIS_URL")
    celery_broker_url: str = Field("redis://localhost:6379/1", alias="CELERY_BROKER_URL")
    celery_result_backend: str = Field("redis://localhost:6379/2", alias="CELERY_RESULT_BACKEND")

    # --- Web push (VAPID) ---
    vapid_public_key: str = Field("", alias="VAPID_PUBLIC_KEY")
    vapid_private_key: str = Field("", alias="VAPID_PRIVATE_KEY")
    vapid_subject: str = Field("mailto:admin@biolympics.example", alias="VAPID_SUBJECT")

    # --- Media storage (Cloudinary) ---
    cloudinary_cloud_name: str = Field("", alias="CLOUDINARY_CLOUD_NAME")
    cloudinary_api_key: str = Field("", alias="CLOUDINARY_API_KEY")
    cloudinary_api_secret: str = Field("", alias="CLOUDINARY_API_SECRET")
    cloudinary_upload_folder: str = Field("biolympics", alias="CLOUDINARY_UPLOAD_FOLDER")

    # --- Initial admin (dev only) ---
    initial_admin_email: str = Field("admin@biolympics.ng", alias="INITIAL_ADMIN_EMAIL")
    initial_admin_password: str = Field("ChangeMe!2026", alias="INITIAL_ADMIN_PASSWORD")

    # --- Observability ---
    sentry_dsn: str = Field("", alias="SENTRY_DSN")

    @field_validator("app_env")
    @classmethod
    def _normalize_env(cls, v: str) -> str:
        return v.strip().lower()

    @property
    def is_production(self) -> bool:
        return self.app_env in {"production", "prod"}

    @property
    def cors_origin_list(self) -> list[str]:
        origins = [o.strip().rstrip("/") for o in self.cors_origins.split(",") if o.strip()]
        if self.app_url:
            origins.append(self.app_url.strip().rstrip("/"))
        origins.extend(KNOWN_FRONTEND_ORIGINS)
        return list(dict.fromkeys(origins))

    @property
    def trusted_host_list(self) -> list[str]:
        return [h.strip() for h in self.trusted_hosts.split(",") if h.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
