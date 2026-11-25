"""Tests for secure file uploads, downloads, deletion, and mocked R2 storage."""

from collections.abc import Generator
from datetime import UTC, date, datetime, timedelta
from typing import BinaryIO
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.security import create_access_token
from app.database.connection import engine, get_db
from app.main import app
from app.models import (
    Assignment,
    Course,
    CourseOffering,
    Department,
    Faculty,
    Semester,
    StoredFile,
    Submission,
    UserRole,
)
from app.schemas.auth import AdminCreateRequest
from app.services.auth_service import create_admin_user
from app.storage.base import (
    StorageConfigurationError,
    StorageError,
    StoredObjectInfo,
)
from app.storage.storage_service import get_storage_backend

STRONG_PASSWORD = "Password123!"
VALID_PDF = b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\ntrailer\n<<>>\n%%EOF"
VALID_PNG = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00"


class FakeStorage:
    """In-memory mock of StorageBackend for isolated tests."""

    def __init__(self) -> None:
        self.objects: dict[str, bytes] = {}
        self.fail_upload = False
        self.fail_delete = False
        self.delete_calls: list[str] = []

    def upload_file(
        self,
        *,
        file_obj: BinaryIO,
        storage_key: str,
        content_type: str,
    ) -> StoredObjectInfo:
        if self.fail_upload:
            raise StorageError("Simulated R2 upload error")
        data = file_obj.read()
        self.objects[storage_key] = data
        return StoredObjectInfo(
            storage_key=storage_key,
            content_type=content_type,
            file_size=len(data),
        )

    def delete_file(self, storage_key: str) -> None:
        self.delete_calls.append(storage_key)
        if self.fail_delete:
            raise StorageError("Simulated R2 delete error")
        self.objects.pop(storage_key, None)

    def get_metadata(self, storage_key: str) -> StoredObjectInfo:
        data = self.objects[storage_key]
        return StoredObjectInfo(
            storage_key=storage_key,
            content_type="application/pdf",
            file_size=len(data),
        )

    def generate_presigned_download_url(
        self,
        storage_key: str,
        *,
        download_filename: str,
        expires_in_seconds: int,
    ) -> str:
        return (
            f"https://r2.example.test/{storage_key}"
            f"?filename={download_filename}&expires={expires_in_seconds}"
        )


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
def fake_storage() -> FakeStorage:
    """Provide a fresh FakeStorage instance per test."""
    return FakeStorage()


@pytest.fixture()
def client(
    db_session: Session,
    fake_storage: FakeStorage,
) -> Generator[TestClient, None, None]:
    """TestClient with isolated DB session and mocked external storage."""

    def override_get_db() -> Generator[Session, None, None]:
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_storage_backend] = lambda: fake_storage
    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.clear()


@pytest.fixture()
def file_world(client: TestClient, db_session: Session) -> dict[str, object]:
    """Seed admin, 2 students, 2 faculty, offering, assignment, and submission."""
    admin = create_admin_user(
        db_session,
        AdminCreateRequest(
            email="files.admin@example.edu",
            full_name="Files Admin",
            password=STRONG_PASSWORD,
        ),
    )
    admin_hdr = {
        "Authorization": f"Bearer {create_access_token(str(admin.id), 'admin')}"
    }
    dept = Department(code="FILE-D", name="Files Dept")
    sem = Semester(
        name="Files Sem",
        academic_year="2026-2027",
        term_number=1,
        start_date=date(2026, 8, 1),
        end_date=date(2026, 12, 15),
    )
    db_session.add_all([dept, sem])
    db_session.commit()

    def _stu(email: str, roll: str):
        r = client.post(
            "/api/v1/admin/students",
            headers=admin_hdr,
            json={
                "email": email,
                "full_name": f"Stu {roll}",
                "password": STRONG_PASSWORD,
                "department_id": dept.id,
                "roll_number": roll,
                "admission_year": 2026,
            },
        ).json()
        tok = create_access_token(str(r["user"]["id"]), UserRole.STUDENT.value)
        return r["id"], {"Authorization": f"Bearer {tok}"}

    def _fac(email: str, emp: str):
        r = client.post(
            "/api/v1/admin/faculty",
            headers=admin_hdr,
            json={
                "email": email,
                "full_name": f"Fac {emp}",
                "password": STRONG_PASSWORD,
                "department_id": dept.id,
                "employee_id": emp,
                "designation": "Professor",
            },
        ).json()
        tok = create_access_token(str(r["user"]["id"]), UserRole.FACULTY.value)
        return r["id"], {"Authorization": f"Bearer {tok}"}

    s1_id, s1_hdr = _stu("fs1@example.edu", "FS-1")
    s2_id, s2_hdr = _stu("fs2@example.edu", "FS-2")
    f1_id, f1_hdr = _fac("ff1@example.edu", "FF-1")
    f2_id, f2_hdr = _fac("ff2@example.edu", "FF-2")

    course = Course(
        department_id=dept.id,
        code="FILE101",
        title="File Systems",
        credits=3,
    )
    db_session.add(course)
    db_session.flush()
    fac1 = db_session.get(Faculty, f1_id)
    assert fac1 is not None
    offering = CourseOffering(
        course_id=course.id,
        semester_id=sem.id,
        faculty_id=fac1.id,
        section="A",
    )
    db_session.add(offering)
    db_session.flush()

    client.post(
        "/api/v1/enrollments",
        headers=admin_hdr,
        json={"student_id": s1_id, "course_offering_id": offering.id},
    )

    asg = Assignment(
        course_offering_id=offering.id,
        created_by_faculty_id=fac1.id,
        title="Lab Attachment",
        due_at=datetime.now(UTC) + timedelta(days=5),
    )
    db_session.add(asg)
    db_session.flush()

    sub = Submission(
        assignment_id=asg.id,
        student_id=s1_id,
        content="See attached",
    )
    db_session.add(sub)
    db_session.commit()

    return {
        "admin_hdr": admin_hdr,
        "s1_hdr": s1_hdr,
        "s2_hdr": s2_hdr,
        "f1_hdr": f1_hdr,
        "f2_hdr": f2_hdr,
        "asg_id": asg.id,
        "sub_id": sub.id,
    }


