"""TimetableSlot ORM model."""

from __future__ import annotations

import enum
from datetime import datetime, time
from typing import TYPE_CHECKING

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    String,
    Time,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base

if TYPE_CHECKING:
    from app.models.course_offering import CourseOffering


class DayOfWeek(enum.StrEnum):
    """Days of the week for recurring timetable slots."""

    MONDAY = "monday"
    TUESDAY = "tuesday"
    WEDNESDAY = "wednesday"
    THURSDAY = "thursday"
    FRIDAY = "friday"
    SATURDAY = "saturday"
    SUNDAY = "sunday"


class TimetableSlot(Base):
    """Weekly recurring class slot for a course offering."""

    __tablename__ = "timetable_slots"
    __table_args__ = (
        CheckConstraint("end_time > start_time", name="ck_timetable_slots_times"),
        UniqueConstraint(
            "course_offering_id",
            "day_of_week",
            "start_time",
            name="uq_timetable_slots_offering_day_start",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    course_offering_id: Mapped[int] = mapped_column(
        ForeignKey("course_offerings.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    day_of_week: Mapped[DayOfWeek] = mapped_column(
        Enum(DayOfWeek, name="day_of_week"),
        index=True,
        nullable=False,
    )
    start_time: Mapped[time] = mapped_column(Time, nullable=False)
    end_time: Mapped[time] = mapped_column(Time, nullable=False)
    room: Mapped[str | None] = mapped_column(String(50), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    course_offering: Mapped[CourseOffering] = relationship(
        back_populates="timetable_slots",
    )
