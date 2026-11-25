"""Comprehensive security and production configuration tests."""

from collections.abc import Generator
from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.security import (
    create_access_token,
    hash_password,
    verify_password,
)
from app.database.connection import engine, get_db
from app.main import app
from app.models import (
    Course,
    CourseOffering,
    Department,
    Faculty,
    Semester,
    User,
    UserRole,
)
from app.schemas.assignment import SubmissionCreate
from app.schemas.auth import AdminCreateRequest
from app.services.auth_service import create_admin_user

STRONG_PASSWORD = "Password123!"


@pytest.fixture()
def db_session() -> Generator[Session, None, None]:
    """Provide an isolated PostgreSQL session using SAVEPOINTs."""
    connection = engine.connect()
    transaction = connection.begin()
    session = Session(bind=connection, join_transaction_mode="create_savepoint")
    try:
        yield session
    finally:
        session.close()
        transaction.rollback()
        connection.close()


@pytest.fixture()
def client(db_session: Session) -> Generator[TestClient, None, None]:
    """FastAPI TestClient with get_db overridden to the isolated test session."""

    def override_get_db() -> Generator[Session, None, None]:
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.clear()


def test_password_hashing_and_verification() -> None:
    """12. Argon2 hashing produces non-plaintext hash and verifies accurately."""
    hashed = hash_password(STRONG_PASSWORD)
    assert hashed != STRONG_PASSWORD
    assert hashed.startswith("$argon2")
    assert verify_password(STRONG_PASSWORD, hashed) is True
    assert verify_password("WrongPassword1!", hashed) is False


def test_jwt_invalid_expired_and_missing_auth(client: TestClient) -> None:
    """1-3. Invalid JWT, expired JWT, and missing Authorization return 401."""
    assert client.get("/api/v1/auth/me").status_code == 401
    assert (
        client.get(
            "/api/v1/auth/me",
            headers={"Authorization": "Bearer invalid.jwt.token"},
        ).status_code
        == 401
    )

    expired = create_access_token(
        subject="1",
        role="student",
        expires_delta=timedelta(minutes=-1),
    )
    assert (
        client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {expired}"},
        ).status_code
        == 401
    )


