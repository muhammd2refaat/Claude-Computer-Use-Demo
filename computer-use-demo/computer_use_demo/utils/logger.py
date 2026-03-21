"""Logging Utility - Centralized logging configuration."""

import logging
import sys
from functools import lru_cache

from computer_use_demo.config.settings import settings


@lru_cache
def setup_logger(name: str) -> logging.Logger:
    """Set up and return a logger with consistent formatting.

    Args:
        name: The logger name (typically __name__)

    Returns:
        Configured logger instance
    """
    logger = logging.getLogger(name)

    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(
            logging.Formatter(
                "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
            )
        )
        logger.addHandler(handler)

    logger.setLevel(getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO))

    return logger


def get_logger(name: str) -> logging.Logger:
    """Alias for setup_logger for consistency with other modules."""
    return setup_logger(name)
