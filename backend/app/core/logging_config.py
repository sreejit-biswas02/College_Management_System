"""Centralized logging configuration for development and production."""

import logging
import sys

from app.core.config import get_settings


def configure_logging() -> None:
    """Configure root logger using standard Python logging."""
    settings = get_settings()
    level = getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO)

    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
        stream=sys.stdout,
        force=True,
    )
    # Reduce noisy SQLAlchemy engine logs unless explicitly debugging.
    logging.getLogger("sqlalchemy.engine").setLevel(
        logging.INFO if settings.DEBUG else logging.WARNING
    )
