# College Management System

A role-based College Management System built with **FastAPI, PostgreSQL,
SQLAlchemy, Alembic, HTML, CSS, and Vanilla JavaScript**.

The application provides separate workflows for administrators, faculty
members, and students, including academic administration, course
enrollment, attendance, assignments, submissions, notices, and timetable
management.

This guide is written for a judge or evaluator setting up the project on
a fresh computer. Follow the steps in order.

------------------------------------------------------------------------

## 1. Features

-   Role-based authentication and authorization
-   Student and faculty management
-   Department, semester, and course management
-   Course offerings and student enrollment
-   Attendance management
-   Assignment creation and submissions
-   Submission evaluation and grading
-   Notice management
-   Timetable management
-   Database migrations with Alembic
-   File-storage integration (Cloudflare R2 / S3-compatible storage,
    when configured)

------------------------------------------------------------------------

## 2. Technology stack

  Layer                                 Technology
  ------------------------------------- -------------------------------
  Backend                               Python, FastAPI
  Database                              PostgreSQL
  ORM                                   SQLAlchemy
  Database migrations                   Alembic
  Frontend                              HTML, CSS, Vanilla JavaScript
  Python environment and dependencies   `uv`
  Authentication                        JWT
  Password hashing                      Argon2

------------------------------------------------------------------------

## 3. Prerequisites

Install the following before starting:

1.  **Git** -- to clone the repository.
2.  **Python 3.12 or later** -- the project requires Python 3.12+.
3.  **uv** -- Python package and environment manager.
4.  **PostgreSQL** -- a local PostgreSQL server and database.
5.  A modern browser such as Chrome, Firefox, or Edge.

### Install uv

Follow the official installation instructions:
<https://docs.astral.sh/uv/getting-started/installation/>.

On Linux/macOS, the standard installer is:

``` bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

On Windows, use the installation instructions on the official uv
website.

Check the installations:

``` bash
git --version
python3 --version
uv --version
```

Make sure Python is version 3.12 or later.

------------------------------------------------------------------------

## 4. Clone the repository

Open a terminal and run:

``` bash
git clone https://github.com/sreejit-biswas02/College_Management_System.git
cd College_Management_System
```

The repository is organized approximately as follows:

``` text
College_Management_System/
├── backend/
│   ├── app/
│   ├── tests/
│   ├── alembic/
│   ├── pyproject.toml
│   └── alembic.ini
├── frontend/
│   ├── index.html
│   ├── css/
│   ├── js/
│   └── build.sh
├── docs/
├── .gitignore
└── README.md
```

Some files or folders may change as the project evolves. The `backend`
directory contains the API and database code; `frontend` contains the
browser application.

------------------------------------------------------------------------

## 5. Create a PostgreSQL database

Start your local PostgreSQL service, then create a database for the
project.

For example, using `psql`:

``` sql
CREATE DATABASE college_management;
```

You may use a different database name, but use the same name in the
connection string below.

A PostgreSQL connection URL has this general format:

``` text
postgresql+psycopg://USERNAME:PASSWORD@HOST:5432/DATABASE_NAME
```

For a local database, `HOST` is usually `localhost`.

If your password contains special URL characters (for example `@`, `:`,
`/`, or `#`), URL-encode those characters before putting the password in
the connection URL.

------------------------------------------------------------------------

## 6. Configure backend environment variables

Move into the backend directory:

``` bash
cd backend
```

Create a `.env` file in `backend/`. Do not commit this file or share its
secrets.

Example:

``` env
APP_NAME="College Management System"
ENVIRONMENT=development
DEBUG=true
LOG_LEVEL=INFO

DATABASE_URL=postgresql+psycopg://USERNAME:PASSWORD@localhost:5432/college_management

SECRET_KEY=REPLACE_WITH_A_LONG_RANDOM_SECRET
ACCESS_TOKEN_EXPIRE_MINUTES=30

FRONTEND_URL=http://127.0.0.1:5500

STORAGE_PROVIDER=r2
```

Replace `USERNAME`, `PASSWORD`, and the database name with your local
PostgreSQL details.

Generate a strong secret key instead of using the example text:

``` bash
openssl rand -hex 32
```

Copy the generated value into `SECRET_KEY`.

### Optional file-storage configuration

If you need to test features that upload or retrieve files, configure
the Cloudflare R2 credentials supplied for the project:

``` env
R2_ACCOUNT_ID=
R2_ACCESS_KEY_ID=
R2_SECRET_ACCESS_KEY=
R2_BUCKET_NAME=
R2_ENDPOINT_URL=
R2_PUBLIC_BASE_URL=
```

Do not invent credentials. If R2 credentials are not available, ask the
project maintainer which file-storage features are expected to be
demonstrated locally.

`DIRECT_DATABASE_URL` is optional for a normal local PostgreSQL setup.
If you set it, it can use the same local database URL as `DATABASE_URL`.

------------------------------------------------------------------------

## 7. Install backend dependencies

Make sure your terminal is inside `backend/`, then run:

``` bash
uv sync
```

This creates the project environment and installs the dependencies
declared by the backend project.

------------------------------------------------------------------------

## 8. Apply database migrations

