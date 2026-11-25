"""Endpoints for Timetable management and viewing."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.orm import Session

from app.database.connection import get_db
from app.dependencies.authentication import require_active_user
from app.dependencies.permissions import require_roles
from app.models.timetable import DayOfWeek
from app.models.user import User, UserRole
from app.schemas.common import PaginatedResponse
from app.schemas.timetable import (
    TimetableSlotCreate,
    TimetableSlotResponse,
    TimetableSlotUpdate,
)
from app.services import timetable_service

router = APIRouter(prefix="/timetable", tags=["Timetable"])


@router.post(
    "",
    response_model=TimetableSlotResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_timetable_slot_endpoint(
    payload: TimetableSlotCreate,
    _admin: Annotated[User, Depends(require_roles(UserRole.ADMIN))],
    db: Annotated[Session, Depends(get_db)],
) -> TimetableSlotResponse:
    """Create a timetable slot while preventing overlaps (Admin only)."""
    slot = timetable_service.create_timetable_slot(db, payload)
    return TimetableSlotResponse.model_validate(slot)


@router.get("", response_model=PaginatedResponse[TimetableSlotResponse])
def list_timetable_slots_endpoint(
    _user: Annotated[User, Depends(require_active_user)],
    db: Annotated[Session, Depends(get_db)],
    semester_id: int | None = Query(default=None, gt=0),
    section: str | None = Query(default=None, max_length=20),
    day_of_week: DayOfWeek | None = None,
    faculty_id: int | None = Query(default=None, gt=0),
    course_offering_id: int | None = Query(default=None, gt=0),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=100),
) -> PaginatedResponse[TimetableSlotResponse]:
    """List timetable slots with semester, section, day, faculty filters."""
    items, total = timetable_service.list_timetable_slots(
        db,
        semester_id=semester_id,
        section=section,
        day_of_week=day_of_week,
        faculty_id=faculty_id,
        course_offering_id=course_offering_id,
        page=page,
        page_size=page_size,
    )
    return PaginatedResponse.create(
        items=[TimetableSlotResponse.model_validate(s) for s in items],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/me", response_model=list[TimetableSlotResponse])
def get_my_timetable_endpoint(
    current_user: Annotated[
        User,
        Depends(require_roles(UserRole.STUDENT, UserRole.FACULTY)),
    ],
    db: Annotated[Session, Depends(get_db)],
    day_of_week: DayOfWeek | None = None,
) -> list[TimetableSlotResponse]:
    """Return personal timetable for the authenticated student or faculty."""
    slots = timetable_service.get_my_timetable(
        db,
        current_user,
        day_of_week=day_of_week,
    )
    return [TimetableSlotResponse.model_validate(s) for s in slots]


@router.patch("/{slot_id}", response_model=TimetableSlotResponse)
def update_timetable_slot_endpoint(
    slot_id: int,
    payload: TimetableSlotUpdate,
    _admin: Annotated[User, Depends(require_roles(UserRole.ADMIN))],
    db: Annotated[Session, Depends(get_db)],
) -> TimetableSlotResponse:
    """Update a timetable slot (Admin only)."""
    slot = timetable_service.update_timetable_slot(db, slot_id, payload)
    return TimetableSlotResponse.model_validate(slot)


@router.delete("/{slot_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_timetable_slot_endpoint(
    slot_id: int,
    _admin: Annotated[User, Depends(require_roles(UserRole.ADMIN))],
    db: Annotated[Session, Depends(get_db)],
) -> Response:
    """Delete a timetable slot (Admin only)."""
    timetable_service.delete_timetable_slot(db, slot_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
