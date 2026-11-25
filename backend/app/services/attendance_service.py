"""Business logic for Attendance sessions and student attendance records."""

from sqlalchemy import case, func, select
from sqlalchemy.orm import Session, selectinload

from app.models.attendance import AttendanceRecord, AttendanceSession, AttendanceStatus
from app.models.course_offering import CourseOffering, Enrollment, EnrollmentStatus
from app.models.user import Faculty, Student, User, UserRole
from app.schemas.attendance import AttendanceRecordInput, AttendanceSessionCreate
from app.services.exceptions import (
    BusinessRuleError,
    ConflictError,
    ForbiddenError,
    NotFoundError,
    commit_or_conflict,
)


def _authorize_offering_actor(
    db: Session,
    offering_id: int,
    actor: User,
) -> CourseOffering:
    offering = db.get(CourseOffering, offering_id)
    if offering is None:
        raise NotFoundError("Course offering not found.")
    if actor.role == UserRole.ADMIN:
        return offering
    if actor.role == UserRole.FACULTY and offering.faculty.user_id == actor.id:
        return offering
    raise ForbiddenError("You are not authorized for this course offering.")


def _validate_enrolled_students(
    db: Session,
    offering_id: int,
    records: list[AttendanceRecordInput],
) -> None:
    if not records:
        return
    student_ids = [r.student_id for r in records]
    if len(student_ids) != len(set(student_ids)):
        raise BusinessRuleError("Duplicate student_id in attendance records payload.")

    enrolled_ids = set(
        db.scalars(
            select(Enrollment.student_id).where(
                Enrollment.course_offering_id == offering_id,
                Enrollment.status == EnrollmentStatus.ENROLLED,
                Enrollment.student_id.in_(student_ids),
            )
        ).all()
    )
    missing = set(student_ids) - enrolled_ids
    if missing:
        raise BusinessRuleError(
            "All students must be actively enrolled in this course offering."
        )


def create_attendance_session(
    db: Session,
    payload: AttendanceSessionCreate,
    actor: User,
) -> AttendanceSession:
    """Create an attendance session and optional initial student marks."""
    offering = _authorize_offering_actor(db, payload.course_offering_id, actor)

    existing = db.scalar(
        select(AttendanceSession).where(
            AttendanceSession.course_offering_id == payload.course_offering_id,
            AttendanceSession.session_date == payload.session_date,
            AttendanceSession.session_number == payload.session_number,
        )
    )
    if existing is not None:
        raise ConflictError(
            "Attendance session already exists for this offering, date, and number."
        )

    _validate_enrolled_students(db, offering.id, payload.records)

    if actor.role == UserRole.FACULTY:
        faculty = db.scalar(select(Faculty).where(Faculty.user_id == actor.id))
        if faculty is None:
            raise NotFoundError("Faculty profile not found.")
        conductor_id = faculty.id
    else:
        conductor_id = offering.faculty_id

    session = AttendanceSession(
        course_offering_id=offering.id,
        conducted_by_faculty_id=conductor_id,
        session_date=payload.session_date,
        session_number=payload.session_number,
        start_time=payload.start_time,
        topic=payload.topic.strip() if payload.topic else None,
    )
    db.add(session)
    db.flush()

    for rec in payload.records:
        db.add(
            AttendanceRecord(
                session_id=session.id,
                student_id=rec.student_id,
                status=rec.status,
                remarks=rec.remarks.strip() if rec.remarks else None,
            )
        )

    commit_or_conflict(db, "Attendance session or record conflicts with existing data.")
    return get_attendance_session_by_id(db, session.id)


def get_attendance_session_by_id(
    db: Session,
    session_id: int,
) -> AttendanceSession:
    """Fetch an attendance session with its records."""
    att_session = db.scalar(
        select(AttendanceSession)
        .options(selectinload(AttendanceSession.records))
        .where(AttendanceSession.id == session_id)
    )
    if att_session is None:
        raise NotFoundError("Attendance session not found.")
    return att_session


