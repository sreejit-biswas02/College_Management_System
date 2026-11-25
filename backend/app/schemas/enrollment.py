"""Pydantic schemas for Course Enrollments."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.course_offering import EnrollmentStatus
from app.schemas.course_offering import CourseOfferingResponse
from app.schemas.student import StudentDetailResponse


class EnrollmentCreate(BaseModel):
    """Payload for enrolling a student into a course offering."""

    student_id: int = Field(gt=0)
    course_offering_id: int = Field(gt=0)
    status: EnrollmentStatus = EnrollmentStatus.ENROLLED


class EnrollmentStatusUpdate(BaseModel):
    """Payload to update an enrollment status."""

    status: EnrollmentStatus


class EnrollmentResponse(BaseModel):
    """Enrollment response with student and course offering details."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    student_id: int
    course_offering_id: int
    status: EnrollmentStatus
    enrolled_at: datetime
    student: StudentDetailResponse
    course_offering: CourseOfferingResponse
