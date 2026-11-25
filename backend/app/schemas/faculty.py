"""Pydantic schemas for administrative and self-service Faculty management."""

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.schemas.academic import DepartmentSummary
from app.schemas.user import UserCreateBase, UserResponse


class AdminFacultyCreate(UserCreateBase):
    """Payload for an admin to create a faculty account and profile."""

    department_id: int = Field(gt=0)
    employee_id: str = Field(min_length=2, max_length=50)
    designation: str = Field(min_length=2, max_length=100)
    phone: str | None = Field(default=None, max_length=20)
    joining_date: date | None = None
    is_active: bool = True


class AdminFacultyUpdate(BaseModel):
    """Payload for an admin to update a faculty member's user or profile."""

    email: EmailStr | None = None
    full_name: str | None = Field(default=None, min_length=2, max_length=120)
    department_id: int | None = Field(default=None, gt=0)
    employee_id: str | None = Field(default=None, min_length=2, max_length=50)
    designation: str | None = Field(default=None, min_length=2, max_length=100)
    phone: str | None = Field(default=None, max_length=20)
    joining_date: date | None = None
    is_active: bool | None = None


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
