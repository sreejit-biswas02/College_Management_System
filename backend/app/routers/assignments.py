"""Endpoints for Assignments and Student Submissions."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.connection import get_db
from app.dependencies.authentication import require_active_user
from app.dependencies.permissions import require_roles
from app.models.assignment import Submission
from app.models.stored_file import StoredFile
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
from app.schemas.file import StoredFileResponse
from app.services import assignment_service
from app.services.file_service import ENTITY_SUBMISSION

router = APIRouter(tags=["Assignments & Submissions"])


def _serialize_submissions_with_attachments(
    db: Session,
    submissions: list[Submission],
) -> list[SubmissionResponse]:
    """Attach active StoredFile metadata to serialized submission responses."""
    if not submissions:
        return []
    sub_ids = [s.id for s in submissions]
    files = list(
        db.scalars(
            select(StoredFile)
            .where(
                StoredFile.entity_type == ENTITY_SUBMISSION,
                StoredFile.entity_id.in_(sub_ids),
                StoredFile.is_active.is_(True),
            )
            .order_by(StoredFile.created_at.desc())
        ).all()
    )
    grouped: dict[int, list[StoredFileResponse]] = {sid: [] for sid in sub_ids}
    for f in files:
        grouped.setdefault(f.entity_id, []).append(StoredFileResponse.model_validate(f))

    results: list[SubmissionResponse] = []
    for sub in submissions:
        resp = SubmissionResponse.model_validate(sub)
        resp.attachments = grouped.get(sub.id, [])
        results.append(resp)
    return results


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
        items=_serialize_submissions_with_attachments(db, items),
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
        items=_serialize_submissions_with_attachments(db, items),
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
    return _serialize_submissions_with_attachments(db, [submission])[0]


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
