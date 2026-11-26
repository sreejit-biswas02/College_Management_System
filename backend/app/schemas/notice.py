"""Pydantic schemas for Notices and Notice Targets."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.user import UserRole
from app.schemas.academic import DepartmentSummary
from app.schemas.course_offering import CourseOfferingResponse


class NoticeTargetInput(BaseModel):
    """Target audience scope for a notice."""

    target_role: UserRole | None = None
    department_id: int | None = Field(default=None, gt=0)
    course_offering_id: int | None = Field(default=None, gt=0)


class NoticeAuthorSummary(BaseModel):
    """Compact notice author representation without sensitive fields."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    full_name: str
    role: UserRole


class NoticeTargetResponse(BaseModel):
    """Notice target scope response."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    notice_id: int
    target_role: UserRole | None
    department_id: int | None
    course_offering_id: int | None
    department: DepartmentSummary | None = None
    course_offering: CourseOfferingResponse | None = None


class NoticeCreate(BaseModel):
    """Payload to create a notice with optional audience targets."""

    title: str = Field(min_length=2, max_length=200)
    body: str = Field(min_length=1)
    is_published: bool = True
    expires_at: datetime | None = None
    targets: list[NoticeTargetInput] = Field(default_factory=list)


class NoticeUpdate(BaseModel):
    """Payload to update an existing notice."""

    title: str | None = Field(default=None, min_length=2, max_length=200)
    body: str | None = Field(default=None, min_length=1)
    is_published: bool | None = None
    expires_at: datetime | None = None
    targets: list[NoticeTargetInput] | None = None


class NoticeResponse(BaseModel):
    """Notice response with targets."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    body: str
    posted_by_user_id: int
    is_published: bool
    published_at: datetime
    expires_at: datetime | None
    created_at: datetime
    updated_at: datetime
    posted_by_user: NoticeAuthorSummary | None = None
    targets: list[NoticeTargetResponse] = Field(default_factory=list)
