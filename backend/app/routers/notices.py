"""Endpoints for Notices and audience-targeted announcements."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.database.connection import get_db
from app.dependencies.authentication import require_active_user
from app.dependencies.permissions import require_roles
from app.models.user import User, UserRole
from app.schemas.common import PaginatedResponse
from app.schemas.notice import NoticeCreate, NoticeResponse, NoticeUpdate
from app.services import notice_service

router = APIRouter(prefix="/notices", tags=["Notices"])


@router.post("", response_model=NoticeResponse, status_code=status.HTTP_201_CREATED)
def create_notice_endpoint(
    payload: NoticeCreate,
    current_user: Annotated[
        User,
        Depends(require_roles(UserRole.ADMIN, UserRole.FACULTY)),
    ],
    db: Annotated[Session, Depends(get_db)],
) -> NoticeResponse:
    """Publish a notice (Admin: any target; Faculty: own course offerings)."""
    notice = notice_service.create_notice(db, payload, current_user)
    return NoticeResponse.model_validate(notice)


@router.get("", response_model=PaginatedResponse[NoticeResponse])
def list_notices_endpoint(
    current_user: Annotated[User, Depends(require_active_user)],
    db: Annotated[Session, Depends(get_db)],
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
) -> PaginatedResponse[NoticeResponse]:
    """List notices visible to the authenticated user."""
    items, total = notice_service.list_visible_notices(
        db,
        current_user,
        page=page,
        page_size=page_size,
    )
    return PaginatedResponse.create(
        items=[NoticeResponse.model_validate(n) for n in items],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/{notice_id}", response_model=NoticeResponse)
def get_notice_endpoint(
    notice_id: int,
    current_user: Annotated[User, Depends(require_active_user)],
    db: Annotated[Session, Depends(get_db)],
) -> NoticeResponse:
    """Get notice details if visible to the authenticated user."""
    notice = notice_service.get_notice_by_id(db, notice_id, current_user)
    return NoticeResponse.model_validate(notice)


@router.patch("/{notice_id}", response_model=NoticeResponse)
def update_notice_endpoint(
    notice_id: int,
    payload: NoticeUpdate,
    current_user: Annotated[
        User,
        Depends(require_roles(UserRole.ADMIN, UserRole.FACULTY)),
    ],
    db: Annotated[Session, Depends(get_db)],
) -> NoticeResponse:
    """Update a notice (Admin or authoring Faculty)."""
    notice = notice_service.update_notice(db, notice_id, payload, current_user)
    return NoticeResponse.model_validate(notice)


@router.patch("/{notice_id}/deactivate", response_model=NoticeResponse)
def deactivate_notice_endpoint(
    notice_id: int,
    current_user: Annotated[
        User,
        Depends(require_roles(UserRole.ADMIN, UserRole.FACULTY)),
    ],
    db: Annotated[Session, Depends(get_db)],
) -> NoticeResponse:
    """Deactivate/unpublish a notice (Admin or authoring Faculty)."""
    notice = notice_service.deactivate_notice(db, notice_id, current_user)
    return NoticeResponse.model_validate(notice)
