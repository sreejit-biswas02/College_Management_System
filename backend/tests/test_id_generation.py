"""Automated tests for automatic Student ID and Faculty ID generation."""

from collections.abc import Generator
from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete
from sqlalchemy.orm import Session

from app.core.security import create_access_token
from app.database.connection import SessionLocal, engine, get_db
from app.main import app
from app.models import Department, Faculty, IDSequence, Student, User, UserRole
from app.schemas.auth import AdminCreateRequest
from app.schemas.faculty import AdminFacultyCreate
from app.schemas.student import AdminStudentCreate
from app.services.auth_service import create_admin_user
from app.services.faculty_service import create_faculty
from app.services.student_service import create_student

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
    """FastAPI TestClient backed by the isolated test session."""

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
    """Create a test admin and return Bearer authorization headers."""
    admin = create_admin_user(
        db_session,
        AdminCreateRequest(
            email="idgen.admin@example.edu",
            full_name="ID Gen Admin",
            password=STRONG_PASSWORD,
        ),
    )
    token = create_access_token(subject=str(admin.id), role=UserRole.ADMIN.value)
    return {"Authorization": f"Bearer {token}"}


def test_student_and_faculty_id_generation_sequences(
    client: TestClient,
    admin_headers: dict[str, str],
    db_session: Session,
) -> None:
    """Verify sequential ID generation per department and admission year."""
    dept_cs = Department(code="CSID", name="Computer Science ID Gen")
    dept_ec = Department(code="ECID", name="Electronics ID Gen")
    db_session.add_all([dept_cs, dept_ec])
    db_session.flush()

    # Students in CSID 2026 -> 001, 002
    s1 = client.post(
        "/api/v1/admin/students",
        headers=admin_headers,
        json={
            "email": "s.cs.26.1@example.edu",
            "full_name": "CS Student One",
            "password": STRONG_PASSWORD,
            "department_id": dept_cs.id,
            "admission_year": 2026,
        },
    )
    assert s1.status_code == 201
    assert s1.json()["roll_number"] == "S-CSID-2026-001"

    s2 = client.post(
        "/api/v1/admin/students",
        headers=admin_headers,
        json={
            "email": "s.cs.26.2@example.edu",
            "full_name": "CS Student Two",
            "password": STRONG_PASSWORD,
            "department_id": dept_cs.id,
            "admission_year": 2026,
            "roll_number": "S-FAKE-999",
        },
    )
    assert s2.status_code == 201
    assert s2.json()["roll_number"] == "S-CSID-2026-002"

    # Different admission year (CSID 2027) -> starts at 001
    s_next_year = client.post(
        "/api/v1/admin/students",
        headers=admin_headers,
        json={
            "email": "s.cs.27.1@example.edu",
            "full_name": "CS Student 2027",
            "password": STRONG_PASSWORD,
            "department_id": dept_cs.id,
            "admission_year": 2027,
        },
    )
    assert s_next_year.status_code == 201
    assert s_next_year.json()["roll_number"] == "S-CSID-2027-001"

    # Different department (ECID 2026) -> starts at 001
    s_ec = client.post(
        "/api/v1/admin/students",
        headers=admin_headers,
        json={
            "email": "s.ec.26.1@example.edu",
            "full_name": "EC Student One",
            "password": STRONG_PASSWORD,
            "department_id": dept_ec.id,
            "admission_year": 2026,
        },
    )
    assert s_ec.status_code == 201
    assert s_ec.json()["roll_number"] == "S-ECID-2026-001"

    # Failed student creation (duplicate email) must not advance sequence
    dup_s = client.post(
        "/api/v1/admin/students",
        headers=admin_headers,
        json={
            "email": "s.cs.26.2@example.edu",
            "full_name": "Dup Email",
            "password": STRONG_PASSWORD,
            "department_id": dept_cs.id,
            "admission_year": 2026,
        },
    )
    assert dup_s.status_code == 409

    s3 = client.post(
        "/api/v1/admin/students",
        headers=admin_headers,
        json={
            "email": "s.cs.26.3@example.edu",
            "full_name": "CS Student Three",
            "password": STRONG_PASSWORD,
            "department_id": dept_cs.id,
            "admission_year": 2026,
        },
    )
    assert s3.status_code == 201
    assert s3.json()["roll_number"] == "S-CSID-2026-003"

    # Faculty in CSID -> F-CSID-001, F-CSID-002; ECID -> F-ECID-001
    f1 = client.post(
        "/api/v1/admin/faculty",
        headers=admin_headers,
        json={
            "email": "f.cs.1@example.edu",
            "full_name": "Prof CS One",
            "password": STRONG_PASSWORD,
            "department_id": dept_cs.id,
            "designation": "Professor",
        },
    )
    assert f1.status_code == 201
    assert f1.json()["employee_id"] == "F-CSID-001"

    f2 = client.post(
        "/api/v1/admin/faculty",
        headers=admin_headers,
        json={
            "email": "f.cs.2@example.edu",
            "full_name": "Prof CS Two",
            "password": STRONG_PASSWORD,
            "department_id": dept_cs.id,
            "designation": "Assistant Professor",
            "employee_id": "F-FAKE-999",
        },
    )
    assert f2.status_code == 201
    assert f2.json()["employee_id"] == "F-CSID-002"

    f_ec = client.post(
        "/api/v1/admin/faculty",
        headers=admin_headers,
        json={
            "email": "f.ec.1@example.edu",
            "full_name": "Prof EC One",
            "password": STRONG_PASSWORD,
            "department_id": dept_ec.id,
            "designation": "Professor",
        },
    )
    assert f_ec.status_code == 201
    assert f_ec.json()["employee_id"] == "F-ECID-001"

    # Patching student/faculty with invalid ID format is rejected (422)
    patch_stu = client.patch(
        f"/api/v1/admin/students/{s1.json()['id']}",
        headers=admin_headers,
        json={"roll_number": "S-OVERRIDE-1", "full_name": "CS Student One Updated"},
    )
    assert patch_stu.status_code == 422

    patch_fac = client.patch(
        f"/api/v1/admin/faculty/{f1.json()['id']}",
        headers=admin_headers,
        json={"employee_id": "F-OVERRIDE-1", "designation": "Dean"},
    )
    assert patch_fac.status_code == 422

    # Invalid department and invalid admission year are rejected
    assert (
        client.post(
            "/api/v1/admin/students",
            headers=admin_headers,
            json={
                "email": "bad.dept.s@example.edu",
                "full_name": "Bad Dept",
                "password": STRONG_PASSWORD,
                "department_id": 999999,
                "admission_year": 2026,
            },
        ).status_code
        == 404
    )
    assert (
        client.post(
            "/api/v1/admin/students",
            headers=admin_headers,
            json={
                "email": "bad.year.s@example.edu",
                "full_name": "Bad Year",
                "password": STRONG_PASSWORD,
                "department_id": dept_cs.id,
                "admission_year": 1800,
            },
        ).status_code
        == 422
    )
    assert (
        client.post(
            "/api/v1/admin/faculty",
            headers=admin_headers,
            json={
                "email": "bad.dept.f@example.edu",
                "full_name": "Bad Dept Fac",
                "password": STRONG_PASSWORD,
                "department_id": 999999,
                "designation": "Lecturer",
            },
        ).status_code
        == 404
    )


