"""Application configuration loaded from environment variables."""

from functools import lru_cache
from typing import Literal

from pydantic import AliasChoices, Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_INSECURE_SECRET_MARKERS = (
    "change-me",
    "changeme",
    "secret",
    "placeholder",
    "dev-secret",
)


class Settings(BaseSettings):
    """Typed application settings backed by environment variables and .env."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    APP_NAME: str = "College Management System"
    ENVIRONMENT: Literal["development", "staging", "production"] = Field(
        default="development",
        validation_alias=AliasChoices("ENVIRONMENT", "APP_ENV"),
    )
    DEBUG: bool = False
    LOG_LEVEL: str = "INFO"

    DATABASE_URL: str = Field(..., repr=False)
    DIRECT_DATABASE_URL: str | None = Field(default=None, repr=False)
    DB_POOL_SIZE: int = Field(default=10, ge=1, le=100)
    DB_MAX_OVERFLOW: int = Field(default=20, ge=0, le=100)
    DB_POOL_RECYCLE: int = Field(default=1800, ge=60)

    SECRET_KEY: SecretStr
    ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(default=30, ge=5, le=1440)
    FRONTEND_URL: str = "http://127.0.0.1:5500"

    LOGIN_RATE_LIMIT_MAX_ATTEMPTS: int = Field(default=5, ge=1, le=100)
    LOGIN_RATE_LIMIT_WINDOW_SECONDS: int = Field(default=60, ge=10, le=3600)

    # Object Storage (Cloudflare R2 / S3-compatible)
    STORAGE_PROVIDER: str = "r2"
    R2_ACCOUNT_ID: str | None = None
    R2_ACCESS_KEY_ID: SecretStr | None = None
    R2_SECRET_ACCESS_KEY: SecretStr | None = None
    R2_BUCKET_NAME: str | None = None
    R2_ENDPOINT_URL: str | None = None
    R2_PUBLIC_BASE_URL: str | None = None
    STORAGE_TIMEOUT_SECONDS: int = Field(default=15, ge=1, le=120)
    SIGNED_URL_EXPIRE_SECONDS: int = Field(default=300, ge=30, le=3600)
    MAX_DOCUMENT_UPLOAD_BYTES: int = Field(default=10 * 1024 * 1024, ge=1024)
    MAX_ASSIGNMENT_UPLOAD_BYTES: int = Field(default=20 * 1024 * 1024, ge=1024)

    @staticmethod
    def _normalize_postgres_url(url: str) -> str:
        """Ensure PostgreSQL URLs use the psycopg3 SQLAlchemy dialect."""
        if url.startswith("postgres://"):
            return "postgresql+psycopg://" + url[len("postgres://") :]
        if url.startswith("postgresql://"):
            return "postgresql+psycopg://" + url[len("postgresql://") :]
        return url

    @property
    def effective_database_url(self) -> str:
        """Return normalized SQLAlchemy database URL for application traffic."""
        return self._normalize_postgres_url(self.DATABASE_URL)

    @property
    def effective_migration_database_url(self) -> str:
        """Return direct database URL for Alembic migrations if configured."""
        raw = self.DIRECT_DATABASE_URL or self.DATABASE_URL
        return self._normalize_postgres_url(raw)

    @property
    def effective_r2_endpoint(self) -> str | None:
        """Return explicit R2_ENDPOINT_URL or derive it from R2_ACCOUNT_ID."""
        if self.R2_ENDPOINT_URL:
            return self.R2_ENDPOINT_URL.rstrip("/")
        if self.R2_ACCOUNT_ID:
            return f"https://{self.R2_ACCOUNT_ID}.r2.cloudflarestorage.com"
        return None

    @property
    def APP_ENV(self) -> str:
        """Backwards-compatible alias for ENVIRONMENT."""
        return self.ENVIRONMENT

    @property
    def is_production(self) -> bool:
        """Return True when running in production environment."""
        return self.ENVIRONMENT == "production"

    @property
    def cors_origins(self) -> list[str]:
        """Return normalized allowed CORS origins from FRONTEND_URL."""
        return [
            origin.strip().rstrip("/")
            for origin in self.FRONTEND_URL.split(",")
            if origin.strip()
        ]

    @model_validator(mode="after")
    def validate_production_settings(self) -> "Settings":
        """Enforce strict security invariants in production."""
        if "*" in self.cors_origins:
            raise ValueError(
                "Wildcard '*' is not allowed in FRONTEND_URL with credentials."
            )

        if self.is_production:
            if self.DEBUG:
                raise ValueError("DEBUG must be false in production.")

            secret = self.SECRET_KEY.get_secret_value()
            if len(secret) < 32 or any(
                marker in secret.lower() for marker in _INSECURE_SECRET_MARKERS
            ):
                raise ValueError(
                    "SECRET_KEY must be >= 32 random characters in production."
                )

            if not self.cors_origins:
                raise ValueError(
                    "FRONTEND_URL must specify an explicit origin in production."
                )

            if any(not o.startswith("https://") for o in self.cors_origins):
                raise ValueError("Production FRONTEND_URL origins must use https://.")

            if "sslmode=require" not in self.DATABASE_URL:
                raise ValueError(
                    "Production DATABASE_URL must require SSL (sslmode=require)."
                )

        return self


@lru_cache
def get_settings() -> Settings:
    """Return cached application settings instance."""
    return Settings()
