"""Factory for resolving the configured external storage backend."""

from app.core.config import get_settings
from app.storage.base import StorageBackend, StorageConfigurationError
from app.storage.s3_storage import S3CompatibleStorage


def get_storage_backend() -> StorageBackend:
    """Instantiate the configured object storage backend from settings."""
    settings = get_settings()
    provider = settings.STORAGE_PROVIDER.strip().lower()
    if provider in {"r2", "s3"}:
        return S3CompatibleStorage(
            endpoint_url=settings.effective_r2_endpoint,
            access_key_id=(
                settings.R2_ACCESS_KEY_ID.get_secret_value()
                if settings.R2_ACCESS_KEY_ID
                else None
            ),
            secret_access_key=(
                settings.R2_SECRET_ACCESS_KEY.get_secret_value()
                if settings.R2_SECRET_ACCESS_KEY
                else None
            ),
            bucket_name=settings.R2_BUCKET_NAME,
            timeout_seconds=settings.STORAGE_TIMEOUT_SECONDS,
        )
    raise StorageConfigurationError(
        f"Unsupported storage provider: {settings.STORAGE_PROVIDER}"
    )
