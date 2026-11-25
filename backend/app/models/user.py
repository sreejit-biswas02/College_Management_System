"""User, Student, and Faculty ORM models."""

from __future__ import annotations

import enum
from datetime import date, datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, Date, DateTime, Enum, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base

if TYPE_CHECKING:
    from app.models.academic import Department
    from app.models.assignment import Assignment, Submission
    from app.models.attendance import AttendanceRecord, AttendanceSession
    from app.models.course_offering import CourseOffering, Enrollment
    from app.models.notice import Notice


class UserRole(enum.StrEnum):
    """Supported user roles in the College Management System."""

    ADMIN = "admin"
    FACULTY = "faculty"
    STUDENT = "student"


class User(Base):
    """Central user identity table."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    email: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        index=True,
        nullable=False,
    )
    full_name: Mapped[str] = mapped_column(String(120), nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[UserRole] = mapped_column(
        Enum(UserRole, name="user_role"),
        nullable=False,
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
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

    student_profile: Mapped[Student | None] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
        uselist=False,
    )
    faculty_profile: Mapped[Faculty | None] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
        uselist=False,
    )
    posted_notices: Mapped[list[Notice]] = relationship(
        back_populates="posted_by_user",
    )


class Student(Base):
    """Student-specific profile linked 1-to-1 to a User."""

    __tablename__ = "students"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        unique=True,
        index=True,
        nullable=False,
    )
    department_id: Mapped[int] = mapped_column(
        ForeignKey("departments.id", ondelete="RESTRICT"),
        index=True,
        nullable=False,
    )
    roll_number: Mapped[str] = mapped_column(
        String(50),
        unique=True,
        index=True,
        nullable=False,
    )
    admission_year: Mapped[int] = mapped_column(Integer, nullable=False)
    current_semester_number: Mapped[int] = mapped_column(
        Integer,
        default=1,
        nullable=False,
    )
    phone: Mapped[str | None] = mapped_column(String(20), nullable=True)
    date_of_birth: Mapped[date | None] = mapped_column(Date, nullable=True)
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

    user: Mapped[User] = relationship(back_populates="student_profile")
    department: Mapped[Department] = relationship(back_populates="students")
    enrollments: Mapped[list[Enrollment]] = relationship(
        back_populates="student",
        cascade="all, delete-orphan",
    )
    attendance_records: Mapped[list[AttendanceRecord]] = relationship(
        back_populates="student",
        cascade="all, delete-orphan",
    )
    submissions: Mapped[list[Submission]] = relationship(
        back_populates="student",
        cascade="all, delete-orphan",
    )


class Faculty(Base):
    """Faculty-specific profile linked 1-to-1 to a User."""

    __tablename__ = "faculty"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        unique=True,
        index=True,
        nullable=False,
    )
    department_id: Mapped[int] = mapped_column(
        ForeignKey("departments.id", ondelete="RESTRICT"),
        index=True,
        nullable=False,
    )
    employee_id: Mapped[str] = mapped_column(
        String(50),
        unique=True,
        index=True,
        nullable=False,
    )
    designation: Mapped[str] = mapped_column(String(100), nullable=False)
    phone: Mapped[str | None] = mapped_column(String(20), nullable=True)
    joining_date: Mapped[date | None] = mapped_column(Date, nullable=True)
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

    user: Mapped[User] = relationship(back_populates="faculty_profile")
    department: Mapped[Department] = relationship(back_populates="faculty_members")
    course_offerings: Mapped[list[CourseOffering]] = relationship(
        back_populates="faculty",
    )
    conducted_sessions: Mapped[list[AttendanceSession]] = relationship(
        back_populates="conducted_by_faculty",
    )
    created_assignments: Mapped[list[Assignment]] = relationship(
        back_populates="created_by_faculty",
    )
    graded_submissions: Mapped[list[Submission]] = relationship(
        back_populates="graded_by_faculty",
    )
