"""Pydantic schemas for administrative and self-service Faculty management."""

import re
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.schemas.academic import DepartmentSummary
from app.schemas.user import UserCreateBase, UserResponse

FACULTY_ID_PATTERN = re.compile(r"^F-[A-Z0-9_-]+-\d{3,}$")


class AdminFacultyCreate(UserCreateBase):
    """Payload for an admin to create a faculty account and profile."""

    department_id: int = Field(gt=0)
    designation: str = Field(min_length=2, max_length=100)
    phone: str | None = Field(default=None, max_length=20)
    joining_date: date | None = None
    is_active: bool = True


class AdminFacultyUpdate(BaseModel):
    """Payload for an admin to update a faculty member's user or profile."""

    email: EmailStr | None = None
    full_name: str | None = Field(default=None, min_length=2, max_length=120)
    department_id: int | None = Field(default=None, gt=0)
    employee_id: str | None = Field(default=None, min_length=5, max_length=50)
    designation: str | None = Field(default=None, min_length=2, max_length=100)
    phone: str | None = Field(default=None, max_length=20)
    joining_date: date | None = None
    is_active: bool | None = None
    recalculate_id: bool = False

    @field_validator("employee_id")
    @classmethod
    def validate_faculty_id_format(cls, value: str | None) -> str | None:
        """Ensure manually edited Faculty IDs follow F-DEPTCODE-XXX."""
        if value is None:
            return None
        cleaned = value.strip().upper()
        if not FACULTY_ID_PATTERN.match(cleaned):
            raise ValueError(
                "Faculty ID must match format F-DEPTCODE-XXX (e.g. F-CS-001)."
            )
        return cleaned


class FacultySummary(BaseModel):
    """Compact faculty representation for nested course offering responses."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    department_id: int
    employee_id: str
    designation: str
    user: UserResponse


class FacultyDetailResponse(BaseModel):
    """Detailed faculty profile with linked User and Department."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    department_id: int
    employee_id: str
    designation: str
    phone: str | None
    joining_date: date | None
    created_at: datetime
    updated_at: datetime
    user: UserResponse
    department: DepartmentSummary
