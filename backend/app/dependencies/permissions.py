"""Role-based access control and resource ownership dependencies."""

from collections.abc import Callable
from typing import Annotated

from fastapi import Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database.connection import get_db
from app.dependencies.authentication import require_active_user
from app.models.course_offering import CourseOffering
from app.models.user import Student, User, UserRole


def require_roles(*allowed_roles: UserRole) -> Callable[[User], User]:
    """Return a dependency enforcing that the active user has an allowed role."""

    def _role_checker(
        current_user: Annotated[User, Depends(require_active_user)],
    ) -> User:
        if current_user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions.",
            )
        return current_user

    return _role_checker


def verify_student_self_or_admin(
    student_id: int,
    current_user: Annotated[User, Depends(require_active_user)],
    db: Annotated[Session, Depends(get_db)],
) -> Student:
    """Allow ADMIN, or a STUDENT accessing only their own student profile."""
    student = db.get(Student, student_id)
    if student is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Student record not found.",
        )

    if current_user.role == UserRole.ADMIN:
        return student

    if current_user.role == UserRole.STUDENT and student.user_id == current_user.id:
        return student

    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="You do not have permission to access this student record.",
    )


def verify_faculty_offering_access(
    course_offering_id: int,
    current_user: Annotated[User, Depends(require_active_user)],
    db: Annotated[Session, Depends(get_db)],
) -> CourseOffering:
    """Allow ADMIN, or FACULTY assigned to the requested course offering."""
    offering = db.get(CourseOffering, course_offering_id)
    if offering is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Course offering not found.",
        )

    if current_user.role == UserRole.ADMIN:
        return offering

    if (
        current_user.role == UserRole.FACULTY
        and offering.faculty is not None
        and offering.faculty.user_id == current_user.id
    ):
        return offering

    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="You are not assigned to this course offering.",
    )
