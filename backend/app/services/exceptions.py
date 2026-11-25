"""Shared service-layer exceptions and transaction helpers."""

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session


class NotFoundError(Exception):
    """Raised when a requested resource or foreign key target does not exist."""


class ConflictError(Exception):
    """Raised when an operation violates a uniqueness or conflict constraint."""


class BusinessRuleError(Exception):
    """Raised when an operation violates domain validation rules."""


class ForbiddenError(Exception):
    """Raised when an actor is not authorized to access/modify a resource."""


def commit_or_conflict(db: Session, conflict_message: str) -> None:
    """Commit the current transaction or roll back and raise ConflictError."""
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise ConflictError(conflict_message) from exc
