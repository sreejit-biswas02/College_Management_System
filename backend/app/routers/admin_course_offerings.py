"""Administrative endpoints for Course Offering management."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.database.connection import get_db
from app.dependencies.permissions import require_roles
from app.models.user import UserRole
from app.schemas.common import PaginatedResponse
from app.schemas.course_offering import (
    CourseOfferingCreate,
    CourseOfferingResponse,
    CourseOfferingUpdate,
)
from app.services import course_offering_service

router = APIRouter(
    prefix="/admin/course-offerings",
    tags=["Admin - Course Offerings"],
    dependencies=[Depends(require_roles(UserRole.ADMIN))],
)


@router.post(
    "",
    response_model=CourseOfferingResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_course_offering_endpoint(
    payload: CourseOfferingCreate,
    db: Annotated[Session, Depends(get_db)],
) -> CourseOfferingResponse:
    """Create a new course offering and assign faculty."""
    offering = course_offering_service.create_course_offering(db, payload)
    return CourseOfferingResponse.model_validate(offering)


@router.get("", response_model=PaginatedResponse[CourseOfferingResponse])
def list_course_offerings_endpoint(
    db: Annotated[Session, Depends(get_db)],
    semester_id: int | None = Query(default=None, gt=0),
    faculty_id: int | None = Query(default=None, gt=0),
    course_id: int | None = Query(default=None, gt=0),
    section: str | None = Query(default=None, max_length=20),
    is_active: bool | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
) -> PaginatedResponse[CourseOfferingResponse]:
    """List course offerings with filtering and pagination."""
    items, total = course_offering_service.list_course_offerings(
        db,
        semester_id=semester_id,
        faculty_id=faculty_id,
        course_id=course_id,
        section=section,
        is_active=is_active,
        page=page,
        page_size=page_size,
    )
    return PaginatedResponse.create(
        items=[CourseOfferingResponse.model_validate(o) for o in items],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/{offering_id}", response_model=CourseOfferingResponse)
def get_course_offering_endpoint(
    offering_id: int,
    db: Annotated[Session, Depends(get_db)],
) -> CourseOfferingResponse:
    """Retrieve a course offering by ID."""
    offering = course_offering_service.get_course_offering_by_id(db, offering_id)
    return CourseOfferingResponse.model_validate(offering)


@router.patch("/{offering_id}", response_model=CourseOfferingResponse)
def update_course_offering_endpoint(
    offering_id: int,
    payload: CourseOfferingUpdate,
    db: Annotated[Session, Depends(get_db)],
) -> CourseOfferingResponse:
    """Update course offering details or faculty assignment."""
    offering = course_offering_service.update_course_offering(
        db,
        offering_id,
        payload,
    )
    return CourseOfferingResponse.model_validate(offering)


@router.patch("/{offering_id}/activate", response_model=CourseOfferingResponse)
def activate_course_offering_endpoint(
    offering_id: int,
    db: Annotated[Session, Depends(get_db)],
) -> CourseOfferingResponse:
    """Activate a course offering."""
    offering = course_offering_service.set_course_offering_active_status(
        db,
        offering_id,
        True,
    )
    return CourseOfferingResponse.model_validate(offering)


@router.patch("/{offering_id}/deactivate", response_model=CourseOfferingResponse)
def deactivate_course_offering_endpoint(
    offering_id: int,
    db: Annotated[Session, Depends(get_db)],
) -> CourseOfferingResponse:
    """Deactivate a course offering."""
    offering = course_offering_service.set_course_offering_active_status(
        db,
        offering_id,
        False,
    )
    return CourseOfferingResponse.model_validate(offering)
