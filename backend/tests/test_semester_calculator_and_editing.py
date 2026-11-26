"""Tests for automatic student semester calculation and admin-only editing."""

from collections.abc import Generator
from datetime import date

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import update
from sqlalchemy.orm import Session

from app.core.security import create_access_token
from app.database.connection import engine, get_db
from app.main import app
from app.models import Department, Semester, UserRole
from app.schemas.auth import AdminCreateRequest
from app.services.auth_service import create_admin_user
from app.services.exceptions import BusinessRuleError
from app.services.semester_calculator import (
    calculate_student_semester,
    resolve_student_semester_safe,
)

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
            email="semcalc.admin@example.edu",
            full_name="SemCalc Admin",
            password=STRONG_PASSWORD,
        ),
    )
    token = create_access_token(subject=str(admin.id), role=UserRole.ADMIN.value)
    return {"Authorization": f"Bearer {token}"}


def test_semester_calculator_progression_and_calendar_states(
    client: TestClient,
    admin_headers: dict[str, str],
    db_session: Session,
) -> None:
    """Verify odd/even calculation, transitions, completion, and calendar errors."""
    # Ensure no pre-existing active semesters interfere inside this SAVEPOINT
    db_session.execute(update(Semester).values(is_active=False))
    db_session.flush()

    # 1. Missing active semester -> raises on strict call, safe returns status
    with pytest.raises(BusinessRuleError, match="No active semester"):
        calculate_student_semester(db_session, admission_year=2026)

    missing = resolve_student_semester_safe(db_session, admission_year=2026)
    assert missing.calculated_semester is None
    assert missing.semester_status == "Calendar Not Configured"

    # 2. Ambiguous active semesters (2 active) -> raises BusinessRuleError
    sem_a = Semester(
        name="Semester 1",
        academic_year="2035-2036",
        term_number=1,
        start_date=date(2035, 7, 15),
        end_date=date(2035, 12, 15),
        is_active=True,
    )
    sem_b = Semester(
        name="Semester 2",
        academic_year="2035-2036",
        term_number=2,
        start_date=date(2036, 1, 10),
        end_date=date(2036, 5, 25),
        is_active=True,
    )
    db_session.add_all([sem_a, sem_b])
    db_session.flush()

    with pytest.raises(BusinessRuleError, match="ambiguous"):
        calculate_student_semester(db_session, admission_year=2035)
    assert (
        resolve_student_semester_safe(db_session, admission_year=2035).semester_status
        == "Calendar Ambiguous"
    )

    # 3. Single active Odd semester (2035-2036, Term 1)
    sem_b.is_active = False
    db_session.flush()

    assert (
        calculate_student_semester(db_session, admission_year=2035).calculated_semester
        == 1
    )
    assert (
        calculate_student_semester(db_session, admission_year=2034).calculated_semester
        == 3
    )
    assert (
        calculate_student_semester(db_session, admission_year=2033).calculated_semester
        == 5
    )
    assert (
        calculate_student_semester(db_session, admission_year=2032).calculated_semester
        == 7
    )

    # Completed programme (2031-2032 -> raw 9 > 8)
    completed = calculate_student_semester(db_session, admission_year=2031)
    assert completed.is_completed is True
    assert completed.semester_status == "Completed"
    assert completed.calculated_semester == 8

    # Future admission year rejected (prevents negative semester)
    with pytest.raises(BusinessRuleError, match="cannot be later"):
        calculate_student_semester(db_session, admission_year=2036)

    # 4. Transition to Even semester (2035-2036, Term 2) -> Sem 2, 4, 6, 8
    sem_a.is_active = False
    sem_b.is_active = True
    db_session.flush()

    assert (
        calculate_student_semester(db_session, admission_year=2035).calculated_semester
        == 2
    )
    assert (
        calculate_student_semester(db_session, admission_year=2034).calculated_semester
        == 4
    )
    assert (
        calculate_student_semester(db_session, admission_year=2033).calculated_semester
        == 6
    )
    assert (
        calculate_student_semester(db_session, admission_year=2032).calculated_semester
        == 8
    )

    # 5. Create student via API and verify automatic update on academic year transition
    dept = Department(code="SEMC", name="Semester Calc Dept")
    db_session.add(dept)
    db_session.flush()

    stu_resp = client.post(
        "/api/v1/admin/students",
        headers=admin_headers,
        json={
            "email": "prog.stu@example.edu",
            "full_name": "Progressing Student",
            "password": STRONG_PASSWORD,
            "department_id": dept.id,
            "admission_year": 2035,
        },
    )
    assert stu_resp.status_code == 201
    stu = stu_resp.json()
    assert stu["calculated_semester"] == 2
    assert stu["admission_academic_year"] == "2035-2036"

    # Reject future admission year via API
    bad_stu = client.post(
        "/api/v1/admin/students",
        headers=admin_headers,
        json={
            "email": "future.stu@example.edu",
            "full_name": "Future Student",
            "password": STRONG_PASSWORD,
            "department_id": dept.id,
            "admission_year": 2036,
        },
    )
    assert bad_stu.status_code == 422

    # Transition to 2036-2037 Term 1 -> student automatically becomes Sem 3
    sem_b.is_active = False
    sem_next = Semester(
        name="Semester 1",
        academic_year="2036-2037",
        term_number=1,
        start_date=date(2036, 7, 15),
        end_date=date(2036, 12, 15),
        is_active=True,
    )
    db_session.add(sem_next)
    db_session.flush()

    fetched = client.get(f"/api/v1/admin/students/{stu['id']}", headers=admin_headers)
    assert fetched.status_code == 200
    assert fetched.json()["calculated_semester"] == 3