def test_inactive_user_rejected_on_protected_endpoint(
    client: TestClient,
    db_session: Session,
) -> None:
    """4. Inactive user with an otherwise valid JWT is rejected with 403."""
    user = User(
        email="inactive.sec@example.edu",
        full_name="Inactive User",
        hashed_password=hash_password(STRONG_PASSWORD),
        role=UserRole.STUDENT,
        is_active=False,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    token = create_access_token(subject=str(user.id), role=UserRole.STUDENT.value)
    resp = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 403


def test_rbac_and_idor_protections(
    client: TestClient,
    db_session: Session,
) -> None:
    """5-8. Admin endpoint, student IDOR, faculty offering IDOR, public admin reg."""
    dept = Department(code="SEC-CSE", name="Security CSE")
    db_session.add(dept)
    db_session.commit()
    db_session.refresh(dept)

    # 8. Public admin registration rejected
    assert (
        client.post(
            "/api/v1/auth/register",
            json={
                "email": "evil.admin@example.edu",
                "full_name": "Evil Admin",
                "password": STRONG_PASSWORD,
                "role": "admin",
            },
        ).status_code
        == 403
    )

    admin = create_admin_user(
        db_session,
        AdminCreateRequest(
            email="sec.admin@example.edu",
            full_name="Sec Admin",
            password=STRONG_PASSWORD,
        ),
    )
    admin_hdr = {
        "Authorization": f"Bearer {create_access_token(str(admin.id), 'admin')}"
    }

    s1 = client.post(
        "/api/v1/admin/students",
        headers=admin_hdr,
        json={
            "email": "sec.s1@example.edu",
            "full_name": "Sec Student 1",
            "password": STRONG_PASSWORD,
            "department_id": dept.id,
            "roll_number": "SEC-1",
            "admission_year": 2026,
        },
    ).json()
    s2 = client.post(
        "/api/v1/admin/students",
        headers=admin_hdr,
        json={
            "email": "sec.s2@example.edu",
            "full_name": "Sec Student 2",
            "password": STRONG_PASSWORD,
            "department_id": dept.id,
            "roll_number": "SEC-2",
            "admission_year": 2026,
        },
    ).json()
    f1 = client.post(
        "/api/v1/admin/faculty",
        headers=admin_hdr,
        json={
            "email": "sec.f1@example.edu",
            "full_name": "Sec Faculty 1",
            "password": STRONG_PASSWORD,
            "department_id": dept.id,
            "employee_id": "SEC-F1",
            "designation": "Professor",
        },
    ).json()
    f2 = client.post(
        "/api/v1/admin/faculty",
        headers=admin_hdr,
        json={
            "email": "sec.f2@example.edu",
            "full_name": "Sec Faculty 2",
            "password": STRONG_PASSWORD,
            "department_id": dept.id,
            "employee_id": "SEC-F2",
            "designation": "Professor",
        },
    ).json()

    s1_tok = create_access_token(str(s1["user"]["id"]), "student")
    f2_tok = create_access_token(str(f2["user"]["id"]), "faculty")
    s1_hdr = {"Authorization": f"Bearer {s1_tok}"}
    f2_hdr = {"Authorization": f"Bearer {f2_tok}"}

    # 5. Student attempting admin endpoint -> 403
    assert client.get("/api/v1/admin/students", headers=s1_hdr).status_code == 403

    # 6. Student attempting another student's profile -> 403
    assert (
        client.get(
            f"/api/v1/access/students/{s2['id']}",
            headers=s1_hdr,
        ).status_code
        == 403
    )

    # 7. Faculty attempting unassigned offering -> 403
    sem = Semester(
        name="Sec Fall",
        academic_year="2026-2027",
        term_number=1,
        start_date=date(2026, 8, 1),
        end_date=date(2026, 12, 15),
    )
    course = Course(
        department_id=dept.id,
        code="SEC101",
        title="App Security",
        credits=3,
    )
    db_session.add_all([sem, course])
    db_session.flush()
    fac1 = db_session.get(Faculty, f1["id"])
    assert fac1 is not None
    offering = CourseOffering(
        course_id=course.id,
        semester_id=sem.id,
        faculty_id=fac1.id,
        section="A",
    )
    db_session.add(offering)
    db_session.commit()
    db_session.refresh(offering)

    assert (
        client.get(
            f"/api/v1/enrollments/offerings/{offering.id}",
            headers=f2_hdr,
        ).status_code
        == 403
    )


def test_login_rate_limiting(client: TestClient) -> None:
    """9. Repeated login attempts trigger HTTP 429 with Retry-After header."""
    settings = get_settings()
    for _ in range(settings.LOGIN_RATE_LIMIT_MAX_ATTEMPTS):
        resp = client.post(
            "/api/v1/auth/login",
            json={"email": "nobody@example.edu", "password": "WrongPassword1!"},
        )
        assert resp.status_code == 401

    limited = client.post(
        "/api/v1/auth/login",
        json={"email": "nobody@example.edu", "password": "WrongPassword1!"},
    )
    assert limited.status_code == 429
    assert "retry-after" in {k.lower() for k in limited.headers}


def test_invalid_production_configuration_rejected() -> None:
    """10. Production settings reject DEBUG=True, weak SECRET_KEY, and '*' CORS."""
    base_kwargs = {
        "_env_file": None,
        "ENVIRONMENT": "production",
        "DEBUG": False,
        "DATABASE_URL": "postgresql+psycopg://u:p@db.internal:5432/cms?sslmode=require",
        "SECRET_KEY": "A" * 48,
        "FRONTEND_URL": "https://portal.college.edu",
    }

    # Valid production config succeeds
    valid = Settings(**base_kwargs)
    assert valid.is_production is True

    # DEBUG=True in production rejected
    with pytest.raises(ValidationError):
        Settings(**{**base_kwargs, "DEBUG": True})

    # Weak or short SECRET_KEY in production rejected
    with pytest.raises(ValidationError):
        Settings(**{**base_kwargs, "SECRET_KEY": "short-key"})
    with pytest.raises(ValidationError):
        Settings(**{**base_kwargs, "SECRET_KEY": "change-me-" + "x" * 32})

    # Wildcard '*' origin rejected
    with pytest.raises(ValidationError):
        Settings(**{**base_kwargs, "FRONTEND_URL": "*"})

    # Non-HTTPS origin rejected in production
    with pytest.raises(ValidationError):
        Settings(**{**base_kwargs, "FRONTEND_URL": "http://portal.college.edu"})

    # Missing sslmode, non-required sslmode, or duplicate sslmode rejected
    for bad_db_url in (
        "postgresql+psycopg://u:p@db.internal:5432/cms",
        "postgresql+psycopg://u:p@db.internal:5432/cms?sslmode=disable",
        "postgresql+psycopg://u:p@db.internal:5432/cms?sslmode=prefer",
        "postgresql://u:p@ep-neon.aws.neon.tech/neondb?SSLMODE=allow",
        "postgresql+psycopg://u:p@db.internal:5432/cms?sslmode=require&sslmode=disable",
        "postgresql://u:p@ep-neon.aws.neon.tech/neondb?sslmode=require&SSLMODE=prefer",
        "postgresql+psycopg://u:p@db.internal:5432/cms?sslmode=require&sslmode=require",
    ):
        with pytest.raises(ValidationError):
            Settings(**{**base_kwargs, "DATABASE_URL": bad_db_url})

    # Required SSL modes and case variations accepted (Neon & psycopg URLs)
    for good_db_url in (
        "postgresql+psycopg://u:p@db.internal:5432/cms?sslmode=require",
        "postgresql://u:p@ep-neon.aws.neon.tech/neondb?sslmode=require",
        "postgresql+psycopg://u:p@db.internal:5432/cms?SSLMODE=REQUIRE",
        "postgresql://u:p@ep-neon.aws.neon.tech/neondb?SslMode=Verify-Full",
    ):
        cfg = Settings(**{**base_kwargs, "DATABASE_URL": good_db_url})
        assert cfg.effective_database_url.startswith("postgresql+psycopg://")


def test_production_direct_database_url_ssl_validation() -> None:
    """Production DIRECT_DATABASE_URL enforces single required SSL mode."""
    base_kwargs = {
        "_env_file": None,
        "ENVIRONMENT": "production",
        "DEBUG": False,
        "DATABASE_URL": "postgresql+psycopg://u:p@db.internal:5432/cms?sslmode=require",
        "SECRET_KEY": "A" * 48,
        "FRONTEND_URL": "https://portal.college.edu",
    }

    for good_direct_url in (
        "postgresql://u:p@ep-neon.aws.neon.tech/neondb?sslmode=require",
        "postgresql+psycopg://u:p@ep-neon.aws.neon.tech/neondb?sslmode=verify-full",
    ):
        cfg = Settings(**{**base_kwargs, "DIRECT_DATABASE_URL": good_direct_url})
        assert cfg.effective_migration_database_url.startswith("postgresql+psycopg://")

    for bad_direct_url in (
        "postgresql://u:p@ep-neon.aws.neon.tech/neondb",
        "postgresql://u:p@ep-neon.aws.neon.tech/neondb?sslmode=disable",
        "postgresql://u:p@ep-neon.aws.neon.tech/neondb?sslmode=require&sslmode=disable",
    ):
        with pytest.raises(ValidationError):
            Settings(**{**base_kwargs, "DIRECT_DATABASE_URL": bad_direct_url})


def test_storage_timeout_configuration() -> None:
    """Storage timeout uses default when omitted and validates explicit bounds."""
    base_kwargs = {
        "_env_file": None,
        "DATABASE_URL": "postgresql+psycopg://u:p@localhost:5432/cms",
        "SECRET_KEY": "dev-secret-key",
    }

    default_cfg = Settings(**base_kwargs)
    assert default_cfg.STORAGE_TIMEOUT_SECONDS == 15

    explicit_cfg = Settings(**{**base_kwargs, "STORAGE_TIMEOUT_SECONDS": 30})
    assert explicit_cfg.STORAGE_TIMEOUT_SECONDS == 30

    for invalid_timeout in (0, -5, 121):
        with pytest.raises(ValidationError):
            Settings(**{**base_kwargs, "STORAGE_TIMEOUT_SECONDS": invalid_timeout})


def test_cors_restrictions(client: TestClient) -> None:
    """11. CORS allows configured origin and rejects unauthorized origin."""
    allowed = client.options(
        "/api/v1/auth/login",
        headers={
            "Origin": "http://127.0.0.1:5500",
            "Access-Control-Request-Method": "POST",
        },
    )
    assert allowed.status_code == 200
    assert allowed.headers.get("access-control-allow-origin") == "http://127.0.0.1:5500"

    disallowed = client.options(
        "/api/v1/auth/login",
        headers={
            "Origin": "https://evil.attacker.example",
            "Access-Control-Request-Method": "POST",
        },
    )
    assert "access-control-allow-origin" not in disallowed.headers


def test_unsafe_submission_url_scheme_rejected() -> None:
    """SubmissionCreate rejects javascript: and non-HTTP(S) URLs."""
    with pytest.raises(ValidationError):
        SubmissionCreate(file_url="javascript:alert(1)")
    valid = SubmissionCreate(file_url="https://example.com/homework.pdf")
    assert valid.file_url == "https://example.com/homework.pdf"
