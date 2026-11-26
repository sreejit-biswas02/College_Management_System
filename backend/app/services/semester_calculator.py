"""Automatic student semester calculation from admission academic year."""

import re
from dataclasses import dataclass
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.academic import Semester
from app.services.exceptions import BusinessRuleError

PROGRAMME_MAX_SEMESTERS = 8
_YEAR_PREFIX_RE = re.compile(r"^(\d{4})-(\d{4})$")


@dataclass(frozen=True)
class SemesterCalculationResult:
    """Computed semester state for a student based on admission academic year."""

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
            "Academic year must follow YYYY-YYYY format (e.g. 2026-2027)."
        )
    start_year, end_year = int(match.group(1)), int(match.group(2))
    if end_year != start_year + 1:
        raise BusinessRuleError(
            "Academic year must use consecutive years (e.g. 2026-2027)."
        )
    return start_year


def get_current_academic_year_start(
    db: Session,
    *,
    reference_date: date | None = None,
) -> int:
    """Resolve current Indian academic year start year without requiring calendar setup.

    If active semesters exist in the database and agree on a single academic_year,
    that academic_year is used; otherwise the Indian July-June academic year is
    derived from ``reference_date`` (or today's date).
    """
    active_years = {
        sem.academic_year
        for sem in db.scalars(
            select(Semester).where(Semester.is_active.is_(True))
        ).all()
    }
    if len(active_years) == 1:
        return parse_academic_year_start(next(iter(active_years)))

    today = reference_date or date.today()
    return today.year if today.month >= 7 else today.year - 1


def calculate_student_semester(
    db: Session,
    *,
    admission_year: int,
    reference_date: date | None = None,
    max_semesters: int = PROGRAMME_MAX_SEMESTERS,
) -> SemesterCalculationResult:
    """Calculate the initial odd semester: 1 + 2 * (current_year - admission_year)."""
    if admission_year < 1950 or admission_year > 2100:
        raise BusinessRuleError("Admission year must be between 1950 and 2100.")

    current_start_year = get_current_academic_year_start(
        db,
        reference_date=reference_date,
    )
    current_academic_year = f"{current_start_year}-{current_start_year + 1}"

    year_diff = current_start_year - admission_year
    if year_diff < 0:
        raise BusinessRuleError(
            "Admission academic year cannot be later than the current academic year."
        )

    raw_semester = 1 + (2 * year_diff)
    if raw_semester > max_semesters:
        return SemesterCalculationResult(
            calculated_semester=max_semesters,
            semester_status="Completed",
            is_completed=True,
            active_academic_year=current_academic_year,
            active_term_number=1,
        )

    return SemesterCalculationResult(
        calculated_semester=raw_semester,
        semester_status="In Progress",
        is_completed=False,
        active_academic_year=current_academic_year,
        active_term_number=1,
    )


def resolve_student_semester_safe(
    db: Session,
    *,
    admission_year: int,
    reference_date: date | None = None,
    max_semesters: int = PROGRAMME_MAX_SEMESTERS,
) -> SemesterCalculationResult:
    """Resolve semester calculation safely for previews without throwing."""
    try:
        return calculate_student_semester(
            db,
            admission_year=admission_year,
            reference_date=reference_date,
            max_semesters=max_semesters,
        )
    except BusinessRuleError:
        current_start_year = get_current_academic_year_start(
            db,
            reference_date=reference_date,
        )
        return SemesterCalculationResult(
            calculated_semester=None,
            semester_status="Invalid Admission Year",
            is_completed=False,
            active_academic_year=f"{current_start_year}-{current_start_year + 1}",
            active_term_number=1,
        )
