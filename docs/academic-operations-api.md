# College Management System — Academic Operations API

All endpoints are prefixed with `/api/v1` and require a valid Bearer JWT.

---

## 1. Enrollments (`/api/v1/enrollments`)
- `POST /api/v1/enrollments` (`ADMIN`) — Enrolls a student in an active offering. Prevents duplicates (`409`) and enforces `max_capacity` (`422`).
- `GET /api/v1/enrollments` (`ADMIN`) — Paginated list filtered by `student_id`, `course_offering_id`, `status`.
- `GET /api/v1/enrollments/me` (`STUDENT`) — Student's own enrollments.
- `GET /api/v1/enrollments/offerings/{offering_id}` (`ADMIN`, assigned `FACULTY`) — Enrollments for an offering.
- `PATCH /api/v1/enrollments/{enrollment_id}` (`ADMIN`) — Update enrollment status (`enrolled`, `dropped`, `completed`).

## 2. Attendance (`/api/v1/attendance`)
- `POST /api/v1/attendance/sessions` (`ADMIN`, assigned `FACULTY`) — Creates an attendance session for `(course_offering_id, session_date, session_number)` with optional initial records. Validates that all marked students are actively enrolled.
- `GET /api/v1/attendance/offerings/{offering_id}/sessions` (`ADMIN`, assigned `FACULTY`)
- `GET /api/v1/attendance/sessions/{session_id}` (`ADMIN`, assigned `FACULTY`)
- `PUT /api/v1/attendance/sessions/{session_id}/records` (`ADMIN`, assigned `FACULTY`) — Creates or updates student marks (`present`, `absent`, `late`, `excused`).
- `GET /api/v1/attendance/me` (`STUDENT`) — Own attendance records and calculated percentage.
- **Percentage Rule:** `((present + late + excused) / total_sessions) * 100`, rounded to 2 decimal places (`0.0` when `total_sessions == 0`).

## 3. Assignments & Submissions (`/api/v1/assignments`, `/api/v1/submissions`)
- `POST /api/v1/assignments` (`ADMIN`, assigned `FACULTY`)
- `GET /api/v1/assignments/offerings/{offering_id}` (`ADMIN`, assigned `FACULTY`, enrolled `STUDENT`)
- `GET /api/v1/assignments/{assignment_id}` (`ADMIN`, assigned `FACULTY`, enrolled `STUDENT`)
- `PATCH /api/v1/assignments/{assignment_id}` (`ADMIN`, assigned `FACULTY`)
- `POST /api/v1/assignments/{assignment_id}/submissions` (`STUDENT` enrolled in offering) — Supports text `content` and/or `file_url`. One submission per student per assignment (`409` on duplicate). **Late Policy:** Submissions after `assignment.due_at` are rejected with `422`.
- `GET /api/v1/assignments/{assignment_id}/submissions` (`ADMIN`, assigned `FACULTY`)
- `GET /api/v1/submissions/me` (`STUDENT`) — Own submissions.
- `GET /api/v1/submissions/{submission_id}` (`ADMIN`, assigned `FACULTY`, owning `STUDENT`)
- `PATCH /api/v1/submissions/{submission_id}/grade` (`ADMIN`, assigned `FACULTY`) — Validates `0 <= score <= assignment.max_score` (`422` otherwise).

## 4. Notices (`/api/v1/notices`)
- `POST /api/v1/notices` (`ADMIN`: any targets; `FACULTY`: must scope targets to their assigned `course_offering_id`s).
- `GET /api/v1/notices` — Returns published, non-expired notices matching the user's role, department, or enrolled/taught offerings (or all notices for `ADMIN`).
- `GET /api/v1/notices/{notice_id}` — Audience-checked notice detail.
- `PATCH /api/v1/notices/{notice_id}` & `PATCH /api/v1/notices/{notice_id}/deactivate` (`ADMIN` or authoring `FACULTY`).

## 5. Timetable (`/api/v1/timetable`)
- `POST /api/v1/timetable` (`ADMIN`) — Creates a slot (`end_time > start_time`) and rejects overlaps (`409`) for the same `course_offering_id` or same `faculty_id` within the same `semester_id` and `day_of_week`.
- `GET /api/v1/timetable` — Filter by `semester_id`, `section`, `day_of_week`, `faculty_id`, `course_offering_id`.
- `GET /api/v1/timetable/me` (`STUDENT` or `FACULTY`) — Personal schedule based on enrolled/taught offerings.
- `PATCH /api/v1/timetable/{slot_id}` & `DELETE /api/v1/timetable/{slot_id}` (`ADMIN`).
