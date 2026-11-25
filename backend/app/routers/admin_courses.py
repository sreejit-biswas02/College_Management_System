"""Administrative endpoints for Course management."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.database.connection import get_db
from app.dependencies.permissions import require_roles
from app.models.user import UserRole
from app.schemas.academic import CourseCreate, CourseResponse, CourseUpdate
from app.schemas.common import PaginatedResponse
from app.services import academic_service

router = APIRouter(
    prefix="/admin/courses",
    tags=["Admin - Courses"],
    dependencies=[Depends(require_roles(UserRole.ADMIN))],
)


@router.post(
    "",
    response_model=CourseResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_course_endpoint(
    payload: CourseCreate,
    db: Annotated[Session, Depends(get_db)],
) -> CourseResponse:
    """Create a new catalog course."""
    course = academic_service.create_course(db, payload)
    return CourseResponse.model_validate(course)


@router.get("", response_model=PaginatedResponse[CourseResponse])
def list_courses_endpoint(
    db: Annotated[Session, Depends(get_db)],
    search: str | None = Query(default=None, max_length=100),
    department_id: int | None = Query(default=None, gt=0),
    credits: int | None = Query(default=None, gt=0),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
) -> PaginatedResponse[CourseResponse]:
    """List courses with search, filtering, and pagination."""
    items, total = academic_service.list_courses(
        db,
        search=search,
        department_id=department_id,
        credits=credits,
        page=page,
        page_size=page_size,
    )
    return PaginatedResponse.create(
        items=[CourseResponse.model_validate(c) for c in items],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/{course_id}", response_model=CourseResponse)
def get_course_endpoint(
    course_id: int,
    db: Annotated[Session, Depends(get_db)],
) -> CourseResponse:
    """Retrieve a course by ID."""
    course = academic_service.get_course_by_id(db, course_id)
    return CourseResponse.model_validate(course)


@router.patch("/{course_id}", response_model=CourseResponse)
def update_course_endpoint(
    course_id: int,
    payload: CourseUpdate,
    db: Annotated[Session, Depends(get_db)],
) -> CourseResponse:
    """Update course details."""
    course = academic_service.update_course(db, course_id, payload)
    return CourseResponse.model_validate(course)
