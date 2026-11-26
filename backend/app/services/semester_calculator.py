"""Automatic student semester calculation from the active academic calendar."""

import re
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.academic import Semester
from app.services.exceptions import BusinessRuleError

PROGRAMME_MAX_SEMESTERS = 8
_YEAR_PREFIX_RE = re.compile(r"^(\d{4})-(\d{4})$")


@dataclass(frozen=True)
class SemesterCalculationResult:
    """Computed semester state for a student based on the active calendar."""

    calculated_semester: int | None
    semester_status: str
    is_completed: bool
    active_academic_year: str | None
    active_term_number: int | None


def parse_academic_year_start(academic_year: str) -> int:
    """Extract and validate the start year from a YYYY-YYYY academic year string."""
    match = _YEAR_PREFIX_RE.match(academic_year.strip())
    if not match:
        raise BusinessRuleError(
            "Active semester has an invalid academic year format; expected YYYY-YYYY."
        )
    start_year, end_year = int(match.group(1)), int(match.group(2))
    if end_year != start_year + 1:
        raise BusinessRuleError(
            "Active semester academic year must use consecutive years (YYYY-YYYY)."
        )
    return start_year


def get_single_active_semester(db: Session) -> Semester:
    """Return the active academic calendar session or raise if missing/ambiguous.

    Multiple active semesters are allowed when they belong to the same
    (academic_year, odd/even parity) — for example Semester 1, 3, and 5 all
    running concurrently in 2026-2027 Odd. Only conflicting academic years or
    mixed Odd/Even active semesters are treated as ambiguous.
    """
    active_semesters = list(
        db.scalars(
            select(Semester)
            .where(Semester.is_active.is_(True))
            .order_by(Semester.term_number.asc(), Semester.id.asc())
        ).all()
    )
    if not active_semesters:
        raise BusinessRuleError(
            "No active semester is configured in the academic calendar."
        )
    distinct_sessions = {
        (s.academic_year, 1 if s.term_number % 2 == 1 else 2) for s in active_semesters
    }
    if len(distinct_sessions) > 1:
        raise BusinessRuleError(
            "Multiple active semesters across different academic years/terms are "
            "configured; academic calendar is ambiguous."
        )
    return active_semesters[0]


def calculate_student_semester(
    db: Session,
    *,
    admission_year: int,
    max_semesters: int = PROGRAMME_MAX_SEMESTERS,
) -> SemesterCalculationResult:
    """Calculate student's current semester from admission year and active term."""
    if admission_year < 1950 or admission_year > 2100:
        raise BusinessRuleError("Admission year must be between 1950 and 2100.")

    active_sem = get_single_active_semester(db)
    current_start_year = parse_academic_year_start(active_sem.academic_year)

    year_diff = current_start_year - admission_year
    if year_diff < 0:
        raise BusinessRuleError(
            "Admission academic year cannot be later than the active academic year."
        )

    term_parity = 1 if active_sem.term_number % 2 == 1 else 2
    raw_semester = (year_diff * 2) + term_parity
    if raw_semester < 1:
        raise BusinessRuleError("Calculated semester cannot be less than 1.")

    if raw_semester > max_semesters:
        return SemesterCalculationResult(
            calculated_semester=max_semesters,
            semester_status="Completed",
            is_completed=True,
            active_academic_year=active_sem.academic_year,
            active_term_number=active_sem.term_number,
        )

    return SemesterCalculationResult(
        calculated_semester=raw_semester,
        semester_status="In Progress",
        is_completed=False,
        active_academic_year=active_sem.academic_year,
        active_term_number=active_sem.term_number,
    )


def resolve_student_semester_safe(
    db: Session,
    *,
    admission_year: int,
    max_semesters: int = PROGRAMME_MAX_SEMESTERS,
) -> SemesterCalculationResult:
    """Resolve semester calculation without throwing if calendar is unset/ambiguous."""
    try:
        return calculate_student_semester(
            db,
            admission_year=admission_year,
            max_semesters=max_semesters,
        )
    except BusinessRuleError as exc:
        msg = str(exc)
        if "No active semester" in msg:
            status_label = "Calendar Not Configured"
        elif "ambiguous" in msg:
            status_label = "Calendar Ambiguous"
        else:
            status_label = "Invalid Admission Year"
        return SemesterCalculationResult(
            calculated_semester=None,
            semester_status=status_label,
            is_completed=False,
            active_academic_year=None,
            active_term_number=None,
        )
