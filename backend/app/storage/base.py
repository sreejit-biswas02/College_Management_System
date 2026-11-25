"""Provider-independent object storage interface and exceptions."""

from dataclasses import dataclass
from typing import BinaryIO, Protocol


class StorageError(Exception):
    """Raised when an external object storage operation fails."""


class StorageConfigurationError(StorageError):
    """Raised when required object storage credentials/config are missing."""


@dataclass(frozen=True)
class StoredObjectInfo:
    """Metadata returned by the storage provider for a stored object."""

    storage_key: str
    content_type: str
    file_size: int


class StorageBackend(Protocol):
    """Abstract interface for external object storage providers."""

    def upload_file(
        self,
        *,
        file_obj: BinaryIO,
        storage_key: str,
        content_type: str,
    ) -> StoredObjectInfo:
        """Upload a binary stream to object storage under storage_key."""

    def delete_file(self, storage_key: str) -> None:
        """Delete an object from storage."""

    def get_metadata(self, storage_key: str) -> StoredObjectInfo:
        """Retrieve object metadata from storage."""

    def generate_presigned_download_url(
        self,
        storage_key: str,
        *,
        download_filename: str,
        expires_in_seconds: int,
    ) -> str:
        """Generate a short-lived signed download URL."""
