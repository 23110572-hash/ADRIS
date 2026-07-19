from functools import lru_cache
from typing import Literal

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_env: Literal["development", "staging", "production", "test"] = "development"
    frontend_url: str = ""
    database_url: str = ""
    database_migration_url: str | None = None
    redis_url: str = ""

    groq_api_key: str = ""
    groq_model: str = ""

    aws_access_key_id: str = ""
    aws_secret_access_key: str = ""
    aws_region: str = "ap-south-1"
    s3_quarantine_bucket: str = ""
    s3_evidence_bucket: str = ""
    s3_derivatives_bucket: str = ""
    s3_exports_bucket: str = ""
    aws_kms_key_id: str = ""

    jwt_issuer: str = ""
    jwt_audience: str = "adris-api"
    jwks_url: str = ""
    incident_token_secret: str = ""

    sentry_dsn: str = ""
    otel_exporter_otlp_endpoint: str = ""
    log_level: str = "INFO"
    max_upload_bytes: int = Field(default=25 * 1024 * 1024, ge=1, le=100 * 1024 * 1024)
    presign_ttl_seconds: int = Field(default=600, ge=60, le=3600)
    anonymous_incidents_enabled: bool = True
    agent_timeout_seconds: int = Field(default=30, ge=5, le=120)
    agent_max_steps: int = Field(default=10, ge=1, le=32)
    agent_max_tokens: int = Field(default=1200, ge=128, le=4096)

    @field_validator("database_url", "database_migration_url", mode="before")
    @classmethod
    def normalize_postgres_scheme(cls, value: str | None) -> str | None:
        if value and value.startswith("postgres://"):
            return value.replace("postgres://", "postgresql+psycopg://", 1)
        if value and value.startswith("postgresql://"):
            return value.replace("postgresql://", "postgresql+psycopg://", 1)
        return value

    @model_validator(mode="after")
    def validate_runtime_config(self) -> "Settings":
        # DATABASE_URL is mandatory: the app has no working localhost fallback.
        if not self.database_url:
            raise ValueError(
                "DATABASE_URL is not set. Provide the Neon PostgreSQL connection string; "
                "there is no localhost fallback."
            )
        local_markers = ("localhost", "127.0.0.1", "[::1]", "@localhost")
        if self.app_env == "production":
            for name, value in (
                ("DATABASE_URL", self.database_url),
                ("DATABASE_MIGRATION_URL", self.database_migration_url or ""),
                ("REDIS_URL", self.redis_url),
                ("FRONTEND_URL", self.frontend_url),
            ):
                if value and any(marker in value for marker in local_markers):
                    raise ValueError(
                        f"{name} points to localhost, which is invalid when APP_ENV=production."
                    )
        return self

    @property
    def cors_origins(self) -> list[str]:
        return [origin.strip().rstrip("/") for origin in self.frontend_url.split(",") if origin.strip()]

    @property
    def s3_ready(self) -> bool:
        return all(
            [
                self.s3_quarantine_bucket,
                self.s3_evidence_bucket,
                self.s3_derivatives_bucket,
                self.s3_exports_bucket,
            ]
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()
