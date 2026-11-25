"""Endpoints for Assignments and Student Submissions."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.database.connection import get_db
from app.dependencies.authentication import require_active_user
from app.dependencies.permissions import require_roles
from app.models.user import User, UserRole
from app.schemas.assignment import (
    AssignmentCreate,
    AssignmentResponse,
    AssignmentUpdate,
    SubmissionCreate,
    SubmissionGradeRequest,
    SubmissionResponse,
)
from app.schemas.common import PaginatedResponse
from app.services import assignment_service

router = APIRouter(tags=["Assignments & Submissions"])


@router.post(
    "/assignments",
    response_model=AssignmentResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_assignment_endpoint(
    payload: AssignmentCreate,
    current_user: Annotated[
        User,
        Depends(require_roles(UserRole.ADMIN, UserRole.FACULTY)),
    ],
    db: Annotated[Session, Depends(get_db)],
) -> AssignmentResponse:
    """Create an assignment for a course offering (Admin or assigned Faculty)."""
    assignment = assignment_service.create_assignment(db, payload, current_user)
    return AssignmentResponse.model_validate(assignment)


@router.get(
    "/assignments/offerings/{offering_id}",
    response_model=PaginatedResponse[AssignmentResponse],
)
def list_offering_assignments_endpoint(
    offering_id: int,
    current_user: Annotated[User, Depends(require_active_user)],
    db: Annotated[Session, Depends(get_db)],
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
) -> PaginatedResponse[AssignmentResponse]:
    """List assignments for an offering (Admin, assigned Faculty, enrolled Student)."""
    items, total = assignment_service.list_assignments_for_offering(
        db,
        offering_id,
        current_user,
        page=page,
        page_size=page_size,
    )
    return PaginatedResponse.create(
        items=[AssignmentResponse.model_validate(a) for a in items],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/assignments/{assignment_id}", response_model=AssignmentResponse)
def get_assignment_endpoint(
    assignment_id: int,
    current_user: Annotated[User, Depends(require_active_user)],
    db: Annotated[Session, Depends(get_db)],
) -> AssignmentResponse:
    """Get assignment details."""
    assignment = assignment_service.get_assignment_by_id(
        db,
        assignment_id,
        current_user,
    )
    return AssignmentResponse.model_validate(assignment)


@router.patch("/assignments/{assignment_id}", response_model=AssignmentResponse)
def update_assignment_endpoint(
    assignment_id: int,
    payload: AssignmentUpdate,
    current_user: Annotated[
        User,
        Depends(require_roles(UserRole.ADMIN, UserRole.FACULTY)),
    ],
    db: Annotated[Session, Depends(get_db)],
) -> AssignmentResponse:
    """Update assignment details (Admin or assigned Faculty)."""
    assignment = assignment_service.update_assignment(
        db,
        assignment_id,
        payload,
        current_user,
    )
    return AssignmentResponse.model_validate(assignment)


@router.post(
    "/assignments/{assignment_id}/submissions",
    response_model=SubmissionResponse,
    status_code=status.HTTP_201_CREATED,
)
def submit_assignment_endpoint(
    assignment_id: int,
    payload: SubmissionCreate,
    current_user: Annotated[User, Depends(require_roles(UserRole.STUDENT))],
    db: Annotated[Session, Depends(get_db)],
) -> SubmissionResponse:
    """Submit an assignment as an enrolled student before the deadline."""
    submission = assignment_service.submit_assignment(
        db,
        assignment_id,
        payload,
        current_user,
    )
    return SubmissionResponse.model_validate(submission)


@router.get(
    "/assignments/{assignment_id}/submissions",
    response_model=PaginatedResponse[SubmissionResponse],
)
def list_assignment_submissions_endpoint(
    assignment_id: int,
    current_user: Annotated[
        User,
        Depends(require_roles(UserRole.ADMIN, UserRole.FACULTY)),
    ],
    db: Annotated[Session, Depends(get_db)],
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
) -> PaginatedResponse[SubmissionResponse]:
    """List submissions for an assignment (Admin or assigned Faculty)."""
    items, total = assignment_service.list_submissions(
        db,
        assignment_id,
        current_user,
        page=page,
        page_size=page_size,
    )
    return PaginatedResponse.create(
        items=[SubmissionResponse.model_validate(s) for s in items],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/submissions/me", response_model=PaginatedResponse[SubmissionResponse])
def list_my_submissions_endpoint(
    current_user: Annotated[User, Depends(require_roles(UserRole.STUDENT))],
    db: Annotated[Session, Depends(get_db)],
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
) -> PaginatedResponse[SubmissionResponse]:
    """List submissions belonging to the authenticated student."""
    items, total = assignment_service.list_my_submissions(
        db,
        current_user,
        page=page,
        page_size=page_size,
    )
    return PaginatedResponse.create(
        items=[SubmissionResponse.model_validate(s) for s in items],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/submissions/{submission_id}", response_model=SubmissionResponse)
def get_submission_endpoint(
    submission_id: int,
    current_user: Annotated[User, Depends(require_active_user)],
    db: Annotated[Session, Depends(get_db)],
) -> SubmissionResponse:
    """Get a submission (Admin, assigned Faculty, or owning Student)."""
    submission = assignment_service.get_submission_by_id(
        db,
        submission_id,
        current_user,
    )
    return SubmissionResponse.model_validate(submission)


@router.patch(
    "/submissions/{submission_id}/grade",
    response_model=SubmissionResponse,
)
def grade_submission_endpoint(
    submission_id: int,
    payload: SubmissionGradeRequest,
    current_user: Annotated[
        User,
        Depends(require_roles(UserRole.ADMIN, UserRole.FACULTY)),
    ],
    db: Annotated[Session, Depends(get_db)],
) -> SubmissionResponse:
    """Evaluate a submission and assign score and feedback."""
    submission = assignment_service.grade_submission(
        db,
        submission_id,
        payload,
        current_user,
    )
    return SubmissionResponse.model_validate(submission)
