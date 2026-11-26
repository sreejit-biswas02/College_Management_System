"""Tests for zero-config semester calculation, admin promotion, and editing."""

from collections.abc import Generator
from datetime import date

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.core.security import create_access_token
from app.database.connection import engine, get_db
from app.main import app
from app.models import (
    Course,
    CourseOffering,
    Department,
    Enrollment,
    Semester,
    SemesterPromotionLog,
    UserRole,
)
from app.schemas.auth import AdminCreateRequest
from app.services.auth_service import create_admin_user
from app.services.exceptions import BusinessRuleError
from app.services.semester_calculator import calculate_student_semester

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


def test_zero_config_semester_calculator_formula(db_session: Session) -> None:
    """Calculator works without calendar setup using 1 + 2 * (current - admission)."""
    # Deactivate all semesters so zero calendar config is present
    db_session.execute(update(Semester).values(is_active=False))
    db_session.flush()

    nov_2026 = date(2026, 11, 26)  # Indian academic year 2026-2027
    assert (
        calculate_student_semester(
            db_session, admission_year=2026, reference_date=nov_2026
        ).calculated_semester
        == 1
    )
    assert (
        calculate_student_semester(
            db_session, admission_year=2025, reference_date=nov_2026
        ).calculated_semester
        == 3
    )
    assert (
        calculate_student_semester(
            db_session, admission_year=2024, reference_date=nov_2026
        ).calculated_semester
        == 5
    )
    assert (
        calculate_student_semester(
            db_session, admission_year=2023, reference_date=nov_2026
        ).calculated_semester
        == 7
    )

    # Completed programme for 2022-2023 (raw 9 > 8)
    comp = calculate_student_semester(
        db_session, admission_year=2022, reference_date=nov_2026
    )
    assert comp.is_completed is True
    assert comp.semester_status == "Completed"

    # Admission year later than current academic year is rejected
    with pytest.raises(BusinessRuleError, match="cannot be later"):
        calculate_student_semester(
            db_session, admission_year=2027, reference_date=nov_2026
        )


