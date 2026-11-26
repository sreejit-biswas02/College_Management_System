"""Database-backed atomic sequence counters for Student and Faculty IDs."""

from datetime import datetime

from sqlalchemy import DateTime, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


class IDSequence(Base):
    """Per-scope monotonic counter used for concurrency-safe ID generation."""

    __tablename__ = "id_sequences"
    __table_args__ = (
        UniqueConstraint(
            "entity_type",
            "scope_key",
            name="uq_id_sequences_entity_scope",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    entity_type: Mapped[str] = mapped_column(String(20), nullable=False)
    scope_key: Mapped[str] = mapped_column(String(100), nullable=False)
    last_value: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
