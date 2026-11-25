"""Pydantic schemas for Departments, Semesters, and Courses."""

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator


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
    is_active: bool


class SemesterCreate(BaseModel):
    """Payload to create a semester."""

    name: str = Field(min_length=2, max_length=100)
    academic_year: str = Field(min_length=4, max_length=20)
    term_number: int = Field(ge=1, le=12)
    start_date: date
    end_date: date
    is_active: bool = False

    @model_validator(mode="after")
    def validate_date_range(self) -> "SemesterCreate":
        """Ensure end_date is strictly after start_date."""
        if self.end_date <= self.start_date:
            raise ValueError("end_date must be after start_date.")
        return self


class SemesterUpdate(BaseModel):
    """Payload to update a semester."""

    name: str | None = Field(default=None, min_length=2, max_length=100)
    academic_year: str | None = Field(default=None, min_length=4, max_length=20)
    term_number: int | None = Field(default=None, ge=1, le=12)
    start_date: date | None = None
    end_date: date | None = None
    is_active: bool | None = None


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
