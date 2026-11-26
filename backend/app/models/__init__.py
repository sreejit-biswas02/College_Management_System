"""SQLAlchemy ORM models package."""

from app.models.academic import Course, Department, Semester
from app.models.assignment import Assignment, Submission
from app.models.attendance import AttendanceRecord, AttendanceSession, AttendanceStatus
from app.models.course_offering import CourseOffering, Enrollment, EnrollmentStatus
from app.models.id_sequence import IDSequence
from app.models.notice import Notice, NoticeTarget
from app.models.semester_promotion import SemesterPromotionLog
from app.models.stored_file import StoredFile
from app.models.timetable import DayOfWeek, TimetableSlot
from app.models.user import Faculty, Student, User, UserRole

__all__ = [
    "Assignment",
    "AttendanceRecord",
    "AttendanceSession",
    "AttendanceStatus",
    "Course",
    "CourseOffering",
    "DayOfWeek",
    "Department",
    "Enrollment",
    "EnrollmentStatus",
    "Faculty",
    "IDSequence",
    "Notice",
    "NoticeTarget",
    "Semester",
    "SemesterPromotionLog",
    "StoredFile",
    "Student",
    "Submission",
    "TimetableSlot",
    "User",
    "UserRole",
]
