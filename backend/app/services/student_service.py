"""Administrative and self-service business logic for Student management."""

from datetime import UTC, datetime

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, joinedload

from app.core.security import hash_password
from app.models.academic import Department
from app.models.semester_promotion import SemesterPromotionLog
from app.models.user import Student, User, UserRole
from app.schemas.student import (
    AdminStudentCreate,
    AdminStudentUpdate,
    PromotionBreakdownItem,
)
from app.services.exceptions import (
    BusinessRuleError,
    ConflictError,
    NotFoundError,
    commit_or_conflict,
)
from app.services.id_generator import generate_student_id
from app.services.semester_calculator import (
    PROGRAMME_MAX_SEMESTERS,
    calculate_student_semester,
    get_current_academic_year_start,
)


def _attach_calculated_semester(db: Session, students: list[Student]) -> None:
    """Attach stored semester status and active academic year without overwriting."""
    if not students:
        return
    start_year = get_current_academic_year_start(db)
    active_year = f"{start_year}-{start_year + 1}"
    for student in students:
        sem = student.current_semester_number
        student.calculated_semester = sem
        student.is_completed = sem > PROGRAMME_MAX_SEMESTERS
        student.semester_status = (
            "Completed" if sem > PROGRAMME_MAX_SEMESTERS else "In Progress"
        )
        student.active_academic_year = active_year


def _student_query():
    return select(Student).options(
        joinedload(Student.user),
        joinedload(Student.department),
    )


def _normalize_email(email: str) -> str:
    return email.strip().lower()


def _get_department_or_404(db: Session, department_id: int) -> Department:
    department = db.get(Department, department_id)
    if department is None:
        raise NotFoundError("Department not found.")
    return department


def create_student(db: Session, payload: AdminStudentCreate) -> Student:
    """Create a Student user account and profile with an auto-generated Student ID."""
    normalized_email = _normalize_email(payload.email)
    if db.scalar(select(User).where(User.email == normalized_email)) is not None:
        raise ConflictError("Email is already registered.")

    department = _get_department_or_404(db, payload.department_id)
    calc = calculate_student_semester(db, admission_year=payload.admission_year)
    roll_number = generate_student_id(
        db,
        department_code=department.code,
        admission_year=payload.admission_year,
    )

    user = User(
        email=normalized_email,
        full_name=payload.full_name.strip(),
        hashed_password=hash_password(payload.password),
        role=UserRole.STUDENT,
        is_active=payload.is_active,
    )
    student = Student(
        user=user,
        department_id=payload.department_id,
        roll_number=roll_number,
        admission_year=payload.admission_year,
        current_semester_number=calc.calculated_semester or 1,
        phone=payload.phone.strip() if payload.phone else None,
        date_of_birth=payload.date_of_birth,
    )
    db.add_all([user, student])
    commit_or_conflict(db, "Student conflicts with an existing record.")
    return get_student_by_id(db, student.id)


def get_student_by_id(db: Session, student_id: int) -> Student:
    """Fetch a student by ID with eager-loaded user and department."""
    student = db.scalar(_student_query().where(Student.id == student_id))
    if student is None:
        raise NotFoundError("Student not found.")
    _attach_calculated_semester(db, [student])
    return student


def get_student_by_user_id(db: Session, user_id: int) -> Student:
    """Fetch a student profile by linked user_id."""
    student = db.scalar(_student_query().where(Student.user_id == user_id))
    if student is None:
        raise NotFoundError("Student profile not found.")
    _attach_calculated_semester(db, [student])
    return student


