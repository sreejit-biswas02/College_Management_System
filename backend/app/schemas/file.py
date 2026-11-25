"""Pydantic schemas for StoredFile metadata and authorized downloads."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class StoredFileResponse(BaseModel):
    """Safe file metadata returned by upload and list endpoints."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    original_filename: str
    content_type: str
    file_size: int
    uploaded_by: int
    entity_type: str
    entity_id: int
    is_active: bool
    created_at: datetime


class FileDownloadResponse(BaseModel):
    """Authorized file metadata with short-lived signed download URL."""

    file: StoredFileResponse
    download_url: str
    expires_in_seconds: int
