"""Automated tests for Phase 3 Part 1: Management and Academic Structure."""

from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.security import create_access_token
from app.database.connection import engine, get_db
from app.main import app
from app.models import Department, UserRole
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
def admin_headers(db_session: Session) -> dict[str, str]:
    """Create an admin user and return Bearer authorization headers."""
    admin = create_admin_user(
        db_session,
        AdminCreateRequest(
            email="mgmt.admin@example.edu",
            full_name="Management Admin",
            password=STRONG_PASSWORD,
        ),
    )
    token = create_access_token(subject=str(admin.id), role=UserRole.ADMIN.value)
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture()
def sample_department(db_session: Session) -> Department:
    """Create a sample department for tests."""
    dept = Department(code="CSE", name="Computer Science & Engineering")
    db_session.add(dept)
    db_session.commit()
    db_session.refresh(dept)
    return dept


def test_student_crud_and_duplicates(
    client: TestClient,
    admin_headers: dict[str, str],
    sample_department: Department,
) -> None:
    """Admin can create, view, update, deactivate/reactivate, and search students."""
    create_resp = client.post(
        "/api/v1/admin/students",
        headers=admin_headers,
        json={
            "email": "student1@example.edu",
            "full_name": "Alice Johnson",
            "password": STRONG_PASSWORD,
            "department_id": sample_department.id,
            "roll_number": "CSE-2026-001",
            "admission_year": 2026,
            "current_semester_number": 1,
        },
    )
    assert create_resp.status_code == 201
    student = create_resp.json()
    assert student["roll_number"] == "CSE-2026-001"
    assert student["user"]["email"] == "student1@example.edu"
    assert "hashed_password" not in student["user"]

    # Duplicate email
    dup_email = client.post(
        "/api/v1/admin/students",
        headers=admin_headers,
        json={
            "email": "STUDENT1@example.edu",
            "full_name": "Other",
            "password": STRONG_PASSWORD,
            "department_id": sample_department.id,
            "roll_number": "CSE-2026-002",
            "admission_year": 2026,
        },
    )
    assert dup_email.status_code == 409

    # Duplicate roll number
    dup_roll = client.post(
        "/api/v1/admin/students",
        headers=admin_headers,
        json={
            "email": "student2@example.edu",
            "full_name": "Other",
            "password": STRONG_PASSWORD,
            "department_id": sample_department.id,
            "roll_number": "CSE-2026-001",
            "admission_year": 2026,
        },
    )
    assert dup_roll.status_code == 409

    sid = student["id"]
    # Get by ID
    assert (
        client.get(
            f"/api/v1/admin/students/{sid}",
            headers=admin_headers,
        ).status_code
        == 200
    )

    # Update
    upd = client.patch(
        f"/api/v1/admin/students/{sid}",
        headers=admin_headers,
        json={"full_name": "Alice J. Updated", "current_semester_number": 2},
    )
    assert upd.status_code == 200
    assert upd.json()["user"]["full_name"] == "Alice J. Updated"
    assert upd.json()["current_semester_number"] == 2

    # Deactivate & reactivate
    deact = client.patch(
        f"/api/v1/admin/students/{sid}/deactivate",
        headers=admin_headers,
    )
    assert deact.status_code == 200
    assert deact.json()["user"]["is_active"] is False

    react = client.patch(
        f"/api/v1/admin/students/{sid}/activate",
        headers=admin_headers,
    )
    assert react.status_code == 200
    assert react.json()["user"]["is_active"] is True

    # Search & filter
    listed = client.get(
        "/api/v1/admin/students",
        headers=admin_headers,
        params={"search": "CSE-2026-001", "semester_number": 2},
    )
    assert listed.status_code == 200
    assert listed.json()["total"] == 1


def test_faculty_crud_and_duplicates(
    client: TestClient,
    admin_headers: dict[str, str],
    sample_department: Department,
) -> None:
    """Admin can create, view, update, deactivate/reactivate, and search faculty."""
    resp = client.post(
        "/api/v1/admin/faculty",
        headers=admin_headers,
        json={
            "email": "prof1@example.edu",
            "full_name": "Dr. Bob Smith",
            "password": STRONG_PASSWORD,
            "department_id": sample_department.id,
            "employee_id": "EMP-501",
            "designation": "Professor",
        },
    )
    assert resp.status_code == 201
    fac = resp.json()
    assert fac["employee_id"] == "EMP-501"
    assert "hashed_password" not in fac["user"]

    # Duplicate email & employee_id
    assert (
        client.post(
            "/api/v1/admin/faculty",
            headers=admin_headers,
            json={
                "email": "prof1@example.edu",
                "full_name": "Dup",
                "password": STRONG_PASSWORD,
                "department_id": sample_department.id,
                "employee_id": "EMP-502",
                "designation": "Lecturer",
            },
        ).status_code
        == 409
    )
    assert (
        client.post(
            "/api/v1/admin/faculty",
            headers=admin_headers,
            json={
                "email": "prof2@example.edu",
                "full_name": "Dup",
                "password": STRONG_PASSWORD,
                "department_id": sample_department.id,
                "employee_id": "EMP-501",
                "designation": "Lecturer",
            },
        ).status_code
        == 409
    )

    fid = fac["id"]
    assert (
        client.patch(
            f"/api/v1/admin/faculty/{fid}",
            headers=admin_headers,
            json={"designation": "Senior Professor"},
        ).json()["designation"]
        == "Senior Professor"
    )
    assert (
        client.patch(
            f"/api/v1/admin/faculty/{fid}/deactivate",
            headers=admin_headers,
        ).json()["user"]["is_active"]
        is False
    )
    assert (
        client.patch(
            f"/api/v1/admin/faculty/{fid}/activate",
            headers=admin_headers,
        ).json()["user"]["is_active"]
        is True
    )


