"""Business logic for Notices and audience targeting."""

from datetime import UTC, datetime

from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.models.academic import Department
from app.models.course_offering import CourseOffering, Enrollment, EnrollmentStatus
from app.models.notice import Notice, NoticeTarget
from app.models.user import Faculty, Student, User, UserRole
from app.schemas.notice import NoticeCreate, NoticeTargetInput, NoticeUpdate
from app.services.exceptions import (
    ConflictError,
    ForbiddenError,
    NotFoundError,
    commit_or_conflict,
)


def _validate_targets(
    db: Session,
    targets: list[NoticeTargetInput],
    actor: User,
) -> None:
    if actor.role == UserRole.FACULTY:
        if not targets:
            raise ForbiddenError(
                "Faculty notices must target at least one assigned course offering."
            )
        faculty = db.scalar(select(Faculty).where(Faculty.user_id == actor.id))
        if faculty is None:
            raise NotFoundError("Faculty profile not found.")
        for t in targets:
            if t.course_offering_id is None:
                raise ForbiddenError(
                    "Faculty can only publish notices scoped to assigned offerings."
                )
            offering = db.get(CourseOffering, t.course_offering_id)
            if offering is None:
                raise NotFoundError("Course offering not found.")
            if offering.faculty_id != faculty.id:
                raise ForbiddenError(
                    "You can only publish notices for your assigned course offerings."
                )
    elif actor.role != UserRole.ADMIN:
        raise ForbiddenError("Only Admin or Faculty can publish notices.")

    seen: set[tuple[UserRole | None, int | None, int | None]] = set()
    for t in targets:
        key = (t.target_role, t.department_id, t.course_offering_id)
        if key in seen:
            raise ConflictError("Duplicate notice target in payload.")
        seen.add(key)
        if t.department_id is not None and db.get(Department, t.department_id) is None:
            raise NotFoundError("Department not found.")
        if (
            t.course_offering_id is not None
            and db.get(CourseOffering, t.course_offering_id) is None
        ):
            raise NotFoundError("Course offering not found.")


def create_notice(db: Session, payload: NoticeCreate, actor: User) -> Notice:
    """Create a notice with optional audience targets."""
    _validate_targets(db, payload.targets, actor)

    notice = Notice(
        title=payload.title.strip(),
        body=payload.body.strip(),
        posted_by_user_id=actor.id,
        is_published=payload.is_published,
        expires_at=payload.expires_at,
    )
    db.add(notice)
    db.flush()

    for target in payload.targets:
        db.add(
            NoticeTarget(
                notice_id=notice.id,
                target_role=target.target_role,
                department_id=target.department_id,
                course_offering_id=target.course_offering_id,
            )
        )

    commit_or_conflict(db, "Notice target conflicts with an existing target.")
    return _get_notice_raw(db, notice.id)


def _notice_load_options() -> tuple:
    return (
        selectinload(Notice.posted_by_user),
        selectinload(Notice.targets).selectinload(NoticeTarget.department),
        selectinload(Notice.targets)
        .selectinload(NoticeTarget.course_offering)
        .selectinload(CourseOffering.course),
        selectinload(Notice.targets)
        .selectinload(NoticeTarget.course_offering)
        .selectinload(CourseOffering.semester),
        selectinload(Notice.targets)
        .selectinload(NoticeTarget.course_offering)
        .selectinload(CourseOffering.faculty)
        .selectinload(Faculty.user),
        selectinload(Notice.targets)
        .selectinload(NoticeTarget.course_offering)
        .selectinload(CourseOffering.faculty)
        .selectinload(Faculty.department),
    )


def _get_notice_raw(db: Session, notice_id: int) -> Notice:
    notice = db.scalar(
        select(Notice).options(*_notice_load_options()).where(Notice.id == notice_id)
    )
    if notice is None:
        raise NotFoundError("Notice not found.")
    return notice


def _user_context(
    db: Session,
    actor: User,
) -> tuple[int | None, set[int]]:
    if actor.role == UserRole.STUDENT:
        student = db.scalar(select(Student).where(Student.user_id == actor.id))
        if student is None:
            return None, set()
        offering_ids = set(
            db.scalars(
                select(Enrollment.course_offering_id).where(
                    Enrollment.student_id == student.id,
                    Enrollment.status == EnrollmentStatus.ENROLLED,
                )
            ).all()
        )
        return student.department_id, offering_ids

    if actor.role == UserRole.FACULTY:
        faculty = db.scalar(select(Faculty).where(Faculty.user_id == actor.id))
        if faculty is None:
            return None, set()
        offering_ids = set(
            db.scalars(
                select(CourseOffering.id).where(CourseOffering.faculty_id == faculty.id)
            ).all()
        )
        return faculty.department_id, offering_ids

    return None, set()


