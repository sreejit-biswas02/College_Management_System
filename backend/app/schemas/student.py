"""Pydantic schemas for administrative and self-service Student management."""

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.schemas.academic import DepartmentSummary
from app.schemas.user import UserCreateBase, UserResponse


class AdminStudentCreate(UserCreateBase):
    """Payload for an admin to create a student account and profile."""

    department_id: int = Field(gt=0)
    roll_number: str = Field(min_length=2, max_length=50)
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
    roll_number: str | None = Field(default=None, min_length=2, max_length=50)
    admission_year: int | None = Field(default=None, ge=1950, le=2100)
    current_semester_number: int | None = Field(default=None, ge=1, le=16)
    phone: str | None = Field(default=None, max_length=20)
    date_of_birth: date | None = None
    is_active: bool | None = None


class StudentDetailResponse(BaseModel):
    """Detailed student profile with linked User and Department."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    department_id: int
    roll_number: str
    admission_year: int
    current_semester_number: int
    phone: str | None
    date_of_birth: date | None
    is_archived: bool
    archived_at: datetime | None
    archived_by_user_id: int | None
    created_at: datetime
    updated_at: datetime
    user: UserResponse
    department: DepartmentSummary


class StudentArchiveResponse(BaseModel):
    """Response returned after archiving a student."""

    message: str
    student: StudentDetailResponse
