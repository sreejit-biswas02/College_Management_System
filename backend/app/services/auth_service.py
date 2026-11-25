"""Authentication, registration, and user lookup business logic."""

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.security import create_access_token, hash_password, verify_password
from app.models.academic import Department
from app.models.user import Faculty, Student, User, UserRole
from app.schemas.auth import (
    AdminCreateRequest,
    FacultyRegisterRequest,
    StudentRegisterRequest,
)


class EmailAlreadyExistsError(Exception):
    """Raised when an email is already registered."""


class ProfileConflictError(Exception):
    """Raised when a roll number or employee ID is already registered."""


class DepartmentNotFoundError(Exception):
    """Raised when the referenced department does not exist."""


class InvalidCredentialsError(Exception):
    """Raised when email or password verification fails."""


class InactiveUserError(Exception):
    """Raised when an inactive user attempts to authenticate."""


def _normalize_email(email: str) -> str:
    return email.strip().lower()


def get_user_by_email(db: Session, email: str) -> User | None:
    """Fetch a user by normalized email address."""
    stmt = select(User).where(User.email == _normalize_email(email))
    return db.scalar(stmt)


def get_user_by_id(db: Session, user_id: int) -> User | None:
    """Fetch a user by primary key."""
    return db.get(User, user_id)


def _ensure_department_exists(db: Session, department_id: int) -> None:
    if db.get(Department, department_id) is None:
        raise DepartmentNotFoundError("Referenced department does not exist.")


def _ensure_email_available(db: Session, email: str) -> str:
    normalized = _normalize_email(email)
    if get_user_by_email(db, normalized) is not None:
        raise EmailAlreadyExistsError("Email is already registered.")
    return normalized


def register_student(
    db: Session,
    payload: StudentRegisterRequest,
) -> tuple[User, Student]:
    """Register a new student user and associated student profile atomically."""
    normalized_email = _ensure_email_available(db, payload.email)
    _ensure_department_exists(db, payload.department_id)

    roll_number = payload.roll_number.strip()
    existing_roll = db.scalar(select(Student).where(Student.roll_number == roll_number))
    if existing_roll is not None:
        raise ProfileConflictError("Roll number is already registered.")

    user = User(
        email=normalized_email,
        full_name=payload.full_name.strip(),
        hashed_password=hash_password(payload.password),
        role=UserRole.STUDENT,
    )
    student = Student(
        user=user,
        department_id=payload.department_id,
        roll_number=roll_number,
        admission_year=payload.admission_year,
        current_semester_number=payload.current_semester_number,
        phone=payload.phone.strip() if payload.phone else None,
        date_of_birth=payload.date_of_birth,
    )
    db.add_all([user, student])
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise ProfileConflictError(
            "Unable to complete registration due to a conflicting record."
        ) from exc

    db.refresh(user)
    db.refresh(student)
    return user, student


def register_faculty(
    db: Session,
    payload: FacultyRegisterRequest,
) -> tuple[User, Faculty]:
    """Register a new faculty user and associated faculty profile atomically."""
    normalized_email = _ensure_email_available(db, payload.email)
    _ensure_department_exists(db, payload.department_id)

    employee_id = payload.employee_id.strip()
    existing_emp = db.scalar(select(Faculty).where(Faculty.employee_id == employee_id))
    if existing_emp is not None:
        raise ProfileConflictError("Employee ID is already registered.")

    user = User(
        email=normalized_email,
        full_name=payload.full_name.strip(),
        hashed_password=hash_password(payload.password),
        role=UserRole.FACULTY,
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
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise ProfileConflictError(
            "Unable to complete registration due to a conflicting record."
        ) from exc

    db.refresh(user)
    db.refresh(faculty)
    return user, faculty


def create_admin_user(db: Session, payload: AdminCreateRequest) -> User:
    """Create an administrator account through a controlled workflow."""
    normalized_email = _ensure_email_available(db, payload.email)
    user = User(
        email=normalized_email,
        full_name=payload.full_name.strip(),
        hashed_password=hash_password(payload.password),
        role=UserRole.ADMIN,
    )
    db.add(user)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise EmailAlreadyExistsError("Email is already registered.") from exc
    db.refresh(user)
    return user


def authenticate_user(db: Session, email: str, password: str) -> tuple[User, str]:
    """Authenticate a user by email and password, returning user and JWT."""
    user = get_user_by_email(db, email)
    if user is None or not verify_password(password, user.hashed_password):
        raise InvalidCredentialsError("Invalid email or password.")
    if not user.is_active:
        raise InactiveUserError("User account is inactive.")
    token = create_access_token(subject=str(user.id), role=user.role.value)
    return user, token
