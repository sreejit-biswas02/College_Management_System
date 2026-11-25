"""Database schema, constraints, relationships, and session tests."""

from collections.abc import Generator
from datetime import UTC, date, datetime, time

import pytest
from sqlalchemy import event, inspect, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database.connection import engine, get_db
from app.models import (
    Assignment,
    AttendanceRecord,
    AttendanceSession,
    AttendanceStatus,
    Course,
    CourseOffering,
    DayOfWeek,
    Department,
    Enrollment,
    EnrollmentStatus,
    Faculty,
    Notice,
    NoticeTarget,
    Semester,
    Student,
    Submission,
    TimetableSlot,
    User,
    UserRole,
)

EXPECTED_TABLES = {
    "users",
    "students",
    "faculty",
    "departments",
    "semesters",
    "courses",
    "course_offerings",
    "enrollments",
    "attendance_sessions",
    "attendance_records",
    "assignments",
    "submissions",
    "notices",
    "notice_targets",
    "timetable_slots",
}


@pytest.fixture()
def db_session() -> Generator[Session, None, None]:
    """Provide an isolated PostgreSQL session rolled back after each test."""
    connection = engine.connect()
    transaction = connection.begin()
    session = Session(bind=connection)
    session.begin_nested()

    @event.listens_for(session, "after_transaction_end")
    def restart_savepoint(sess: Session, trans: object) -> None:
        if connection.closed or transaction.is_active is False:
            return
        if not sess.in_nested_transaction():
            sess.begin_nested()

    try:
        yield session
    finally:
        session.close()
        transaction.rollback()
        connection.close()


def test_all_expected_tables_created() -> None:
    """All 15 domain tables exist in PostgreSQL."""
    inspector = inspect(engine)
    existing_tables = set(inspector.get_table_names())
    assert EXPECTED_TABLES.issubset(existing_tables)


def test_foreign_keys_exist() -> None:
    """Critical tables define expected foreign key references."""
    inspector = inspect(engine)

    student_fks = {
        fk["referred_table"] for fk in inspector.get_foreign_keys("students")
    }
    assert {"users", "departments"} == student_fks

    offering_fks = {
        fk["referred_table"] for fk in inspector.get_foreign_keys("course_offerings")
    }
    assert {"courses", "semesters", "faculty"} == offering_fks

    enrollment_fks = {
        fk["referred_table"] for fk in inspector.get_foreign_keys("enrollments")
    }
    assert {"students", "course_offerings"} == enrollment_fks

    attendance_record_fks = {
        fk["referred_table"] for fk in inspector.get_foreign_keys("attendance_records")
    }
    assert {"attendance_sessions", "students"} == attendance_record_fks


def test_get_db_session_works() -> None:
    """The FastAPI get_db dependency yields a working PostgreSQL session."""
    db_gen = get_db()
    session = next(db_gen)
    try:
        result = session.execute(text("SELECT 1")).scalar_one()
        assert result == 1
    finally:
        db_gen.close()


def _seed_academic_graph(db_session: Session) -> dict[str, object]:
    """Create a minimal connected graph of department, users, course, offering."""
    dept = Department(code="TEST-CSE", name="Test Computer Science")
    db_session.add(dept)
    db_session.flush()

    student_user = User(
        email="student.test@example.edu",
        full_name="Test Student",
        hashed_password="test-hash",
        role=UserRole.STUDENT,
    )
    faculty_user = User(
        email="faculty.test@example.edu",
        full_name="Test Faculty",
        hashed_password="test-hash",
        role=UserRole.FACULTY,
    )
    db_session.add_all([student_user, faculty_user])
    db_session.flush()

    student = Student(
        user_id=student_user.id,
        department_id=dept.id,
        roll_number="TEST-ROLL-001",
        admission_year=2026,
        current_semester_number=1,
    )
    faculty = Faculty(
        user_id=faculty_user.id,
        department_id=dept.id,
        employee_id="TEST-EMP-001",
        designation="Assistant Professor",
    )
    semester = Semester(
        name="Fall 2026",
        academic_year="2026-2027",
        term_number=1,
        start_date=date(2026, 8, 1),
        end_date=date(2026, 12, 15),
        is_active=True,
    )
    course = Course(
        department_id=dept.id,
        code="TEST-CS101",
        title="Intro to CS",
        credits=4,
    )
    db_session.add_all([student, faculty, semester, course])
    db_session.flush()

    offering = CourseOffering(
        course_id=course.id,
        semester_id=semester.id,
        faculty_id=faculty.id,
        section="A",
        max_capacity=60,
    )
    db_session.add(offering)
    db_session.flush()

    return {
        "department": dept,
        "student_user": student_user,
        "faculty_user": faculty_user,
        "student": student,
        "faculty": faculty,
        "semester": semester,
        "course": course,
        "offering": offering,
    }


