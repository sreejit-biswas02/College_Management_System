"""Automated tests for authentication, JWT, RBAC, and resource ownership."""

from collections.abc import Generator
from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.security import create_access_token
from app.database.connection import engine, get_db
from app.main import app
from app.models import (
    Course,
    CourseOffering,
    Department,
    Faculty,
    Semester,
    Student,
    User,
)
from app.schemas.auth import AdminCreateRequest
from app.services.auth_service import create_admin_user

STRONG_PASSWORD = "Password123!"


@pytest.fixture()
def db_session() -> Generator[Session, None, None]:
    """Provide an isolated PostgreSQL session using SAVEPOINTs."""
    connection = engine.connect()
    transaction = connection.begin()
    session = Session(bind=connection, join_transaction_mode="create_savepoint")
    try:
        yield session
    finally:
        session.close()
        transaction.rollback()
        connection.close()


@pytest.fixture()
def client(db_session: Session) -> Generator[TestClient, None, None]:
    """FastAPI TestClient with get_db overridden to the isolated test session."""

    def override_get_db() -> Generator[Session, None, None]:
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.clear()


@pytest.fixture()
def department(db_session: Session) -> Department:
    """Create a test department."""
    dept = Department(code="AUTH-CSE", name="Auth Test CSE")
    db_session.add(dept)
    db_session.commit()
    db_session.refresh(dept)
    return dept


def _register_student(
    client: TestClient,
    dept_id: int,
    email: str = "stu1@example.edu",
    roll: str = "ROLL-101",
) -> dict[str, object]:
    resp = client.post(
        "/api/v1/auth/register/student",
        json={
            "email": email,
            "full_name": "Alice Student",
            "password": STRONG_PASSWORD,
            "department_id": dept_id,
            "roll_number": roll,
            "admission_year": 2026,
            "current_semester_number": 1,
        },
    )
    assert resp.status_code == 201
    return resp.json()


def _register_faculty(
    client: TestClient,
    dept_id: int,
    email: str = "fac1@example.edu",
    emp_id: str = "EMP-101",
) -> dict[str, object]:
    resp = client.post(
        "/api/v1/auth/register/faculty",
        json={
            "email": email,
            "full_name": "Dr. Bob Faculty",
            "password": STRONG_PASSWORD,
            "department_id": dept_id,
            "employee_id": emp_id,
            "designation": "Associate Professor",
        },
    )
    assert resp.status_code == 201
    return resp.json()


def _login(client: TestClient, email: str, password: str = STRONG_PASSWORD) -> str:
    resp = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
    )
    assert resp.status_code == 200
    return resp.json()["access_token"]


def test_student_registration_success(
    client: TestClient,
    department: Department,
) -> None:
    """1. Successful student registration creates user + profile without hash."""
    data = _register_student(client, department.id)
    assert data["user"]["email"] == "stu1@example.edu"
    assert data["user"]["role"] == "student"
    assert "hashed_password" not in data["user"]
    assert data["student_profile"]["roll_number"] == "ROLL-101"


def test_faculty_registration_success(
    client: TestClient,
    department: Department,
) -> None:
    """2. Successful faculty registration creates user + profile without hash."""
    data = _register_faculty(client, department.id)
    assert data["user"]["email"] == "fac1@example.edu"
    assert data["user"]["role"] == "faculty"
    assert "hashed_password" not in data["user"]
    assert data["faculty_profile"]["employee_id"] == "EMP-101"


def test_duplicate_email_rejected(
    client: TestClient,
    department: Department,
) -> None:
    """3. Duplicate email registration is rejected with 409 Conflict."""
    _register_student(client, department.id, email="dup@example.edu", roll="R-1")
    resp = client.post(
        "/api/v1/auth/register/student",
        json={
            "email": "DUP@example.edu",
            "full_name": "Duplicate User",
            "password": STRONG_PASSWORD,
            "department_id": department.id,
            "roll_number": "R-2",
            "admission_year": 2026,
        },
    )
    assert resp.status_code == 409


def test_public_admin_registration_rejected(
    client: TestClient,
    department: Department,
) -> None:
    """4. Public registration as ADMIN is rejected with 403 Forbidden."""
    resp = client.post(
        "/api/v1/auth/register",
        json={
            "email": "hacker@example.edu",
            "full_name": "Not An Admin",
            "password": STRONG_PASSWORD,
            "role": "admin",
            "department_id": department.id,
        },
    )
    assert resp.status_code == 403


