"""Authentication, registration, and authorization demonstration endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.rate_limit import get_login_rate_limiter
from app.database.connection import get_db
from app.dependencies.authentication import require_active_user
from app.dependencies.permissions import (
    require_roles,
    verify_faculty_offering_access,
    verify_student_self_or_admin,
)
from app.models.course_offering import CourseOffering
from app.models.user import Student, User, UserRole
from app.schemas.auth import (
    AdminCreateRequest,
    FacultyRegisterRequest,
    LoginRequest,
    LoginResponse,
    PublicRegisterRequest,
    RegisterResponse,
    StudentRegisterRequest,
)
from app.schemas.user import (
    FacultyProfileResponse,
    StudentProfileResponse,
    UserResponse,
)
from app.services.auth_service import (
    DepartmentNotFoundError,
    EmailAlreadyExistsError,
    InactiveUserError,
    InvalidCredentialsError,
    ProfileConflictError,
    authenticate_user,
    create_admin_user,
    register_faculty,
    register_student,
)

router = APIRouter(tags=["Authentication & Authorization"])


@router.post(
    "/auth/register/student",
    response_model=RegisterResponse,
    status_code=status.HTTP_201_CREATED,
)
def register_student_endpoint(
    payload: StudentRegisterRequest,
    db: Annotated[Session, Depends(get_db)],
) -> RegisterResponse:
    """Register a new student account and linked student profile."""
    try:
        user, student = register_student(db, payload)
    except (EmailAlreadyExistsError, ProfileConflictError) as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc
    except DepartmentNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc

    return RegisterResponse(
        user=UserResponse.model_validate(user),
        student_profile=StudentProfileResponse.model_validate(student),
    )


@router.post(
    "/auth/register/faculty",
    response_model=RegisterResponse,
    status_code=status.HTTP_201_CREATED,
)
def register_faculty_endpoint(
    payload: FacultyRegisterRequest,
    db: Annotated[Session, Depends(get_db)],
) -> RegisterResponse:
    """Register a new faculty account and linked faculty profile."""
    try:
        user, faculty = register_faculty(db, payload)
    except (EmailAlreadyExistsError, ProfileConflictError) as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc
    except DepartmentNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc

    return RegisterResponse(
        user=UserResponse.model_validate(user),
        faculty_profile=FacultyProfileResponse.model_validate(faculty),
    )


@router.post(
    "/auth/register",
    response_model=RegisterResponse,
    status_code=status.HTTP_201_CREATED,
)
def public_register_endpoint(
    payload: PublicRegisterRequest,
    db: Annotated[Session, Depends(get_db)],
) -> RegisterResponse:
    """Public registration endpoint; explicitly blocks ADMIN registration."""
    if payload.role == UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Public registration as ADMIN is not permitted.",
        )

    if payload.role == UserRole.STUDENT:
        if (
            payload.department_id is None
            or payload.roll_number is None
            or payload.admission_year is None
        ):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=(
                    "Student registration requires department_id, "
                    "roll_number, and admission_year."
                ),
            )
        student_payload = StudentRegisterRequest(
            email=payload.email,
            full_name=payload.full_name,
            password=payload.password,
            department_id=payload.department_id,
            roll_number=payload.roll_number,
            admission_year=payload.admission_year,
            current_semester_number=payload.current_semester_number,
            phone=payload.phone,
            date_of_birth=payload.date_of_birth,
        )
        return register_student_endpoint(student_payload, db)

    if (
        payload.department_id is None
        or payload.employee_id is None
        or payload.designation is None
    ):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=(
                "Faculty registration requires department_id, "
                "employee_id, and designation."
            ),
        )
    faculty_payload = FacultyRegisterRequest(
        email=payload.email,
        full_name=payload.full_name,
        password=payload.password,
        department_id=payload.department_id,
        employee_id=payload.employee_id,
        designation=payload.designation,
        phone=payload.phone,
        joining_date=payload.joining_date,
    )
    return register_faculty_endpoint(faculty_payload, db)


@router.post("/auth/login", response_model=LoginResponse)
def login_endpoint(
    request: Request,
    payload: LoginRequest,
    db: Annotated[Session, Depends(get_db)],
) -> LoginResponse:
    """Authenticate a user with email and password and issue a JWT."""
    settings = get_settings()
    limiter = get_login_rate_limiter(
        settings.LOGIN_RATE_LIMIT_MAX_ATTEMPTS,
        settings.LOGIN_RATE_LIMIT_WINDOW_SECONDS,
    )
    forwarded_for = request.headers.get("x-forwarded-for")
    client_ip = (
        forwarded_for.split(",")[0].strip()
        if forwarded_for
        else (request.client.host if request.client else "unknown")
    )
    rate_key = f"{client_ip}:{payload.email.strip().lower()}"
    allowed, retry_after = limiter.check_and_record(rate_key)
    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many login attempts. Please try again later.",
            headers={"Retry-After": str(retry_after)},
        )

    try:
        user, token = authenticate_user(db, payload.email, payload.password)
    except InvalidCredentialsError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc
    except InactiveUserError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is inactive.",
        ) from exc

    return LoginResponse(
        access_token=token,
        token_type="bearer",
        user=UserResponse.model_validate(user),
    )


@router.get("/auth/me", response_model=UserResponse)
def get_me_endpoint(
    current_user: Annotated[User, Depends(require_active_user)],
) -> UserResponse:
    """Return the currently authenticated user's profile."""
    return UserResponse.model_validate(current_user)


@router.post(
    "/admin/users/admin",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_admin_endpoint(
    payload: AdminCreateRequest,
    _admin: Annotated[User, Depends(require_roles(UserRole.ADMIN))],
    db: Annotated[Session, Depends(get_db)],
) -> UserResponse:
    """Protected endpoint allowing an existing ADMIN to create another ADMIN."""
    try:
        user = create_admin_user(db, payload)
    except EmailAlreadyExistsError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc
    return UserResponse.model_validate(user)


# --- Demonstration endpoints for RBAC & Resource Ownership ---


@router.get("/access/admin")
def admin_only_demo(
    current_user: Annotated[User, Depends(require_roles(UserRole.ADMIN))],
) -> dict[str, str]:
    """Demonstrate ADMIN-only endpoint protection."""
    return {"message": "Admin access granted", "role": current_user.role.value}


@router.get("/access/faculty")
def faculty_only_demo(
    current_user: Annotated[User, Depends(require_roles(UserRole.FACULTY))],
) -> dict[str, str]:
    """Demonstrate FACULTY-only endpoint protection."""
    return {"message": "Faculty access granted", "role": current_user.role.value}


@router.get("/access/student")
def student_only_demo(
    current_user: Annotated[User, Depends(require_roles(UserRole.STUDENT))],
) -> dict[str, str]:
    """Demonstrate STUDENT-only endpoint protection."""
    return {"message": "Student access granted", "role": current_user.role.value}


@router.get("/access/students/{student_id}", response_model=StudentProfileResponse)
def student_ownership_demo(
    student: Annotated[Student, Depends(verify_student_self_or_admin)],
) -> StudentProfileResponse:
    """Demonstrate student self-ownership or ADMIN access check."""
    return StudentProfileResponse.model_validate(student)


@router.get("/access/offerings/{course_offering_id}")
def faculty_offering_ownership_demo(
    offering: Annotated[CourseOffering, Depends(verify_faculty_offering_access)],
) -> dict[str, int | str]:
    """Demonstrate faculty assignment or ADMIN access check on a course offering."""
    return {
        "course_offering_id": offering.id,
        "course_id": offering.course_id,
        "section": offering.section,
    }
