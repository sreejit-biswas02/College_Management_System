"""Tests for Admin Student Delete/Archive (soft-delete) and retention."""

from collections.abc import Generator
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, date, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.core.security import create_access_token, hash_password
from app.database.connection import SessionLocal, engine, get_db
from app.main import app
from app.models import (
    Assignment,
    AttendanceRecord,
    AttendanceSession,
    AttendanceStatus,
    Course,
    CourseOffering,
    Department,
    Enrollment,
    Faculty,
    Semester,
    Student,
    Submission,
    User,
    UserRole,
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
def archive_world(client: TestClient, db_session: Session) -> dict[str, object]:
    """Seed admin, 2 students, faculty, offering, enrollment, attendance, and grade."""
    admin = create_admin_user(
        db_session,
        AdminCreateRequest(
            email="arch.admin@example.edu",
            full_name="Archive Admin",
            password=STRONG_PASSWORD,
        ),
    )
    admin_hdr = {
        "Authorization": f"Bearer {create_access_token(str(admin.id), 'admin')}"
    }
    dept = Department(code="ARCH-D", name="Archive Dept")
    sem = Semester(
        name="Archive Sem",
        academic_year="2026-2027",
        term_number=1,
        start_date=date(2026, 8, 1),
        end_date=date(2026, 12, 15),
    )
    db_session.add_all([dept, sem])
    db_session.commit()

    s1 = client.post(
        "/api/v1/admin/students",
        headers=admin_hdr,
        json={
            "email": "arch.s1@example.edu",
            "full_name": "Archive Student 1",
            "password": STRONG_PASSWORD,
            "department_id": dept.id,
            "roll_number": "ARCH-001",
            "admission_year": 2026,
        },
    ).json()
    s2 = client.post(
        "/api/v1/admin/students",
        headers=admin_hdr,
        json={
            "email": "arch.s2@example.edu",
            "full_name": "Archive Student 2",
            "password": STRONG_PASSWORD,
            "department_id": dept.id,
            "roll_number": "ARCH-002",
            "admission_year": 2026,
        },
    ).json()
    fac = client.post(
        "/api/v1/admin/faculty",
        headers=admin_hdr,
        json={
            "email": "arch.fac@example.edu",
            "full_name": "Archive Faculty",
            "password": STRONG_PASSWORD,
            "department_id": dept.id,
            "employee_id": "ARCH-F1",
            "designation": "Professor",
        },
    ).json()

    course = Course(
        department_id=dept.id,
        code="ARCH101",
        title="Archival Studies",
        credits=3,
    )
    db_session.add(course)
    db_session.flush()
    fac_row = db_session.get(Faculty, fac["id"])
    assert fac_row is not None
    offering = CourseOffering(
        course_id=course.id,
        semester_id=sem.id,
        faculty_id=fac_row.id,
        section="A",
    )
    db_session.add(offering)
    db_session.flush()

    enrollment = Enrollment(
        student_id=s1["id"],
        course_offering_id=offering.id,
    )
    att_session = AttendanceSession(
        course_offering_id=offering.id,
        conducted_by_faculty_id=fac_row.id,
        session_date=date(2026, 9, 1),
        session_number=1,
    )
    assignment = Assignment(
        course_offering_id=offering.id,
        created_by_faculty_id=fac_row.id,
        title="Midterm",
        due_at=datetime.now(UTC) + timedelta(days=5),
    )
    db_session.add_all([enrollment, att_session, assignment])
    db_session.flush()

    att_record = AttendanceRecord(
        session_id=att_session.id,
        student_id=s1["id"],
        status=AttendanceStatus.PRESENT,
    )
    submission = Submission(
        assignment_id=assignment.id,
        student_id=s1["id"],
        content="Final answer",
        score=92,
        feedback="Well done",
        graded_at=datetime.now(UTC),
        graded_by_faculty_id=fac_row.id,
    )
    db_session.add_all([att_record, submission])
    db_session.commit()

    return {
        "admin": admin,
        "admin_hdr": admin_hdr,
        "s1": s1,
        "s2_hdr": {
            "Authorization": (
                f"Bearer {create_access_token(str(s2['user']['id']), 'student')}"
            )
        },
        "fac_hdr": {
            "Authorization": (
                f"Bearer {create_access_token(str(fac['user']['id']), 'faculty')}"
            )
        },
        "enrollment_id": enrollment.id,
        "att_record_id": att_record.id,
        "submission_id": submission.id,
    }


def test_archive_student_success_retains_records_and_blocks_login(
    client: TestClient,
    db_session: Session,
    archive_world: dict[str, object],
) -> None:
    """Admin archives student; academic records stay intact; login/list blocked."""
    admin = archive_world["admin"]
    admin_hdr = archive_world["admin_hdr"]
    s1 = archive_world["s1"]
    s1_id = s1["id"]

    # Archive student
    resp = client.delete(f"/api/v1/admin/students/{s1_id}", headers=admin_hdr)
    assert resp.status_code == 200
    body = resp.json()
    assert body["student"]["is_archived"] is True
    assert body["student"]["archived_at"] is not None
    assert body["student"]["archived_by_user_id"] == admin.id
    assert body["student"]["user"]["is_active"] is False

    # Already archived student -> 409
    dup = client.delete(f"/api/v1/admin/students/{s1_id}", headers=admin_hdr)
    assert dup.status_code == 409

    # Direct activate while archived -> 409
    assert (
        client.patch(
            f"/api/v1/admin/students/{s1_id}/activate",
            headers=admin_hdr,
        ).status_code
        == 409
    )

    # Archived student cannot log in or use existing JWT
    assert (
        client.post(
            "/api/v1/auth/login",
            json={"email": "arch.s1@example.edu", "password": STRONG_PASSWORD},
        ).status_code
        == 403
    )
    s1_tok = create_access_token(str(s1["user"]["id"]), UserRole.STUDENT.value)
    assert (
        client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {s1_tok}"},
        ).status_code
        == 403
    )

    # Normal listing excludes archived; is_archived=true includes archived
    normal = client.get("/api/v1/admin/students", headers=admin_hdr).json()
    assert all(item["id"] != s1_id for item in normal["items"])

    archived_list = client.get(
        "/api/v1/admin/students",
        headers=admin_hdr,
        params={"is_archived": True},
    ).json()
    assert any(item["id"] == s1_id for item in archived_list["items"])

    # Academic records remain intact
    assert db_session.get(Enrollment, archive_world["enrollment_id"]) is not None
    assert db_session.get(AttendanceRecord, archive_world["att_record_id"]) is not None
    sub = db_session.get(Submission, archive_world["submission_id"])
    assert sub is not None and float(sub.score) == 92.0

    # Restore unarchives profile while keeping login inactive
    restored = client.post(
        f"/api/v1/admin/students/{s1_id}/restore",
        headers=admin_hdr,
    )
    assert restored.status_code == 200
    assert restored.json()["is_archived"] is False
    assert restored.json()["user"]["is_active"] is False


