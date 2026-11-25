"""Shared pytest fixtures for test isolation."""

from collections.abc import Generator

import pytest

from app.core.config import get_settings
from app.core.rate_limit import get_login_rate_limiter


@pytest.fixture(autouse=True)
def reset_rate_limiter() -> Generator[None, None, None]:
    """Reset the in-memory login rate limiter before and after every test."""
    settings = get_settings()
    limiter = get_login_rate_limiter(
        settings.LOGIN_RATE_LIMIT_MAX_ATTEMPTS,
        settings.LOGIN_RATE_LIMIT_WINDOW_SECONDS,
    )
    limiter.reset()
    yield
    limiter.reset()
