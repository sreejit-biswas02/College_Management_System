"""Pydantic schemas for Attendance sessions and records."""

from datetime import date, datetime, time

from pydantic import BaseModel, ConfigDict, Field

from app.models.attendance import AttendanceStatus


class AttendanceRecordInput(BaseModel):
    """Single student attendance mark input."""

    student_id: int = Field(gt=0)
    status: AttendanceStatus
    remarks: str | None = Field(default=None, max_length=255)


class AttendanceSessionCreate(BaseModel):
    """Payload to create an attendance session (with optional initial marks)."""

    course_offering_id: int = Field(gt=0)
    session_date: date
    session_number: int = Field(default=1, ge=1, le=20)
    start_time: time | None = None
    topic: str | None = Field(default=None, max_length=200)
    records: list[AttendanceRecordInput] = Field(default_factory=list)


class AttendanceBulkMarkRequest(BaseModel):
    """Payload to mark attendance for one or more students in a session."""

    records: list[AttendanceRecordInput] = Field(min_length=1)


class AttendanceRecordResponse(BaseModel):
    """Attendance record response."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    session_id: int
    student_id: int
    status: AttendanceStatus
    remarks: str | None
    marked_at: datetime


class AttendanceSessionResponse(BaseModel):
    """Attendance session response with recorded student marks."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    course_offering_id: int
    conducted_by_faculty_id: int
    session_date: date
    session_number: int
    start_time: time | None
    topic: str | None
    created_at: datetime
    records: list[AttendanceRecordResponse] = Field(default_factory=list)


class StudentAttendanceSummary(BaseModel):
    """Aggregated attendance summary for a student."""

    total_sessions: int
    present: int
    absent: int
    late: int
    excused: int
    attendance_percentage: float
    records: list[AttendanceRecordResponse]
