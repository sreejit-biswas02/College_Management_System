"""Endpoints for secure file uploads, metadata listing, and signed downloads."""

from typing import Annotated

from fastapi import APIRouter, Depends, File, Response, UploadFile, status
from sqlalchemy.orm import Session

from app.database.connection import get_db
from app.dependencies.authentication import require_active_user
from app.dependencies.permissions import require_roles
from app.models.user import User, UserRole
from app.schemas.file import FileDownloadResponse, StoredFileResponse
from app.services import file_service
from app.storage.base import StorageBackend
from app.storage.storage_service import get_storage_backend

router = APIRouter(tags=["Files & Attachments"])


@router.post(
    "/assignments/{assignment_id}/attachments",
    response_model=StoredFileResponse,
    status_code=status.HTTP_201_CREATED,
)
async def upload_assignment_attachment_endpoint(
    assignment_id: int,
    file: Annotated[UploadFile, File(...)],
    current_user: Annotated[
        User,
        Depends(require_roles(UserRole.ADMIN, UserRole.FACULTY)),
    ],
    db: Annotated[Session, Depends(get_db)],
    storage: Annotated[StorageBackend, Depends(get_storage_backend)],
) -> StoredFileResponse:
    """Upload an attachment for an assignment (Admin or assigned Faculty)."""
    record = await file_service.upload_assignment_attachment(
        db,
        assignment_id=assignment_id,
        upload_file=file,
        actor=current_user,
        storage=storage,
    )
    return StoredFileResponse.model_validate(record)


@router.get(
    "/assignments/{assignment_id}/attachments",
    response_model=list[StoredFileResponse],
)
def list_assignment_attachments_endpoint(
    assignment_id: int,
    current_user: Annotated[User, Depends(require_active_user)],
    db: Annotated[Session, Depends(get_db)],
) -> list[StoredFileResponse]:
    """List active attachments for an assignment."""
    items = file_service.list_assignment_attachments(
        db,
        assignment_id=assignment_id,
        actor=current_user,
    )
    return [StoredFileResponse.model_validate(item) for item in items]


@router.post(
    "/submissions/{submission_id}/files",
    response_model=StoredFileResponse,
    status_code=status.HTTP_201_CREATED,
)
async def upload_submission_file_endpoint(
    submission_id: int,
    file: Annotated[UploadFile, File(...)],
    current_user: Annotated[
        User,
        Depends(require_roles(UserRole.ADMIN, UserRole.STUDENT)),
    ],
    db: Annotated[Session, Depends(get_db)],
    storage: Annotated[StorageBackend, Depends(get_storage_backend)],
) -> StoredFileResponse:
    """Upload a file for a student's submission."""
    record = await file_service.upload_submission_file(
        db,
        submission_id=submission_id,
        upload_file=file,
        actor=current_user,
        storage=storage,
    )
    return StoredFileResponse.model_validate(record)


@router.get(
    "/submissions/{submission_id}/files",
    response_model=list[StoredFileResponse],
)
def list_submission_files_endpoint(
    submission_id: int,
    current_user: Annotated[User, Depends(require_active_user)],
    db: Annotated[Session, Depends(get_db)],
) -> list[StoredFileResponse]:
    """List active files attached to a submission."""
    items = file_service.list_submission_files(
        db,
        submission_id=submission_id,
        actor=current_user,
    )
    return [StoredFileResponse.model_validate(item) for item in items]


@router.get("/files/{file_id}", response_model=FileDownloadResponse)
def get_file_download_endpoint(
    file_id: int,
    current_user: Annotated[User, Depends(require_active_user)],
    db: Annotated[Session, Depends(get_db)],
    storage: Annotated[StorageBackend, Depends(get_storage_backend)],
) -> FileDownloadResponse:
    """Return file metadata and a short-lived signed download URL."""
    record, url, expires = file_service.get_authorized_file_download(
        db,
        file_id=file_id,
        actor=current_user,
        storage=storage,
    )
    return FileDownloadResponse(
        file=StoredFileResponse.model_validate(record),
        download_url=url,
        expires_in_seconds=expires,
    )


@router.delete("/files/{file_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_file_endpoint(
    file_id: int,
    current_user: Annotated[User, Depends(require_active_user)],
    db: Annotated[Session, Depends(get_db)],
    storage: Annotated[StorageBackend, Depends(get_storage_backend)],
) -> Response:
    """Delete an authorized file from storage and deactivate metadata."""
    file_service.delete_stored_file(
        db,
        file_id=file_id,
        actor=current_user,
        storage=storage,
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)
