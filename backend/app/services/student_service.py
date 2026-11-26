"""Administrative and self-service business logic for Student management."""

from datetime import UTC, datetime

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, joinedload

from app.core.security import hash_password
from app.models.academic import Department
from app.models.user import Student, User, UserRole
from app.schemas.student import AdminStudentCreate, AdminStudentUpdate
from app.services.exceptions import (
    BusinessRuleError,
    ConflictError,
    NotFoundError,
    commit_or_conflict,
)
from app.services.id_generator import generate_student_id
from app.services.semester_calculator import resolve_student_semester_safe


def _attach_calculated_semester(db: Session, students: list[Student]) -> None:
    """Attach live calculated semester metadata from the active academic calendar."""
    for student in students:
        calc = resolve_student_semester_safe(
            db,
            admission_year=student.admission_year,
        )
        student.calculated_semester = calc.calculated_semester
        student.semester_status = calc.semester_status
        student.is_completed = calc.is_completed
        student.active_academic_year = calc.active_academic_year
        if calc.calculated_semester is not None:
            student.current_semester_number = calc.calculated_semester


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
    calc = resolve_student_semester_safe(db, admission_year=payload.admission_year)
    if calc.semester_status == "Invalid Admission Year":
        raise BusinessRuleError(
            "Admission academic year cannot be later than the active academic year."
        )
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
        current_semester_number=(
            calc.calculated_semester
            if calc.calculated_semester is not None
            else payload.current_semester_number
        ),
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

    if payload.admission_year is not None:
        student.admission_year = payload.admission_year

    calc = resolve_student_semester_safe(db, admission_year=student.admission_year)
    if calc.semester_status == "Invalid Admission Year":
        raise BusinessRuleError(
            "Admission academic year cannot be later than the active academic year."
        )
    if calc.calculated_semester is not None:
        student.current_semester_number = calc.calculated_semester
    elif payload.current_semester_number is not None:
        student.current_semester_number = payload.current_semester_number

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
