"""Pydantic schemas for Course Offering management."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.schemas.academic import CourseSummary, SemesterSummary
from app.schemas.faculty import FacultySummary


class CourseOfferingCreate(BaseModel):
    """Payload to create a course offering."""

    course_id: int = Field(gt=0)
    semester_id: int = Field(gt=0)
    faculty_id: int | None = Field(default=None, gt=0)
    faculty_employee_id: str | None = Field(default=None, min_length=1, max_length=50)
    section: str = Field(default="A", min_length=1, max_length=20)
    max_capacity: int | None = Field(default=None, gt=0)
    is_active: bool = True

    @model_validator(mode="after")
    def validate_faculty_identifier(self) -> "CourseOfferingCreate":
        """Ensure exactly one faculty identifier is provided."""
        if self.faculty_employee_id is not None:
            stripped = self.faculty_employee_id.strip()
            if not stripped:
                raise ValueError("faculty_employee_id must not be blank.")
            self.faculty_employee_id = stripped

        if self.faculty_id is None and self.faculty_employee_id is None:
            raise ValueError(
                "Either faculty_id or faculty_employee_id must be provided."
            )
        if self.faculty_id is not None and self.faculty_employee_id is not None:
            raise ValueError(
                "Provide either faculty_id or faculty_employee_id, not both."
            )
        return self


class CourseOfferingUpdate(BaseModel):
    """Payload to update a course offering."""

    course_id: int | None = Field(default=None, gt=0)
    semester_id: int | None = Field(default=None, gt=0)
    faculty_id: int | None = Field(default=None, gt=0)
    faculty_employee_id: str | None = Field(default=None, min_length=1, max_length=50)
    section: str | None = Field(default=None, min_length=1, max_length=20)
    max_capacity: int | None = Field(default=None, gt=0)
    is_active: bool | None = None

    @model_validator(mode="after")
    def validate_faculty_identifier(self) -> "CourseOfferingUpdate":
        """Reject conflicting or blank faculty identifiers on update."""
        if self.faculty_employee_id is not None:
            stripped = self.faculty_employee_id.strip()
            if not stripped:
                raise ValueError("faculty_employee_id must not be blank.")
            self.faculty_employee_id = stripped

        if self.faculty_id is not None and self.faculty_employee_id is not None:
            raise ValueError(
                "Provide either faculty_id or faculty_employee_id, not both."
            )
        return self


class CourseOfferingResponse(BaseModel):
    """Full course offering response with nested course, semester, faculty."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    course_id: int
    semester_id: int
    faculty_id: int
    section: str
    max_capacity: int | None
    is_active: bool
    created_at: datetime
    updated_at: datetime
    course: CourseSummary
    semester: SemesterSummary
    faculty: FacultySummary
