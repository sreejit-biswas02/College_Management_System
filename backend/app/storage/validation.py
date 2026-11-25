"""Strict file upload validation: extensions, MIME, signatures, and keys."""

import os
import re
import uuid
from dataclasses import dataclass

ALLOWED_FILE_TYPES: dict[str, set[str]] = {
    ".pdf": {"application/pdf"},
    ".doc": {"application/msword", "application/octet-stream"},
    ".docx": {
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/zip",
    },
    ".txt": {"text/plain"},
    ".jpg": {"image/jpeg"},
    ".jpeg": {"image/jpeg"},
    ".png": {"image/png"},
}

CANONICAL_MIME_TYPES: dict[str, str] = {
    ".pdf": "application/pdf",
    ".doc": "application/msword",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".txt": "text/plain",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
}

_SAFE_FILENAME_RE = re.compile(r"[^A-Za-z0-9._-]")


class FileValidationError(ValueError):
    """Raised when an uploaded file fails security or format validation."""


@dataclass(frozen=True)
class ValidatedFile:
    """Validated file metadata and sanitized storage key."""

    original_filename: str
    extension: str
    content_type: str
    file_size: int
    storage_key: str


def sanitize_filename(filename: str | None) -> str:
    """Strip directory components and unsafe characters from a filename."""
    if not filename:
        raise FileValidationError("Filename is required.")
    if "\x00" in filename or ".." in filename or "/" in filename or "\\" in filename:
        base = os.path.basename(filename.replace("\\", "/"))
        if not base or ".." in filename or "\x00" in filename:
            raise FileValidationError("Invalid filename.")
    else:
        base = os.path.basename(filename)

    cleaned = _SAFE_FILENAME_RE.sub("_", base).strip("._")
    if not cleaned:
        raise FileValidationError("Invalid filename.")
    return cleaned[:200]


def _validate_signature(ext: str, content: bytes) -> None:
    """Verify file magic bytes / structure to reject spoofed extensions."""
    if ext == ".pdf":
        if not content.startswith(b"%PDF-"):
            raise FileValidationError("File content does not match PDF signature.")
    elif ext == ".png":
        if not content.startswith(b"\x89PNG\r\n\x1a\n"):
            raise FileValidationError("File content does not match PNG signature.")
    elif ext in {".jpg", ".jpeg"}:
        if not content.startswith(b"\xff\xd8\xff"):
            raise FileValidationError("File content does not match JPEG signature.")
    elif ext == ".doc":
        if not content.startswith(b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"):
            raise FileValidationError("File content does not match DOC signature.")
    elif ext == ".docx":
        if not content.startswith(b"PK\x03\x04"):
            raise FileValidationError("File content does not match DOCX signature.")
    elif ext == ".txt":
        if b"\x00" in content:
            raise FileValidationError("Text files must not contain binary null bytes.")
        try:
            content.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise FileValidationError("Text file must be valid UTF-8.") from exc


def validate_upload(
    *,
    filename: str | None,
    declared_content_type: str | None,
    content: bytes,
    max_bytes: int,
    key_prefix: str,
) -> ValidatedFile:
    """Validate size, filename, extension, MIME type, and file signature."""
    if not content:
        raise FileValidationError("Uploaded file is empty.")
    if len(content) > max_bytes:
        max_mb = max_bytes // (1024 * 1024)
        raise FileValidationError(f"File exceeds maximum allowed size ({max_mb} MB).")

    safe_name = sanitize_filename(filename)
    _, ext = os.path.splitext(safe_name)
    ext = ext.lower()

    if ext not in ALLOWED_FILE_TYPES:
        raise FileValidationError(f"File extension '{ext or 'none'}' is not allowed.")

    if declared_content_type:
        normalized_mime = declared_content_type.split(";")[0].strip().lower()
        if normalized_mime not in ALLOWED_FILE_TYPES[ext]:
            raise FileValidationError(
                f"MIME type '{normalized_mime}' does not match extension '{ext}'."
            )

    _validate_signature(ext, content)

    random_key = f"{key_prefix.strip('/')}/{uuid.uuid4().hex}{ext}"
    return ValidatedFile(
        original_filename=safe_name,
        extension=ext,
        content_type=CANONICAL_MIME_TYPES[ext],
        file_size=len(content),
        storage_key=random_key,
    )
