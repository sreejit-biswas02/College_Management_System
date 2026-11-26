"""Pydantic schemas for administrative and self-service Student management."""

import re
from datetime import date, datetime

from pydantic import (
    BaseModel,
    ConfigDict,
    EmailStr,
    Field,
    computed_field,
    field_validator,
)

from app.schemas.academic import DepartmentSummary
from app.schemas.user import UserCreateBase, UserResponse

STUDENT_ID_PATTERN = re.compile(r"^S-[A-Z0-9_-]+-\d{4}-\d{3,}$")


class AdminStudentCreate(UserCreateBase):
    """Payload for an admin to create a student account and profile."""

    department_id: int = Field(gt=0)
    admission_year: int = Field(ge=1950, le=2100)
    current_semester_number: int = Field(default=1, ge=1, le=16)
    phone: str | None = Field(default=None, max_length=20)
    date_of_birth: date | None = None
    is_active: bool = True


class AdminStudentUpdate(BaseModel):
    """Payload for an admin to update a student's user or profile fields."""

    email: EmailStr | None = None
    full_name: str | None = Field(default=None, min_length=2, max_length=120)
    department_id: int | None = Field(default=None, gt=0)
    roll_number: str | None = Field(default=None, min_length=5, max_length=50)
    admission_year: int | None = Field(default=None, ge=1950, le=2100)
    current_semester_number: int | None = Field(default=None, ge=1, le=16)
    phone: str | None = Field(default=None, max_length=20)
    date_of_birth: date | None = None
    is_active: bool | None = None
    recalculate_id: bool = False

    @field_validator("roll_number")
    @classmethod
    def validate_student_id_format(cls, value: str | None) -> str | None:
        """Ensure manually edited Student IDs follow S-DEPTCODE-YYYY-XXX."""
        if value is None:
            return None
        cleaned = value.strip().upper()
        if not STUDENT_ID_PATTERN.match(cleaned):
            raise ValueError(
                "Student ID must match format S-DEPTCODE-YYYY-XXX (e.g. S-CS-2026-001)."
            )
        return cleaned


class StudentDetailResponse(BaseModel):
    """Detailed student profile with linked User and Department."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    department_id: int
    roll_number: str
    admission_year: int
    current_semester_number: int
    calculated_semester: int | None = None
    semester_status: str = "In Progress"
    is_completed: bool = False
    active_academic_year: str | None = None
    phone: str | None
    date_of_birth: date | None
    is_archived: bool
    archived_at: datetime | None
    archived_by_user_id: int | None
    created_at: datetime
    updated_at: datetime
    user: UserResponse
    department: DepartmentSummary

    @computed_field
    @property
    def admission_academic_year(self) -> str:
        """Return YYYY-YYYY academic year corresponding to admission_year."""
        return f"{self.admission_year}-{self.admission_year + 1}"


class SemesterPreviewResponse(BaseModel):
    """Preview of calculated semester for a given admission year."""

    admission_year: int
    admission_academic_year: str
    calculated_semester: int | None
    semester_status: str
    is_completed: bool
    active_academic_year: str | None
    active_term_number: int | None


class PromotionBreakdownItem(BaseModel):
    """Count of students moving from an odd semester to the next even semester."""

    old_semester: int
    new_semester: int
    count: int


class SemesterPromotionPreviewResponse(BaseModel):
    """Preview summary before executing odd-to-even semester promotion."""

    academic_year: str
    eligible_count: int
    inactive_skipped_count: int
    already_promoted_count: int
    can_promote: bool
    breakdown: list[PromotionBreakdownItem]


class SemesterPromotionResultResponse(BaseModel):
    """Result returned after executing odd-to-even semester promotion."""

    academic_year: str
    promoted_count: int
    message: str


class StudentArchiveResponse(BaseModel):
    """Response returned after archiving a student."""

    message: str
    student: StudentDetailResponse


class AdminDashboardSummaryResponse(BaseModel):
    """Aggregated institutional metrics for the Admin dashboard."""

    total_students: int
    active_students: int
    total_faculty: int
    total_departments: int
    active_courses: int
    active_offerings: int
    total_enrollments: int
    total_attendance_sessions: int
    total_attendance_records: int
    attendance_rate_percentage: float
    pending_submissions: int
    total_assignments: int
