"""Business logic for Course Enrollments."""

from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from app.models.course_offering import CourseOffering, Enrollment, EnrollmentStatus
from app.models.user import Faculty, Student, User
from app.schemas.enrollment import EnrollmentCreate
from app.services.exceptions import (
    BusinessRuleError,
    ConflictError,
    ForbiddenError,
    NotFoundError,
    commit_or_conflict,
)


def _enrollment_query():
    return select(Enrollment).options(
        joinedload(Enrollment.student).joinedload(Student.user),
        joinedload(Enrollment.student).joinedload(Student.department),
        joinedload(Enrollment.course_offering).joinedload(CourseOffering.course),
        joinedload(Enrollment.course_offering).joinedload(CourseOffering.semester),
        joinedload(Enrollment.course_offering)
        .joinedload(CourseOffering.faculty)
        .joinedload(Faculty.user),
    )


def enroll_student(db: Session, payload: EnrollmentCreate) -> Enrollment:
    """Enroll a student into an active course offering."""
    student = db.get(Student, payload.student_id)
    if student is None:
        raise NotFoundError("Student not found.")

    offering = db.get(CourseOffering, payload.course_offering_id)
    if offering is None:
        raise NotFoundError("Course offering not found.")
    if not offering.is_active:
        raise BusinessRuleError("Cannot enroll in an inactive course offering.")

    existing = db.scalar(
        select(Enrollment).where(
            Enrollment.student_id == payload.student_id,
            Enrollment.course_offering_id == payload.course_offering_id,
        )
    )
    if existing is not None:
        raise ConflictError("Student is already enrolled in this course offering.")

    if (
        payload.status == EnrollmentStatus.ENROLLED
        and offering.max_capacity is not None
    ):
        active_count = (
            db.scalar(
                select(func.count(Enrollment.id)).where(
                    Enrollment.course_offering_id == offering.id,
                    Enrollment.status == EnrollmentStatus.ENROLLED,
                )
            )
            or 0
        )
        if active_count >= offering.max_capacity:
            raise BusinessRuleError("Course offering has reached maximum capacity.")

    enrollment = Enrollment(
        student_id=payload.student_id,
        course_offering_id=payload.course_offering_id,
        status=payload.status,
    )
    db.add(enrollment)
    commit_or_conflict(db, "Student is already enrolled in this course offering.")
    return get_enrollment_by_id(db, enrollment.id)


def get_enrollment_by_id(db: Session, enrollment_id: int) -> Enrollment:
    """Fetch an enrollment by ID with eager-loaded relationships."""
    enrollment = db.scalar(_enrollment_query().where(Enrollment.id == enrollment_id))
    if enrollment is None:
        raise NotFoundError("Enrollment not found.")
    return enrollment


def list_enrollments(
    db: Session,
    *,
    student_id: int | None = None,
    course_offering_id: int | None = None,
    status: EnrollmentStatus | None = None,
    page: int = 1,
    page_size: int = 20,
) -> tuple[list[Enrollment], int]:
    """List enrollments with optional filters and pagination."""
    stmt = _enrollment_query()
    count_stmt = select(func.count(Enrollment.id))

    filters = []
    if student_id is not None:
        filters.append(Enrollment.student_id == student_id)
    if course_offering_id is not None:
        filters.append(Enrollment.course_offering_id == course_offering_id)
    if status is not None:
        filters.append(Enrollment.status == status)

    if filters:
        stmt = stmt.where(*filters)
        count_stmt = count_stmt.where(*filters)

    total = db.scalar(count_stmt) or 0
    items = list(
        db.scalars(
            stmt.order_by(Enrollment.id.asc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        ).all()
    )
    return items, total


def update_enrollment_status(
    db: Session,
    enrollment_id: int,
    new_status: EnrollmentStatus,
) -> Enrollment:
    """Update the status of an existing enrollment."""
    enrollment = get_enrollment_by_id(db, enrollment_id)
    enrollment.status = new_status
    db.commit()
    return get_enrollment_by_id(db, enrollment.id)


def list_student_enrollments(
    db: Session,
    *,
    user_id: int,
    status: EnrollmentStatus | None = None,
    page: int = 1,
    page_size: int = 20,
) -> tuple[list[Enrollment], int]:
    """List enrollments belonging to the authenticated student."""
    student = db.scalar(select(Student).where(Student.user_id == user_id))
    if student is None:
        raise NotFoundError("Student profile not found.")
    return list_enrollments(
        db,
        student_id=student.id,
        status=status,
        page=page,
        page_size=page_size,
    )


def list_offering_enrollments_for_faculty(
    db: Session,
    *,
    offering_id: int,
    actor: User,
    page: int = 1,
    page_size: int = 20,
) -> tuple[list[Enrollment], int]:
    """List enrollments for an offering, enforcing faculty assignment."""
    offering = db.scalar(
        select(CourseOffering)
        .options(joinedload(CourseOffering.faculty))
        .where(CourseOffering.id == offering_id)
    )
    if offering is None:
        raise NotFoundError("Course offering not found.")
    if offering.faculty.user_id != actor.id:
        raise ForbiddenError("You are not assigned to this course offering.")

    return list_enrollments(
        db,
        course_offering_id=offering_id,
        page=page,
        page_size=page_size,
    )
