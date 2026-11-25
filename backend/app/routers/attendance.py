"""Endpoints for Attendance sessions, marking, and student summaries."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.database.connection import get_db
from app.dependencies.permissions import require_roles
from app.models.user import User, UserRole
from app.schemas.attendance import (
    AttendanceBulkMarkRequest,
    AttendanceRecordResponse,
    AttendanceSessionCreate,
    AttendanceSessionResponse,
    StudentAttendanceSummary,
)
from app.schemas.common import PaginatedResponse
from app.services import attendance_service

router = APIRouter(prefix="/attendance", tags=["Attendance"])


@router.post(
    "/sessions",
    response_model=AttendanceSessionResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_attendance_session_endpoint(
    payload: AttendanceSessionCreate,
    current_user: Annotated[
        User,
        Depends(require_roles(UserRole.ADMIN, UserRole.FACULTY)),
    ],
    db: Annotated[Session, Depends(get_db)],
) -> AttendanceSessionResponse:
    """Create an attendance session (Admin or assigned Faculty)."""
    session = attendance_service.create_attendance_session(db, payload, current_user)
    return AttendanceSessionResponse.model_validate(session)


@router.get(
    "/offerings/{offering_id}/sessions",
    response_model=PaginatedResponse[AttendanceSessionResponse],
)
def list_offering_sessions_endpoint(
    offering_id: int,
    current_user: Annotated[
        User,
        Depends(require_roles(UserRole.ADMIN, UserRole.FACULTY)),
    ],
    db: Annotated[Session, Depends(get_db)],
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
) -> PaginatedResponse[AttendanceSessionResponse]:
    """List attendance sessions for a course offering."""
    items, total = attendance_service.list_offering_attendance_sessions(
        db,
        offering_id,
        current_user,
        page=page,
        page_size=page_size,
    )
    return PaginatedResponse.create(
        items=[AttendanceSessionResponse.model_validate(s) for s in items],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/sessions/{session_id}", response_model=AttendanceSessionResponse)
def get_attendance_session_endpoint(
    session_id: int,
    current_user: Annotated[
        User,
        Depends(require_roles(UserRole.ADMIN, UserRole.FACULTY)),
    ],
    db: Annotated[Session, Depends(get_db)],
) -> AttendanceSessionResponse:
    """Get an attendance session and its records (Admin or assigned Faculty)."""
    att_session = attendance_service.get_attendance_session_by_id(db, session_id)
    attendance_service._authorize_offering_actor(
        db,
        att_session.course_offering_id,
        current_user,
    )
    return AttendanceSessionResponse.model_validate(att_session)


@router.put(
    "/sessions/{session_id}/records",
    response_model=AttendanceSessionResponse,
)
def mark_attendance_records_endpoint(
    session_id: int,
    payload: AttendanceBulkMarkRequest,
    current_user: Annotated[
        User,
        Depends(require_roles(UserRole.ADMIN, UserRole.FACULTY)),
    ],
    db: Annotated[Session, Depends(get_db)],
) -> AttendanceSessionResponse:
    """Create or update attendance records for a session."""
    att_session = attendance_service.mark_attendance_records(
        db,
        session_id,
        payload.records,
        current_user,
    )
    return AttendanceSessionResponse.model_validate(att_session)


@router.get("/me", response_model=StudentAttendanceSummary)
def get_my_attendance_endpoint(
    current_user: Annotated[User, Depends(require_roles(UserRole.STUDENT))],
    db: Annotated[Session, Depends(get_db)],
    course_offering_id: int | None = Query(default=None, gt=0),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=100),
) -> StudentAttendanceSummary:
    """Get attendance records and percentage for the authenticated student."""
    summary = attendance_service.get_student_attendance(
        db,
        user_id=current_user.id,
        course_offering_id=course_offering_id,
        page=page,
        page_size=page_size,
    )
    return StudentAttendanceSummary(
        total_sessions=summary["total_sessions"],  # type: ignore[arg-type]
        present=summary["present"],  # type: ignore[arg-type]
        absent=summary["absent"],  # type: ignore[arg-type]
        late=summary["late"],  # type: ignore[arg-type]
        excused=summary["excused"],  # type: ignore[arg-type]
        attendance_percentage=summary["attendance_percentage"],  # type: ignore[arg-type]
        records=[
            AttendanceRecordResponse.model_validate(r)
            for r in summary["records"]  # type: ignore[attr-defined]
        ],
    )