def mark_attendance_records(
    db: Session,
    session_id: int,
    records: list[AttendanceRecordInput],
    actor: User,
) -> AttendanceSession:
    """Mark or update attendance records for a session."""
    att_session = get_attendance_session_by_id(db, session_id)
    _authorize_offering_actor(db, att_session.course_offering_id, actor)
    _validate_enrolled_students(db, att_session.course_offering_id, records)

    existing_by_student = {r.student_id: r for r in att_session.records}
    for item in records:
        if item.student_id in existing_by_student:
            existing = existing_by_student[item.student_id]
            existing.status = item.status
            existing.remarks = item.remarks.strip() if item.remarks else None
        else:
            db.add(
                AttendanceRecord(
                    session_id=att_session.id,
                    student_id=item.student_id,
                    status=item.status,
                    remarks=item.remarks.strip() if item.remarks else None,
                )
            )

    commit_or_conflict(db, "Failed to record attendance.")
    return get_attendance_session_by_id(db, att_session.id)


def list_offering_attendance_sessions(
    db: Session,
    offering_id: int,
    actor: User,
    *,
    page: int = 1,
    page_size: int = 20,
) -> tuple[list[AttendanceSession], int]:
    """List attendance sessions for a course offering."""
    _authorize_offering_actor(db, offering_id, actor)
    stmt = (
        select(AttendanceSession)
        .options(selectinload(AttendanceSession.records))
        .where(AttendanceSession.course_offering_id == offering_id)
    )
    count_stmt = select(func.count(AttendanceSession.id)).where(
        AttendanceSession.course_offering_id == offering_id
    )
    total = db.scalar(count_stmt) or 0
    items = list(
        db.scalars(
            stmt.order_by(
                AttendanceSession.session_date.desc(),
                AttendanceSession.session_number.desc(),
            )
            .offset((page - 1) * page_size)
            .limit(page_size)
        ).all()
    )
    return items, total


def get_student_attendance(
    db: Session,
    *,
    user_id: int,
    course_offering_id: int | None = None,
    page: int = 1,
    page_size: int = 50,
) -> dict[str, object]:
    """Return SQL-aggregated attendance summary and paginated records."""
    student = db.scalar(select(Student).where(Student.user_id == user_id))
    if student is None:
        raise NotFoundError("Student profile not found.")

    filters = [AttendanceRecord.student_id == student.id]
    if course_offering_id is not None:
        filters.append(AttendanceSession.course_offering_id == course_offering_id)

    agg_stmt = (
        select(
            func.count(AttendanceRecord.id),
            func.coalesce(
                func.sum(
                    case(
                        (AttendanceRecord.status == AttendanceStatus.PRESENT, 1),
                        else_=0,
                    )
                ),
                0,
            ),
            func.coalesce(
                func.sum(
                    case(
                        (AttendanceRecord.status == AttendanceStatus.ABSENT, 1), else_=0
                    )
                ),
                0,
            ),
            func.coalesce(
                func.sum(
                    case((AttendanceRecord.status == AttendanceStatus.LATE, 1), else_=0)
                ),
                0,
            ),
            func.coalesce(
                func.sum(
                    case(
                        (AttendanceRecord.status == AttendanceStatus.EXCUSED, 1),
                        else_=0,
                    )
                ),
                0,
            ),
        )
        .select_from(AttendanceRecord)
        .join(AttendanceRecord.session)
        .where(*filters)
    )
    total, present, absent, late, excused = db.execute(agg_stmt).one()
    attended = int(present) + int(late) + int(excused)
    percentage = round((attended / total) * 100, 2) if total > 0 else 0.0

    records_stmt = (
        select(AttendanceRecord)
        .join(AttendanceRecord.session)
        .where(*filters)
        .order_by(AttendanceRecord.marked_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    records = list(db.scalars(records_stmt).all())

    return {
        "total_sessions": int(total),
        "present": int(present),
        "absent": int(absent),
        "late": int(late),
        "excused": int(excused),
        "attendance_percentage": percentage,
        "records": records,
    }
