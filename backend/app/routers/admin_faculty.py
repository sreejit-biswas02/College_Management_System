"""Administrative endpoints for Faculty management."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.database.connection import get_db
from app.dependencies.permissions import require_roles
from app.models.user import UserRole
from app.schemas.common import PaginatedResponse
from app.schemas.faculty import (
    AdminFacultyCreate,
    AdminFacultyUpdate,
    FacultyDetailResponse,
)
from app.services import faculty_service

router = APIRouter(
    prefix="/admin/faculty",
    tags=["Admin - Faculty"],
    dependencies=[Depends(require_roles(UserRole.ADMIN))],
)


@router.post(
    "",
    response_model=FacultyDetailResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_faculty_endpoint(
    payload: AdminFacultyCreate,
    db: Annotated[Session, Depends(get_db)],
) -> FacultyDetailResponse:
    """Create a new faculty account and profile."""
    faculty = faculty_service.create_faculty(db, payload)
    return FacultyDetailResponse.model_validate(faculty)


@router.get("", response_model=PaginatedResponse[FacultyDetailResponse])
def list_faculty_endpoint(
    db: Annotated[Session, Depends(get_db)],
    search: str | None = Query(default=None, max_length=100),
    department_id: int | None = Query(default=None, gt=0),
    is_active: bool | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
) -> PaginatedResponse[FacultyDetailResponse]:
    """List faculty members with search, filtering, and pagination."""
    items, total = faculty_service.list_faculty(
        db,
        search=search,
        department_id=department_id,
        is_active=is_active,
        page=page,
        page_size=page_size,
    )
    return PaginatedResponse.create(
        items=[FacultyDetailResponse.model_validate(f) for f in items],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/{faculty_id}", response_model=FacultyDetailResponse)
def get_faculty_endpoint(
    faculty_id: int,
    db: Annotated[Session, Depends(get_db)],
) -> FacultyDetailResponse:
    """Retrieve a faculty member by ID."""
    faculty = faculty_service.get_faculty_by_id(db, faculty_id)
    return FacultyDetailResponse.model_validate(faculty)


@router.patch("/{faculty_id}", response_model=FacultyDetailResponse)
def update_faculty_endpoint(
    faculty_id: int,
    payload: AdminFacultyUpdate,
    db: Annotated[Session, Depends(get_db)],
) -> FacultyDetailResponse:
    """Update a faculty member's account or profile details."""
    faculty = faculty_service.update_faculty(db, faculty_id, payload)
    return FacultyDetailResponse.model_validate(faculty)


@router.patch("/{faculty_id}/activate", response_model=FacultyDetailResponse)
def activate_faculty_endpoint(
    faculty_id: int,
    db: Annotated[Session, Depends(get_db)],
) -> FacultyDetailResponse:
    """Reactivate a faculty account."""
    faculty = faculty_service.set_faculty_active_status(db, faculty_id, True)
    return FacultyDetailResponse.model_validate(faculty)


@router.patch("/{faculty_id}/deactivate", response_model=FacultyDetailResponse)
def deactivate_faculty_endpoint(
    faculty_id: int,
    db: Annotated[Session, Depends(get_db)],
) -> FacultyDetailResponse:
    """Deactivate a faculty account."""
    faculty = faculty_service.set_faculty_active_status(db, faculty_id, False)
    return FacultyDetailResponse.model_validate(faculty)
