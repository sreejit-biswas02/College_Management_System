"""Business logic for Timetable slots and conflict detection."""

from datetime import time

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.models.course_offering import CourseOffering, Enrollment, EnrollmentStatus
from app.models.timetable import DayOfWeek, TimetableSlot
from app.models.user import Faculty, Student, User, UserRole
from app.schemas.timetable import TimetableSlotCreate, TimetableSlotUpdate
from app.services.exceptions import (
    BusinessRuleError,
    ConflictError,
    ForbiddenError,
    NotFoundError,
    commit_or_conflict,
)


def _check_slot_conflicts(
    db: Session,
    *,
    offering: CourseOffering,
    day_of_week: DayOfWeek,
    start_time: time,
    end_time: time,
    exclude_slot_id: int | None = None,
) -> None:
    """Prevent overlapping slots for the same offering or same faculty in a semester."""
    # 1. Check same offering overlap
    offering_stmt = select(TimetableSlot).where(
        TimetableSlot.course_offering_id == offering.id,
        TimetableSlot.day_of_week == day_of_week,
        TimetableSlot.start_time < end_time,
        TimetableSlot.end_time > start_time,
    )
    if exclude_slot_id is not None:
        offering_stmt = offering_stmt.where(TimetableSlot.id != exclude_slot_id)
    if db.scalar(offering_stmt) is not None:
        raise ConflictError(
            "Timetable slot overlaps with an existing slot for this course offering."
        )

    # 2. Check faculty overlap within the same semester
    faculty_stmt = (
        select(TimetableSlot)
        .join(TimetableSlot.course_offering)
        .where(
            CourseOffering.semester_id == offering.semester_id,
            CourseOffering.faculty_id == offering.faculty_id,
            CourseOffering.is_active.is_(True),
            TimetableSlot.day_of_week == day_of_week,
            TimetableSlot.start_time < end_time,
            TimetableSlot.end_time > start_time,
        )
    )
    if exclude_slot_id is not None:
        faculty_stmt = faculty_stmt.where(TimetableSlot.id != exclude_slot_id)
    if db.scalar(faculty_stmt) is not None:
        raise ConflictError(
            "Timetable slot overlaps with another slot for the assigned faculty."
        )


def create_timetable_slot(
    db: Session,
    payload: TimetableSlotCreate,
) -> TimetableSlot:
    """Create a timetable slot while preventing offering and faculty overlaps."""
    offering = db.get(CourseOffering, payload.course_offering_id)
    if offering is None:
        raise NotFoundError("Course offering not found.")

    _check_slot_conflicts(
        db,
        offering=offering,
        day_of_week=payload.day_of_week,
        start_time=payload.start_time,
        end_time=payload.end_time,
    )

    slot = TimetableSlot(
        course_offering_id=offering.id,
        day_of_week=payload.day_of_week,
        start_time=payload.start_time,
        end_time=payload.end_time,
        room=payload.room.strip() if payload.room else None,
    )
    db.add(slot)
    commit_or_conflict(db, "Timetable slot conflicts with an existing slot.")
    db.refresh(slot)
    return slot


def update_timetable_slot(
    db: Session,
    slot_id: int,
    payload: TimetableSlotUpdate,
) -> TimetableSlot:
    """Update a timetable slot while validating times and overlaps."""
    slot = db.get(TimetableSlot, slot_id)
    if slot is None:
        raise NotFoundError("Timetable slot not found.")

    offering = db.get(CourseOffering, slot.course_offering_id)
    if offering is None:
        raise NotFoundError("Course offering not found.")

    new_day = (
        payload.day_of_week if payload.day_of_week is not None else slot.day_of_week
    )
    new_start = (
        payload.start_time if payload.start_time is not None else slot.start_time
    )
    new_end = payload.end_time if payload.end_time is not None else slot.end_time
    if new_end <= new_start:
        raise BusinessRuleError("end_time must be after start_time.")

    _check_slot_conflicts(
        db,
        offering=offering,
        day_of_week=new_day,
        start_time=new_start,
        end_time=new_end,
        exclude_slot_id=slot.id,
    )

    slot.day_of_week = new_day
    slot.start_time = new_start
    slot.end_time = new_end
    if payload.room is not None:
        slot.room = payload.room.strip() or None

    commit_or_conflict(db, "Timetable slot conflicts with an existing slot.")
    db.refresh(slot)
    return slot


