"""Business logic for Departments, Semesters, and Courses."""

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, joinedload

from app.models.academic import Course, Department, Semester
from app.schemas.academic import (
    CourseCreate,
    CourseUpdate,
    DepartmentCreate,
    DepartmentUpdate,
    SemesterCreate,
    SemesterUpdate,
)
from app.services.exceptions import (
    BusinessRuleError,
    ConflictError,
    NotFoundError,
    commit_or_conflict,
)

# --- Departments ---


def create_department(db: Session, payload: DepartmentCreate) -> Department:
    """Create a new academic department."""
    code = payload.code.strip().upper()
    name = payload.name.strip()

    existing = db.scalar(
        select(Department).where(or_(Department.code == code, Department.name == name))
    )
    if existing is not None:
        raise ConflictError("Department code or name already exists.")

    dept = Department(
        code=code,
        name=name,
        description=payload.description.strip() if payload.description else None,
        is_active=payload.is_active,
    )
    db.add(dept)
    commit_or_conflict(db, "Department code or name already exists.")
    db.refresh(dept)
    return dept


def get_department_by_id(db: Session, department_id: int) -> Department:
    """Fetch a department by ID."""
    dept = db.get(Department, department_id)
    if dept is None:
        raise NotFoundError("Department not found.")
    return dept


