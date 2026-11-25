"""Negative, edge-case, and dedicated RBAC/ownership tests (Parts 2 & 3)."""

from collections.abc import Generator
from datetime import UTC, date, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.security import create_access_token
from app.database.connection import engine, get_db
from app.main import app
from app.models import (
    Assignment,
    Course,
    CourseOffering,
    Department,
    Faculty,
    Notice,
    Semester,
    Submission,
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


def test_invalid_pagination_and_missing_fields(
    client: TestClient,
    db_session: Session,
) -> None:
    """Invalid pagination params and missing required fields return 422."""
    admin = create_admin_user(
        db_session,
        AdminCreateRequest(
            email="edge.admin@example.edu",
            full_name="Edge Admin",
            password=STRONG_PASSWORD,
        ),
    )
    hdr = {"Authorization": f"Bearer {create_access_token(str(admin.id), 'admin')}"}

    assert (
        client.get(
            "/api/v1/admin/students",
            headers=hdr,
            params={"page": 0},
        ).status_code
        == 422
    )
    assert (
        client.get(
            "/api/v1/admin/students",
            headers=hdr,
            params={"page_size": 500},
        ).status_code
        == 422
    )
    assert (
        client.post(
            "/api/v1/admin/departments",
            headers=hdr,
            json={"code": "ONLYCODE"},
        ).status_code
        == 422
    )


def test_empty_database_list_results(
    client: TestClient,
    db_session: Session,
) -> None:
    """Listing an empty dataset returns clean PaginatedResponse with 0 items."""
    admin = create_admin_user(
        db_session,
        AdminCreateRequest(
            email="empty.admin@example.edu",
            full_name="Empty Admin",
            password=STRONG_PASSWORD,
        ),
    )
    hdr = {"Authorization": f"Bearer {create_access_token(str(admin.id), 'admin')}"}

    resp = client.get(
        "/api/v1/admin/students",
        headers=hdr,
        params={"search": "definitely-no-match-xyz"},
    )
    assert resp.status_code == 200
    assert resp.json() == {
        "items": [],
        "total": 0,
        "page": 1,
        "page_size": 20,
        "pages": 0,
    }


def test_late_submission_and_invalid_attendance_status(
    client: TestClient,
    db_session: Session,
) -> None:
    """Late submissions and invalid attendance statuses are rejected with 422."""
    admin = create_admin_user(
        db_session,
        AdminCreateRequest(
            email="late.admin@example.edu",
            full_name="Late Admin",
            password=STRONG_PASSWORD,
        ),
    )
    admin_hdr = {
        "Authorization": f"Bearer {create_access_token(str(admin.id), 'admin')}"
    }
    dept = Department(code="EDGE-D", name="Edge Dept")
    sem = Semester(
        name="Edge Sem",
        academic_year="2026-2027",
        term_number=1,
        start_date=date(2026, 8, 1),
        end_date=date(2026, 12, 15),
    )
    db_session.add_all([dept, sem])
    db_session.commit()

    stu = client.post(
        "/api/v1/admin/students",
        headers=admin_hdr,
        json={
            "email": "edge.stu@example.edu",
            "full_name": "Edge Student",
            "password": STRONG_PASSWORD,
            "department_id": dept.id,
            "roll_number": "EDGE-1",
            "admission_year": 2026,
        },
    ).json()
    fac = client.post(
        "/api/v1/admin/faculty",
        headers=admin_hdr,
        json={
            "email": "edge.fac@example.edu",
            "full_name": "Edge Faculty",
            "password": STRONG_PASSWORD,
            "department_id": dept.id,
            "employee_id": "EDGE-F1",
            "designation": "Lecturer",
        },
    ).json()

    course = Course(
        department_id=dept.id,
        code="EDGE101",
        title="Edge Course",
        credits=3,
    )
    db_session.add(course)
    db_session.flush()
    offering = CourseOffering(
        course_id=course.id,
        semester_id=sem.id,
        faculty_id=fac["id"],
        section="A",
    )
    db_session.add(offering)
    db_session.commit()

    client.post(
        "/api/v1/enrollments",
        headers=admin_hdr,
        json={"student_id": stu["id"], "course_offering_id": offering.id},
    )

    fac_tok = create_access_token(str(fac["user"]["id"]), "faculty")
    stu_tok = create_access_token(str(stu["user"]["id"]), "student")
    fac_hdr = {"Authorization": f"Bearer {fac_tok}"}
    stu_hdr = {"Authorization": f"Bearer {stu_tok}"}

    # Invalid attendance status -> 422
    assert (
        client.post(
            "/api/v1/attendance/sessions",
            headers=fac_hdr,
            json={
                "course_offering_id": offering.id,
                "session_date": "2026-09-10",
                "session_number": 1,
                "records": [{"student_id": stu["id"], "status": "unknown_status"}],
            },
        ).status_code
        == 422
    )

    # Past-deadline assignment -> 422 on submission
    past_due = datetime.now(UTC) - timedelta(hours=2)
    asg = Assignment(
        course_offering_id=offering.id,
        created_by_faculty_id=fac["id"],
        title="Expired HW",
        due_at=past_due,
    )
    db_session.add(asg)
    db_session.commit()

    assert (
        client.post(
            f"/api/v1/assignments/{asg.id}/submissions",
            headers=stu_hdr,
            json={"content": "Late submission"},
        ).status_code
        == 422
    )


def test_dedicated_ownership_and_privilege_escalation_blocks(
    client: TestClient,
    db_session: Session,
) -> None:
    """Students and unassigned faculty cannot escalate privileges via resource IDs."""
    admin = create_admin_user(
        db_session,
        AdminCreateRequest(
            email="rbac.admin@example.edu",
            full_name="RBAC Admin",
            password=STRONG_PASSWORD,
        ),
    )
    admin_hdr = {
        "Authorization": f"Bearer {create_access_token(str(admin.id), 'admin')}"
    }
    dept = Department(code="RBAC-D", name="RBAC Dept")
    sem = Semester(
        name="RBAC Sem",
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
            "email": "rbac.s1@example.edu",
            "full_name": "RBAC S1",
            "password": STRONG_PASSWORD,
            "department_id": dept.id,
            "roll_number": "RBAC-S1",
            "admission_year": 2026,
        },
    ).json()
    f1 = client.post(
        "/api/v1/admin/faculty",
        headers=admin_hdr,
        json={
            "email": "rbac.f1@example.edu",
            "full_name": "RBAC F1",
            "password": STRONG_PASSWORD,
            "department_id": dept.id,
            "employee_id": "RBAC-F1",
            "designation": "Professor",
        },
    ).json()
    f2 = client.post(
        "/api/v1/admin/faculty",
        headers=admin_hdr,
        json={
            "email": "rbac.f2@example.edu",
            "full_name": "RBAC F2",
            "password": STRONG_PASSWORD,
            "department_id": dept.id,
            "employee_id": "RBAC-F2",
            "designation": "Professor",
        },
    ).json()

    course = Course(
        department_id=dept.id,
        code="RBAC101",
        title="RBAC Course",
        credits=3,
    )
    db_session.add(course)
    db_session.flush()
    fac1 = db_session.get(Faculty, f1["id"])
    assert fac1 is not None
    offering = CourseOffering(
        course_id=course.id,
        semester_id=sem.id,
        faculty_id=fac1.id,
        section="A",
    )
    db_session.add(offering)
    db_session.flush()

    asg = Assignment(
        course_offering_id=offering.id,
        created_by_faculty_id=fac1.id,
        title="RBAC HW",
        due_at=datetime.now(UTC) + timedelta(days=5),
    )
    db_session.add(asg)
    db_session.flush()

    sub = Submission(
        assignment_id=asg.id,
        student_id=s1["id"],
        content="My work",
    )
    notice = Notice(
        title="Admin Notice",
        body="Important",
        posted_by_user_id=admin.id,
    )
    db_session.add_all([sub, notice])
    db_session.commit()

    s1_tok = create_access_token(str(s1["user"]["id"]), UserRole.STUDENT.value)
    f2_tok = create_access_token(str(f2["user"]["id"]), UserRole.FACULTY.value)
    s1_hdr = {"Authorization": f"Bearer {s1_tok}"}
    f2_hdr = {"Authorization": f"Bearer {f2_tok}"}

    # Student cannot grade submission, mark attendance, or manage notices
    assert (
        client.patch(
            f"/api/v1/submissions/{sub.id}/grade",
            headers=s1_hdr,
            json={"score": 100},
        ).status_code
        == 403
    )
    assert (
        client.post(
            "/api/v1/attendance/sessions",
            headers=s1_hdr,
            json={"course_offering_id": offering.id, "session_date": "2026-09-11"},
        ).status_code
        == 403
    )
    assert (
        client.post(
            "/api/v1/notices",
            headers=s1_hdr,
            json={"title": "Fake", "body": "Nope"},
        ).status_code
        == 403
    )
    assert (
        client.patch(
            f"/api/v1/notices/{notice.id}/deactivate",
            headers=s1_hdr,
        ).status_code
        == 403
    )

    # Unassigned faculty F2 cannot grade F1's submission or update F1's assignment
    assert (
        client.patch(
            f"/api/v1/submissions/{sub.id}/grade",
            headers=f2_hdr,
            json={"score": 80},
        ).status_code
        == 403
    )
    assert (
        client.patch(
            f"/api/v1/assignments/{asg.id}",
            headers=f2_hdr,
            json={"title": "Hijacked"},
        ).status_code
        == 403
    )
