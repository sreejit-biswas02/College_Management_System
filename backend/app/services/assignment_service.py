"""Business logic for Assignments and Student Submissions."""

from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.assignment import Assignment, Submission
from app.models.course_offering import CourseOffering, Enrollment, EnrollmentStatus
from app.models.user import Faculty, Student, User, UserRole
from app.schemas.assignment import (
    AssignmentCreate,
    AssignmentUpdate,
    SubmissionCreate,
    SubmissionGradeRequest,
)
from app.services.exceptions import (
    BusinessRuleError,
    ConflictError,
    ForbiddenError,
    NotFoundError,
    commit_or_conflict,
)


def _authorize_offering_instructor(
    db: Session,
    offering_id: int,
    actor: User,
) -> CourseOffering:
    offering = db.get(CourseOffering, offering_id)
    if offering is None:
        raise NotFoundError("Course offering not found.")
    if actor.role == UserRole.ADMIN:
        return offering
    if actor.role == UserRole.FACULTY and offering.faculty.user_id == actor.id:
        return offering
    raise ForbiddenError("You are not authorized for this course offering.")


def create_assignment(
    db: Session,
    payload: AssignmentCreate,
    actor: User,
) -> Assignment:
    """Publish a new assignment for a course offering."""
    offering = _authorize_offering_instructor(db, payload.course_offering_id, actor)

    if actor.role == UserRole.FACULTY:
        faculty = db.scalar(select(Faculty).where(Faculty.user_id == actor.id))
        if faculty is None:
            raise NotFoundError("Faculty profile not found.")
        creator_id = faculty.id
    else:
        creator_id = offering.faculty_id

    assignment = Assignment(
        course_offering_id=offering.id,
        created_by_faculty_id=creator_id,
        title=payload.title.strip(),
        description=payload.description.strip() if payload.description else None,
        due_at=payload.due_at,
        max_score=payload.max_score,
    )
    db.add(assignment)
    db.commit()
    db.refresh(assignment)
    return assignment


def get_assignment_by_id(
    db: Session,
    assignment_id: int,
    actor: User,
) -> Assignment:
    """Fetch an assignment if actor is Admin, assigned Faculty, or enrolled Student."""
    assignment = db.get(Assignment, assignment_id)
    if assignment is None:
        raise NotFoundError("Assignment not found.")
    _authorize_offering_viewer(db, assignment.course_offering_id, actor)
    return assignment


def update_assignment(
    db: Session,
    assignment_id: int,
    payload: AssignmentUpdate,
    actor: User,
) -> Assignment:
    """Update an assignment (Admin or assigned Faculty)."""
    assignment = db.get(Assignment, assignment_id)
    if assignment is None:
        raise NotFoundError("Assignment not found.")
    _authorize_offering_instructor(db, assignment.course_offering_id, actor)

    if payload.title is not None:
        assignment.title = payload.title.strip()
    if payload.description is not None:
        assignment.description = payload.description.strip() or None
    if payload.due_at is not None:
        assignment.due_at = payload.due_at
    if payload.max_score is not None:
        assignment.max_score = payload.max_score

    db.commit()
    db.refresh(assignment)
    return assignment


def _authorize_offering_viewer(
    db: Session,
    offering_id: int,
    actor: User,
) -> CourseOffering:
    offering = db.get(CourseOffering, offering_id)
    if offering is None:
        raise NotFoundError("Course offering not found.")

    if actor.role == UserRole.FACULTY:
        if offering.faculty.user_id != actor.id:
            raise ForbiddenError("You are not assigned to this course offering.")
    elif actor.role == UserRole.STUDENT:
        student = db.scalar(select(Student).where(Student.user_id == actor.id))
        if student is None:
            raise NotFoundError("Student profile not found.")
        enrolled = db.scalar(
            select(Enrollment).where(
                Enrollment.student_id == student.id,
                Enrollment.course_offering_id == offering_id,
                Enrollment.status == EnrollmentStatus.ENROLLED,
            )
        )
        if enrolled is None:
            raise ForbiddenError("You are not enrolled in this course offering.")
    return offering


