"""Concurrency-safe automatic ID generation for Students and Faculty."""

from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.models.id_sequence import IDSequence
from app.services.exceptions import BusinessRuleError


def _next_sequence_value(db: Session, *, entity_type: str, scope_key: str) -> int:
    """Atomically increment and return the next sequence number for a scope."""
    stmt = (
        pg_insert(IDSequence)
        .values(entity_type=entity_type, scope_key=scope_key, last_value=1)
        .on_conflict_do_update(
            index_elements=["entity_type", "scope_key"],
            set_={"last_value": IDSequence.last_value + 1},
        )
        .returning(IDSequence.last_value)
    )
    next_val = db.scalar(stmt)
    if next_val is None or next_val < 1:
        raise BusinessRuleError("Failed to generate sequential identifier.")
    return next_val


def generate_student_id(
    db: Session,
    *,
    department_code: str,
    admission_year: int,
) -> str:
    """Generate a unique Student ID in the format S-DEPTCODE-ADMISSIONYEAR-XXX."""
    dept_code = department_code.strip().upper()
    if not dept_code:
        raise BusinessRuleError(
            "Department code is required for Student ID generation."
        )
    if admission_year < 1950 or admission_year > 2100:
        raise BusinessRuleError("Admission year must be between 1950 and 2100.")

    seq = _next_sequence_value(
        db,
        entity_type="student",
        scope_key=f"{dept_code}:{admission_year}",
    )
    return f"S-{dept_code}-{admission_year}-{seq:03d}"


def generate_faculty_id(db: Session, *, department_code: str) -> str:
    """Generate a unique Faculty ID in the format F-DEPTCODE-XXX."""
    dept_code = department_code.strip().upper()
    if not dept_code:
        raise BusinessRuleError(
            "Department code is required for Faculty ID generation."
        )

    seq = _next_sequence_value(
        db,
        entity_type="faculty",
        scope_key=dept_code,
    )
    return f"F-{dept_code}-{seq:03d}"
