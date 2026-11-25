"""Administrative endpoints for Student management."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.database.connection import get_db
from app.dependencies.permissions import require_roles
from app.models.user import User, UserRole
from app.schemas.common import PaginatedResponse
from app.schemas.student import (
    AdminStudentCreate,
    AdminStudentUpdate,
    StudentArchiveResponse,
    StudentDetailResponse,
)
from app.services import student_service

router = APIRouter(
    prefix="/admin/students",
    tags=["Admin - Students"],
    dependencies=[Depends(require_roles(UserRole.ADMIN))],
)


@router.post(
    "",
    response_model=StudentDetailResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_student_endpoint(
    payload: AdminStudentCreate,
    db: Annotated[Session, Depends(get_db)],
) -> StudentDetailResponse:
    """Create a new student account and profile."""
    student = student_service.create_student(db, payload)
    return StudentDetailResponse.model_validate(student)


@router.get("", response_model=PaginatedResponse[StudentDetailResponse])
def list_students_endpoint(
    db: Annotated[Session, Depends(get_db)],
    search: str | None = Query(default=None, max_length=100),
    department_id: int | None = Query(default=None, gt=0),
    semester_number: int | None = Query(default=None, ge=1, le=16),
    is_active: bool | None = None,
    is_archived: bool = False,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
) -> PaginatedResponse[StudentDetailResponse]:
    """List students with search, filtering, and pagination."""
    items, total = student_service.list_students(
        db,
        search=search,
        department_id=department_id,
        semester_number=semester_number,
        is_active=is_active,
        is_archived=is_archived,
        page=page,
        page_size=page_size,
    )
    return PaginatedResponse.create(
        items=[StudentDetailResponse.model_validate(s) for s in items],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/{student_id}", response_model=StudentDetailResponse)
def get_student_endpoint(
    student_id: int,
    db: Annotated[Session, Depends(get_db)],
) -> StudentDetailResponse:
    """Retrieve a student by ID."""
    student = student_service.get_student_by_id(db, student_id)
    return StudentDetailResponse.model_validate(student)


@router.patch("/{student_id}", response_model=StudentDetailResponse)
def update_student_endpoint(
    student_id: int,
    payload: AdminStudentUpdate,
    db: Annotated[Session, Depends(get_db)],
) -> StudentDetailResponse:
    """Update a student's account or profile details."""
    student = student_service.update_student(db, student_id, payload)
    return StudentDetailResponse.model_validate(student)


@router.patch("/{student_id}/activate", response_model=StudentDetailResponse)
def activate_student_endpoint(
    student_id: int,
    db: Annotated[Session, Depends(get_db)],
) -> StudentDetailResponse:
    """Reactivate a student account."""
    student = student_service.set_student_active_status(db, student_id, True)
    return StudentDetailResponse.model_validate(student)


@router.patch("/{student_id}/deactivate", response_model=StudentDetailResponse)
def deactivate_student_endpoint(
    student_id: int,
    db: Annotated[Session, Depends(get_db)],
) -> StudentDetailResponse:
    """Deactivate a student account."""
    student = student_service.set_student_active_status(db, student_id, False)
    return StudentDetailResponse.model_validate(student)


@router.delete("/{student_id}", response_model=StudentArchiveResponse)
def archive_student_endpoint(
    student_id: int,
    current_admin: Annotated[User, Depends(require_roles(UserRole.ADMIN))],
    db: Annotated[Session, Depends(get_db)],
) -> StudentArchiveResponse:
    """Archive (soft-delete) a student account while retaining academic records."""
    student = student_service.archive_student(db, student_id, current_admin.id)
    return StudentArchiveResponse(
        message="Student archived successfully. Academic records have been retained.",
        student=StudentDetailResponse.model_validate(student),
    )


@router.post("/{student_id}/restore", response_model=StudentDetailResponse)
def restore_student_endpoint(
    student_id: int,
    db: Annotated[Session, Depends(get_db)],
) -> StudentDetailResponse:
    """Restore an archived student profile (account remains inactive)."""
    student = student_service.restore_student(db, student_id)
    return StudentDetailResponse.model_validate(student)
