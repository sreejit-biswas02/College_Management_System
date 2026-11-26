"""Pydantic schemas for Departments, Semesters, and Courses."""

import re
from datetime import date, datetime
from typing import Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    computed_field,
    field_validator,
    model_validator,
)

ACADEMIC_YEAR_PATTERN = re.compile(r"^(\d{4})-(\d{4})$")


def validate_indian_academic_year(value: str) -> str:
    """Validate YYYY-YYYY format where the second year is start_year + 1."""
    cleaned = value.strip()
    match = ACADEMIC_YEAR_PATTERN.match(cleaned)
    if not match:
        raise ValueError("Academic year must follow YYYY-YYYY format (e.g. 2026-2027).")
    start_year, end_year = int(match.group(1)), int(match.group(2))
    if end_year != start_year + 1:
        raise ValueError("Academic year must use consecutive years (e.g. 2026-2027).")
    return cleaned


class DepartmentSummary(BaseModel):
    """Compact department representation for nested responses."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    code: str
    name: str
    is_active: bool


class DepartmentCreate(BaseModel):
    """Payload to create a department."""

    code: str = Field(min_length=2, max_length=20)
    name: str = Field(min_length=2, max_length=150)
    description: str | None = None
    is_active: bool = True


class DepartmentUpdate(BaseModel):
    """Payload to update a department."""

    code: str | None = Field(default=None, min_length=2, max_length=20)
    name: str | None = Field(default=None, min_length=2, max_length=150)
    description: str | None = None
    is_active: bool | None = None


class DepartmentResponse(BaseModel):
    """Full department response."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    code: str
    name: str
    description: str | None
    is_active: bool
    created_at: datetime
    updated_at: datetime


class SemesterSummary(BaseModel):
    """Compact semester representation for nested responses."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    academic_year: str
    term_number: int
    start_date: date | None = None
    end_date: date | None = None
    is_active: bool

    @computed_field
    @property
    def semester_type(self) -> Literal["Odd", "Even"]:
        """Return Odd or Even based on the Indian semester number."""
        return "Odd" if self.term_number % 2 == 1 else "Even"


class SemesterCreate(BaseModel):
    """Payload to create a semester."""

    name: str | None = Field(default=None, max_length=100)
    academic_year: str = Field(min_length=9, max_length=20)
    term_number: int = Field(ge=1)
    start_date: date
    end_date: date
    is_active: bool = False

    @field_validator("academic_year")
    @classmethod
    def check_academic_year(cls, value: str) -> str:
        """Enforce YYYY-YYYY format with consecutive years."""
        return validate_indian_academic_year(value)

    @model_validator(mode="after")
    def validate_and_populate_semester(self) -> "SemesterCreate":
        """Auto-generate semester name if omitted and validate date range."""
        if self.name is None or not self.name.strip():
            self.name = f"Semester {self.term_number}"
        else:
            cleaned_name = self.name.strip()
            if len(cleaned_name) < 2:
                raise ValueError("name must be at least 2 characters.")
            self.name = cleaned_name

        if self.end_date <= self.start_date:
            raise ValueError("end_date must be after start_date.")
        return self


class SemesterUpdate(BaseModel):
    """Payload to update a semester."""

    name: str | None = Field(default=None, min_length=2, max_length=100)
    academic_year: str | None = Field(default=None, min_length=9, max_length=20)
    term_number: int | None = Field(default=None, ge=1)
    start_date: date | None = None
    end_date: date | None = None
    is_active: bool | None = None

    @field_validator("academic_year")
    @classmethod
    def check_academic_year(cls, value: str | None) -> str | None:
        """Enforce YYYY-YYYY format when academic_year is provided."""
        if value is None:
            return None
        return validate_indian_academic_year(value)

    @model_validator(mode="after")
    def validate_date_range(self) -> "SemesterUpdate":
        """Ensure end_date is strictly after start_date when both are provided."""
        if (
            self.start_date is not None
            and self.end_date is not None
            and self.end_date <= self.start_date
        ):
            raise ValueError("end_date must be after start_date.")
        return self


class SemesterResponse(BaseModel):
    """Full semester response."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    academic_year: str
    term_number: int
    start_date: date
    end_date: date
    is_active: bool
    created_at: datetime
    updated_at: datetime

    @computed_field
    @property
    def semester_type(self) -> Literal["Odd", "Even"]:
        """Return Odd or Even based on the Indian semester number."""
        return "Odd" if self.term_number % 2 == 1 else "Even"


class CourseSummary(BaseModel):
    """Compact course representation for nested responses."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    code: str
    title: str
    credits: int
    department_id: int


class CourseCreate(BaseModel):
    """Payload to create a course."""

    department_id: int = Field(gt=0)
    code: str = Field(min_length=2, max_length=30)
    title: str = Field(min_length=2, max_length=200)
    credits: int = Field(gt=0, le=30)
    description: str | None = None


class CourseUpdate(BaseModel):
    """Payload to update a course."""

    department_id: int | None = Field(default=None, gt=0)
    code: str | None = Field(default=None, min_length=2, max_length=30)
    title: str | None = Field(default=None, min_length=2, max_length=200)
    credits: int | None = Field(default=None, gt=0, le=30)
    description: str | None = None


class CourseResponse(BaseModel):
    """Full course response with nested department summary."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    department_id: int
    code: str
    title: str
    credits: int
    description: str | None
    created_at: datetime
    updated_at: datetime
    department: DepartmentSummary