def delete_timetable_slot(db: Session, slot_id: int) -> None:
    """Remove a timetable slot."""
    slot = db.get(TimetableSlot, slot_id)
    if slot is None:
        raise NotFoundError("Timetable slot not found.")
    db.delete(slot)
    db.commit()


def _timetable_load_options() -> tuple:
    return (
        selectinload(TimetableSlot.course_offering).selectinload(CourseOffering.course),
        selectinload(TimetableSlot.course_offering).selectinload(
            CourseOffering.semester
        ),
        selectinload(TimetableSlot.course_offering)
        .selectinload(CourseOffering.faculty)
        .selectinload(Faculty.user),
        selectinload(TimetableSlot.course_offering)
        .selectinload(CourseOffering.faculty)
        .selectinload(Faculty.department),
    )


def list_timetable_slots(
    db: Session,
    *,
    semester_id: int | None = None,
    section: str | None = None,
    day_of_week: DayOfWeek | None = None,
    faculty_id: int | None = None,
    course_offering_id: int | None = None,
    page: int = 1,
    page_size: int = 50,
) -> tuple[list[TimetableSlot], int]:
    """List timetable slots with filtering and pagination."""
    stmt = (
        select(TimetableSlot)
        .options(*_timetable_load_options())
        .join(TimetableSlot.course_offering)
    )
    count_stmt = select(func.count(TimetableSlot.id)).join(
        TimetableSlot.course_offering
    )

    filters = []
    if semester_id is not None:
        filters.append(CourseOffering.semester_id == semester_id)
    if section:
        filters.append(CourseOffering.section == section.strip().upper())
    if day_of_week is not None:
        filters.append(TimetableSlot.day_of_week == day_of_week)
    if faculty_id is not None:
        filters.append(CourseOffering.faculty_id == faculty_id)
    if course_offering_id is not None:
        filters.append(TimetableSlot.course_offering_id == course_offering_id)

    if filters:
        stmt = stmt.where(*filters)
        count_stmt = count_stmt.where(*filters)

    total = db.scalar(count_stmt) or 0
    items = list(
        db.scalars(
            stmt.order_by(TimetableSlot.day_of_week, TimetableSlot.start_time)
            .offset((page - 1) * page_size)
            .limit(page_size)
        ).all()
    )
    return items, total


def get_my_timetable(
    db: Session,
    actor: User,
    *,
    day_of_week: DayOfWeek | None = None,
) -> list[TimetableSlot]:
    """Return timetable slots for the authenticated student or faculty member."""
    if actor.role == UserRole.STUDENT:
        student = db.scalar(select(Student).where(Student.user_id == actor.id))
        if student is None:
            raise NotFoundError("Student profile not found.")
        offering_ids = list(
            db.scalars(
                select(Enrollment.course_offering_id).where(
                    Enrollment.student_id == student.id,
                    Enrollment.status == EnrollmentStatus.ENROLLED,
                )
            ).all()
        )
    elif actor.role == UserRole.FACULTY:
        faculty = db.scalar(select(Faculty).where(Faculty.user_id == actor.id))
        if faculty is None:
            raise NotFoundError("Faculty profile not found.")
        offering_ids = list(
            db.scalars(
                select(CourseOffering.id).where(
                    CourseOffering.faculty_id == faculty.id,
                    CourseOffering.is_active.is_(True),
                )
            ).all()
        )
    else:
        raise ForbiddenError(
            "Personal timetable is only available to students and faculty."
        )

    if not offering_ids:
        return []

    stmt = (
        select(TimetableSlot)
        .options(*_timetable_load_options())
        .where(TimetableSlot.course_offering_id.in_(offering_ids))
    )
    if day_of_week is not None:
        stmt = stmt.where(TimetableSlot.day_of_week == day_of_week)

    return list(
        db.scalars(
            stmt.order_by(TimetableSlot.day_of_week, TimetableSlot.start_time)
        ).all()
    )
