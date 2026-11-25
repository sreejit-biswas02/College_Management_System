"""Business logic for authorized file uploads, downloads, and cleanup."""

import io
import logging

from fastapi import UploadFile
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.assignment import Assignment, Submission
from app.models.course_offering import CourseOffering, Enrollment, EnrollmentStatus
from app.models.stored_file import StoredFile
from app.models.user import Student, User, UserRole
from app.services.exceptions import BusinessRuleError, ForbiddenError, NotFoundError
from app.storage.base import StorageBackend, StorageError
from app.storage.validation import validate_upload

logger = logging.getLogger(__name__)

ENTITY_ASSIGNMENT = "assignment"
ENTITY_SUBMISSION = "submission"


def _authorize_assignment_instructor(
    db: Session,
    assignment_id: int,
    actor: User,
) -> Assignment:
    assignment = db.get(Assignment, assignment_id)
    if assignment is None:
        raise NotFoundError("Assignment not found.")
    if actor.role == UserRole.ADMIN:
        return assignment
    offering = db.get(CourseOffering, assignment.course_offering_id)
    if (
        actor.role == UserRole.FACULTY
        and offering is not None
        and offering.faculty.user_id == actor.id
    ):
        return assignment
    raise ForbiddenError("You are not authorized to manage files for this assignment.")


def _authorize_assignment_viewer(
    db: Session,
    assignment_id: int,
    actor: User,
) -> Assignment:
    assignment = db.get(Assignment, assignment_id)
    if assignment is None:
        raise NotFoundError("Assignment not found.")
    if actor.role == UserRole.ADMIN:
        return assignment
    if actor.role == UserRole.FACULTY:
        offering = db.get(CourseOffering, assignment.course_offering_id)
        if offering is not None and offering.faculty.user_id == actor.id:
            return assignment
        raise ForbiddenError("You are not assigned to this course offering.")

    student = db.scalar(select(Student).where(Student.user_id == actor.id))
    if student is None:
        raise ForbiddenError("Student profile not found.")
    enrolled = db.scalar(
        select(Enrollment).where(
            Enrollment.student_id == student.id,
            Enrollment.course_offering_id == assignment.course_offering_id,
            Enrollment.status == EnrollmentStatus.ENROLLED,
        )
    )
    if enrolled is None:
        raise ForbiddenError("You are not enrolled in this course offering.")
    return assignment


def _authorize_submission_access(
    db: Session,
    submission_id: int,
    actor: User,
    *,
    require_owner_for_upload: bool = False,
) -> Submission:
    submission = db.get(Submission, submission_id)
    if submission is None:
        raise NotFoundError("Submission not found.")

    if actor.role == UserRole.STUDENT:
        student = db.scalar(select(Student).where(Student.user_id == actor.id))
        if student is None or submission.student_id != student.id:
            raise ForbiddenError("You do not have access to this submission.")
        return submission

    if require_owner_for_upload and actor.role != UserRole.ADMIN:
        raise ForbiddenError("Only the owning student can upload submission files.")

    if actor.role == UserRole.ADMIN:
        return submission

    assignment = db.get(Assignment, submission.assignment_id)
    if assignment is None:
        raise NotFoundError("Assignment not found.")
    offering = db.get(CourseOffering, assignment.course_offering_id)
    if offering is not None and offering.faculty.user_id == actor.id:
        return submission
    raise ForbiddenError("You are not authorized for this submission.")


async def _upload_and_persist(
    db: Session,
    *,
    upload_file: UploadFile,
    actor: User,
    entity_type: str,
    entity_id: int,
    max_bytes: int,
    key_prefix: str,
    storage: StorageBackend,
) -> StoredFile:
    content = await upload_file.read(max_bytes + 1)
    if len(content) > max_bytes:
        max_mb = max_bytes // (1024 * 1024)
        raise BusinessRuleError(f"File exceeds maximum allowed size ({max_mb} MB).")

    validated = validate_upload(
        filename=upload_file.filename,
        declared_content_type=upload_file.content_type,
        content=content,
        max_bytes=max_bytes,
        key_prefix=key_prefix,
    )

    storage.upload_file(
        file_obj=io.BytesIO(content),
        storage_key=validated.storage_key,
        content_type=validated.content_type,
    )

    record = StoredFile(
        original_filename=validated.original_filename,
        storage_key=validated.storage_key,
        content_type=validated.content_type,
        file_size=validated.file_size,
        uploaded_by=actor.id,
        entity_type=entity_type,
        entity_id=entity_id,
        is_active=True,
    )
    db.add(record)
    try:
        db.commit()
    except SQLAlchemyError as exc:
        db.rollback()
        try:
            storage.delete_file(validated.storage_key)
        except StorageError:
            logger.warning(
                "Orphaned object cleanup failed for key=%s",
                validated.storage_key,
            )
        raise BusinessRuleError("Failed to save file metadata.") from exc

    db.refresh(record)
    return record