def test_archive_student_permissions_and_not_found(
    client: TestClient,
    archive_world: dict[str, object],
) -> None:
    """Faculty, students, and unauthenticated callers cannot archive; 404 on missing."""
    admin_hdr = archive_world["admin_hdr"]
    s1_id = archive_world["s1"]["id"]

    assert client.delete(f"/api/v1/admin/students/{s1_id}").status_code == 401
    assert (
        client.delete(
            f"/api/v1/admin/students/{s1_id}",
            headers=archive_world["fac_hdr"],
        ).status_code
        == 403
    )
    assert (
        client.delete(
            f"/api/v1/admin/students/{s1_id}",
            headers=archive_world["s2_hdr"],
        ).status_code
        == 403
    )
    assert (
        client.delete(
            "/api/v1/admin/students/999999",
            headers=admin_hdr,
        ).status_code
        == 404
    )


def test_concurrent_archive_requests_safe() -> None:
    """Concurrent DELETE requests on the same student yield one 200 and rest 409."""
    db = SessionLocal()
    created_users: list[int] = []
    created_depts: list[int] = []
    created_students: list[int] = []
    try:
        dept = Department(code="C-ARCH", name="Concurrent Archive Dept")
        db.add(dept)
        db.flush()
        created_depts.append(dept.id)

        admin = User(
            email="carch.admin@example.edu",
            full_name="CArch Admin",
            hashed_password=hash_password(STRONG_PASSWORD),
            role=UserRole.ADMIN,
        )
        stu_user = User(
            email="carch.stu@example.edu",
            full_name="CArch Stu",
            hashed_password=hash_password(STRONG_PASSWORD),
            role=UserRole.STUDENT,
        )
        db.add_all([admin, stu_user])
        db.flush()
        created_users.extend([admin.id, stu_user.id])

        stu = Student(
            user_id=stu_user.id,
            department_id=dept.id,
            roll_number="CARCH-1",
            admission_year=2026,
        )
        db.add(stu)
        db.flush()
        created_students.append(stu.id)
        db.commit()

        admin_hdr = {
            "Authorization": f"Bearer {create_access_token(str(admin.id), 'admin')}"
        }
        with TestClient(app) as client:
            with ThreadPoolExecutor(max_workers=6) as pool:
                futures = [
                    pool.submit(
                        client.delete,
                        f"/api/v1/admin/students/{stu.id}",
                        headers=admin_hdr,
                    )
                    for _ in range(6)
                ]
                codes = [f.result().status_code for f in futures]

        assert codes.count(200) == 1
        assert codes.count(409) == 5

        count = db.scalar(
            select(func.count(Student.id)).where(
                Student.id == stu.id,
                Student.is_archived.is_(True),
            )
        )
        assert count == 1
    finally:
        db.execute(delete(Student).where(Student.id.in_(created_students)))
        db.execute(delete(Department).where(Department.id.in_(created_depts)))
        db.execute(delete(User).where(User.id.in_(created_users)))
        db.commit()
        db.close()


def test_frontend_admin_api_exports_archive_student() -> None:
    """Verify frontend adminApi.js exports archiveStudent and adminPages uses it."""
    from pathlib import Path

    frontend_dir = Path(__file__).resolve().parents[2] / "frontend"
    admin_api = (frontend_dir / "js" / "api" / "adminApi.js").read_text()
    admin_pages = (frontend_dir / "js" / "pages" / "adminPages.js").read_text()

    assert "export const archiveStudent" in admin_api
    assert 'method: "DELETE"' in admin_api
    assert "/admin/students/${id}" in admin_api
    assert "adminApi.archiveStudent(id)" in admin_pages
    assert "import * as adminApi" in admin_pages
