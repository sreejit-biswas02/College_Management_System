"""Endpoints for Course Enrollment management and viewing."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.database.connection import get_db
from app.dependencies.permissions import require_roles
from app.models.course_offering import EnrollmentStatus
from app.models.user import User, UserRole
from app.schemas.common import PaginatedResponse
from app.schemas.enrollment import (
    EnrollmentCreate,
    EnrollmentResponse,
    EnrollmentStatusUpdate,
)
from app.services import enrollment_service

router = APIRouter(prefix="/enrollments", tags=["Enrollments"])


@router.post(
    "",
    response_model=EnrollmentResponse,
    status_code=status.HTTP_201_CREATED,
)
def enroll_student_endpoint(
    payload: EnrollmentCreate,
    _admin: Annotated[User, Depends(require_roles(UserRole.ADMIN))],
    db: Annotated[Session, Depends(get_db)],
) -> EnrollmentResponse:
    """Enroll a student into an active course offering (Admin only)."""
    enrollment = enrollment_service.enroll_student(db, payload)
    return EnrollmentResponse.model_validate(enrollment)


@router.get("", response_model=PaginatedResponse[EnrollmentResponse])
def list_enrollments_endpoint(
    _admin: Annotated[User, Depends(require_roles(UserRole.ADMIN))],
    db: Annotated[Session, Depends(get_db)],
    student_id: int | None = Query(default=None, gt=0),
    course_offering_id: int | None = Query(default=None, gt=0),
    enrollment_status: Annotated[EnrollmentStatus | None, Query(alias="status")] = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
) -> PaginatedResponse[EnrollmentResponse]:
    """List enrollments with filtering and pagination (Admin only)."""
    items, total = enrollment_service.list_enrollments(
        db,
        student_id=student_id,
        course_offering_id=course_offering_id,
        status=enrollment_status,
        page=page,
        page_size=page_size,
    )
    return PaginatedResponse.create(
        items=[EnrollmentResponse.model_validate(e) for e in items],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/me", response_model=PaginatedResponse[EnrollmentResponse])
def list_my_enrollments_endpoint(
    current_user: Annotated[User, Depends(require_roles(UserRole.STUDENT))],
    db: Annotated[Session, Depends(get_db)],
    enrollment_status: Annotated[EnrollmentStatus | None, Query(alias="status")] = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
) -> PaginatedResponse[EnrollmentResponse]:
    """List enrollments for the authenticated student."""
    items, total = enrollment_service.list_student_enrollments(
        db,
        user_id=current_user.id,
        status=enrollment_status,
        page=page,
        page_size=page_size,
    )
    return PaginatedResponse.create(
        items=[EnrollmentResponse.model_validate(e) for e in items],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get(
    "/offerings/{offering_id}",
    response_model=PaginatedResponse[EnrollmentResponse],
)
def list_offering_enrollments_endpoint(
    offering_id: int,
    current_user: Annotated[
        User,
        Depends(require_roles(UserRole.ADMIN, UserRole.FACULTY)),
    ],
    db: Annotated[Session, Depends(get_db)],
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
) -> PaginatedResponse[EnrollmentResponse]:
    """List enrollments for a course offering (Admin or assigned Faculty)."""
    if current_user.role == UserRole.ADMIN:
        items, total = enrollment_service.list_enrollments(
            db,
            course_offering_id=offering_id,
            page=page,
            page_size=page_size,
        )
    else:
        items, total = enrollment_service.list_offering_enrollments_for_faculty(
            db,
            offering_id=offering_id,
            actor=current_user,
            page=page,
            page_size=page_size,
        )
    return PaginatedResponse.create(
        items=[EnrollmentResponse.model_validate(e) for e in items],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.patch("/{enrollment_id}", response_model=EnrollmentResponse)
def update_enrollment_status_endpoint(
    enrollment_id: int,
    payload: EnrollmentStatusUpdate,
    _admin: Annotated[User, Depends(require_roles(UserRole.ADMIN))],
    db: Annotated[Session, Depends(get_db)],
) -> EnrollmentResponse:
    """Update enrollment status (Admin only)."""
    enrollment = enrollment_service.update_enrollment_status(
        db,
        enrollment_id,
        payload.status,
    )
    return EnrollmentResponse.model_validate(enrollment)