Still inside `backend/`, run:

``` bash
uv run alembic upgrade head
```

This applies the database migrations and creates or updates the tables
required by the application.

If the command reports a database connection error, check:

-   PostgreSQL is running.
-   The database exists.
-   The username and password in `DATABASE_URL` are correct.
-   The database name and port are correct.

Do not manually create application tables if migrations are available.

------------------------------------------------------------------------

## 9. Start the FastAPI backend

From the `backend/` directory, run:

``` bash
uv run uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Keep this terminal open while using the application.

Useful backend URLs:

  Purpose                            URL
  ---------------------------------- -----------------------------------------
  API base                           `http://127.0.0.1:8000`
  Health check                       `http://127.0.0.1:8000/health`
  Database health check              `http://127.0.0.1:8000/health/database`
  API documentation (when enabled)   `http://127.0.0.1:8000/docs`

A successful health check should return a successful HTTP response. The
API documentation may be disabled by application configuration.

------------------------------------------------------------------------

## 10. Start the frontend

Open a **second terminal**. From the repository root, run:

``` bash
cd frontend
python3 -m http.server 5500 --bind 127.0.0.1
```

Then open:

<http://127.0.0.1:5500>

Keep both the backend and frontend terminals running.

The frontend's local runtime configuration should point API requests to:

``` text
http://127.0.0.1:8000/api/v1
```

If the browser cannot connect to the API, verify that the backend is
running and that the frontend runtime configuration uses the local API
URL.

------------------------------------------------------------------------

## 11. Administrator account and login

The application uses role-based authentication. An administrator account
must exist before an evaluator can access administrator-only workflows.

Use the project's administrator bootstrap procedure or ask the project
maintainer for the approved initial administrator setup instructions.

Do not assume that a default username or password exists. Do not put
administrator credentials in this README, source control, or public
project screenshots.

If an administrator account already exists and you have authorization to
change its password, use the project's password-reset utility and follow
its help output. Keep the new password private.

------------------------------------------------------------------------

## 12. Run tests

From the `backend/` directory:

``` bash
uv run pytest
```

If you want to run lint checks and Ruff is installed in the project
environment:

``` bash
uv run ruff check .
```

To check formatting:

``` bash
uv run ruff format --check .
```

If a test command is unavailable, first check the development
dependencies in `backend/pyproject.toml`.

------------------------------------------------------------------------

## 13. Troubleshooting

### `uv: command not found`

Install uv using the instructions in [Prerequisites](#3-prerequisites),
then restart the terminal so its updated PATH is loaded.

### PostgreSQL connection refused

Make sure the PostgreSQL service is running and that `DATABASE_URL`
points to the correct host, port, database, username, and password.

### Database does not exist

Create the database in PostgreSQL, then run the migration command again.

### Missing environment variable or settings validation error

Check that `backend/.env` exists, is in the backend directory, and
contains the required settings. Do not paste secret values into issue
reports.

### Frontend loads but API requests fail

1.  Confirm the backend is running at `http://127.0.0.1:8000`.
2.  Open `http://127.0.0.1:8000/health`.
3.  Confirm the frontend uses `http://127.0.0.1:8000/api/v1` as its API
    base URL.
4.  Check the browser developer console and backend terminal for errors.

### Login does not work

Confirm that migrations have been applied and that an administrator
account has been created using the approved bootstrap process. There is
no assumed default password.

### File upload or download fails

Check that the R2 environment variables are configured correctly and
that the bucket and credentials are valid. File-storage functionality
may require external R2 access even when the rest of the application
runs locally.

------------------------------------------------------------------------

## 14. Recommended evaluation order

For a smooth demonstration, use this order:

1.  Start PostgreSQL.
2.  Start the FastAPI backend.
3.  Start the frontend server.
4.  Open the frontend in the browser.
5.  Sign in using the administrator credentials provided by the project
    maintainer.
6.  Demonstrate department, semester, course, student, and faculty
    management.
7.  Demonstrate course offerings and enrollment.
8.  Demonstrate attendance, assignments, submissions, and grading.
9.  Demonstrate notices and timetable management.
10. Sign in with faculty and student accounts, if those test accounts
    have been prepared, to demonstrate role-based access.

Prepare authorized demonstration accounts and sample data before the
judging session. Do not rely on a public default password.

------------------------------------------------------------------------

## 15. Security notes

-   Never commit `.env` files, database passwords, JWT secrets, or R2
    credentials.
-   Use a unique, randomly generated `SECRET_KEY`.
-   Do not use production credentials for a public demonstration.
-   Use only test data or data you are authorized to show.
-   Keep administrator credentials private.
-   Do not disable authentication or authorization to make the
    demonstration easier.

------------------------------------------------------------------------

## 16. Support and project information

**Project:** College Management System\
**Backend:** FastAPI\
**Database:** PostgreSQL\
**Frontend:** HTML, CSS, Vanilla JavaScript\
**Repository:**
<https://github.com/sreejit-biswas02/College_Management_System>

For setup issues, provide the error message and the command that
produced it, but remove passwords, tokens, connection strings, and other
secrets before sharing logs.


------------------------------------------------------------------------

**Thank you for evaluating the College Management System.**
