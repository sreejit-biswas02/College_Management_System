"""Audit log model for Admin-triggered odd-to-even semester promotions."""

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


class SemesterPromotionLog(Base):
    """Records each student's semester promotion per academic year."""

    __tablename__ = "semester_promotion_logs"
    __table_args__ = (
        UniqueConstraint(
            "academic_year",
            "student_id",
            name="uq_semester_promotion_year_student",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    academic_year: Mapped[str] = mapped_column(String(20), index=True, nullable=False)
    student_id: Mapped[int] = mapped_column(
        ForeignKey("students.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    old_semester: Mapped[int] = mapped_column(Integer, nullable=False)
    new_semester: Mapped[int] = mapped_column(Integer, nullable=False)
    promoted_by_user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    promoted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