def test_concurrent_student_and_faculty_id_generation() -> None:
    """Concurrent student and faculty creation must produce unique sequential IDs."""
    setup_db = SessionLocal()
    dept_id: int | None = None
    created_user_ids: list[int] = []
    try:
        dept = Department(code="CONCID", name="Concurrency ID Dept")
        setup_db.add(dept)
        setup_db.commit()
        setup_db.refresh(dept)
        dept_id = dept.id

        def _make_student(idx: int) -> str:
            db = SessionLocal()
            try:
                stu = create_student(
                    db,
                    AdminStudentCreate(
                        email=f"conc.stu.{idx}@example.edu",
                        full_name=f"Concurrent Student {idx}",
                        password=STRONG_PASSWORD,
                        department_id=dept_id,
                        admission_year=2028,
                    ),
                )
                created_user_ids.append(stu.user_id)
                return stu.roll_number
            finally:
                db.close()

        def _make_faculty(idx: int) -> str:
            db = SessionLocal()
            try:
                fac = create_faculty(
                    db,
                    AdminFacultyCreate(
                        email=f"conc.fac.{idx}@example.edu",
                        full_name=f"Concurrent Faculty {idx}",
                        password=STRONG_PASSWORD,
                        department_id=dept_id,
                        designation="Lecturer",
                    ),
                )
                created_user_ids.append(fac.user_id)
                return fac.employee_id
            finally:
                db.close()

        with ThreadPoolExecutor(max_workers=5) as pool:
            student_ids = list(pool.map(_make_student, range(5)))
            faculty_ids = list(pool.map(_make_faculty, range(5)))

        assert sorted(student_ids) == [f"S-CONCID-2028-{i:03d}" for i in range(1, 6)]
        assert sorted(faculty_ids) == [f"F-CONCID-{i:03d}" for i in range(1, 6)]
    finally:
        if created_user_ids:
            setup_db.execute(
                delete(Student).where(Student.user_id.in_(created_user_ids))
            )
            setup_db.execute(
                delete(Faculty).where(Faculty.user_id.in_(created_user_ids))
            )
            setup_db.execute(delete(User).where(User.id.in_(created_user_ids)))
        setup_db.execute(
            delete(IDSequence).where(
                IDSequence.scope_key.in_(["CONCID:2028", "CONCID"])
            )
        )
        if dept_id is not None:
            setup_db.execute(delete(Department).where(Department.id == dept_id))
        setup_db.commit()
        setup_db.close()