def test_relationships_work_correctly(db_session: Session) -> None:
    """ORM relationships resolve across all academic and communication models."""
    graph = _seed_academic_graph(db_session)
    student: Student = graph["student"]  # type: ignore[assignment]
    faculty: Faculty = graph["faculty"]  # type: ignore[assignment]
    offering: CourseOffering = graph["offering"]  # type: ignore[assignment]
    faculty_user: User = graph["faculty_user"]  # type: ignore[assignment]
    dept: Department = graph["department"]  # type: ignore[assignment]

    enrollment = Enrollment(
        student_id=student.id,
        course_offering_id=offering.id,
        status=EnrollmentStatus.ENROLLED,
    )
    session = AttendanceSession(
        course_offering_id=offering.id,
        conducted_by_faculty_id=faculty.id,
        session_date=date(2026, 9, 1),
        session_number=1,
        start_time=time(9, 0),
        topic="Course Introduction",
    )
    assignment = Assignment(
        course_offering_id=offering.id,
        created_by_faculty_id=faculty.id,
        title="Lab 1",
        due_at=datetime(2026, 9, 15, 23, 59, tzinfo=UTC),
    )
    slot = TimetableSlot(
        course_offering_id=offering.id,
        day_of_week=DayOfWeek.MONDAY,
        start_time=time(9, 0),
        end_time=time(10, 0),
        room="Room 101",
    )
    notice = Notice(
        title="Welcome",
        body="Classes start Monday.",
        posted_by_user_id=faculty_user.id,
    )
    db_session.add_all([enrollment, session, assignment, slot, notice])
    db_session.flush()

    record = AttendanceRecord(
        session_id=session.id,
        student_id=student.id,
        status=AttendanceStatus.PRESENT,
    )
    submission = Submission(
        assignment_id=assignment.id,
        student_id=student.id,
        content="Solution attached",
    )
    target = NoticeTarget(
        notice_id=notice.id,
        target_role=UserRole.STUDENT,
        department_id=dept.id,
        course_offering_id=offering.id,
    )
    db_session.add_all([record, submission, target])
    db_session.flush()

    assert student.user.email == "student.test@example.edu"
    assert student.department.code == "TEST-CSE"
    assert offering.course.code == "TEST-CS101"
    assert offering.enrollments[0].student.roll_number == "TEST-ROLL-001"
    assert session.records[0].status == AttendanceStatus.PRESENT
    assert assignment.submissions[0].student_id == student.id
    assert notice.targets[0].target_role == UserRole.STUDENT
    assert offering.timetable_slots[0].room == "Room 101"


def test_duplicate_enrollment_rejected(db_session: Session) -> None:
    """Enrolling the same student twice in the same offering raises IntegrityError."""
    graph = _seed_academic_graph(db_session)
    student: Student = graph["student"]  # type: ignore[assignment]
    offering: CourseOffering = graph["offering"]  # type: ignore[assignment]

    db_session.add(Enrollment(student_id=student.id, course_offering_id=offering.id))
    db_session.flush()

    db_session.add(Enrollment(student_id=student.id, course_offering_id=offering.id))
    with pytest.raises(IntegrityError):
        db_session.flush()


def test_duplicate_attendance_record_rejected(db_session: Session) -> None:
    """Recording attendance twice for the same student in one session fails."""
    graph = _seed_academic_graph(db_session)
    student: Student = graph["student"]  # type: ignore[assignment]
    faculty: Faculty = graph["faculty"]  # type: ignore[assignment]
    offering: CourseOffering = graph["offering"]  # type: ignore[assignment]

    att_session = AttendanceSession(
        course_offering_id=offering.id,
        conducted_by_faculty_id=faculty.id,
        session_date=date(2026, 9, 2),
        session_number=1,
    )
    db_session.add(att_session)
    db_session.flush()

    db_session.add(
        AttendanceRecord(
            session_id=att_session.id,
            student_id=student.id,
            status=AttendanceStatus.PRESENT,
        )
    )
    db_session.flush()

    db_session.add(
        AttendanceRecord(
            session_id=att_session.id,
            student_id=student.id,
            status=AttendanceStatus.ABSENT,
        )
    )
    with pytest.raises(IntegrityError):
        db_session.flush()


def test_unique_user_email_enforced(db_session: Session) -> None:
    """Duplicate user emails raise IntegrityError."""
    db_session.add(
        User(
            email="dup@example.edu",
            full_name="User One",
            hashed_password="test-hash",
            role=UserRole.ADMIN,
        )
    )
    db_session.flush()

    db_session.add(
        User(
            email="dup@example.edu",
            full_name="User Two",
            hashed_password="test-hash",
            role=UserRole.ADMIN,
        )
    )
    with pytest.raises(IntegrityError):
        db_session.flush()


def test_invalid_foreign_key_rejected(db_session: Session) -> None:
    """Inserting a record with a nonexistent foreign key raises IntegrityError."""
    db_session.add(
        Course(
            department_id=999999,
            code="INVALID-FK",
            title="Invalid Dept Course",
            credits=3,
        )
    )
    with pytest.raises(IntegrityError):
        db_session.flush()
