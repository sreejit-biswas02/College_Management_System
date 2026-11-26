"""Pydantic schemas for Timetable slots."""

from datetime import datetime, time

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.timetable import DayOfWeek
from app.schemas.course_offering import CourseOfferingResponse


class TimetableSlotCreate(BaseModel):
    """Payload to create a recurring timetable slot."""

    course_offering_id: int = Field(gt=0)
    day_of_week: DayOfWeek
    start_time: time
    end_time: time
    room: str | None = Field(default=None, max_length=50)

    @model_validator(mode="after")
    def validate_time_range(self) -> "TimetableSlotCreate":
        """Ensure end_time is strictly after start_time."""
        if self.end_time <= self.start_time:
            raise ValueError("end_time must be after start_time.")
        return self


class TimetableSlotUpdate(BaseModel):
    """Payload to update an existing timetable slot."""

    day_of_week: DayOfWeek | None = None
    start_time: time | None = None
    end_time: time | None = None
    room: str | None = Field(default=None, max_length=50)


class TimetableSlotResponse(BaseModel):
    """Timetable slot response."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    course_offering_id: int
    day_of_week: DayOfWeek
    start_time: time
    end_time: time
    room: str | None
    created_at: datetime
    updated_at: datetime
    course_offering: CourseOfferingResponse | None = None
