"""AttendanceSession and AttendanceRecord ORM models."""

from __future__ import annotations

import enum
from datetime import date, datetime, time
from typing import TYPE_CHECKING

from sqlalchemy import (
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    Time,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base

if TYPE_CHECKING:
    from app.models.course_offering import CourseOffering
    from app.models.user import Faculty, Student


class AttendanceStatus(enum.StrEnum):
    """Attendance status for a student in a session."""

    PRESENT = "present"
    ABSENT = "absent"
    LATE = "late"
    EXCUSED = "excused"


class AttendanceSession(Base):
    """Class session for which attendance is recorded."""

    __tablename__ = "attendance_sessions"
    __table_args__ = (
        UniqueConstraint(
            "course_offering_id",
            "session_date",
            "session_number",
            name="uq_attendance_sessions_offering_date_num",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    course_offering_id: Mapped[int] = mapped_column(
        ForeignKey("course_offerings.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    conducted_by_faculty_id: Mapped[int] = mapped_column(
        ForeignKey("faculty.id", ondelete="RESTRICT"),
        index=True,
        nullable=False,
    )
    session_date: Mapped[date] = mapped_column(Date, index=True, nullable=False)
    session_number: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    start_time: Mapped[time | None] = mapped_column(Time, nullable=True)
    topic: Mapped[str | None] = mapped_column(String(200), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    course_offering: Mapped[CourseOffering] = relationship(
        back_populates="attendance_sessions",
    )
    conducted_by_faculty: Mapped[Faculty] = relationship(
        back_populates="conducted_sessions",
    )
    records: Mapped[list[AttendanceRecord]] = relationship(
        back_populates="session",
        cascade="all, delete-orphan",
    )


class AttendanceRecord(Base):
    """Individual student attendance record within a session."""

    __tablename__ = "attendance_records"
    __table_args__ = (
        UniqueConstraint(
            "session_id",
            "student_id",
            name="uq_attendance_records_session_student",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    session_id: Mapped[int] = mapped_column(
        ForeignKey("attendance_sessions.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    student_id: Mapped[int] = mapped_column(
        ForeignKey("students.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    status: Mapped[AttendanceStatus] = mapped_column(
        Enum(AttendanceStatus, name="attendance_status"),
        nullable=False,
    )
    remarks: Mapped[str | None] = mapped_column(String(255), nullable=True)
    marked_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    session: Mapped[AttendanceSession] = relationship(back_populates="records")
    student: Mapped[Student] = relationship(back_populates="attendance_records")
