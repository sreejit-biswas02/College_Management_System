"""User Pydantic schemas and password strength validation."""

import re
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.models.user import UserRole

PASSWORD_MIN_LENGTH = 8


def validate_password_strength(password: str) -> str:
    """Enforce baseline password complexity requirements."""
    if len(password) < PASSWORD_MIN_LENGTH:
        raise ValueError(
            f"Password must be at least {PASSWORD_MIN_LENGTH} characters long."
        )
    if not re.search(r"[A-Z]", password):
        raise ValueError("Password must contain at least one uppercase letter.")
    if not re.search(r"[a-z]", password):
        raise ValueError("Password must contain at least one lowercase letter.")
    if not re.search(r"\d", password):
        raise ValueError("Password must contain at least one digit.")
    if not re.search(r"[^A-Za-z0-9]", password):
        raise ValueError("Password must contain at least one special character.")
    return password


class UserResponse(BaseModel):
    """Public user representation without sensitive credentials."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    email: EmailStr
    full_name: str
    role: UserRole
    is_active: bool
    created_at: datetime
    updated_at: datetime


class StudentProfileResponse(BaseModel):
    """Public student profile representation."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    department_id: int
    roll_number: str
    admission_year: int
    current_semester_number: int
    phone: str | None = None
    date_of_birth: date | None = None


class FacultyProfileResponse(BaseModel):
    """Public faculty profile representation."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    department_id: int
    employee_id: str
    designation: str
    phone: str | None = None
    joining_date: date | None = None


class UserCreateBase(BaseModel):
    """Shared registration fields for user accounts."""

    email: EmailStr
    full_name: str = Field(min_length=2, max_length=120)
    password: str = Field(min_length=PASSWORD_MIN_LENGTH, max_length=128)

    @field_validator("password")
    @classmethod
    def check_password_strength(cls, value: str) -> str:
        """Validate password complexity."""
        return validate_password_strength(value)
