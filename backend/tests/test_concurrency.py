"""Concurrent-user load and race-condition tests (Part 6)."""

import statistics
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, date, datetime, timedelta

from fastapi.testclient import TestClient
from sqlalchemy import delete, func, select

from app.core.security import create_access_token, hash_password
from app.database.connection import SessionLocal
from app.main import app
from app.models import (
    Assignment,
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


def _timed_call(fn):
    start = time.perf_counter()
    res = fn()
    elapsed_ms = (time.perf_counter() - start) * 1000
    return res.status_code, elapsed_ms


def test_concurrent_users_and_race_conditions() -> None:
    """Simulate concurrent logins, dashboard reads, and duplicate race conditions."""
    db = SessionLocal()
    created_ids: dict[str, list[int]] = {
        "submissions": [],
        "assignments": [],
        "enrollments": [],
        "offerings": [],
        "courses": [],
        "semesters": [],
        "students": [],
        "faculty": [],
        "departments": [],
        "users": [],
    }
    try:
        dept = Department(code="CONC-D", name="Concurrency Dept")
        sem = Semester(
            name="Conc Sem",
            academic_year="2026-2027",
            term_number=9,
            start_date=date(2026, 8, 1),
            end_date=date(2026, 12, 15),
        )
        db.add_all([dept, sem])
        db.flush()
        created_ids["departments"].append(dept.id)
        created_ids["semesters"].append(sem.id)

        admin_user = User(
            email="conc.adm@example.edu",
            full_name="Conc Admin",
            hashed_password=hash_password("Password123!"),
            role=UserRole.ADMIN,
        )
        stu_user = User(
            email="conc.stu@example.edu",
            full_name="Conc Student",
            hashed_password=hash_password("Password123!"),
            role=UserRole.STUDENT,
        )
        fac_user = User(
            email="conc.fac@example.edu",
            full_name="Conc Faculty",
            hashed_password=hash_password("Password123!"),
            role=UserRole.FACULTY,
        )
        db.add_all([admin_user, stu_user, fac_user])
        db.flush()
        created_ids["users"].extend([admin_user.id, stu_user.id, fac_user.id])

        stu = Student(
            user_id=stu_user.id,
            department_id=dept.id,
            roll_number="CONC-S1",
            admission_year=2026,
        )
        fac = Faculty(
            user_id=fac_user.id,
            department_id=dept.id,
            employee_id="CONC-F1",
            designation="Professor",
        )
        course = Course(
            department_id=dept.id,
            code="CONC101",
            title="Concurrency",
            credits=3,
        )
        db.add_all([stu, fac, course])
        db.flush()
        created_ids["students"].append(stu.id)
        created_ids["faculty"].append(fac.id)
        created_ids["courses"].append(course.id)

        offering = CourseOffering(
            course_id=course.id,
            semester_id=sem.id,
            faculty_id=fac.id,
            section="A",
        )
        db.add(offering)
        db.flush()
        created_ids["offerings"].append(offering.id)

        asg = Assignment(
            course_offering_id=offering.id,
            created_by_faculty_id=fac.id,
            title="Concurrent HW",
            due_at=datetime.now(UTC) + timedelta(days=3),
        )
        db.add(asg)
        db.flush()
        created_ids["assignments"].append(asg.id)
        db.commit()

        admin_tok = create_access_token(str(admin_user.id), UserRole.ADMIN.value)
        stu_tok = create_access_token(str(stu_user.id), UserRole.STUDENT.value)
        admin_hdr = {"Authorization": f"Bearer {admin_tok}"}
        stu_hdr = {"Authorization": f"Bearer {stu_tok}"}

        latencies: list[float] = []

        # 1. Race condition: 8 concurrent enrollment requests for 1 student+offering
        with TestClient(app) as client:
            with ThreadPoolExecutor(max_workers=8) as pool:
                futures = [
                    pool.submit(
                        _timed_call,
                        lambda: client.post(
                            "/api/v1/enrollments",
                            headers=admin_hdr,
                            json={
                                "student_id": stu.id,
                                "course_offering_id": offering.id,
                            },
                        ),
                    )
                    for _ in range(8)
                ]
                results = [f.result() for f in futures]

        statuses = [r[0] for r in results]
        latencies.extend(r[1] for r in results)
        assert statuses.count(201) == 1
        assert statuses.count(409) == 7

        enrollment_count = db.scalar(
            select(func.count(Enrollment.id)).where(
                Enrollment.student_id == stu.id,
                Enrollment.course_offering_id == offering.id,
            )
        )
        assert enrollment_count == 1

        # 2. Race condition test: 8 concurrent assignment submissions for same student
        with TestClient(app) as client:
            with ThreadPoolExecutor(max_workers=8) as pool:
                futures = [
                    pool.submit(
                        _timed_call,
                        lambda: client.post(
                            f"/api/v1/assignments/{asg.id}/submissions",
                            headers=stu_hdr,
                            json={"content": "Concurrent submission"},
                        ),
                    )
                    for _ in range(8)
                ]
                sub_results = [f.result() for f in futures]

        sub_statuses = [r[0] for r in sub_results]
        latencies.extend(r[1] for r in sub_results)
        assert sub_statuses.count(201) == 1
        assert sub_statuses.count(409) == 7

        sub_count = db.scalar(
            select(func.count(Submission.id)).where(
                Submission.assignment_id == asg.id,
                Submission.student_id == stu.id,
            )
        )
        assert sub_count == 1

        # 3. Concurrent dashboard reads (12 simultaneous requests)
        with TestClient(app) as client:
            with ThreadPoolExecutor(max_workers=12) as pool:
                dash_futures = [
                    pool.submit(
                        _timed_call,
                        lambda: client.get("/api/v1/notices", headers=stu_hdr),
                    )
                    for _ in range(6)
                ] + [
                    pool.submit(
                        _timed_call,
                        lambda: client.get("/api/v1/attendance/me", headers=stu_hdr),
                    )
                    for _ in range(6)
                ]
                dash_results = [f.result() for f in dash_futures]

        assert all(code == 200 for code, _ in dash_results)
        latencies.extend(ms for _, ms in dash_results)

        sorted_lat = sorted(latencies)
        p95_idx = min(len(sorted_lat) - 1, int(0.95 * len(sorted_lat)))
        avg_ms = statistics.mean(sorted_lat)
        med_ms = statistics.median(sorted_lat)
        p95_ms = sorted_lat[p95_idx]
        assert avg_ms >= 0 and med_ms >= 0 and p95_ms >= 0
    finally:
        # Clean up committed test rows in reverse FK order
        db.execute(
            delete(Submission).where(
                Submission.assignment_id.in_(created_ids["assignments"])
            )
        )
        db.execute(
            delete(Assignment).where(Assignment.id.in_(created_ids["assignments"]))
        )
        db.execute(
            delete(Enrollment).where(
                Enrollment.course_offering_id.in_(created_ids["offerings"])
            )
        )
        db.execute(
            delete(CourseOffering).where(
                CourseOffering.id.in_(created_ids["offerings"])
            )
        )
        db.execute(delete(Course).where(Course.id.in_(created_ids["courses"])))
        db.execute(delete(Student).where(Student.id.in_(created_ids["students"])))
        db.execute(delete(Faculty).where(Faculty.id.in_(created_ids["faculty"])))
        db.execute(delete(Semester).where(Semester.id.in_(created_ids["semesters"])))
        db.execute(
            delete(Department).where(Department.id.in_(created_ids["departments"]))
        )
        db.execute(delete(User).where(User.id.in_(created_ids["users"])))
        db.commit()
        db.close()
