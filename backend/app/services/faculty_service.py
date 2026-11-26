"""Administrative and self-service business logic for Faculty management."""

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, joinedload

from app.core.security import hash_password
from app.models.academic import Department
from app.models.user import Faculty, User, UserRole
from app.schemas.faculty import AdminFacultyCreate, AdminFacultyUpdate
from app.services.exceptions import ConflictError, NotFoundError, commit_or_conflict
from app.services.id_generator import generate_faculty_id


def _faculty_query():
    return select(Faculty).options(
        joinedload(Faculty.user),
        joinedload(Faculty.department),
    )


def _normalize_email(email: str) -> str:
    return email.strip().lower()


def _get_department_or_404(db: Session, department_id: int) -> Department:
    department = db.get(Department, department_id)
    if department is None:
        raise NotFoundError("Department not found.")
    return department


def create_faculty(db: Session, payload: AdminFacultyCreate) -> Faculty:
    """Create a Faculty user account and profile with an auto-generated Faculty ID."""
    normalized_email = _normalize_email(payload.email)
    if db.scalar(select(User).where(User.email == normalized_email)) is not None:
        raise ConflictError("Email is already registered.")

    department = _get_department_or_404(db, payload.department_id)
    employee_id = generate_faculty_id(db, department_code=department.code)

    user = User(
        email=normalized_email,
        full_name=payload.full_name.strip(),
        hashed_password=hash_password(payload.password),
        role=UserRole.FACULTY,
        is_active=payload.is_active,
    )
    faculty = Faculty(
        user=user,
        department_id=payload.department_id,
        employee_id=employee_id,
        designation=payload.designation.strip(),
        phone=payload.phone.strip() if payload.phone else None,
        joining_date=payload.joining_date,
    )
    db.add_all([user, faculty])
    commit_or_conflict(db, "Faculty conflicts with an existing record.")
    return get_faculty_by_id(db, faculty.id)


def get_faculty_by_id(db: Session, faculty_id: int) -> Faculty:
    """Fetch a faculty member by ID with eager-loaded user and department."""
    faculty = db.scalar(_faculty_query().where(Faculty.id == faculty_id))
    if faculty is None:
        raise NotFoundError("Faculty member not found.")
    return faculty


def get_faculty_by_user_id(db: Session, user_id: int) -> Faculty:
    """Fetch a faculty profile by linked user_id."""
    faculty = db.scalar(_faculty_query().where(Faculty.user_id == user_id))
    if faculty is None:
        raise NotFoundError("Faculty profile not found.")
    return faculty


def list_faculty(
    db: Session,
    *,
    search: str | None = None,
    department_id: int | None = None,
    is_active: bool | None = None,
    page: int = 1,
    page_size: int = 20,
) -> tuple[list[Faculty], int]:
    """List faculty members with search, filtering, and pagination."""
    stmt = _faculty_query().join(Faculty.user)
    count_stmt = select(func.count(Faculty.id)).join(Faculty.user)

    filters = []
    if search:
        pattern = f"%{search.strip()}%"
        filters.append(
            or_(
                User.full_name.ilike(pattern),
                User.email.ilike(pattern),
                Faculty.employee_id.ilike(pattern),
            )
        )
    if department_id is not None:
        filters.append(Faculty.department_id == department_id)
    if is_active is not None:
        filters.append(User.is_active == is_active)

    if filters:
        stmt = stmt.where(*filters)
        count_stmt = count_stmt.where(*filters)

    total = db.scalar(count_stmt) or 0
    items = list(
        db.scalars(
            stmt.order_by(Faculty.id.asc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        ).all()
    )
    return items, total


def update_faculty(
    db: Session,
    faculty_id: int,
    payload: AdminFacultyUpdate,
) -> Faculty:
    """Update a faculty member's user and profile attributes atomically."""
    faculty = get_faculty_by_id(db, faculty_id)
    user = faculty.user

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

    target_department = faculty.department
    if payload.department_id is not None:
        target_department = _get_department_or_404(db, payload.department_id)
        faculty.department_id = target_department.id

    if payload.recalculate_id:
        faculty.employee_id = generate_faculty_id(
            db,
            department_code=target_department.code,
        )
    elif payload.employee_id is not None:
        existing_emp = db.scalar(
            select(Faculty).where(
                Faculty.employee_id == payload.employee_id,
                Faculty.id != faculty.id,
            )
        )
        if existing_emp is not None:
            raise ConflictError("Faculty ID is already registered.")
        faculty.employee_id = payload.employee_id

    if payload.designation is not None:
        faculty.designation = payload.designation.strip()
    if payload.phone is not None:
        faculty.phone = payload.phone.strip() or None
    if payload.joining_date is not None:
        faculty.joining_date = payload.joining_date

    commit_or_conflict(db, "Faculty update conflicts with an existing record.")
    return get_faculty_by_id(db, faculty.id)


def set_faculty_active_status(
    db: Session,
    faculty_id: int,
    is_active: bool,
) -> Faculty:
    """Activate or deactivate a faculty member's user account."""
    faculty = get_faculty_by_id(db, faculty_id)
    faculty.user.is_active = is_active
    db.commit()
    return get_faculty_by_id(db, faculty.id)