async def upload_assignment_attachment(
    db: Session,
    *,
    assignment_id: int,
    upload_file: UploadFile,
    actor: User,
    storage: StorageBackend,
) -> StoredFile:
    """Upload an attachment to an assignment (Admin or assigned Faculty)."""
    _authorize_assignment_instructor(db, assignment_id, actor)
    settings = get_settings()
    return await _upload_and_persist(
        db,
        upload_file=upload_file,
        actor=actor,
        entity_type=ENTITY_ASSIGNMENT,
        entity_id=assignment_id,
        max_bytes=settings.MAX_ASSIGNMENT_UPLOAD_BYTES,
        key_prefix=f"assignments/{assignment_id}",
        storage=storage,
    )


def list_assignment_attachments(
    db: Session,
    *,
    assignment_id: int,
    actor: User,
) -> list[StoredFile]:
    """List active attachments for an assignment."""
    _authorize_assignment_viewer(db, assignment_id, actor)
    return list(
        db.scalars(
            select(StoredFile)
            .where(
                StoredFile.entity_type == ENTITY_ASSIGNMENT,
                StoredFile.entity_id == assignment_id,
                StoredFile.is_active.is_(True),
            )
            .order_by(StoredFile.created_at.desc())
        ).all()
    )


async def upload_submission_file(
    db: Session,
    *,
    submission_id: int,
    upload_file: UploadFile,
    actor: User,
    storage: StorageBackend,
) -> StoredFile:
    """Upload a file for a student's own ungraded submission."""
    submission = _authorize_submission_access(
        db,
        submission_id,
        actor,
        require_owner_for_upload=True,
    )
    if submission.graded_at is not None and actor.role != UserRole.ADMIN:
        raise BusinessRuleError("Cannot upload files to an already graded submission.")

    settings = get_settings()
    return await _upload_and_persist(
        db,
        upload_file=upload_file,
        actor=actor,
        entity_type=ENTITY_SUBMISSION,
        entity_id=submission_id,
        max_bytes=settings.MAX_DOCUMENT_UPLOAD_BYTES,
        key_prefix=f"submissions/{submission_id}",
        storage=storage,
    )


def list_submission_files(
    db: Session,
    *,
    submission_id: int,
    actor: User,
) -> list[StoredFile]:
    """List active files attached to a submission."""
    _authorize_submission_access(db, submission_id, actor)
    return list(
        db.scalars(
            select(StoredFile)
            .where(
                StoredFile.entity_type == ENTITY_SUBMISSION,
                StoredFile.entity_id == submission_id,
                StoredFile.is_active.is_(True),
            )
            .order_by(StoredFile.created_at.desc())
        ).all()
    )


def _get_active_file(db: Session, file_id: int) -> StoredFile:
    record = db.get(StoredFile, file_id)
    if record is None or not record.is_active:
        raise NotFoundError("File not found.")
    return record


def get_authorized_file_download(
    db: Session,
    *,
    file_id: int,
    actor: User,
    storage: StorageBackend,
) -> tuple[StoredFile, str, int]:
    """Authorize file access and generate a short-lived signed URL."""
    record = _get_active_file(db, file_id)
    if record.entity_type == ENTITY_ASSIGNMENT:
        _authorize_assignment_viewer(db, record.entity_id, actor)
    elif record.entity_type == ENTITY_SUBMISSION:
        _authorize_submission_access(db, record.entity_id, actor)
    else:
        if actor.role != UserRole.ADMIN and record.uploaded_by != actor.id:
            raise ForbiddenError("You do not have permission to access this file.")

    expires = get_settings().SIGNED_URL_EXPIRE_SECONDS
    url = storage.generate_presigned_download_url(
        record.storage_key,
        download_filename=record.original_filename,
        expires_in_seconds=expires,
    )
    return record, url, expires


def delete_stored_file(
    db: Session,
    *,
    file_id: int,
    actor: User,
    storage: StorageBackend,
) -> None:
    """Delete a file from object storage first, then soft-delete DB metadata."""
    record = _get_active_file(db, file_id)

    if actor.role != UserRole.ADMIN:
        if record.uploaded_by != actor.id:
            raise ForbiddenError("You do not have permission to delete this file.")
        if record.entity_type == ENTITY_SUBMISSION:
            submission = db.get(Submission, record.entity_id)
            if submission is not None and submission.graded_at is not None:
                raise BusinessRuleError(
                    "Graded submission files cannot be deleted by students."
                )

    # Confirm external storage deletion before updating database metadata.
    storage.delete_file(record.storage_key)
    record.is_active = False
    db.commit()
