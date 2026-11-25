"""Business logic for Course Offering management."""

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, joinedload

from app.models.academic import Course, Semester
from app.models.course_offering import CourseOffering
from app.models.user import Faculty, User
from app.schemas.course_offering import CourseOfferingCreate, CourseOfferingUpdate
from app.services.exceptions import (
    BusinessRuleError,
    ConflictError,
    NotFoundError,
    commit_or_conflict,
)


def _offering_query():
    return select(CourseOffering).options(
        joinedload(CourseOffering.course),
        joinedload(CourseOffering.semester),
        joinedload(CourseOffering.faculty).joinedload(Faculty.user),
    )


def _resolve_faculty_id(
    db: Session,
    *,
    faculty_id: int | None = None,
    faculty_employee_id: str | None = None,
) -> int:
    """Resolve faculty_id or faculty_employee_id to an active Faculty primary key."""
    stmt = select(Faculty).options(joinedload(Faculty.user))
    if faculty_employee_id is not None:
        faculty = db.scalar(
            stmt.where(Faculty.employee_id == faculty_employee_id.strip())
        )
    elif faculty_id is not None:
        faculty = db.scalar(stmt.where(Faculty.id == faculty_id))
    else:
        raise BusinessRuleError(
            "Either faculty_id or faculty_employee_id must be provided."
        )

    if faculty is None:
        raise NotFoundError("Faculty member not found.")
    if not faculty.user.is_active:
        raise BusinessRuleError(
            "Inactive faculty member cannot be assigned to a course offering."
        )
    return faculty.id


def _validate_offering_refs(
    db: Session,
    *,
    course_id: int,
    semester_id: int,
) -> None:
    if db.get(Course, course_id) is None:
        raise NotFoundError("Course not found.")
    if db.get(Semester, semester_id) is None:
        raise NotFoundError("Semester not found.")


def create_course_offering(
    db: Session,
    payload: CourseOfferingCreate,
) -> CourseOffering:
    """Create a course offering for a course, semester, faculty, and section."""
    _validate_offering_refs(
        db,
        course_id=payload.course_id,
        semester_id=payload.semester_id,
    )
    faculty_id = _resolve_faculty_id(
        db,
        faculty_id=payload.faculty_id,
        faculty_employee_id=payload.faculty_employee_id,
    )
    section = payload.section.strip().upper()
    existing = db.scalar(
        select(CourseOffering).where(
            CourseOffering.course_id == payload.course_id,
            CourseOffering.semester_id == payload.semester_id,
            CourseOffering.section == section,
        )
    )
    if existing is not None:
        raise ConflictError(
            "Course offering for this course, semester, and section already exists."
        )

    offering = CourseOffering(
        course_id=payload.course_id,
        semester_id=payload.semester_id,
        faculty_id=faculty_id,
        section=section,
        max_capacity=payload.max_capacity,
        is_active=payload.is_active,
    )
    db.add(offering)
    commit_or_conflict(
        db,
        "Course offering for this course, semester, and section already exists.",
    )
    return get_course_offering_by_id(db, offering.id)


def get_course_offering_by_id(db: Session, offering_id: int) -> CourseOffering:
    """Fetch a course offering by ID with eager-loaded relationships."""
    offering = db.scalar(_offering_query().where(CourseOffering.id == offering_id))
    if offering is None:
        raise NotFoundError("Course offering not found.")
    return offering


def list_course_offerings(
    db: Session,
    *,
    search: str | None = None,
    semester_id: int | None = None,
    faculty_id: int | None = None,
    course_id: int | None = None,
    section: str | None = None,
    is_active: bool | None = None,
    page: int = 1,
    page_size: int = 20,
) -> tuple[list[CourseOffering], int]:
    """List course offerings with search, filtering, and pagination."""
    stmt = _offering_query()
    count_stmt = select(func.count(CourseOffering.id))

    filters = []
    if search:
        pattern = f"%{search.strip()}%"
        stmt = (
            stmt.join(CourseOffering.course)
            .join(CourseOffering.semester)
            .join(CourseOffering.faculty)
            .join(Faculty.user)
        )
        count_stmt = (
            count_stmt.join(CourseOffering.course)
            .join(CourseOffering.semester)
            .join(CourseOffering.faculty)
            .join(Faculty.user)
        )
        filters.append(
            or_(
                Course.code.ilike(pattern),
                Course.title.ilike(pattern),
                Semester.name.ilike(pattern),
                Semester.academic_year.ilike(pattern),
                CourseOffering.section.ilike(pattern),
                Faculty.employee_id.ilike(pattern),
                User.full_name.ilike(pattern),
            )
        )
    if semester_id is not None:
        filters.append(CourseOffering.semester_id == semester_id)
    if faculty_id is not None:
        filters.append(CourseOffering.faculty_id == faculty_id)
    if course_id is not None:
        filters.append(CourseOffering.course_id == course_id)
    if section:
        filters.append(CourseOffering.section == section.strip().upper())
    if is_active is not None:
        filters.append(CourseOffering.is_active == is_active)

    if filters:
        stmt = stmt.where(*filters)
        count_stmt = count_stmt.where(*filters)

    total = db.scalar(count_stmt) or 0
    items = list(
        db.scalars(
            stmt.order_by(CourseOffering.id.asc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        ).all()
    )
    return items, total


def update_course_offering(
    db: Session,
    offering_id: int,
    payload: CourseOfferingUpdate,
) -> CourseOffering:
    """Update a course offering and validate uniqueness and foreign keys."""
    offering = get_course_offering_by_id(db, offering_id)

    new_course_id = (
        payload.course_id if payload.course_id is not None else offering.course_id
    )
    new_semester_id = (
        payload.semester_id if payload.semester_id is not None else offering.semester_id
    )
    new_section = (
        payload.section.strip().upper()
        if payload.section is not None
        else offering.section
    )
    _validate_offering_refs(
        db,
        course_id=new_course_id,
        semester_id=new_semester_id,
    )
    if payload.faculty_id is not None or payload.faculty_employee_id is not None:
        new_faculty_id = _resolve_faculty_id(
            db,
            faculty_id=payload.faculty_id,
            faculty_employee_id=payload.faculty_employee_id,
        )
    else:
        new_faculty_id = offering.faculty_id

    if (new_course_id, new_semester_id, new_section) != (
        offering.course_id,
        offering.semester_id,
        offering.section,
    ):
        existing = db.scalar(
            select(CourseOffering).where(
                CourseOffering.course_id == new_course_id,
                CourseOffering.semester_id == new_semester_id,
                CourseOffering.section == new_section,
                CourseOffering.id != offering.id,
            )
        )
        if existing is not None:
            raise ConflictError(
                "Course offering for this course, semester, and section already exists."
            )

    offering.course_id = new_course_id
    offering.semester_id = new_semester_id
    offering.faculty_id = new_faculty_id
    offering.section = new_section
    if payload.max_capacity is not None:
        offering.max_capacity = payload.max_capacity
    if payload.is_active is not None:
        offering.is_active = payload.is_active

    commit_or_conflict(
        db,
        "Course offering update conflicts with an existing offering.",
    )
    return get_course_offering_by_id(db, offering.id)


def set_course_offering_active_status(
    db: Session,
    offering_id: int,
    is_active: bool,
) -> CourseOffering:
    """Activate or deactivate a course offering."""
    offering = get_course_offering_by_id(db, offering_id)
    offering.is_active = is_active
    db.commit()
    return get_course_offering_by_id(db, offering.id)
