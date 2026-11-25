# College Management System — Authentication & Authorization Guide

## 1. Overview

The backend uses stateless **JWT Bearer access tokens** (`PyJWT`, `HS256`) paired with **Argon2** password hashing (`pwdlib[argon2]`) and **database-backed user resolution** on every protected request.

Refresh tokens are intentionally omitted in the initial MVP to keep session handling simple and auditable within hackathon scope; short-lived access tokens (`ACCESS_TOKEN_EXPIRE_MINUTES`, default `30`) are used instead.

---

## 2. User Roles & Permission Rules

| Role | Scope & Permissions |
| :--- | :--- |
| `admin` | Full administrative access; can manage users, student/faculty records, and academic structure; can create additional `admin` accounts. |
| `faculty` | Faculty endpoints; access to course offerings assigned to them (`CourseOffering.faculty_id`). Cannot access unassigned offerings or arbitrary student records. |
| `student` | Student endpoints; access to their own profile (`Student.user_id == current_user.id`) and own academic data. |

---

## 3. Registration Workflow

Public registration is available for **students** and **faculty** only:

- `POST /api/v1/auth/register/student` — Creates a `User` (`role=student`) and linked `Student` profile atomically.
- `POST /api/v1/auth/register/faculty` — Creates a `User` (`role=faculty`) and linked `Faculty` profile atomically.
- `POST /api/v1/auth/register` — Generic endpoint accepting `role` (`student` or `faculty`). Requests with `role: "admin"` are rejected with `403 Forbidden`.

**Validation & Security:**
- Email addresses are validated (`EmailStr`), normalized (trimmed & lowercased), and checked for uniqueness (`409 Conflict` on duplicate).
- Passwords must be at least 8 characters and include uppercase, lowercase, digit, and special character.
- Passwords are hashed with Argon2 before database insertion; `hashed_password` is never returned in API responses.

### Example: Student Registration
```http
POST /api/v1/auth/register/student
Content-Type: application/json

{
  "email": "alice@college.edu",
  "full_name": "Alice Student",
  "password": "Password123!",
  "department_id": 1,
  "roll_number": "CSE-2026-001",
  "admission_year": 2026,
  "current_semester_number": 1
}
```

**Response (`201 Created`):**
```json
{
  "user": {
    "id": 1,
    "email": "alice@college.edu",
    "full_name": "Alice Student",
    "role": "student",
    "is_active": true,
    "created_at": "2026-11-25T12:00:00Z",
    "updated_at": "2026-11-25T12:00:00Z"
  },
  "student_profile": {
    "id": 1,
    "user_id": 1,
    "department_id": 1,
    "roll_number": "CSE-2026-001",
    "admission_year": 2026,
    "current_semester_number": 1,
    "phone": null,
    "date_of_birth": null
  },
  "faculty_profile": null
}
```

---

## 4. Login Workflow & JWT Authentication

- **Endpoint:** `POST /api/v1/auth/login`
- Authenticates email + password against the stored Argon2 hash.
- Returns `401 Unauthorized` with a generic `"Invalid email or password."` message if either email or password is incorrect.
- Returns `403 Forbidden` if `user.is_active` is `false`.
- Signs a JWT using `settings.SECRET_KEY` (`HS256`) with `sub` (user ID), `role`, `iat`, and `exp` (`ACCESS_TOKEN_EXPIRE_MINUTES`).
- On protected requests, `get_current_user` validates the JWT signature and expiration, then loads the user from PostgreSQL so deactivated accounts or role changes take effect immediately.

### Example: Login
```http
POST /api/v1/auth/login
Content-Type: application/json

{
  "email": "alice@college.edu",
  "password": "Password123!"
}
```

**Response (`200 OK`):**
```json
{
  "access_token": "<jwt-token>",
  "token_type": "bearer",
  "user": {
    "id": 1,
    "email": "alice@college.edu",
    "full_name": "Alice Student",
    "role": "student",
    "is_active": true,
    "created_at": "2026-11-25T12:00:00Z",
    "updated_at": "2026-11-25T12:00:00Z"
  }
}
```

### Example: Protected Request
```http
GET /api/v1/auth/me
Authorization: Bearer <jwt-token>
```

---

## 5. Admin Account Creation Process

Public `ADMIN` registration is disabled. Admin accounts are created via:

1. **Initial Bootstrap CLI** (run from `backend/`):
   ```bash
   uv run python -m app.cli.create_admin --email admin@college.edu --full-name "System Admin"
   ```
   *(Prompts securely for password if `--password` is omitted.)*
2. **Protected Admin Endpoint:**
   `POST /api/v1/admin/users/admin` (requires an active `ADMIN` Bearer token).