def _is_notice_visible_to_user(
    notice: Notice,
    actor: User,
    dept_id: int | None,
    offering_ids: set[int],
    now: datetime,
) -> bool:
    if actor.role == UserRole.ADMIN or notice.posted_by_user_id == actor.id:
        return True
    if not notice.is_published:
        return False
    if notice.expires_at is not None:
        exp = (
            notice.expires_at
            if notice.expires_at.tzinfo is not None
            else notice.expires_at.replace(tzinfo=UTC)
        )
        if exp <= now:
            return False

    if not notice.targets:
        return True

    for t in notice.targets:
        role_ok = t.target_role is None or t.target_role == actor.role
        dept_ok = t.department_id is None or t.department_id == dept_id
        off_ok = t.course_offering_id is None or t.course_offering_id in offering_ids
        if role_ok and dept_ok and off_ok:
            return True
    return False


def get_notice_by_id(db: Session, notice_id: int, actor: User) -> Notice:
    """Fetch a notice if the user is authorized to view it."""
    notice = _get_notice_raw(db, notice_id)
    dept_id, offering_ids = _user_context(db, actor)
    if not _is_notice_visible_to_user(
        notice, actor, dept_id, offering_ids, datetime.now(UTC)
    ):
        raise ForbiddenError("You do not have permission to view this notice.")
    return notice


def list_visible_notices(
    db: Session,
    actor: User,
    *,
    page: int = 1,
    page_size: int = 20,
) -> tuple[list[Notice], int]:
    """List notices visible to the authenticated user using SQL filtering."""
    stmt = select(Notice).options(*_notice_load_options())
    count_stmt = select(func.count(Notice.id))

    if actor.role != UserRole.ADMIN:
        dept_id, offering_ids = _user_context(db, actor)
        now = datetime.now(UTC)
        target_match = Notice.targets.any(
            and_(
                or_(
                    NoticeTarget.target_role.is_(None),
                    NoticeTarget.target_role == actor.role,
                ),
                or_(
                    NoticeTarget.department_id.is_(None),
                    NoticeTarget.department_id == dept_id,
                ),
                or_(
                    NoticeTarget.course_offering_id.is_(None),
                    NoticeTarget.course_offering_id.in_(offering_ids),
                ),
            )
        )
        visibility_filter = or_(
            Notice.posted_by_user_id == actor.id,
            and_(
                Notice.is_published.is_(True),
                or_(Notice.expires_at.is_(None), Notice.expires_at > now),
                or_(~Notice.targets.any(), target_match),
            ),
        )
        stmt = stmt.where(visibility_filter)
        count_stmt = count_stmt.where(visibility_filter)

    total = db.scalar(count_stmt) or 0
    items = list(
        db.scalars(
            stmt.order_by(Notice.published_at.desc(), Notice.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        ).all()
    )
    return items, total


def update_notice(
    db: Session,
    notice_id: int,
    payload: NoticeUpdate,
    actor: User,
) -> Notice:
    """Update a notice (Admin or the authoring Faculty)."""
    notice = _get_notice_raw(db, notice_id)
    if actor.role != UserRole.ADMIN and notice.posted_by_user_id != actor.id:
        raise ForbiddenError("You do not have permission to modify this notice.")

    if payload.targets is not None:
        _validate_targets(db, payload.targets, actor)
        for existing_target in list(notice.targets):
            db.delete(existing_target)
        db.flush()
        for target in payload.targets:
            db.add(
                NoticeTarget(
                    notice_id=notice.id,
                    target_role=target.target_role,
                    department_id=target.department_id,
                    course_offering_id=target.course_offering_id,
                )
            )

    if payload.title is not None:
        notice.title = payload.title.strip()
    if payload.body is not None:
        notice.body = payload.body.strip()
    if payload.is_published is not None:
        notice.is_published = payload.is_published
    if payload.expires_at is not None:
        notice.expires_at = payload.expires_at

    commit_or_conflict(db, "Notice update conflicts with existing targets.")
    return _get_notice_raw(db, notice.id)


def deactivate_notice(db: Session, notice_id: int, actor: User) -> Notice:
    """Deactivate/unpublish a notice."""
    notice = _get_notice_raw(db, notice_id)
    if actor.role != UserRole.ADMIN and notice.posted_by_user_id != actor.id:
        raise ForbiddenError("You do not have permission to deactivate this notice.")
    notice.is_published = False
    db.commit()
    return _get_notice_raw(db, notice.id)
