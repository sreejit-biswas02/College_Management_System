"""CourseOffering and Enrollment ORM models."""

from __future__ import annotations

import enum
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base

if TYPE_CHECKING:
    from app.models.academic import Course, Semester
    from app.models.assignment import Assignment
    from app.models.attendance import AttendanceSession
    from app.models.notice import NoticeTarget
    from app.models.timetable import TimetableSlot
    from app.models.user import Faculty, Student


class EnrollmentStatus(enum.StrEnum):
    """Status of a student's enrollment in a course offering."""

    ENROLLED = "enrolled"
    DROPPED = "dropped"
    COMPLETED = "completed"


class CourseOffering(Base):
    """Specific semester offering of a course taught by a faculty member."""

    __tablename__ = "course_offerings"
    __table_args__ = (
        UniqueConstraint(
            "course_id",
            "semester_id",
            "section",
            name="uq_course_offerings_course_sem_section",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    course_id: Mapped[int] = mapped_column(
        ForeignKey("courses.id", ondelete="RESTRICT"),
        index=True,
        nullable=False,
    )
    semester_id: Mapped[int] = mapped_column(
        ForeignKey("semesters.id", ondelete="RESTRICT"),
        index=True,
        nullable=False,
    )
    faculty_id: Mapped[int] = mapped_column(
        ForeignKey("faculty.id", ondelete="RESTRICT"),
        index=True,
        nullable=False,
    )
    section: Mapped[str] = mapped_column(String(20), default="A", nullable=False)
    max_capacity: Mapped[int | None] = mapped_column(Integer, nullable=True)
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        server_default=text("true"),
        index=True,
        nullable=False,
    )
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

    course: Mapped[Course] = relationship(back_populates="offerings")
    semester: Mapped[Semester] = relationship(back_populates="course_offerings")
    faculty: Mapped[Faculty] = relationship(back_populates="course_offerings")
    enrollments: Mapped[list[Enrollment]] = relationship(
        back_populates="course_offering",
        cascade="all, delete-orphan",
    )
    attendance_sessions: Mapped[list[AttendanceSession]] = relationship(
        back_populates="course_offering",
        cascade="all, delete-orphan",
    )
    assignments: Mapped[list[Assignment]] = relationship(
        back_populates="course_offering",
        cascade="all, delete-orphan",
    )
    timetable_slots: Mapped[list[TimetableSlot]] = relationship(
        back_populates="course_offering",
        cascade="all, delete-orphan",
    )
    notice_targets: Mapped[list[NoticeTarget]] = relationship(
        back_populates="course_offering",
        cascade="all, delete-orphan",
    )


class Enrollment(Base):
    """Student enrollment in a specific course offering."""

    __tablename__ = "enrollments"
    __table_args__ = (
        UniqueConstraint(
            "student_id",
            "course_offering_id",
            name="uq_enrollments_student_offering",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    student_id: Mapped[int] = mapped_column(
        ForeignKey("students.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    course_offering_id: Mapped[int] = mapped_column(
        ForeignKey("course_offerings.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    status: Mapped[EnrollmentStatus] = mapped_column(
        Enum(EnrollmentStatus, name="enrollment_status"),
        default=EnrollmentStatus.ENROLLED,
        index=True,
        nullable=False,
    )
    enrolled_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    student: Mapped[Student] = relationship(back_populates="enrollments")
    course_offering: Mapped[CourseOffering] = relationship(back_populates="enrollments")