def test_student_promotion_odd_to_even_and_preservation(
    client: TestClient,
    admin_headers: dict[str, str],
    db_session: Session,
) -> None:
    """Promote active odd-semester students 1->2, 3->4, 5->6, 7->8 with audit & RBAC."""
    db_session.execute(update(Semester).values(is_active=False))
    active_sem = Semester(
        name="Semester 1",
        academic_year="2026-2027",
        term_number=1,
        start_date=date(2026, 7, 15),
        end_date=date(2026, 12, 20),
        is_active=True,
    )
    dept = Department(code="PROMO", name="Promotion Dept")
    db_session.add_all([active_sem, dept])
    db_session.flush()

    # Create 4 active students (batches 2026, 2025, 2024, 2023 -> Sem 1, 3, 5, 7)
    # plus 1 inactive student (2026 -> Sem 1) who must NOT be promoted.
    created_students = []
    for idx, yr in enumerate((2026, 2025, 2024, 2023), start=1):
        resp = client.post(
            "/api/v1/admin/students",
            headers=admin_headers,
            json={
                "email": f"promo.s{idx}@example.edu",
                "full_name": f"Promo Student {idx}",
                "password": STRONG_PASSWORD,
                "department_id": dept.id,
                "admission_year": yr,
                "current_semester_number": 8,  # must be ignored by backend
            },
        )
        assert resp.status_code == 201
        created_students.append(resp.json())

    assert [s["current_semester_number"] for s in created_students] == [1, 3, 5, 7]

    inactive_stu = client.post(
        "/api/v1/admin/students",
        headers=admin_headers,
        json={
            "email": "promo.inactive@example.edu",
            "full_name": "Inactive Student",
            "password": STRONG_PASSWORD,
            "department_id": dept.id,
            "admission_year": 2026,
            "is_active": False,
        },
    ).json()
    assert inactive_stu["current_semester_number"] == 1

    # Create faculty, course, offering, and enrollment to verify records stay intact
    fac = client.post(
        "/api/v1/admin/faculty",
        headers=admin_headers,
        json={
            "email": "promo.fac@example.edu",
            "full_name": "Promo Faculty",
            "password": STRONG_PASSWORD,
            "department_id": dept.id,
            "designation": "Professor",
        },
    ).json()
    course = Course(
        department_id=dept.id,
        code="PRM101",
        title="Promotion Verification",
        credits=4,
    )
    db_session.add(course)
    db_session.flush()
    offering = CourseOffering(
        course_id=course.id,
        semester_id=active_sem.id,
        faculty_id=fac["id"],
        section="A",
        is_active=True,
    )
    db_session.add(offering)
    db_session.flush()
    db_session.add(
        Enrollment(student_id=created_students[0]["id"], course_offering_id=offering.id)
    )
    db_session.flush()

    # Preview endpoint checks
    prev_resp = client.get(
        "/api/v1/admin/students/promotion-preview",
        headers=admin_headers,
    )
    assert prev_resp.status_code == 200
    prev = prev_resp.json()
    assert prev["academic_year"] == "2026-2027"
    assert prev["eligible_count"] >= 4
    assert prev["inactive_skipped_count"] >= 1
    assert prev["can_promote"] is True

    # Non-admin users cannot access promotion endpoints
    stu_token = create_access_token(
        subject=str(created_students[0]["user"]["id"]),
        role=UserRole.STUDENT.value,
    )
    fac_token = create_access_token(
        subject=str(fac["user"]["id"]),
        role=UserRole.FACULTY.value,
    )
    for non_admin in (
        {"Authorization": f"Bearer {stu_token}"},
        {"Authorization": f"Bearer {fac_token}"},
    ):
        assert (
            client.get(
                "/api/v1/admin/students/promotion-preview",
                headers=non_admin,
            ).status_code
            == 403
        )
        assert (
            client.post(
                "/api/v1/admin/students/promote-semester",
                headers=non_admin,
            ).status_code
            == 403
        )

    # Execute promotion
    promo_resp = client.post(
        "/api/v1/admin/students/promote-semester",
        headers=admin_headers,
    )
    assert promo_resp.status_code == 200
    assert promo_resp.json()["promoted_count"] >= 4

    # Verify active students moved 1->2, 3->4, 5->6, 7->8 and stay even on fetch
    expected_even = [2, 4, 6, 8]
    for stu_obj, expected_sem in zip(created_students, expected_even, strict=True):
        fetched = client.get(
            f"/api/v1/admin/students/{stu_obj['id']}",
            headers=admin_headers,
        )
        assert fetched.status_code == 200
        assert fetched.json()["current_semester_number"] == expected_sem

    # Verify inactive student was NOT promoted
    inactive_after = client.get(
        f"/api/v1/admin/students/{inactive_stu['id']}",
        headers=admin_headers,
    ).json()
    assert inactive_after["current_semester_number"] == 1

    # Verify audit logs recorded
    logs = list(
        db_session.scalars(
            select(SemesterPromotionLog).where(
                SemesterPromotionLog.academic_year == "2026-2027",
                SemesterPromotionLog.student_id.in_(
                    [s["id"] for s in created_students]
                ),
            )
        ).all()
    )
    assert len(logs) == 4

    # Repeating promotion in the same academic year is rejected with 409
    repeat_resp = client.post(
        "/api/v1/admin/students/promote-semester",
        headers=admin_headers,
    )
    assert repeat_resp.status_code == 409

    # Existing enrollment remains intact
    enr = db_session.scalar(
        select(Enrollment).where(Enrollment.student_id == created_students[0]["id"])
    )
    assert enr is not None


def test_admin_only_student_and_faculty_editing_and_rbac(
    client: TestClient,
    admin_headers: dict[str, str],
    db_session: Session,
) -> None:
    """Verify Admin editing of Student/Faculty, validations, and 403 RBAC blocks."""
    db_session.execute(update(Semester).values(is_active=False))
    active_sem = Semester(
        name="Semester 1",
        academic_year="2026-2027",
        term_number=1,
        start_date=date(2026, 7, 15),
        end_date=date(2026, 12, 15),
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
            "admission_year": 2026,
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
            "admission_year": 2026,
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

    # Preview endpoint reflects updated admission_year
    prev_2024 = client.get(
        "/api/v1/admin/semesters/active-preview",
        headers=admin_headers,
        params={"admission_year": 2024},
    )
    assert prev_2024.status_code == 200
    assert prev_2024.json()["calculated_semester"] == 5

    # Admin edits student: change admission year (2025 -> Sem 3) & recalculate_id
    upd_s = client.patch(
        f"/api/v1/admin/students/{s1['id']}",
        headers=admin_headers,
        json={
            "full_name": "Edit Student One Updated",
            "department_id": dept2.id,
            "admission_year": 2025,
            "recalculate_id": True,
        },
    )
    assert upd_s.status_code == 200
    assert upd_s.json()["user"]["full_name"] == "Edit Student One Updated"
    assert upd_s.json()["current_semester_number"] == 3
    assert upd_s.json()["roll_number"] == "S-EDITB-2025-001"

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