def list_assignments_for_offering(
    db: Session,
    offering_id: int,
    actor: User,
    *,
    page: int = 1,
    page_size: int = 20,
) -> tuple[list[Assignment], int]:
    """List assignments for an offering (Admin, assigned Faculty, enrolled Student)."""
    _authorize_offering_viewer(db, offering_id, actor)

    stmt = select(Assignment).where(Assignment.course_offering_id == offering_id)
    count_stmt = select(func.count(Assignment.id)).where(
        Assignment.course_offering_id == offering_id
    )
    total = db.scalar(count_stmt) or 0
    items = list(
        db.scalars(
            stmt.order_by(Assignment.due_at.asc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        ).all()
    )
    return items, total


def submit_assignment(
    db: Session,
    assignment_id: int,
    payload: SubmissionCreate,
    actor: User,
) -> Submission:
    """Submit an assignment as an enrolled student."""
    assignment = db.get(Assignment, assignment_id)
    if assignment is None:
        raise NotFoundError("Assignment not found.")

    student = db.scalar(select(Student).where(Student.user_id == actor.id))
    if student is None:
        raise NotFoundError("Student profile not found.")

    enrolled = db.scalar(
        select(Enrollment).where(
            Enrollment.student_id == student.id,
            Enrollment.course_offering_id == assignment.course_offering_id,
            Enrollment.status == EnrollmentStatus.ENROLLED,
        )
    )
    if enrolled is None:
        raise ForbiddenError("You are not enrolled in this course offering.")

    due_at = (
        assignment.due_at
        if assignment.due_at.tzinfo is not None
        else assignment.due_at.replace(tzinfo=UTC)
    )
    if datetime.now(UTC) > due_at:
        raise BusinessRuleError("Submission deadline has passed.")

    existing = db.scalar(
        select(Submission).where(
            Submission.assignment_id == assignment_id,
            Submission.student_id == student.id,
        )
    )
    if existing is not None:
        raise ConflictError("You have already submitted this assignment.")

    submission = Submission(
        assignment_id=assignment.id,
        student_id=student.id,
        content=payload.content.strip() if payload.content else None,
        file_url=payload.file_url.strip() if payload.file_url else None,
    )
    db.add(submission)
    commit_or_conflict(db, "Duplicate submission.")
    db.refresh(submission)
    return submission


def list_submissions(
    db: Session,
    assignment_id: int,
    actor: User,
    *,
    page: int = 1,
    page_size: int = 20,
) -> tuple[list[Submission], int]:
    """List submissions for an assignment (Admin or assigned Faculty)."""
    assignment = db.get(Assignment, assignment_id)
    if assignment is None:
        raise NotFoundError("Assignment not found.")
    _authorize_offering_instructor(db, assignment.course_offering_id, actor)

    stmt = select(Submission).where(Submission.assignment_id == assignment_id)
    count_stmt = select(func.count(Submission.id)).where(
        Submission.assignment_id == assignment_id
    )
    total = db.scalar(count_stmt) or 0
    items = list(
        db.scalars(
            stmt.order_by(Submission.submitted_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        ).all()
    )
    return items, total


def grade_submission(
    db: Session,
    submission_id: int,
    payload: SubmissionGradeRequest,
    actor: User,
) -> Submission:
    """Grade a student submission (Admin or assigned Faculty)."""
    submission = db.get(Submission, submission_id)
    if submission is None:
        raise NotFoundError("Submission not found.")

    assignment = db.get(Assignment, submission.assignment_id)
    if assignment is None:
        raise NotFoundError("Assignment not found.")

    offering = _authorize_offering_instructor(
        db,
        assignment.course_offering_id,
        actor,
    )

    if payload.score > assignment.max_score:
        raise BusinessRuleError(
            f"Score cannot exceed assignment max_score ({assignment.max_score})."
        )

    if actor.role == UserRole.FACULTY:
        faculty = db.scalar(select(Faculty).where(Faculty.user_id == actor.id))
        grader_id = faculty.id if faculty is not None else offering.faculty_id
    else:
        grader_id = offering.faculty_id

    submission.score = payload.score
    submission.feedback = payload.feedback.strip() if payload.feedback else None
    submission.graded_at = datetime.now(UTC)
    submission.graded_by_faculty_id = grader_id

    db.commit()
    db.refresh(submission)
    return submission


def get_submission_by_id(
    db: Session,
    submission_id: int,
    actor: User,
) -> Submission:
    """Fetch a submission if actor is Admin, assigned Faculty, or owning Student."""
    submission = db.get(Submission, submission_id)
    if submission is None:
        raise NotFoundError("Submission not found.")

    if actor.role == UserRole.ADMIN:
        return submission

    if actor.role == UserRole.STUDENT:
        student = db.scalar(select(Student).where(Student.user_id == actor.id))
        if student is None or submission.student_id != student.id:
            raise ForbiddenError("You do not have access to this submission.")
        return submission

    assignment = db.get(Assignment, submission.assignment_id)
    if assignment is None:
        raise NotFoundError("Assignment not found.")
    _authorize_offering_instructor(db, assignment.course_offering_id, actor)
    return submission


def list_my_submissions(
    db: Session,
    actor: User,
    *,
    page: int = 1,
    page_size: int = 20,
) -> tuple[list[Submission], int]:
    """List submissions belonging to the authenticated student."""
    student = db.scalar(select(Student).where(Student.user_id == actor.id))
    if student is None:
        raise NotFoundError("Student profile not found.")

    stmt = select(Submission).where(Submission.student_id == student.id)
    count_stmt = select(func.count(Submission.id)).where(
        Submission.student_id == student.id
    )
    total = db.scalar(count_stmt) or 0
    items = list(
        db.scalars(
            stmt.order_by(Submission.submitted_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        ).all()
    )
    return items, total