def list_students(
    db: Session,
    *,
    search: str | None = None,
    department_id: int | None = None,
    semester_number: int | None = None,
    is_active: bool | None = None,
    is_archived: bool = False,
    page: int = 1,
    page_size: int = 20,
) -> tuple[list[Student], int]:
    """List students with search, filtering, and pagination."""
    stmt = _student_query().join(Student.user)
    count_stmt = select(func.count(Student.id)).join(Student.user)

    filters = [Student.is_archived == is_archived]
    if search:
        pattern = f"%{search.strip()}%"
        filters.append(
            or_(
                User.full_name.ilike(pattern),
                User.email.ilike(pattern),
                Student.roll_number.ilike(pattern),
            )
        )
    if department_id is not None:
        filters.append(Student.department_id == department_id)
    if semester_number is not None:
        filters.append(Student.current_semester_number == semester_number)
    if is_active is not None:
        filters.append(User.is_active == is_active)

    if filters:
        stmt = stmt.where(*filters)
        count_stmt = count_stmt.where(*filters)

    total = db.scalar(count_stmt) or 0
    items = list(
        db.scalars(
            stmt.order_by(Student.id.asc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        ).all()
    )
    _attach_calculated_semester(db, items)
    return items, total


def update_student(
    db: Session,
    student_id: int,
    payload: AdminStudentUpdate,
) -> Student:
    """Update a student's user and profile attributes atomically."""
    student = get_student_by_id(db, student_id)
    user = student.user

    if payload.email is not None:
        normalized_email = _normalize_email(payload.email)
        existing = db.scalar(
            select(User).where(User.email == normalized_email, User.id != user.id)
        )
        if existing is not None:
            raise ConflictError("Email is already registered.")
        user.email = normalized_email

    if payload.full_name is not None:
        user.full_name = payload.full_name.strip()
    if payload.is_active is not None:
        user.is_active = payload.is_active

    target_department = student.department
    if payload.department_id is not None:
        target_department = _get_department_or_404(db, payload.department_id)
        student.department_id = target_department.id

    if (
        payload.admission_year is not None
        and payload.admission_year != student.admission_year
    ):
        student.admission_year = payload.admission_year
        calc = calculate_student_semester(db, admission_year=student.admission_year)
        student.current_semester_number = calc.calculated_semester or 1

    if payload.recalculate_id:
        student.roll_number = generate_student_id(
            db,
            department_code=target_department.code,
            admission_year=student.admission_year,
        )
    elif payload.roll_number is not None:
        existing_roll = db.scalar(
            select(Student).where(
                Student.roll_number == payload.roll_number,
                Student.id != student.id,
            )
        )
        if existing_roll is not None:
            raise ConflictError("Student ID is already registered.")
        student.roll_number = payload.roll_number

    if payload.phone is not None:
        student.phone = payload.phone.strip() or None
    if payload.date_of_birth is not None:
        student.date_of_birth = payload.date_of_birth

    commit_or_conflict(db, "Student update conflicts with an existing record.")
    return get_student_by_id(db, student.id)


def set_student_active_status(
    db: Session,
    student_id: int,
    is_active: bool,
) -> Student:
    """Activate or deactivate a student's user account."""
    student = get_student_by_id(db, student_id)
    if is_active and student.is_archived:
        raise ConflictError(
            "Archived student cannot be activated directly; restore first."
        )
    student.user.is_active = is_active
    db.commit()
    return get_student_by_id(db, student.id)


def archive_student(
    db: Session,
    student_id: int,
    actor_user_id: int,
) -> Student:
    """Soft-delete/archive a student, disabling login while retaining records."""
    student = db.scalar(
        select(Student).where(Student.id == student_id).with_for_update()
    )
    if student is None:
        raise NotFoundError("Student not found.")
    if student.is_archived:
        raise ConflictError("Student is already archived.")

    student.is_archived = True
    student.archived_at = datetime.now(UTC)
    student.archived_by_user_id = actor_user_id
    student.user.is_active = False
    db.commit()
    return get_student_by_id(db, student.id)


def restore_student(db: Session, student_id: int) -> Student:
    """Unarchive a student profile while keeping login disabled until activated."""
    student = db.scalar(
        select(Student).where(Student.id == student_id).with_for_update()
    )
    if student is None:
        raise NotFoundError("Student not found.")
    if not student.is_archived:
        raise ConflictError("Student is not archived.")

    student.is_archived = False
    student.archived_at = None
    student.archived_by_user_id = None
    db.commit()
    return get_student_by_id(db, student.id)


def _eligible_odd_semester_students(
    db: Session,
    *,
    academic_year: str,
) -> tuple[list[Student], int, int]:
    """Return eligible active odd-semester students and skipped/logged counts."""
    already_promoted_ids = select(SemesterPromotionLog.student_id).where(
        SemesterPromotionLog.academic_year == academic_year
    )
    already_promoted_count = (
        db.scalar(
            select(func.count(SemesterPromotionLog.id)).where(
                SemesterPromotionLog.academic_year == academic_year
            )
        )
        or 0
    )

    eligible = list(
        db.scalars(
            select(Student)
            .join(Student.user)
            .where(
                Student.is_archived.is_(False),
                User.is_active.is_(True),
                Student.current_semester_number.in_([1, 3, 5, 7]),
                Student.id.not_in(already_promoted_ids),
            )
            .order_by(Student.current_semester_number.asc(), Student.id.asc())
        ).all()
    )

    inactive_skipped = (
        db.scalar(
            select(func.count(Student.id))
            .join(Student.user)
            .where(
                Student.is_archived.is_(False),
                User.is_active.is_(False),
                Student.current_semester_number.in_([1, 3, 5, 7]),
            )
        )
        or 0
    )
    return eligible, inactive_skipped, already_promoted_count


def get_semester_promotion_preview(db: Session) -> dict[str, object]:
    """Build a preview of eligible active odd-semester students for promotion."""
    start_year = get_current_academic_year_start(db)
    academic_year = f"{start_year}-{start_year + 1}"
    eligible, inactive_skipped, already_promoted = _eligible_odd_semester_students(
        db,
        academic_year=academic_year,
    )
    counts_by_sem: dict[int, int] = {}
    for stu in eligible:
        counts_by_sem[stu.current_semester_number] = (
            counts_by_sem.get(stu.current_semester_number, 0) + 1
        )
    breakdown = [
        PromotionBreakdownItem(
            old_semester=sem,
            new_semester=sem + 1,
            count=count,
        )
        for sem, count in sorted(counts_by_sem.items())
    ]
    return {
        "academic_year": academic_year,
        "eligible_count": len(eligible),
        "inactive_skipped_count": inactive_skipped,
        "already_promoted_count": already_promoted,
        "can_promote": len(eligible) > 0,
        "breakdown": breakdown,
    }


def promote_students_to_next_semester(
    db: Session,
    *,
    actor: User,
) -> tuple[str, int]:
    """Promote eligible active odd-semester students to the next even semester."""
    start_year = get_current_academic_year_start(db)
    academic_year = f"{start_year}-{start_year + 1}"
    eligible, _inactive_skipped, already_promoted = _eligible_odd_semester_students(
        db,
        academic_year=academic_year,
    )
    if not eligible:
        if already_promoted > 0:
            raise ConflictError(
                f"Semester promotion for {academic_year} has already been performed."
            )
        raise BusinessRuleError(
            "No eligible active students in odd semesters to promote."
        )

    for stu in eligible:
        old_sem = stu.current_semester_number
        new_sem = old_sem + 1
        stu.current_semester_number = new_sem
        db.add(
            SemesterPromotionLog(
                academic_year=academic_year,
                student_id=stu.id,
                old_semester=old_sem,
                new_semester=new_sem,
                promoted_by_user_id=actor.id,
            )
        )

    commit_or_conflict(
        db,
        f"Semester promotion for {academic_year} conflicts with an existing promotion.",
    )
    return academic_year, len(eligible)


def get_admin_dashboard_summary(db: Session) -> dict[str, int | float]:
    """Return institutional summary counts for the Admin dashboard."""
    from app.models.academic import Course, Department
    from app.models.assignment import Assignment, Submission
    from app.models.attendance import (
        AttendanceRecord,
        AttendanceSession,
        AttendanceStatus,
    )
    from app.models.course_offering import CourseOffering, Enrollment, EnrollmentStatus
    from app.models.user import Faculty

    total_students = (
        db.scalar(select(func.count(Student.id)).where(Student.is_archived.is_(False)))
        or 0
    )
    active_students = (
        db.scalar(
            select(func.count(Student.id))
            .join(Student.user)
            .where(Student.is_archived.is_(False), User.is_active.is_(True))
        )
        or 0
    )
    total_faculty = db.scalar(select(func.count(Faculty.id))) or 0
    total_departments = (
        db.scalar(
            select(func.count(Department.id)).where(Department.is_active.is_(True))
        )
        or 0
    )
    active_courses = db.scalar(select(func.count(Course.id))) or 0
    active_offerings = (
        db.scalar(
            select(func.count(CourseOffering.id)).where(
                CourseOffering.is_active.is_(True)
            )
        )
        or 0
    )
    total_enrollments = (
        db.scalar(
            select(func.count(Enrollment.id)).where(
                Enrollment.status == EnrollmentStatus.ENROLLED
            )
        )
        or 0
    )
    total_attendance_sessions = db.scalar(select(func.count(AttendanceSession.id))) or 0
    total_attendance_records = db.scalar(select(func.count(AttendanceRecord.id))) or 0
    attended_records = (
        db.scalar(
            select(func.count(AttendanceRecord.id)).where(
                AttendanceRecord.status.in_(
                    [
                        AttendanceStatus.PRESENT,
                        AttendanceStatus.LATE,
                        AttendanceStatus.EXCUSED,
                    ]
                )
            )
        )
        or 0
    )
    attendance_rate = (
        round((attended_records / total_attendance_records) * 100, 1)
        if total_attendance_records > 0
        else 0.0
    )
    total_assignments = db.scalar(select(func.count(Assignment.id))) or 0
    pending_submissions = (
        db.scalar(select(func.count(Submission.id)).where(Submission.score.is_(None)))
        or 0
    )

    return {
        "total_students": int(total_students),
        "active_students": int(active_students),
        "total_faculty": int(total_faculty),
        "total_departments": int(total_departments),
        "active_courses": int(active_courses),
        "active_offerings": int(active_offerings),
        "total_enrollments": int(total_enrollments),
        "total_attendance_sessions": int(total_attendance_sessions),
        "total_attendance_records": int(total_attendance_records),
        "attendance_rate_percentage": attendance_rate,
        "pending_submissions": int(pending_submissions),
        "total_assignments": int(total_assignments),
    }