def test_login_success(client: TestClient, department: Department) -> None:
    """5. Valid credentials return JWT access token and safe user info."""
    _register_student(client, department.id)
    resp = client.post(
        "/api/v1/auth/login",
        json={"email": "stu1@example.edu", "password": STRONG_PASSWORD},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["token_type"] == "bearer"
    assert isinstance(body["access_token"], str) and len(body["access_token"]) > 10
    assert body["user"]["email"] == "stu1@example.edu"
    assert "hashed_password" not in body["user"]


def test_login_incorrect_password_rejected(
    client: TestClient,
    department: Department,
) -> None:
    """6. Incorrect password returns 401 with generic error message."""
    _register_student(client, department.id)
    resp = client.post(
        "/api/v1/auth/login",
        json={"email": "stu1@example.edu", "password": "WrongPassword1!"},
    )
    assert resp.status_code == 401
    assert resp.json()["detail"] == "Invalid email or password."


def test_inactive_user_login_rejected(
    client: TestClient,
    db_session: Session,
    department: Department,
) -> None:
    """7. Inactive user account is rejected with 403 on login."""
    data = _register_student(client, department.id)
    user = db_session.get(User, data["user"]["id"])
    assert user is not None
    user.is_active = False
    db_session.commit()

    resp = client.post(
        "/api/v1/auth/login",
        json={"email": "stu1@example.edu", "password": STRONG_PASSWORD},
    )
    assert resp.status_code == 403


def test_valid_jwt_authentication(
    client: TestClient,
    department: Department,
) -> None:
    """8. Valid Bearer JWT authenticates /api/v1/auth/me."""
    _register_student(client, department.id)
    token = _login(client, "stu1@example.edu")
    resp = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["email"] == "stu1@example.edu"


def test_invalid_jwt_rejected(client: TestClient) -> None:
    """9. Malformed or invalid JWT returns 401 Unauthorized."""
    resp = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": "Bearer not.a.valid.jwt"},
    )
    assert resp.status_code == 401


def test_expired_jwt_rejected(
    client: TestClient,
    department: Department,
) -> None:
    """10. Expired JWT returns 401 Unauthorized."""
    data = _register_student(client, department.id)
    expired_token = create_access_token(
        subject=str(data["user"]["id"]),
        role="student",
        expires_delta=timedelta(minutes=-5),
    )
    resp = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {expired_token}"},
    )
    assert resp.status_code == 401


def test_unauthorized_access_rejected(client: TestClient) -> None:
    """11. Missing Authorization header returns 401 Unauthorized."""
    resp = client.get("/api/v1/auth/me")
    assert resp.status_code == 401


def test_admin_only_endpoint_access(
    client: TestClient,
    db_session: Session,
    department: Department,
) -> None:
    """12. Admin-only endpoint allows ADMIN and rejects STUDENT with 403."""
    create_admin_user(
        db_session,
        AdminCreateRequest(
            email="admin@example.edu",
            full_name="System Admin",
            password=STRONG_PASSWORD,
        ),
    )
    _register_student(client, department.id)

    admin_token = _login(client, "admin@example.edu")
    student_token = _login(client, "stu1@example.edu")

    assert (
        client.get(
            "/api/v1/access/admin",
            headers={"Authorization": f"Bearer {admin_token}"},
        ).status_code
        == 200
    )
    assert (
        client.get(
            "/api/v1/access/admin",
            headers={"Authorization": f"Bearer {student_token}"},
        ).status_code
        == 403
    )


def test_faculty_only_endpoint_access(
    client: TestClient,
    department: Department,
) -> None:
    """13. Faculty-only endpoint allows FACULTY and rejects STUDENT with 403."""
    _register_faculty(client, department.id)
    _register_student(client, department.id)

    faculty_token = _login(client, "fac1@example.edu")
    student_token = _login(client, "stu1@example.edu")

    assert (
        client.get(
            "/api/v1/access/faculty",
            headers={"Authorization": f"Bearer {faculty_token}"},
        ).status_code
        == 200
    )
    assert (
        client.get(
            "/api/v1/access/faculty",
            headers={"Authorization": f"Bearer {student_token}"},
        ).status_code
        == 403
    )


def test_student_only_endpoint_access(
    client: TestClient,
    department: Department,
) -> None:
    """14. Student-only endpoint allows STUDENT and rejects FACULTY with 403."""
    _register_faculty(client, department.id)
    _register_student(client, department.id)

    student_token = _login(client, "stu1@example.edu")
    faculty_token = _login(client, "fac1@example.edu")

    assert (
        client.get(
            "/api/v1/access/student",
            headers={"Authorization": f"Bearer {student_token}"},
        ).status_code
        == 200
    )
    assert (
        client.get(
            "/api/v1/access/student",
            headers={"Authorization": f"Bearer {faculty_token}"},
        ).status_code
        == 403
    )


