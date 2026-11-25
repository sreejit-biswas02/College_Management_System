"""Authentication request and response Pydantic schemas."""

from datetime import date

from pydantic import BaseModel, EmailStr, Field

from app.models.user import UserRole
from app.schemas.user import (
    FacultyProfileResponse,
    StudentProfileResponse,
    UserCreateBase,
    UserResponse,
)


class StudentRegisterRequest(UserCreateBase):
    """Registration payload for a new student account and profile."""

    department_id: int = Field(gt=0)
    roll_number: str = Field(min_length=2, max_length=50)
    admission_year: int = Field(ge=1950, le=2100)
    current_semester_number: int = Field(default=1, ge=1, le=16)
    phone: str | None = Field(default=None, max_length=20)
    date_of_birth: date | None = None


class FacultyRegisterRequest(UserCreateBase):
    """Registration payload for a new faculty account and profile."""

    department_id: int = Field(gt=0)
    employee_id: str = Field(min_length=2, max_length=50)
    designation: str = Field(min_length=2, max_length=100)
    phone: str | None = Field(default=None, max_length=20)
    joining_date: date | None = None


class PublicRegisterRequest(UserCreateBase):
    """Generic public registration request (rejects ADMIN role)."""

    role: UserRole
    department_id: int | None = Field(default=None, gt=0)
    roll_number: str | None = Field(default=None, min_length=2, max_length=50)
    admission_year: int | None = Field(default=None, ge=1950, le=2100)
    current_semester_number: int = Field(default=1, ge=1, le=16)
    employee_id: str | None = Field(default=None, min_length=2, max_length=50)
    designation: str | None = Field(default=None, min_length=2, max_length=100)
    phone: str | None = Field(default=None, max_length=20)
    date_of_birth: date | None = None
    joining_date: date | None = None


class AdminCreateRequest(UserCreateBase):
    """Protected payload for creating an administrator account."""


class RegisterResponse(BaseModel):
    """Safe registration response with user and optional profile."""

    user: UserResponse
    student_profile: StudentProfileResponse | None = None
    faculty_profile: FacultyProfileResponse | None = None


class LoginRequest(BaseModel):
    """Email and password login payload."""

    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class LoginResponse(BaseModel):
    """JWT access token and safe user payload returned on login."""

    access_token: str
    token_type: str = "bearer"
    user: UserResponse