def test_admin_only_student_and_faculty_editing_and_rbac(
    client: TestClient,
    admin_headers: dict[str, str],
    db_session: Session,
) -> None:
    """Verify Admin editing of Student/Faculty, validations, and 403 RBAC blocks."""
    db_session.execute(update(Semester).values(is_active=False))
    active_sem = Semester(
        name="Semester 1",
        academic_year="2037-2038",
        term_number=1,
        start_date=date(2037, 7, 15),
        end_date=date(2037, 12, 15),
        is_active=True,
    )
    dept1 = Department(code="EDITA", name="Edit Dept A")
    dept2 = Department(code="EDITB", name="Edit Dept B")
    db_session.add_all([active_sem, dept1, dept2])
    db_session.flush()

    s1 = client.post(
        "/api/v1/admin/students",
        headers=admin_headers,
        json={
            "email": "edit.s1@example.edu",
            "full_name": "Edit Student One",
            "password": STRONG_PASSWORD,
            "department_id": dept1.id,
            "admission_year": 2037,
        },
    ).json()
    s2 = client.post(
        "/api/v1/admin/students",
        headers=admin_headers,
        json={
            "email": "edit.s2@example.edu",
            "full_name": "Edit Student Two",
            "password": STRONG_PASSWORD,
            "department_id": dept1.id,
            "admission_year": 2037,
        },
    ).json()

    f1 = client.post(
        "/api/v1/admin/faculty",
        headers=admin_headers,
        json={
            "email": "edit.f1@example.edu",
            "full_name": "Edit Faculty One",
            "password": STRONG_PASSWORD,
            "department_id": dept1.id,
            "designation": "Lecturer",
        },
    ).json()
    f2 = client.post(
        "/api/v1/admin/faculty",
        headers=admin_headers,
        json={
            "email": "edit.f2@example.edu",
            "full_name": "Edit Faculty Two",
            "password": STRONG_PASSWORD,
            "department_id": dept1.id,
            "designation": "Professor",
        },
    ).json()

    # Admin edits student: change admission year (2036 -> Sem 3) & recalculate_id
    upd_s = client.patch(
        f"/api/v1/admin/students/{s1['id']}",
        headers=admin_headers,
        json={
            "full_name": "Edit Student One Updated",
            "department_id": dept2.id,
            "admission_year": 2036,
            "recalculate_id": True,
        },
    )
    assert upd_s.status_code == 200
    assert upd_s.json()["user"]["full_name"] == "Edit Student One Updated"
    assert upd_s.json()["calculated_semester"] == 3
    assert upd_s.json()["roll_number"] == "S-EDITB-2036-001"

    # Duplicate student ID & duplicate email rejected (409)
    assert (
        client.patch(
            f"/api/v1/admin/students/{s1['id']}",
            headers=admin_headers,
            json={"roll_number": s2["roll_number"]},
        ).status_code
        == 409
    )
    assert (
        client.patch(
            f"/api/v1/admin/students/{s1['id']}",
            headers=admin_headers,
            json={"email": s2["user"]["email"]},
        ).status_code
        == 409
    )

    # Admin edits faculty
    upd_f = client.patch(
        f"/api/v1/admin/faculty/{f1['id']}",
        headers=admin_headers,
        json={
            "full_name": "Edit Faculty One Updated",
            "designation": "Associate Professor",
            "department_id": dept2.id,
            "recalculate_id": True,
        },
    )
    assert upd_f.status_code == 200
    assert upd_f.json()["designation"] == "Associate Professor"
    assert upd_f.json()["employee_id"] == "F-EDITB-001"

    # Duplicate faculty ID & duplicate email rejected (409)
    assert (
        client.patch(
            f"/api/v1/admin/faculty/{f1['id']}",
            headers=admin_headers,
            json={"employee_id": f2["employee_id"]},
        ).status_code
        == 409
    )
    assert (
        client.patch(
            f"/api/v1/admin/faculty/{f1['id']}",
            headers=admin_headers,
            json={"email": f2["user"]["email"]},
        ).status_code
        == 409
    )

    # RBAC: Faculty and Student cannot edit any student or faculty record (403)
    fac_token = create_access_token(
        subject=str(f1["user"]["id"]),
        role=UserRole.FACULTY.value,
    )
    stu_token = create_access_token(
        subject=str(s1["user"]["id"]),
        role=UserRole.STUDENT.value,
    )
    fac_headers = {"Authorization": f"Bearer {fac_token}"}
    stu_headers = {"Authorization": f"Bearer {stu_token}"}

    for non_admin_headers in (fac_headers, stu_headers):
        assert (
            client.patch(
                f"/api/v1/admin/students/{s2['id']}",
                headers=non_admin_headers,
                json={"full_name": "Hacked"},
            ).status_code
            == 403
        )
        assert (
            client.patch(
                f"/api/v1/admin/faculty/{f2['id']}",
                headers=non_admin_headers,
                json={"full_name": "Hacked"},
            ).status_code
            == 403
        )
