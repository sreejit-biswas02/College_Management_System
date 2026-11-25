"""FastAPI application entry point for the College Management System."""

import logging
from typing import Annotated

from fastapi import Depends, FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.logging_config import configure_logging
from app.database.connection import get_db
from app.routers.admin_course_offerings import router as admin_course_offerings_router
from app.routers.admin_courses import router as admin_courses_router
from app.routers.admin_departments import router as admin_departments_router
from app.routers.admin_faculty import router as admin_faculty_router
from app.routers.admin_semesters import router as admin_semesters_router
from app.routers.admin_students import router as admin_students_router
from app.routers.assignments import router as assignments_router
from app.routers.attendance import router as attendance_router
from app.routers.auth import router as auth_router
from app.routers.enrollments import router as enrollments_router
from app.routers.files import router as files_router
from app.routers.notices import router as notices_router
from app.routers.profiles import router as profiles_router
from app.routers.timetable import router as timetable_router
from app.services.exceptions import (
    BusinessRuleError,
    ConflictError,
    ForbiddenError,
    NotFoundError,
)
from app.storage.base import StorageConfigurationError, StorageError
from app.storage.validation import FileValidationError

configure_logging()
logger = logging.getLogger(__name__)
settings = get_settings()

_show_docs = not (settings.is_production and not settings.DEBUG)

app = FastAPI(
    title="College Management System API",
    description=(
        "Backend API for managing college operations, academics, and administration."
    ),
    version="1.0.0",
    docs_url="/docs" if _show_docs else None,
    redoc_url="/redoc" if _show_docs else None,
    openapi_url="/openapi.json" if _show_docs else None,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "Accept"],
)

app.include_router(auth_router, prefix="/api/v1")
app.include_router(admin_students_router, prefix="/api/v1")
app.include_router(admin_faculty_router, prefix="/api/v1")
app.include_router(admin_departments_router, prefix="/api/v1")
app.include_router(admin_semesters_router, prefix="/api/v1")
app.include_router(admin_courses_router, prefix="/api/v1")
app.include_router(admin_course_offerings_router, prefix="/api/v1")
app.include_router(profiles_router, prefix="/api/v1")
app.include_router(enrollments_router, prefix="/api/v1")
app.include_router(attendance_router, prefix="/api/v1")
app.include_router(assignments_router, prefix="/api/v1")
app.include_router(notices_router, prefix="/api/v1")
app.include_router(timetable_router, prefix="/api/v1")
app.include_router(files_router, prefix="/api/v1")


@app.exception_handler(NotFoundError)
def not_found_exception_handler(_request: Request, exc: NotFoundError) -> JSONResponse:
    """Map domain NotFoundError to HTTP 404."""
    return JSONResponse(
        status_code=status.HTTP_404_NOT_FOUND,
        content={"detail": str(exc)},
    )


@app.exception_handler(ConflictError)
def conflict_exception_handler(_request: Request, exc: ConflictError) -> JSONResponse:
    """Map domain ConflictError to HTTP 409."""
    return JSONResponse(
        status_code=status.HTTP_409_CONFLICT,
        content={"detail": str(exc)},
    )


@app.exception_handler(BusinessRuleError)
def business_rule_exception_handler(
    _request: Request,
    exc: BusinessRuleError,
) -> JSONResponse:
    """Map domain BusinessRuleError to HTTP 422."""
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        content={"detail": str(exc)},
    )


@app.exception_handler(ForbiddenError)
def forbidden_exception_handler(
    _request: Request,
    exc: ForbiddenError,
) -> JSONResponse:
    """Map domain ForbiddenError to HTTP 403."""
    return JSONResponse(
        status_code=status.HTTP_403_FORBIDDEN,
        content={"detail": str(exc)},
    )


@app.exception_handler(FileValidationError)
def file_validation_exception_handler(
    _request: Request,
    exc: FileValidationError,
) -> JSONResponse:
    """Map FileValidationError to HTTP 422."""
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        content={"detail": str(exc)},
    )


@app.exception_handler(StorageConfigurationError)
def storage_config_exception_handler(
    _request: Request,
    exc: StorageConfigurationError,
) -> JSONResponse:
    """Map missing storage configuration to HTTP 503."""
    return JSONResponse(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        content={"detail": str(exc)},
    )


@app.exception_handler(StorageError)
def storage_exception_handler(
    _request: Request,
    exc: StorageError,
) -> JSONResponse:
    """Map external object storage failure to HTTP 502."""
    logger.error("External storage error: %s", exc)
    return JSONResponse(
        status_code=status.HTTP_502_BAD_GATEWAY,
        content={"detail": "External storage service error."},
    )


@app.exception_handler(Exception)
def unhandled_exception_handler(
    request: Request,
    _exc: Exception,
) -> JSONResponse:
    """Log unexpected errors server-side and return a safe 500 response."""
    logger.exception(
        "Unhandled error during %s %s",
        request.method,
        request.url.path,
    )
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "Internal server error."},
    )


@app.get("/", tags=["Root"])
def read_root() -> dict[str, str]:
    """Return basic API metadata."""
    return {
        "message": "Welcome to College Management System API",
        "app_name": settings.APP_NAME,
        "version": app.version,
    }


@app.get("/health", tags=["Health"])
def health_check() -> dict[str, str]:
    """Return application liveness status."""
    return {
        "status": "ok",
        "environment": settings.APP_ENV,
    }


@app.get("/health/database", tags=["Health"])
def database_health_check(
    db: Annotated[Session, Depends(get_db)],
) -> JSONResponse:
    """Verify database connectivity with a lightweight query."""
    try:
        db.execute(text("SELECT 1"))
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={"status": "ok", "database": "connected"},
        )
    except SQLAlchemyError as exc:
        logger.error("Database health check failed (%s)", type(exc).__name__)
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"status": "error", "database": "unavailable"},
        )
