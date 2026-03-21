"""Logging Context - Async context variables for request correlation."""

import contextvars
from typing import Optional

# Context variables for request tracing
correlation_id: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar(
    'correlation_id', default=None
)
session_id: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar(
    'session_id', default=None
)


def set_correlation_id(cid: str) -> None:
    """Set correlation ID for current async context."""
    correlation_id.set(cid)


def get_correlation_id() -> Optional[str]:
    """Get correlation ID from current async context."""
    return correlation_id.get()


def clear_correlation_id() -> None:
    """Clear correlation ID from current async context."""
    correlation_id.set(None)


def set_session_id(sid: str) -> None:
    """Set session ID for current async context."""
    session_id.set(sid)


def get_session_id() -> Optional[str]:
    """Get session ID from current async context."""
    return session_id.get()


def clear_session_id() -> None:
    """Clear session ID from current async context."""
    session_id.set(None)
