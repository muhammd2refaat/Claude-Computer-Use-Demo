"""Logging Utility - Centralized logging configuration with dual output."""

import logging
import logging.handlers
import os
import sys
from functools import lru_cache
from pathlib import Path

from computer_use_demo.config.settings import settings
from computer_use_demo.utils.log_formatters import ContextFormatter, JsonFormatter


def _ensure_log_dir() -> Path:
    """Ensure log directory exists."""
    log_dir = Path(settings.LOG_DIR)
    log_dir.mkdir(parents=True, exist_ok=True)
    return log_dir


def _get_log_file_path(component: str = "app") -> Path:
    """Get log file path for component."""
    log_dir = _ensure_log_dir()
    return log_dir / f"{component}.log"


def _create_console_handler() -> logging.StreamHandler:
    """Create console handler with human-readable formatting."""
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(
        ContextFormatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )
    )
    return handler


def _create_file_handler(component: str = "app") -> logging.handlers.RotatingFileHandler:
    """Create rotating file handler with JSON formatting."""
    log_file = _get_log_file_path(component)
    handler = logging.handlers.RotatingFileHandler(
        log_file,
        maxBytes=settings.LOG_MAX_SIZE_MB * 1024 * 1024,  # Convert MB to bytes
        backupCount=settings.LOG_BACKUP_COUNT,
    )
    handler.setFormatter(JsonFormatter())
    return handler


@lru_cache
def setup_logger(name: str, component: str = "app") -> logging.Logger:
    """Set up and return a logger with dual output (console + file).

    Args:
        name: The logger name (typically __name__)
        component: Component name for log file (app, api, database, tools)

    Returns:
        Configured logger instance with dual handlers
    """
    logger = logging.getLogger(name)

    if not logger.handlers:
        # Add console handler (human-readable)
        log_format = settings.LOG_FORMAT.lower()

        if log_format in ("console", "dual"):
            console_handler = _create_console_handler()
            logger.addHandler(console_handler)

        # Add file handler (JSON)
        if log_format in ("json", "dual"):
            try:
                file_handler = _create_file_handler(component)
                logger.addHandler(file_handler)
            except Exception as e:
                # Fallback to console only if file handler fails
                print(f"Warning: Could not create file handler: {e}", file=sys.stderr)

    logger.setLevel(getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO))

    return logger


def get_logger(name: str, component: str = "app") -> logging.Logger:
    """Get logger for specific component.

    Args:
        name: The logger name (typically __name__)
        component: Component name (app, api, database, tools)

    Returns:
        Configured logger instance

    Example:
        logger = get_logger(__name__, "api")
        logger = get_logger(__name__, "database")
        logger = get_logger(__name__, "tools")
    """
    return setup_logger(name, component)
