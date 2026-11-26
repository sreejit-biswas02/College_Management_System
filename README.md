# College Management System

A scalable, role-based College Management System built using **FastAPI, PostgreSQL, HTML, CSS, and Vanilla JavaScript**.

The system provides separate dashboards and functionality for administrators, faculty members, and students.

## Features

- Role-based authentication and authorization
- Student and faculty management
- Department, semester, and course management
- Course offerings and student enrollment
- Attendance management
- Assignments and submissions
- Submission evaluation and grading
- Notice management
- Timetable management
- Secure file uploads and downloads
- Automatic semester calculation and promotion

## Technology Stack

| Component | Technology |
|---|---|
| Frontend | HTML, CSS, JavaScript |
| Backend | Python, FastAPI |
| Database | PostgreSQL |
| ORM | SQLAlchemy |
| Migrations | Alembic |
| Authentication | JWT, Argon2 |
| Package Manager | uv |
| File Storage | Cloudflare R2 |

## Project Structure

```text
College_Management_System/
├── backend/
│   ├── app/
│   ├── alembic/
│   ├── tests/
│   ├── pyproject.toml
│   └── .env.example
├── frontend/
│   ├── index.html
│   ├── css/
│   └── js/
├── docs/
└── render.yaml
```

## Setup Instructions

### 1. Clone the repository

```bash
git clone https://github.com/sreejit-biswas02/College_Management_System.git
cd College_Management_System
```

### 2. Install prerequisites

Install:
- Python 3.12
- uv
- PostgreSQL (only if using a local database)

### 3. Configure PostgreSQL

You can use either a local PostgreSQL database or a hosted PostgreSQL database such as Neon.

Create a database and database user if using PostgreSQL locally.

### 4. Configure the backend

```bash
cd backend
uv sync
cp .env.example .env
```

Edit `.env` and configure your database connection, secret key, and other required environment variables.

### 5. Run database migrations

```bash
uv run alembic upgrade head
```

### 6. Create the administrator account

```bash
uv run python -m app.cli.create_admin \
  --email admin@example.com \
  --full-name "System Admin"
```

Set the administrator password securely when prompted.

### 7. Start the backend

```bash
uv run uvicorn app.main:app --reload
```

Backend: http://127.0.0.1:8000

API documentation: http://127.0.0.1:8000/docs

### 8. Start the frontend

Open another terminal:

```bash
cd frontend
python3 -m http.server 5500
```

Open: http://127.0.0.1:5500

## Deployment Architecture

The project is designed for cloud deployment:

- Frontend: Cloudflare Pages
- Backend: Render
- Database: Neon PostgreSQL
- File Storage: Cloudflare R2
- Source Control: GitHub

## Important Notes

- Configure your own database and environment variables before running the application.
- Cloudflare R2 credentials are required for live file storage functionality.
- Database migrations must be applied before using the application.

---

**College Management System** — A modern platform for managing academic and administrative operations.