def test_valid_pdf_and_png_uploads_and_signed_download(
    client: TestClient,
    fake_storage: FakeStorage,
    file_world: dict[str, object],
) -> None:
    """Valid PDF and PNG uploads succeed, store random keys, and return signed URLs."""
    f1_hdr = file_world["f1_hdr"]
    s1_hdr = file_world["s1_hdr"]
    asg_id = file_world["asg_id"]
    sub_id = file_world["sub_id"]

    # Faculty uploads PDF attachment
    pdf_resp = client.post(
        f"/api/v1/assignments/{asg_id}/attachments",
        headers=f1_hdr,
        files={"file": ("syllabus.pdf", VALID_PDF, "application/pdf")},
    )
    assert pdf_resp.status_code == 201
    pdf_meta = pdf_resp.json()
    assert pdf_meta["original_filename"] == "syllabus.pdf"
    assert "storage_key" not in pdf_meta
    assert len(fake_storage.objects) == 1

    # Enrolled student lists and downloads assignment PDF
    listed = client.get(
        f"/api/v1/assignments/{asg_id}/attachments",
        headers=s1_hdr,
    )
    assert listed.status_code == 200 and len(listed.json()) == 1

    dl = client.get(f"/api/v1/files/{pdf_meta['id']}", headers=s1_hdr)
    assert dl.status_code == 200
    assert dl.json()["download_url"].startswith("https://r2.example.test/")

    # Student uploads PNG to own submission; faculty downloads it
    png_resp = client.post(
        f"/api/v1/submissions/{sub_id}/files",
        headers=s1_hdr,
        files={"file": ("diagram.png", VALID_PNG, "image/png")},
    )
    assert png_resp.status_code == 201
    png_id = png_resp.json()["id"]

    fac_dl = client.get(f"/api/v1/files/{png_id}", headers=f1_hdr)
    assert fac_dl.status_code == 200


