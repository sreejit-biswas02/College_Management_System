"""Self-service read-only endpoints for Students and Faculty."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database.connection import get_db
from app.dependencies.permissions import require_roles
from app.models.user import User, UserRole
from app.schemas.common import PaginatedResponse
from app.schemas.course_offering import CourseOfferingResponse
from app.schemas.faculty import FacultyDetailResponse
from app.schemas.student import StudentDetailResponse
from app.services import course_offering_service, faculty_service, student_service

router = APIRouter(tags=["Self-Service Profiles"])


@router.get("/students/me", response_model=StudentDetailResponse)
def get_my_student_profile(
    current_user: Annotated[User, Depends(require_roles(UserRole.STUDENT))],
    db: Annotated[Session, Depends(get_db)],
) -> StudentDetailResponse:
    """Return the authenticated student's own profile."""
    student = student_service.get_student_by_user_id(db, current_user.id)
    return StudentDetailResponse.model_validate(student)


@router.get("/faculty/me", response_model=FacultyDetailResponse)
def get_my_faculty_profile(
    current_user: Annotated[User, Depends(require_roles(UserRole.FACULTY))],
    db: Annotated[Session, Depends(get_db)],
) -> FacultyDetailResponse:
    """Return the authenticated faculty member's own profile."""
    faculty = faculty_service.get_faculty_by_user_id(db, current_user.id)
    return FacultyDetailResponse.model_validate(faculty)


@router.get(
    "/faculty/me/course-offerings",
    response_model=PaginatedResponse[CourseOfferingResponse],
)
def get_my_assigned_course_offerings(
    current_user: Annotated[User, Depends(require_roles(UserRole.FACULTY))],
    db: Annotated[Session, Depends(get_db)],
    semester_id: int | None = Query(default=None, gt=0),
    is_active: bool | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
) -> PaginatedResponse[CourseOfferingResponse]:
    """Return course offerings assigned to the authenticated faculty member."""
    faculty = faculty_service.get_faculty_by_user_id(db, current_user.id)
    items, total = course_offering_service.list_course_offerings(
        db,
        semester_id=semester_id,
        faculty_id=faculty.id,
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
