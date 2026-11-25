"""Pydantic schemas for Course Offering management."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.academic import CourseSummary, SemesterSummary
from app.schemas.faculty import FacultySummary


class CourseOfferingCreate(BaseModel):
    """Payload to create a course offering."""

    course_id: int = Field(gt=0)
    semester_id: int = Field(gt=0)
    faculty_id: int = Field(gt=0)
    section: str = Field(default="A", min_length=1, max_length=20)
    max_capacity: int | None = Field(default=None, gt=0)
    is_active: bool = True


class CourseOfferingUpdate(BaseModel):
    """Payload to update a course offering."""

    course_id: int | None = Field(default=None, gt=0)
    semester_id: int | None = Field(default=None, gt=0)
    faculty_id: int | None = Field(default=None, gt=0)
    section: str | None = Field(default=None, min_length=1, max_length=20)
    max_capacity: int | None = Field(default=None, gt=0)
    is_active: bool | None = None


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
