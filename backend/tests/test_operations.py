"""Automated tests for Phase 3 Part 2: Academic Operations."""

from collections.abc import Generator
from datetime import UTC, date, datetime, timedelta

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
def world(client: TestClient, db_session: Session) -> dict[str, object]:
    """Seed an admin, 2 students, 2 faculty, dept, semester, and 2 offerings."""
    admin = create_admin_user(
        db_session,
        AdminCreateRequest(
            email="ops.admin@example.edu",
            full_name="Ops Admin",
            password=STRONG_PASSWORD,
        ),
    )
    admin_hdr = {
        "Authorization": f"Bearer {create_access_token(str(admin.id), 'admin')}"
    }

    dept = Department(code="OPS-CSE", name="Ops Computer Science")
    semester = Semester(
        name="Fall 2026",
        academic_year="2026-2027",
        term_number=1,
        start_date=date(2026, 8, 1),
        end_date=date(2026, 12, 15),
        is_active=True,
    )
    db_session.add_all([dept, semester])
    db_session.flush()

    course1 = Course(
        department_id=dept.id,
        code="OPS101",
        title="Algorithms",
        credits=4,
    )
    course2 = Course(
        department_id=dept.id,
        code="OPS102",
        title="Databases",
        credits=3,
    )
    db_session.add_all([course1, course2])
    db_session.commit()

    def _make_student(email: str, roll: str) -> tuple[int, dict[str, str]]:
        resp = client.post(
            "/api/v1/admin/students",
            headers=admin_hdr,
            json={
                "email": email,
                "full_name": f"Student {roll}",
                "password": STRONG_PASSWORD,
                "department_id": dept.id,
                "roll_number": roll,
                "admission_year": 2026,
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        tok = create_access_token(str(data["user"]["id"]), UserRole.STUDENT.value)
        return data["id"], {"Authorization": f"Bearer {tok}"}

    def _make_faculty(email: str, emp: str) -> tuple[int, dict[str, str]]:
        resp = client.post(
            "/api/v1/admin/faculty",
            headers=admin_hdr,
            json={
                "email": email,
                "full_name": f"Faculty {emp}",
                "password": STRONG_PASSWORD,
                "department_id": dept.id,
                "employee_id": emp,
                "designation": "Professor",
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        tok = create_access_token(str(data["user"]["id"]), UserRole.FACULTY.value)
        return data["id"], {"Authorization": f"Bearer {tok}"}

    s1_id, s1_hdr = _make_student("s1.ops@example.edu", "OPS-S1")
    s2_id, s2_hdr = _make_student("s2.ops@example.edu", "OPS-S2")
    f1_id, f1_hdr = _make_faculty("f1.ops@example.edu", "OPS-F1")
    f2_id, f2_hdr = _make_faculty("f2.ops@example.edu", "OPS-F2")

    off1 = CourseOffering(
        course_id=course1.id,
        semester_id=semester.id,
        faculty_id=f1_id,
        section="A",
        max_capacity=2,
    )
    off2 = CourseOffering(
        course_id=course2.id,
        semester_id=semester.id,
        faculty_id=f2_id,
        section="A",
        max_capacity=5,
    )
    db_session.add_all([off1, off2])
    db_session.commit()
    db_session.refresh(off1)
    db_session.refresh(off2)

    assert db_session.get(Student, s1_id) is not None
    assert db_session.get(Faculty, f1_id) is not None

    return {
        "admin_hdr": admin_hdr,
        "dept": dept,
        "semester": semester,
        "s1_id": s1_id,
        "s1_hdr": s1_hdr,
        "s2_id": s2_id,
        "s2_hdr": s2_hdr,
        "f1_id": f1_id,
        "f1_hdr": f1_hdr,
        "f2_id": f2_id,
        "f2_hdr": f2_hdr,
        "off1_id": off1.id,
        "off2_id": off2.id,
    }


def test_enrollment_lifecycle_and_permissions(
    client: TestClient,
    world: dict[str, object],
) -> None:
    """Enrollment creation, duplicate prevention, invalid FKs, and ownership."""
    admin_hdr = world["admin_hdr"]
    s1_id, s1_hdr = world["s1_id"], world["s1_hdr"]
    s2_hdr = world["s2_hdr"]
    f1_hdr, f2_hdr = world["f1_hdr"], world["f2_hdr"]
    off1_id = world["off1_id"]

    # Student/Faculty cannot enroll
    assert (
        client.post(
            "/api/v1/enrollments",
            headers=s1_hdr,
            json={"student_id": s1_id, "course_offering_id": off1_id},
        ).status_code
        == 403
    )

    # Admin enrolls student 1
    r1 = client.post(
        "/api/v1/enrollments",
        headers=admin_hdr,
        json={"student_id": s1_id, "course_offering_id": off1_id},
    )
    assert r1.status_code == 201
    eid = r1.json()["id"]

    # Duplicate enrollment rejected
    assert (
        client.post(
            "/api/v1/enrollments",
            headers=admin_hdr,
            json={"student_id": s1_id, "course_offering_id": off1_id},
        ).status_code
        == 409
    )

    # Invalid references rejected
    assert (
        client.post(
            "/api/v1/enrollments",
            headers=admin_hdr,
            json={"student_id": 999999, "course_offering_id": off1_id},
        ).status_code
        == 404
    )

    # Student 1 sees own enrollment; Student 2 does not
    assert (
        len(client.get("/api/v1/enrollments/me", headers=s1_hdr).json()["items"]) == 1
    )
    assert (
        len(client.get("/api/v1/enrollments/me", headers=s2_hdr).json()["items"]) == 0
    )

    # Assigned faculty sees offering enrollments; unassigned faculty gets 403
    assert (
        client.get(
            f"/api/v1/enrollments/offerings/{off1_id}",
            headers=f1_hdr,
        ).status_code
        == 200
    )
    assert (
        client.get(
            f"/api/v1/enrollments/offerings/{off1_id}",
            headers=f2_hdr,
        ).status_code
        == 403
    )

    # Update status
    upd = client.patch(
        f"/api/v1/enrollments/{eid}",
        headers=admin_hdr,
        json={"status": "completed"},
    )
    assert upd.status_code == 200
    assert upd.json()["status"] == "completed"


def test_attendance_sessions_marking_and_percentage(
    client: TestClient,
    world: dict[str, object],
) -> None:
    """Attendance creation, updating, percentage calculation, and permissions."""
    admin_hdr = world["admin_hdr"]
    s1_id, s1_hdr = world["s1_id"], world["s1_hdr"]
    f1_hdr, f2_hdr = world["f1_hdr"], world["f2_hdr"]
    off1_id = world["off1_id"]

    client.post(
        "/api/v1/enrollments",
        headers=admin_hdr,
        json={"student_id": s1_id, "course_offering_id": off1_id},
    )

    # Unassigned faculty and student cannot create attendance sessions
    assert (
        client.post(
            "/api/v1/attendance/sessions",
            headers=f2_hdr,
            json={
                "course_offering_id": off1_id,
                "session_date": "2026-09-01",
                "session_number": 1,
            },
        ).status_code
        == 403
    )
    assert (
        client.post(
            "/api/v1/attendance/sessions",
            headers=s1_hdr,
            json={
                "course_offering_id": off1_id,
                "session_date": "2026-09-01",
                "session_number": 1,
            },
        ).status_code
        == 403
    )

    # Assigned faculty creates session 1 (present) and session 2 (absent)
    sess1 = client.post(
        "/api/v1/attendance/sessions",
        headers=f1_hdr,
        json={
            "course_offering_id": off1_id,
            "session_date": "2026-09-01",
            "session_number": 1,
            "records": [{"student_id": s1_id, "status": "present"}],
        },
    )
    assert sess1.status_code == 201
    sess1_id = sess1.json()["id"]

    sess2 = client.post(
        "/api/v1/attendance/sessions",
        headers=f1_hdr,
        json={
            "course_offering_id": off1_id,
            "session_date": "2026-09-02",
            "session_number": 1,
            "records": [{"student_id": s1_id, "status": "absent"}],
        },
    )
    assert sess2.status_code == 201

    # Check percentage: 1 present / 2 total = 50.0%
    summary = client.get("/api/v1/attendance/me", headers=s1_hdr).json()
    assert summary["total_sessions"] == 2
    assert summary["attendance_percentage"] == 50.0

    # Update session 1 record to late; attended = 1 (late) / 2 = 50.0%,
    # then update session 2 to present -> 100.0%
    upd = client.put(
        f"/api/v1/attendance/sessions/{sess1_id}/records",
        headers=f1_hdr,
        json={"records": [{"student_id": s1_id, "status": "late"}]},
    )
    assert upd.status_code == 200
    client.put(
        f"/api/v1/attendance/sessions/{sess2.json()['id']}/records",
        headers=f1_hdr,
        json={"records": [{"student_id": s1_id, "status": "present"}]},
    )
    summary2 = client.get("/api/v1/attendance/me", headers=s1_hdr).json()
    assert summary2["attendance_percentage"] == 100.0


def test_assignments_submissions_and_grading(
    client: TestClient,
    world: dict[str, object],
) -> None:
    """Assignment lifecycle, student submission, ownership, and score validation."""
    admin_hdr = world["admin_hdr"]
    s1_id, s1_hdr = world["s1_id"], world["s1_hdr"]
    s2_hdr = world["s2_hdr"]
    f1_hdr, f2_hdr = world["f1_hdr"], world["f2_hdr"]
    off1_id = world["off1_id"]

    client.post(
        "/api/v1/enrollments",
        headers=admin_hdr,
        json={"student_id": s1_id, "course_offering_id": off1_id},
    )

    future_due = (datetime.now(UTC) + timedelta(days=7)).isoformat()
    # Unassigned faculty cannot create assignment
    assert (
        client.post(
            "/api/v1/assignments",
            headers=f2_hdr,
            json={
                "course_offering_id": off1_id,
                "title": "HW1",
                "due_at": future_due,
                "max_score": 50,
            },
        ).status_code
        == 403
    )

    # Assigned faculty creates & updates assignment
    a_resp = client.post(
        "/api/v1/assignments",
        headers=f1_hdr,
        json={
            "course_offering_id": off1_id,
            "title": "HW1",
            "due_at": future_due,
            "max_score": 50,
        },
    )
    assert a_resp.status_code == 201
    aid = a_resp.json()["id"]

    assert (
        client.patch(
            f"/api/v1/assignments/{aid}",
            headers=f1_hdr,
            json={"title": "HW1 Updated"},
        ).json()["title"]
        == "HW1 Updated"
    )

    # Unenrolled student 2 cannot submit
    assert (
        client.post(
            f"/api/v1/assignments/{aid}/submissions",
            headers=s2_hdr,
            json={"content": "My answer"},
        ).status_code
        == 403
    )

    # Enrolled student 1 submits
    sub_resp = client.post(
        f"/api/v1/assignments/{aid}/submissions",
        headers=s1_hdr,
        json={"content": "Here is my solution."},
    )
    assert sub_resp.status_code == 201
    sub_id = sub_resp.json()["id"]

    # Student 2 cannot view Student 1's submission
    assert (
        client.get(
            f"/api/v1/submissions/{sub_id}",
            headers=s2_hdr,
        ).status_code
        == 403
    )

    # Score > max_score (50) rejected with 422
    assert (
        client.patch(
            f"/api/v1/submissions/{sub_id}/grade",
            headers=f1_hdr,
            json={"score": 60, "feedback": "Too high"},
        ).status_code
        == 422
    )

    # Valid grade succeeds
    graded = client.patch(
        f"/api/v1/submissions/{sub_id}/grade",
        headers=f1_hdr,
        json={"score": 45, "feedback": "Great work"},
    )
    assert graded.status_code == 200
    assert float(graded.json()["score"]) == 45.0


def test_notices_targeting_and_visibility(
    client: TestClient,
    world: dict[str, object],
) -> None:
    """Notice targeting respects role and offering assignment."""
    admin_hdr = world["admin_hdr"]
    s1_id, s1_hdr = world["s1_id"], world["s1_hdr"]
    f1_hdr, f2_hdr = world["f1_hdr"], world["f2_hdr"]
    off1_id = world["off1_id"]

    client.post(
        "/api/v1/enrollments",
        headers=admin_hdr,
        json={"student_id": s1_id, "course_offering_id": off1_id},
    )

    # Admin posts student-only notice
    n_admin = client.post(
        "/api/v1/notices",
        headers=admin_hdr,
        json={
            "title": "Student Orientation",
            "body": "Welcome!",
            "targets": [{"target_role": "student"}],
        },
    )
    assert n_admin.status_code == 201

    # Faculty 1 cannot post notice for Faculty 2's offering or global notice
    assert (
        client.post(
            "/api/v1/notices",
            headers=f1_hdr,
            json={"title": "Global", "body": "Denied", "targets": []},
        ).status_code
        == 403
    )

    # Faculty 1 posts notice for off1
    n_fac = client.post(
        "/api/v1/notices",
        headers=f1_hdr,
        json={
            "title": "Algorithms Exam",
            "body": "Friday 9am",
            "targets": [{"course_offering_id": off1_id}],
        },
    )
    assert n_fac.status_code == 201

    # Student 1 sees both notices; Faculty 2 sees neither
    s1_notices = client.get("/api/v1/notices", headers=s1_hdr).json()["items"]
    assert len(s1_notices) == 2
    f2_notices = client.get("/api/v1/notices", headers=f2_hdr).json()["items"]
    assert len(f2_notices) == 0


def test_timetable_creation_overlap_and_views(
    client: TestClient,
    world: dict[str, object],
) -> None:
    """Timetable overlap prevention and personal timetable views."""
    admin_hdr = world["admin_hdr"]
    s1_id, s1_hdr = world["s1_id"], world["s1_hdr"]
    f1_hdr = world["f1_hdr"]
    off1_id = world["off1_id"]

    client.post(
        "/api/v1/enrollments",
        headers=admin_hdr,
        json={"student_id": s1_id, "course_offering_id": off1_id},
    )

    # Student cannot create timetable slot
    assert (
        client.post(
            "/api/v1/timetable",
            headers=s1_hdr,
            json={
                "course_offering_id": off1_id,
                "day_of_week": "monday",
                "start_time": "09:00:00",
                "end_time": "10:00:00",
                "room": "R101",
            },
        ).status_code
        == 403
    )

    # Admin creates slot
    slot = client.post(
        "/api/v1/timetable",
        headers=admin_hdr,
        json={
            "course_offering_id": off1_id,
            "day_of_week": "monday",
            "start_time": "09:00:00",
            "end_time": "10:00:00",
            "room": "R101",
        },
    )
    assert slot.status_code == 201

    # Overlapping slot rejected with 409
    assert (
        client.post(
            "/api/v1/timetable",
            headers=admin_hdr,
            json={
                "course_offering_id": off1_id,
                "day_of_week": "monday",
                "start_time": "09:30:00",
                "end_time": "10:30:00",
                "room": "R102",
            },
        ).status_code
        == 409
    )

    # Both enrolled student and assigned faculty see the slot in /timetable/me
    assert len(client.get("/api/v1/timetable/me", headers=s1_hdr).json()) == 1
    assert len(client.get("/api/v1/timetable/me", headers=f1_hdr).json()) == 1