def test_upload_validation_rejections(
    client: TestClient,
    file_world: dict[str, object],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Reject unsupported ext, bad MIME, bad signature, empty, oversized, traversal."""
    f1_hdr = file_world["f1_hdr"]
    asg_id = file_world["asg_id"]
    url = f"/api/v1/assignments/{asg_id}/attachments"

    # Unsupported extension
    assert (
        client.post(
            url,
            headers=f1_hdr,
            files={"file": ("malware.exe", b"MZ...", "application/octet-stream")},
        ).status_code
        == 422
    )
    # Invalid MIME type
    assert (
        client.post(
            url,
            headers=f1_hdr,
            files={"file": ("doc.pdf", VALID_PDF, "image/png")},
        ).status_code
        == 422
    )
    # Spoofed signature
    assert (
        client.post(
            url,
            headers=f1_hdr,
            files={"file": ("fake.pdf", b"NOT_A_PDF", "application/pdf")},
        ).status_code
        == 422
    )
    # Empty file
    assert (
        client.post(
            url,
            headers=f1_hdr,
            files={"file": ("empty.pdf", b"", "application/pdf")},
        ).status_code
        == 422
    )
    # Malicious path traversal filename
    assert (
        client.post(
            url,
            headers=f1_hdr,
            files={"file": ("../../etc/passwd.pdf", VALID_PDF, "application/pdf")},
        ).status_code
        == 422
    )
    # Oversized file
    from app.core.config import get_settings

    monkeypatch.setattr(get_settings(), "MAX_ASSIGNMENT_UPLOAD_BYTES", 10)
    assert (
        client.post(
            url,
            headers=f1_hdr,
            files={"file": ("big.pdf", VALID_PDF, "application/pdf")},
        ).status_code
        == 422
    )


def test_file_authorization_and_deletion_rules(
    client: TestClient,
    file_world: dict[str, object],
) -> None:
    """Enforce auth, ownership, download, and deletion permissions."""
    f1_hdr = file_world["f1_hdr"]
    f2_hdr = file_world["f2_hdr"]
    s1_hdr = file_world["s1_hdr"]
    s2_hdr = file_world["s2_hdr"]
    asg_id = file_world["asg_id"]
    sub_id = file_world["sub_id"]

    # Unauthenticated upload -> 401
    assert (
        client.post(
            f"/api/v1/assignments/{asg_id}/attachments",
            files={"file": ("a.pdf", VALID_PDF, "application/pdf")},
        ).status_code
        == 401
    )
    # Unassigned faculty uploading to assignment -> 403
    assert (
        client.post(
            f"/api/v1/assignments/{asg_id}/attachments",
            headers=f2_hdr,
            files={"file": ("a.pdf", VALID_PDF, "application/pdf")},
        ).status_code
        == 403
    )
    # Student 2 uploading to Student 1's submission -> 403
    assert (
        client.post(
            f"/api/v1/submissions/{sub_id}/files",
            headers=s2_hdr,
            files={"file": ("a.pdf", VALID_PDF, "application/pdf")},
        ).status_code
        == 403
    )

    # Upload by F1, then test unauthorized download/delete by S2 and F2
    up = client.post(
        f"/api/v1/assignments/{asg_id}/attachments",
        headers=f1_hdr,
        files={"file": ("notes.pdf", VALID_PDF, "application/pdf")},
    ).json()
    fid = up["id"]

    assert client.get(f"/api/v1/files/{fid}", headers=s2_hdr).status_code == 403
    assert client.get(f"/api/v1/files/{fid}", headers=f2_hdr).status_code == 403
    assert client.delete(f"/api/v1/files/{fid}", headers=s1_hdr).status_code == 403
    assert client.delete(f"/api/v1/files/{fid}", headers=f1_hdr).status_code == 204
    # Deleted file cannot be downloaded
    assert client.get(f"/api/v1/files/{fid}", headers=f1_hdr).status_code == 404


def test_storage_failure_and_missing_config_handling(
    client: TestClient,
    db_session: Session,
    fake_storage: FakeStorage,
    file_world: dict[str, object],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Handle storage failures, DB failure rollback, and missing config."""
    f1_hdr = file_world["f1_hdr"]
    asg_id = file_world["asg_id"]

    # 1. Storage upload failure -> 502 and no StoredFile created
    fake_storage.fail_upload = True
    assert (
        client.post(
            f"/api/v1/assignments/{asg_id}/attachments",
            headers=f1_hdr,
            files={"file": ("fail.pdf", VALID_PDF, "application/pdf")},
        ).status_code
        == 502
    )
    fake_storage.fail_upload = False

    # 2. Failed metadata persistence triggers storage cleanup
    orig_commit = db_session.commit
    monkeypatch.setattr(
        db_session,
        "commit",
        MagicMock(side_effect=__import__("sqlalchemy.exc").exc.SQLAlchemyError("db")),
    )
    assert (
        client.post(
            f"/api/v1/assignments/{asg_id}/attachments",
            headers=f1_hdr,
            files={"file": ("dberr.pdf", VALID_PDF, "application/pdf")},
        ).status_code
        == 422
    )
    assert len(fake_storage.delete_calls) == 1
    monkeypatch.setattr(db_session, "commit", orig_commit)

    # 3. Storage deletion failure keeps DB record active
    up = client.post(
        f"/api/v1/assignments/{asg_id}/attachments",
        headers=f1_hdr,
        files={"file": ("keep.pdf", VALID_PDF, "application/pdf")},
    ).json()
    fake_storage.fail_delete = True
    assert client.delete(f"/api/v1/files/{up['id']}", headers=f1_hdr).status_code == 502
    db_file = db_session.get(StoredFile, up["id"])
    assert db_file is not None and db_file.is_active is True
    fake_storage.fail_delete = False

    # 4. Missing storage configuration -> 503
    def raise_config_err():
        raise StorageConfigurationError("R2 not configured")

    app.dependency_overrides[get_storage_backend] = raise_config_err
    assert (
        client.post(
            f"/api/v1/assignments/{asg_id}/attachments",
            headers=f1_hdr,
            files={"file": ("noconfig.pdf", VALID_PDF, "application/pdf")},
        ).status_code
        == 503
    )