def list_departments(
    db: Session,
    *,
    search: str | None = None,
    is_active: bool | None = None,
    page: int = 1,
    page_size: int = 20,
) -> tuple[list[Department], int]:
    """List departments with search, active filter, and pagination."""
    stmt = select(Department)
    count_stmt = select(func.count(Department.id))

    filters = []
    if search:
        pattern = f"%{search.strip()}%"
        filters.append(
            or_(Department.code.ilike(pattern), Department.name.ilike(pattern))
        )
    if is_active is not None:
        filters.append(Department.is_active == is_active)

    if filters:
        stmt = stmt.where(*filters)
        count_stmt = count_stmt.where(*filters)

    total = db.scalar(count_stmt) or 0
    items = list(
        db.scalars(
            stmt.order_by(Department.id.asc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        ).all()
    )
    return items, total


def update_department(
    db: Session,
    department_id: int,
    payload: DepartmentUpdate,
) -> Department:
    """Update a department's attributes."""
    dept = get_department_by_id(db, department_id)

    if payload.code is not None:
        code = payload.code.strip().upper()
        if (
            db.scalar(
                select(Department).where(
                    Department.code == code,
                    Department.id != dept.id,
                )
            )
            is not None
        ):
            raise ConflictError("Department code already exists.")
        dept.code = code

    if payload.name is not None:
        name = payload.name.strip()
        if (
            db.scalar(
                select(Department).where(
                    Department.name == name,
                    Department.id != dept.id,
                )
            )
            is not None
        ):
            raise ConflictError("Department name already exists.")
        dept.name = name

    if payload.description is not None:
        dept.description = payload.description.strip() or None
    if payload.is_active is not None:
        dept.is_active = payload.is_active

    commit_or_conflict(db, "Department code or name already exists.")
    db.refresh(dept)
    return dept


def set_department_active_status(
    db: Session,
    department_id: int,
    is_active: bool,
) -> Department:
    """Activate or deactivate a department."""
    dept = get_department_by_id(db, department_id)
    dept.is_active = is_active
    db.commit()
    db.refresh(dept)
    return dept


# --- Semesters ---


def create_semester(db: Session, payload: SemesterCreate) -> Semester:
    """Create a new academic semester."""
    academic_year = payload.academic_year.strip()
    existing = db.scalar(
        select(Semester).where(
            Semester.academic_year == academic_year,
            Semester.term_number == payload.term_number,
        )
    )
    if existing is not None:
        raise ConflictError(
            "Semester for this academic year and term number already exists."
        )

    semester = Semester(
        name=(payload.name or f"Semester {payload.term_number}").strip(),
        academic_year=academic_year,
        term_number=payload.term_number,
        start_date=payload.start_date,
        end_date=payload.end_date,
        is_active=payload.is_active,
    )
    db.add(semester)
    commit_or_conflict(
        db,
        "Semester for this academic year and term number already exists.",
    )
    db.refresh(semester)
    return semester


def get_semester_by_id(db: Session, semester_id: int) -> Semester:
    """Fetch a semester by ID."""
    semester = db.get(Semester, semester_id)
    if semester is None:
        raise NotFoundError("Semester not found.")
    return semester


def list_semesters(
    db: Session,
    *,
    search: str | None = None,
    academic_year: str | None = None,
    is_active: bool | None = None,
    page: int = 1,
    page_size: int = 20,
) -> tuple[list[Semester], int]:
    """List semesters with optional search, filters, and pagination."""
    stmt = select(Semester)
    count_stmt = select(func.count(Semester.id))

    filters = []
    if search:
        pattern = f"%{search.strip()}%"
        filters.append(
            or_(
                Semester.name.ilike(pattern),
                Semester.academic_year.ilike(pattern),
            )
        )
    if academic_year:
        filters.append(Semester.academic_year == academic_year.strip())
    if is_active is not None:
        filters.append(Semester.is_active == is_active)

    if filters:
        stmt = stmt.where(*filters)
        count_stmt = count_stmt.where(*filters)

    total = db.scalar(count_stmt) or 0
    items = list(
        db.scalars(
            stmt.order_by(Semester.start_date.desc(), Semester.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        ).all()
    )
    return items, total


def update_semester(
    db: Session,
    semester_id: int,
    payload: SemesterUpdate,
) -> Semester:
    """Update semester details while enforcing date and uniqueness rules."""
    semester = get_semester_by_id(db, semester_id)

    new_year = (
        payload.academic_year.strip()
        if payload.academic_year is not None
        else semester.academic_year
    )
    new_term = (
        payload.term_number if payload.term_number is not None else semester.term_number
    )
    if (new_year, new_term) != (semester.academic_year, semester.term_number):
        existing = db.scalar(
            select(Semester).where(
                Semester.academic_year == new_year,
                Semester.term_number == new_term,
                Semester.id != semester.id,
            )
        )
        if existing is not None:
            raise ConflictError(
                "Semester for this academic year and term number already exists."
            )

    new_start = (
        payload.start_date if payload.start_date is not None else semester.start_date
    )
    new_end = payload.end_date if payload.end_date is not None else semester.end_date
    if new_end <= new_start:
        raise BusinessRuleError("end_date must be after start_date.")

    if payload.name is not None:
        semester.name = payload.name.strip()
    elif (
        payload.term_number is not None
        and semester.name == f"Semester {semester.term_number}"
    ):
        semester.name = f"Semester {new_term}"
    semester.academic_year = new_year
    semester.term_number = new_term
    semester.start_date = new_start
    semester.end_date = new_end
    if payload.is_active is not None:
        semester.is_active = payload.is_active

    commit_or_conflict(
        db,
        "Semester update conflicts with an existing academic year/term.",
    )
    db.refresh(semester)
    return semester


def set_semester_active_status(
    db: Session,
    semester_id: int,
    is_active: bool,
) -> Semester:
    """Activate or deactivate a semester."""
    semester = get_semester_by_id(db, semester_id)
    semester.is_active = is_active
    db.commit()
    db.refresh(semester)
    return semester


# --- Courses ---


def create_course(db: Session, payload: CourseCreate) -> Course:
    """Create a catalog course under an existing department."""
    get_department_by_id(db, payload.department_id)

    code = payload.code.strip().upper()
    if db.scalar(select(Course).where(Course.code == code)) is not None:
        raise ConflictError("Course code already exists.")

    course = Course(
        department_id=payload.department_id,
        code=code,
        title=payload.title.strip(),
        credits=payload.credits,
        description=payload.description.strip() if payload.description else None,
    )
    db.add(course)
    commit_or_conflict(db, "Course code already exists.")
    return get_course_by_id(db, course.id)


def get_course_by_id(db: Session, course_id: int) -> Course:
    """Fetch a course by ID with eager-loaded department."""
    course = db.scalar(
        select(Course)
        .options(joinedload(Course.department))
        .where(Course.id == course_id)
    )
    if course is None:
        raise NotFoundError("Course not found.")
    return course


def list_courses(
    db: Session,
    *,
    search: str | None = None,
    department_id: int | None = None,
    credits: int | None = None,
    page: int = 1,
    page_size: int = 20,
) -> tuple[list[Course], int]:
    """List courses with search, filtering, and pagination."""
    stmt = select(Course).options(joinedload(Course.department))
    count_stmt = select(func.count(Course.id))

    filters = []
    if search:
        pattern = f"%{search.strip()}%"
        filters.append(or_(Course.code.ilike(pattern), Course.title.ilike(pattern)))
    if department_id is not None:
        filters.append(Course.department_id == department_id)
    if credits is not None:
        filters.append(Course.credits == credits)

    if filters:
        stmt = stmt.where(*filters)
        count_stmt = count_stmt.where(*filters)

    total = db.scalar(count_stmt) or 0
    items = list(
        db.scalars(
            stmt.order_by(Course.id.asc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        ).all()
    )
    return items, total


def update_course(
    db: Session,
    course_id: int,
    payload: CourseUpdate,
) -> Course:
    """Update a catalog course."""
    course = get_course_by_id(db, course_id)

    if payload.department_id is not None:
        get_department_by_id(db, payload.department_id)
        course.department_id = payload.department_id

    if payload.code is not None:
        code = payload.code.strip().upper()
        if (
            db.scalar(select(Course).where(Course.code == code, Course.id != course.id))
            is not None
        ):
            raise ConflictError("Course code already exists.")
        course.code = code

    if payload.title is not None:
        course.title = payload.title.strip()
    if payload.credits is not None:
        course.credits = payload.credits
    if payload.description is not None:
        course.description = payload.description.strip() or None

    commit_or_conflict(db, "Course code already exists.")
    return get_course_by_id(db, course.id)