def test_department_crud(
    client: TestClient,
    admin_headers: dict[str, str],
) -> None:
    """Admin can create, list, view, update, and toggle departments."""
    resp = client.post(
        "/api/v1/admin/departments",
        headers=admin_headers,
        json={"code": "ece", "name": "Electronics Engineering"},
    )
    assert resp.status_code == 201
    dept = resp.json()
    assert dept["code"] == "ECE"

    # Duplicate code rejected
    assert (
        client.post(
            "/api/v1/admin/departments",
            headers=admin_headers,
            json={"code": "ECE", "name": "Different Name"},
        ).status_code
        == 409
    )

    did = dept["id"]
    assert (
        client.get(
            f"/api/v1/admin/departments/{did}",
            headers=admin_headers,
        ).status_code
        == 200
    )
    assert (
        client.patch(
            f"/api/v1/admin/departments/{did}",
            headers=admin_headers,
            json={"name": "Electronics & Comm Engineering"},
        ).json()["name"]
        == "Electronics & Comm Engineering"
    )
    assert (
        client.patch(
            f"/api/v1/admin/departments/{did}/deactivate",
            headers=admin_headers,
        ).json()["is_active"]
        is False
    )
    assert (
        client.patch(
            f"/api/v1/admin/departments/{did}/activate",
            headers=admin_headers,
        ).json()["is_active"]
        is True
    )


def test_semester_crud(
    client: TestClient,
    admin_headers: dict[str, str],
) -> None:
    """Admin can create, list, view, update, and toggle semesters."""
    resp = client.post(
        "/api/v1/admin/semesters",
        headers=admin_headers,
        json={
            "name": "Fall 2026",
            "academic_year": "2026-2027",
            "term_number": 1,
            "start_date": "2026-08-01",
            "end_date": "2026-12-15",
            "is_active": False,
        },
    )
    assert resp.status_code == 201
    sem = resp.json()

    # Duplicate year+term rejected
    assert (
        client.post(
            "/api/v1/admin/semesters",
            headers=admin_headers,
            json={
                "name": "Fall 2026 Dup",
                "academic_year": "2026-2027",
                "term_number": 1,
                "start_date": "2026-08-01",
                "end_date": "2026-12-15",
            },
        ).status_code
        == 409
    )

    # Invalid date range rejected
    assert (
        client.post(
            "/api/v1/admin/semesters",
            headers=admin_headers,
            json={
                "name": "Bad Dates",
                "academic_year": "2026-2027",
                "term_number": 2,
                "start_date": "2026-12-15",
                "end_date": "2026-08-01",
            },
        ).status_code
        == 422
    )

    sid = sem["id"]
    assert (
        client.patch(
            f"/api/v1/admin/semesters/{sid}/activate",
            headers=admin_headers,
        ).json()["is_active"]
        is True
    )
    assert (
        client.patch(
            f"/api/v1/admin/semesters/{sid}",
            headers=admin_headers,
            json={"name": "Autumn 2026"},
        ).json()["name"]
        == "Autumn 2026"
    )


