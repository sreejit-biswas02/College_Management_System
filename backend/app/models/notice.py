"""Notice and NoticeTarget ORM models."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base
from app.models.user import UserRole

if TYPE_CHECKING:
    from app.models.academic import Department
    from app.models.course_offering import CourseOffering
    from app.models.user import User


class Notice(Base):
    """Announcement or notice posted by an authorized user."""

    __tablename__ = "notices"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    posted_by_user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"),
        index=True,
        nullable=False,
    )
    is_published: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        index=True,
        nullable=False,
    )
    published_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        index=True,
        nullable=False,
    )
    expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
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

    posted_by_user: Mapped[User] = relationship(back_populates="posted_notices")
    targets: Mapped[list[NoticeTarget]] = relationship(
        back_populates="notice",
        cascade="all, delete-orphan",
    )


class NoticeTarget(Base):
    """Audience target scope for a notice."""

    __tablename__ = "notice_targets"
    __table_args__ = (
        UniqueConstraint(
            "notice_id",
            "target_role",
            "department_id",
            "course_offering_id",
            name="uq_notice_targets_scope",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    notice_id: Mapped[int] = mapped_column(
        ForeignKey("notices.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    target_role: Mapped[UserRole | None] = mapped_column(
        Enum(UserRole, name="user_role", create_type=False),
        index=True,
        nullable=True,
    )
    department_id: Mapped[int | None] = mapped_column(
        ForeignKey("departments.id", ondelete="CASCADE"),
        index=True,
        nullable=True,
    )
    course_offering_id: Mapped[int | None] = mapped_column(
        ForeignKey("course_offerings.id", ondelete="CASCADE"),
        index=True,
        nullable=True,
    )

    notice: Mapped[Notice] = relationship(back_populates="targets")
    department: Mapped[Department | None] = relationship(
        back_populates="notice_targets",
    )
    course_offering: Mapped[CourseOffering | None] = relationship(
        back_populates="notice_targets",
    )