def test_resource_ownership_restrictions(
    client: TestClient,
    db_session: Session,
    department: Department,
) -> None:
    """15. Students and faculty cannot access resources they do not own/teach."""
    stu1_data = _register_student(
        client,
        department.id,
        email="s1@example.edu",
        roll="R-10",
    )
    stu2_data = _register_student(
        client,
        department.id,
        email="s2@example.edu",
        roll="R-20",
    )
    fac1_data = _register_faculty(
        client,
        department.id,
        email="f1@example.edu",
        emp_id="E-10",
    )
    _register_faculty(
        client,
        department.id,
        email="f2@example.edu",
        emp_id="E-20",
    )

    stu1_token = _login(client, "s1@example.edu")
    fac1_token = _login(client, "f1@example.edu")
    fac2_token = _login(client, "f2@example.edu")

    stu1_id = stu1_data["student_profile"]["id"]
    stu2_id = stu2_data["student_profile"]["id"]

    # Student 1 can read own profile, but gets 403 on Student 2's profile.
    assert (
        client.get(
            f"/api/v1/access/students/{stu1_id}",
            headers={"Authorization": f"Bearer {stu1_token}"},
        ).status_code
        == 200
    )
    assert (
        client.get(
            f"/api/v1/access/students/{stu2_id}",
            headers={"Authorization": f"Bearer {stu1_token}"},
        ).status_code
        == 403
    )

    # Create a course offering assigned to Faculty 1.
    fac1 = db_session.get(Faculty, fac1_data["faculty_profile"]["id"])
    assert fac1 is not None
    semester = Semester(
        name="Fall 2026",
        academic_year="2026-2027",
        term_number=1,
        start_date=date(2026, 8, 1),
        end_date=date(2026, 12, 15),
    )
    course = Course(
        department_id=department.id,
        code="AUTH-CS101",
        title="Auth Test Course",
        credits=3,
    )
    db_session.add_all([semester, course])
    db_session.flush()
    offering = CourseOffering(
        course_id=course.id,
        semester_id=semester.id,
        faculty_id=fac1.id,
        section="A",
    )
    db_session.add(offering)
    db_session.commit()
    db_session.refresh(offering)

    # Assigned faculty gets 200; unassigned faculty gets 403.
    assert (
        client.get(
            f"/api/v1/access/offerings/{offering.id}",
            headers={"Authorization": f"Bearer {fac1_token}"},
        ).status_code
        == 200
    )
    assert (
        client.get(
            f"/api/v1/access/offerings/{offering.id}",
            headers={"Authorization": f"Bearer {fac2_token}"},
        ).status_code
        == 403
    )

    # Verify Student model relationship integrity still holds.
    assert db_session.get(Student, stu1_id) is not None


def test_public_registration_blocked_in_production_and_admin_creation_works(
    client: TestClient,
    db_session: Session,
    department: Department,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Block public registration in production while preserving Admin creation."""
    from app.core.config import get_settings

    prod_settings = get_settings().model_copy(update={"ENVIRONMENT": "production"})
    monkeypatch.setattr("app.routers.auth.get_settings", lambda: prod_settings)

    assert (
        client.post(
            "/api/v1/auth/register/student",
            json={
                "email": "prod.stu@example.edu",
                "full_name": "Prod Student",
                "password": STRONG_PASSWORD,
                "department_id": department.id,
                "roll_number": "MANUAL-01",
                "admission_year": 2026,
            },
        ).status_code
        == 403
    )
    assert (
        client.post(
            "/api/v1/auth/register/faculty",
            json={
                "email": "prod.fac@example.edu",
                "full_name": "Prod Faculty",
                "password": STRONG_PASSWORD,
                "department_id": department.id,
                "employee_id": "MANUAL-F1",
                "designation": "Lecturer",
            },
        ).status_code
        == 403
    )
    for role in ("student", "faculty", "admin"):
        assert (
            client.post(
                "/api/v1/auth/register",
                json={
                    "email": f"prod.{role}@example.edu",
                    "full_name": f"Prod {role}",
                    "password": STRONG_PASSWORD,
                    "role": role,
                    "department_id": department.id,
                    "roll_number": "MANUAL-X",
                    "admission_year": 2026,
                    "employee_id": "MANUAL-FX",
                    "designation": "Lecturer",
                },
            ).status_code
            == 403
        )

    # Admin-managed student & faculty creation still works with auto ID & semester
    create_admin_user(
        db_session,
        AdminCreateRequest(
            email="prod.admin@example.edu",
            full_name="Prod Admin",
            password=STRONG_PASSWORD,
        ),
    )
    login_resp = client.post(
        "/api/v1/auth/login",
        json={"email": "prod.admin@example.edu", "password": STRONG_PASSWORD},
    )
    assert login_resp.status_code == 200
    admin_headers = {"Authorization": f"Bearer {login_resp.json()['access_token']}"}

    stu_resp = client.post(
        "/api/v1/admin/students",
        headers=admin_headers,
        json={
            "email": "managed.stu@example.edu",
            "full_name": "Managed Student",
            "password": STRONG_PASSWORD,
            "department_id": department.id,
            "admission_year": 2026,
        },
    )
    assert stu_resp.status_code == 201
    stu_data = stu_resp.json()
    assert stu_data["roll_number"].startswith(f"S-{department.code}-2026-")
    assert stu_data["current_semester_number"] == 1

    fac_resp = client.post(
        "/api/v1/admin/faculty",
        headers=admin_headers,
        json={
            "email": "managed.fac@example.edu",
            "full_name": "Managed Faculty",
            "password": STRONG_PASSWORD,
            "department_id": department.id,
            "designation": "Assistant Professor",
        },
    )
    assert fac_resp.status_code == 201
    assert fac_resp.json()["employee_id"].startswith(f"F-{department.code}-")