def test_course_and_offering_crud_and_invalid_fks(
    client: TestClient,
    admin_headers: dict[str, str],
    sample_department: Department,
) -> None:
    """Course and CourseOffering CRUD, filtering, pagination, and FK validation."""
    # Create course
    c_resp = client.post(
        "/api/v1/admin/courses",
        headers=admin_headers,
        json={
            "department_id": sample_department.id,
            "code": "cs101",
            "title": "Data Structures",
            "credits": 4,
        },
    )
    assert c_resp.status_code == 201
    course = c_resp.json()
    assert course["code"] == "CS101"

    # Duplicate course code & invalid FK
    assert (
        client.post(
            "/api/v1/admin/courses",
            headers=admin_headers,
            json={
                "department_id": sample_department.id,
                "code": "CS101",
                "title": "Duplicate",
                "credits": 3,
            },
        ).status_code
        == 409
    )
    assert (
        client.post(
            "/api/v1/admin/courses",
            headers=admin_headers,
            json={
                "department_id": 999999,
                "code": "CS999",
                "title": "Bad Dept",
                "credits": 3,
            },
        ).status_code
        == 404
    )

    # Create semester and faculty
    sem = client.post(
        "/api/v1/admin/semesters",
        headers=admin_headers,
        json={
            "name": "Spring 2027",
            "academic_year": "2026-2027",
            "term_number": 2,
            "start_date": "2027-01-10",
            "end_date": "2027-05-15",
            "is_active": True,
        },
    ).json()
    fac = client.post(
        "/api/v1/admin/faculty",
        headers=admin_headers,
        json={
            "email": "offering.fac@example.edu",
            "full_name": "Prof. Offering",
            "password": STRONG_PASSWORD,
            "department_id": sample_department.id,
            "employee_id": "EMP-701",
            "designation": "Assistant Professor",
        },
    ).json()

    # Create course offering
    off_resp = client.post(
        "/api/v1/admin/course-offerings",
        headers=admin_headers,
        json={
            "course_id": course["id"],
            "semester_id": sem["id"],
            "faculty_id": fac["id"],
            "section": "a",
            "max_capacity": 60,
        },
    )
    assert off_resp.status_code == 201
    offering = off_resp.json()
    assert offering["section"] == "A"
    assert offering["course"]["code"] == "CS101"

    # Duplicate offering & invalid faculty FK
    assert (
        client.post(
            "/api/v1/admin/course-offerings",
            headers=admin_headers,
            json={
                "course_id": course["id"],
                "semester_id": sem["id"],
                "faculty_id": fac["id"],
                "section": "A",
            },
        ).status_code
        == 409
    )
    assert (
        client.post(
            "/api/v1/admin/course-offerings",
            headers=admin_headers,
            json={
                "course_id": course["id"],
                "semester_id": sem["id"],
                "faculty_id": 999999,
                "section": "B",
            },
        ).status_code
        == 404
    )

    # Filter offerings
    filtered = client.get(
        "/api/v1/admin/course-offerings",
        headers=admin_headers,
        params={"semester_id": sem["id"], "faculty_id": fac["id"], "section": "A"},
    )
    assert filtered.status_code == 200
    assert filtered.json()["total"] == 1


def test_pagination_and_role_restrictions(
    client: TestClient,
    admin_headers: dict[str, str],
    sample_department: Department,
) -> None:
    """Pagination works and Student/Faculty cannot access /admin/* endpoints."""
    # Create 3 courses to test pagination
    for idx in range(1, 4):
        resp = client.post(
            "/api/v1/admin/courses",
            headers=admin_headers,
            json={
                "department_id": sample_department.id,
                "code": f"PAG10{idx}",
                "title": f"Paginated Course {idx}",
                "credits": 3,
            },
        )
        assert resp.status_code == 201

    page1 = client.get(
        "/api/v1/admin/courses",
        headers=admin_headers,
        params={"page": 1, "page_size": 2},
    ).json()
    assert len(page1["items"]) == 2
    assert page1["total"] == 3
    assert page1["pages"] == 2

    # Create a student & a faculty member and verify access restrictions
    stu = client.post(
        "/api/v1/admin/students",
        headers=admin_headers,
        json={
            "email": "stu.perm@example.edu",
            "full_name": "Student Perm",
            "password": STRONG_PASSWORD,
            "department_id": sample_department.id,
            "roll_number": "PERM-01",
            "admission_year": 2026,
        },
    ).json()
    fac = client.post(
        "/api/v1/admin/faculty",
        headers=admin_headers,
        json={
            "email": "fac.perm@example.edu",
            "full_name": "Faculty Perm",
            "password": STRONG_PASSWORD,
            "department_id": sample_department.id,
            "employee_id": "PERM-FAC-01",
            "designation": "Lecturer",
        },
    ).json()

    stu_token = create_access_token(
        subject=str(stu["user"]["id"]),
        role=UserRole.STUDENT.value,
    )
    fac_token = create_access_token(
        subject=str(fac["user"]["id"]),
        role=UserRole.FACULTY.value,
    )
    stu_headers = {"Authorization": f"Bearer {stu_token}"}
    fac_headers = {"Authorization": f"Bearer {fac_token}"}

    # Neither student nor faculty can access admin routes
    assert client.get("/api/v1/admin/students", headers=stu_headers).status_code == 403
    assert (
        client.get("/api/v1/admin/departments", headers=fac_headers).status_code == 403
    )

    # Self-service routes work for respective roles
    assert client.get("/api/v1/students/me", headers=stu_headers).status_code == 200
    assert client.get("/api/v1/faculty/me", headers=fac_headers).status_code == 200
    assert (
        client.get(
            "/api/v1/faculty/me/course-offerings",
            headers=fac_headers,
        ).status_code
        == 200
    )
    # Student cannot hit faculty self-service route
    assert client.get("/api/v1/faculty/me", headers=stu_headers).status_code == 403
