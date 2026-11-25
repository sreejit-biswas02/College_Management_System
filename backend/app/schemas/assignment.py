"""Pydantic schemas for Assignments and Submissions."""

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class AssignmentCreate(BaseModel):
    """Payload to publish an assignment for a course offering."""

    course_offering_id: int = Field(gt=0)
    title: str = Field(min_length=2, max_length=200)
    description: str | None = None
    due_at: datetime
    max_score: Decimal = Field(default=Decimal("100.00"), gt=0, max_digits=6)


class AssignmentUpdate(BaseModel):
    """Payload to update an existing assignment."""

    title: str | None = Field(default=None, min_length=2, max_length=200)
    description: str | None = None
    due_at: datetime | None = None
    max_score: Decimal | None = Field(default=None, gt=0, max_digits=6)


class AssignmentResponse(BaseModel):
    """Assignment response."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    course_offering_id: int
    created_by_faculty_id: int
    title: str
    description: str | None
    due_at: datetime
    max_score: Decimal
    created_at: datetime
    updated_at: datetime


class SubmissionCreate(BaseModel):
    """Payload for a student to submit an assignment."""

    content: str | None = None
    file_url: str | None = Field(default=None, max_length=500)

    @field_validator("file_url")
    @classmethod
    def validate_file_url_scheme(cls, value: str | None) -> str | None:
        """Allow only HTTP/HTTPS URLs to prevent unsafe URI schemes."""
        if value is None:
            return None
        cleaned = value.strip()
        if not cleaned:
            return None
        if not (cleaned.startswith("https://") or cleaned.startswith("http://")):
            raise ValueError("file_url must start with http:// or https://.")
        return cleaned

    @model_validator(mode="after")
    def validate_submission_not_empty(self) -> "SubmissionCreate":
        """Require at least text content or a file URL."""
        if not (self.content and self.content.strip()) and not (
            self.file_url and self.file_url.strip()
        ):
            raise ValueError("Either content or file_url must be provided.")
        return self


class SubmissionGradeRequest(BaseModel):
    """Payload to grade a student submission."""

    score: Decimal = Field(ge=0, max_digits=6)
    feedback: str | None = None


class SubmissionResponse(BaseModel):
    """Assignment submission and grading response."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    assignment_id: int
    student_id: int
    content: str | None
    file_url: str | None
    submitted_at: datetime
    score: Decimal | None
    feedback: str | None
    graded_at: datetime | None
    graded_by_faculty_id: int | None
