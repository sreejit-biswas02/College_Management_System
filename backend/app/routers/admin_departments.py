"""Administrative endpoints for Department management."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.database.connection import get_db
from app.dependencies.permissions import require_roles
from app.models.user import UserRole
from app.schemas.academic import (
    DepartmentCreate,
    DepartmentResponse,
    DepartmentUpdate,
)
from app.schemas.common import PaginatedResponse
from app.services import academic_service

router = APIRouter(
    prefix="/admin/departments",
    tags=["Admin - Departments"],
    dependencies=[Depends(require_roles(UserRole.ADMIN))],
)


@router.post(
    "",
    response_model=DepartmentResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_department_endpoint(
    payload: DepartmentCreate,
    db: Annotated[Session, Depends(get_db)],
) -> DepartmentResponse:
    """Create a new academic department."""
    dept = academic_service.create_department(db, payload)
    return DepartmentResponse.model_validate(dept)


@router.get("", response_model=PaginatedResponse[DepartmentResponse])
def list_departments_endpoint(
    db: Annotated[Session, Depends(get_db)],
    search: str | None = Query(default=None, max_length=100),
    is_active: bool | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
) -> PaginatedResponse[DepartmentResponse]:
    """List departments with search, active filter, and pagination."""
    items, total = academic_service.list_departments(
        db,
        search=search,
        is_active=is_active,
        page=page,
        page_size=page_size,
    )
    return PaginatedResponse.create(
        items=[DepartmentResponse.model_validate(d) for d in items],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/{department_id}", response_model=DepartmentResponse)
def get_department_endpoint(
    department_id: int,
    db: Annotated[Session, Depends(get_db)],
) -> DepartmentResponse:
    """Retrieve a department by ID."""
    dept = academic_service.get_department_by_id(db, department_id)
    return DepartmentResponse.model_validate(dept)


@router.patch("/{department_id}", response_model=DepartmentResponse)
def update_department_endpoint(
    department_id: int,
    payload: DepartmentUpdate,
    db: Annotated[Session, Depends(get_db)],
) -> DepartmentResponse:
    """Update department details."""
    dept = academic_service.update_department(db, department_id, payload)
    return DepartmentResponse.model_validate(dept)


@router.patch("/{department_id}/activate", response_model=DepartmentResponse)
def activate_department_endpoint(
    department_id: int,
    db: Annotated[Session, Depends(get_db)],
) -> DepartmentResponse:
    """Activate a department."""
    dept = academic_service.set_department_active_status(db, department_id, True)
    return DepartmentResponse.model_validate(dept)


@router.patch("/{department_id}/deactivate", response_model=DepartmentResponse)
def deactivate_department_endpoint(
    department_id: int,
    db: Annotated[Session, Depends(get_db)],
) -> DepartmentResponse:
    """Deactivate a department."""
    dept = academic_service.set_department_active_status(db, department_id, False)
    return DepartmentResponse.model_validate(dept)
