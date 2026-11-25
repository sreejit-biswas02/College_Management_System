"""Tests for root and health check endpoints."""

from collections.abc import Generator
from unittest.mock import MagicMock

from fastapi.testclient import TestClient
from sqlalchemy.exc import SQLAlchemyError

from app.database.connection import get_db
from app.main import app


def test_read_root() -> None:
    """Root endpoint returns API welcome metadata."""
    with TestClient(app) as client:
        response = client.get("/")

    assert response.status_code == 200
    data = response.json()
    assert data["message"] == "Welcome to College Management System API"
    assert data["version"] == "1.0.0"
    assert "app_name" in data


def test_health_check() -> None:
    """Health endpoint returns application liveness status."""
    with TestClient(app) as client:
        response = client.get("/health")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "environment" in data


def test_database_health_check_success() -> None:
    """Database health endpoint returns 200 when query succeeds."""
    mock_session = MagicMock()
    mock_session.execute.return_value = 1

    def override_get_db() -> Generator[MagicMock, None, None]:
        yield mock_session

    app.dependency_overrides[get_db] = override_get_db
    try:
        with TestClient(app) as client:
            response = client.get("/health/database")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "database": "connected"}
    mock_session.execute.assert_called_once()


def test_database_health_check_failure() -> None:
    """Database health endpoint returns 503 without leaking details on DB error."""
    mock_session = MagicMock()
    mock_session.execute.side_effect = SQLAlchemyError("sensitive-connection-detail")

    def override_get_db() -> Generator[MagicMock, None, None]:
        yield mock_session

    app.dependency_overrides[get_db] = override_get_db
    try:
        with TestClient(app) as client:
            response = client.get("/health/database")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 503
    assert response.json() == {"status": "error", "database": "unavailable"}
    assert "sensitive-connection-detail" not in response.text
