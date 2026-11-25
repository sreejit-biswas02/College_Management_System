# College Management System — Management & Academic Structure API

All endpoints are prefixed with `/api/v1` and require a valid Bearer JWT (`Authorization: Bearer <token>`).

---

## 1. Permissions Matrix

| Endpoint Group | `ADMIN` | `FACULTY` | `STUDENT` |
| :--- | :--- | :--- | :--- |
| `/api/v1/admin/students*` | Full CRUD + activate/deactivate | `403` | `403` |
| `/api/v1/admin/faculty*` | Full CRUD + activate/deactivate | `403` | `403` |
| `/api/v1/admin/departments*` | Full CRUD + activate/deactivate | `403` | `403` |
| `/api/v1/admin/semesters*` | Full CRUD + activate/deactivate | `403` | `403` |
| `/api/v1/admin/courses*` | Full CRUD | `403` | `403` |
| `/api/v1/admin/course-offerings*` | Full CRUD + activate/deactivate | `403` | `403` |
| `/api/v1/students/me` | `403` | `403` | Own profile |
| `/api/v1/faculty/me` | `403` | Own profile | `403` |
| `/api/v1/faculty/me/course-offerings` | `403` | Assigned offerings | `403` |

---

## 2. Endpoints Overview

### A. Admin — Students (`/api/v1/admin/students`)
- `POST /api/v1/admin/students` — Create user + student profile (`201`).
- `GET /api/v1/admin/students?search=&department_id=&semester_number=&is_active=&page=1&page_size=20`
- `GET /api/v1/admin/students/{student_id}`
- `PATCH /api/v1/admin/students/{student_id}`
- `PATCH /api/v1/admin/students/{student_id}/activate`
- `PATCH /api/v1/admin/students/{student_id}/deactivate`

### B. Admin — Faculty (`/api/v1/admin/faculty`)
- `POST /api/v1/admin/faculty` — Create user + faculty profile (`201`).
- `GET /api/v1/admin/faculty?search=&department_id=&is_active=&page=1&page_size=20`
- `GET /api/v1/admin/faculty/{faculty_id}`
- `PATCH /api/v1/admin/faculty/{faculty_id}`
- `PATCH /api/v1/admin/faculty/{faculty_id}/activate`
- `PATCH /api/v1/admin/faculty/{faculty_id}/deactivate`

### C. Admin — Departments (`/api/v1/admin/departments`)
- `POST /api/v1/admin/departments` (`201`)
- `GET /api/v1/admin/departments?search=&is_active=&page=1&page_size=20`
- `GET /api/v1/admin/departments/{department_id}`
- `PATCH /api/v1/admin/departments/{department_id}`
- `PATCH /api/v1/admin/departments/{department_id}/activate`
- `PATCH /api/v1/admin/departments/{department_id}/deactivate`

### D. Admin — Semesters (`/api/v1/admin/semesters`)
- `POST /api/v1/admin/semesters` (`201`)
- `GET /api/v1/admin/semesters?academic_year=&is_active=&page=1&page_size=20`
- `GET /api/v1/admin/semesters/{semester_id}`
- `PATCH /api/v1/admin/semesters/{semester_id}`
- `PATCH /api/v1/admin/semesters/{semester_id}/activate`
- `PATCH /api/v1/admin/semesters/{semester_id}/deactivate`

### E. Admin — Courses (`/api/v1/admin/courses`)
- `POST /api/v1/admin/courses` (`201`)
- `GET /api/v1/admin/courses?search=&department_id=&credits=&page=1&page_size=20`
- `GET /api/v1/admin/courses/{course_id}`
- `PATCH /api/v1/admin/courses/{course_id}`

### F. Admin — Course Offerings (`/api/v1/admin/course-offerings`)
- `POST /api/v1/admin/course-offerings` (`201`)
- `GET /api/v1/admin/course-offerings?semester_id=&faculty_id=&course_id=&section=&is_active=&page=1&page_size=20`
- `GET /api/v1/admin/course-offerings/{offering_id}`
- `PATCH /api/v1/admin/course-offerings/{offering_id}`
- `PATCH /api/v1/admin/course-offerings/{offering_id}/activate`
- `PATCH /api/v1/admin/course-offerings/{offering_id}/deactivate`

### G. Self-Service Profiles
- `GET /api/v1/students/me`
- `GET /api/v1/faculty/me`
- `GET /api/v1/faculty/me/course-offerings?semester_id=&is_active=&page=1&page_size=20`

---

## 3. Common Error Responses

- `401 Unauthorized`: Missing, malformed, or expired Bearer JWT.
- `403 Forbidden`: Authenticated user lacks required role or ownership.
- `404 Not Found`: Referenced resource or foreign key (`department_id`, `course_id`, `semester_id`, `faculty_id`) does not exist.
- `409 Conflict`: Duplicate email, roll number, employee ID, department code/name, course code, semester `(academic_year, term_number)`, or offering `(course_id, semester_id, section)`.
- `422 Unprocessable Content`: Invalid payload types, weak password, `credits <= 0`, or `end_date <= start_date`.
