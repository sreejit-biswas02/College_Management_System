# College Management System — Frontend Foundation

Static HTML5, CSS3, and Vanilla JavaScript (ES6+ Modules) frontend for the College Management System.

## 1. Architecture & Folder Structure

```text
frontend/
├── index.html                 # Single HTML entry point
├── assets/
│   ├── images/
│   └── icons/
├── css/
│   ├── variables.css          # Design tokens (colors, spacing, shadows, radii)
│   ├── reset.css              # Base browser reset
│   ├── global.css             # Utility classes and focus styles
│   ├── components.css         # Reusable buttons, forms, tables, modals, toasts
│   ├── layout.css             # Responsive sidebar + topbar + main area shell
│   ├── auth.css               # Login page styling
│   ├── admin.css              # Admin role theme accents
│   ├── faculty.css            # Faculty role theme accents
│   └── student.css            # Student role theme accents
└── js/
    ├── app.js                 # Application bootstrap and session routing
    ├── config.js              # Centralized API_BASE_URL and role navigation
    ├── api/
    │   ├── client.js          # Fetch wrapper (Bearer auth, timeout, 401 handling)
    │   └── authApi.js         # /auth/login and /auth/me endpoints
    ├── auth/
    │   └── authService.js     # sessionStorage token & user state management
    ├── components/            # Reusable UI components (Sidebar, Navbar, Table, Modal, Toast)
    └── pages/                 # Login page & role-aware dashboard shell
```

## 2. Running Locally

1. Start the FastAPI backend from `backend/`:
   ```bash
   uv run uvicorn app.main:app --reload
   ```
2. Serve `frontend/` on `http://127.0.0.1:5500` (matches `FRONTEND_URL` in `backend/.env`):
   ```bash
   cd frontend
   python3 -m http.server 5500
   ```
3. Open `http://127.0.0.1:5500` in your browser.

## 3. API Base URL Configuration

Update `CONFIG.API_BASE_URL` in `frontend/js/config.js` (default: `http://127.0.0.1:8000/api/v1`).

## 4. Authentication & Role-Based Navigation

- **Login:** `POST /api/v1/auth/login` returns `{ access_token, token_type, user }`.
- **Session Storage:** The JWT is stored in `sessionStorage` (`cms_access_token`) and cleared on logout or `401 Unauthorized`.
- **Session Restore:** On page reload, `restoreSession()` calls `GET /api/v1/auth/me` to verify the token and load the authoritative user role from the backend.
- **Role Navigation:** `ROLE_NAVIGATION` in `js/config.js` renders navigation items for `admin`, `faculty`, and `student`. Backend endpoints enforce all actual permissions.

## 5. Role-Based Dashboards (Phase 4 Part 2)

- **Admin (`js/pages/adminPages.js`):** Overview stats, Student/Faculty/Department/Semester/Course/Course Offering management, Enrollments, Attendance & Assignment overviews, Notices, and Timetable slot management.
- **Faculty (`js/pages/facultyPages.js`):** Overview, My Profile, Assigned Course Offerings, Enrolled Student lists, Attendance session creation & marking, Assignment publishing & submission grading, Course Notices, and Weekly Timetable.
- **Student (`js/pages/studentPages.js`):** Overview, My Profile, Enrolled Courses, Attendance percentage & history, Assignment viewing & text/URL submission, Submissions & Grades, Notices, and Weekly Timetable.

## 6. Known Limitations

- Backend `GET /faculty/me` and `GET /students/me` are read-only; profile editing by students/faculty is disabled in the UI.
- Assignment submissions support text content and external `file_url` (no binary file upload storage).
- Node.js is not installed in the current environment, so automated browser/Playwright UI tests are not included; backend integration is verified via pytest + live HTTP/CORS checks.

## 7. Adding New Pages & API Modules

1. Create an API module in `frontend/js/api/` using `apiRequest(...)` from `client.js`.
2. Create a page renderer in `frontend/js/pages/` using components from `frontend/js/components/`.
3. Wire the route ID in `frontend/js/pages/dashboardShell.js`.
