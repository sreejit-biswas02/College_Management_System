"""Administrative endpoints for Semester management."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.database.connection import get_db
from app.dependencies.permissions import require_roles
from app.models.user import UserRole
from app.schemas.academic import (
    SemesterCreate,
    SemesterResponse,
    SemesterUpdate,
)
from app.schemas.common import PaginatedResponse
from app.services import academic_service

router = APIRouter(
    prefix="/admin/semesters",
    tags=["Admin - Semesters"],
    dependencies=[Depends(require_roles(UserRole.ADMIN))],
)


@router.post(
    "",
    response_model=SemesterResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_semester_endpoint(
    payload: SemesterCreate,
    db: Annotated[Session, Depends(get_db)],
) -> SemesterResponse:
    """Create a new academic semester."""
    semester = academic_service.create_semester(db, payload)
    return SemesterResponse.model_validate(semester)


@router.get("", response_model=PaginatedResponse[SemesterResponse])
def list_semesters_endpoint(
    db: Annotated[Session, Depends(get_db)],
    academic_year: str | None = Query(default=None, max_length=20),
    is_active: bool | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
) -> PaginatedResponse[SemesterResponse]:
    """List semesters with optional academic year/active filter and pagination."""
    items, total = academic_service.list_semesters(
        db,
        academic_year=academic_year,
        is_active=is_active,
        page=page,
        page_size=page_size,
    )
    return PaginatedResponse.create(
        items=[SemesterResponse.model_validate(s) for s in items],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/{semester_id}", response_model=SemesterResponse)
def get_semester_endpoint(
    semester_id: int,
    db: Annotated[Session, Depends(get_db)],
) -> SemesterResponse:
    """Retrieve a semester by ID."""
    semester = academic_service.get_semester_by_id(db, semester_id)
    return SemesterResponse.model_validate(semester)


@router.patch("/{semester_id}", response_model=SemesterResponse)
def update_semester_endpoint(
    semester_id: int,
    payload: SemesterUpdate,
    db: Annotated[Session, Depends(get_db)],
) -> SemesterResponse:
    """Update semester details."""
    semester = academic_service.update_semester(db, semester_id, payload)
    return SemesterResponse.model_validate(semester)


@router.patch("/{semester_id}/activate", response_model=SemesterResponse)
def activate_semester_endpoint(
    semester_id: int,
    db: Annotated[Session, Depends(get_db)],
) -> SemesterResponse:
    """Activate a semester."""
    semester = academic_service.set_semester_active_status(db, semester_id, True)
    return SemesterResponse.model_validate(semester)


@router.patch("/{semester_id}/deactivate", response_model=SemesterResponse)
def deactivate_semester_endpoint(
    semester_id: int,
    db: Annotated[Session, Depends(get_db)],
) -> SemesterResponse:
    """Deactivate a semester."""
    semester = academic_service.set_semester_active_status(db, semester_id, False)
    return SemesterResponse.model_validate(semester)
