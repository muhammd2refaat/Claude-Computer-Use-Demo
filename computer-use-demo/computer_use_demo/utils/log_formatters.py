"""Log Formatters - JSON and context-aware formatters."""

import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict

from computer_use_demo.utils.log_context import get_correlation_id, get_session_id


class JsonFormatter(logging.Formatter):
    """Formats log records as JSON with correlation ID and context."""

    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON string."""
        log_data: Dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(
                record.created, tz=timezone.utc
            ).isoformat(),
            "logger": record.name,
            "level": record.levelname,
            "message": record.getMessage(),
        }

        # Add correlation ID if available
        correlation_id = get_correlation_id()
        if correlation_id:
            log_data["correlation_id"] = correlation_id

        # Add session ID if available
        session_id = get_session_id()
        if session_id:
            log_data["session_id"] = session_id

        # Add extra fields from record
        if hasattr(record, "extra_fields"):
            log_data.update(record.extra_fields)

        # Add exception info if present
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_data)


class ContextFormatter(logging.Formatter):
    """Human-readable formatter with correlation ID injection."""

    def format(self, record: logging.LogRecord) -> str:
        """Format log record with context information."""
        # Get context IDs
        correlation_id = get_correlation_id()
        session_id = get_session_id()

        # Build context prefix
        context_parts = []
        if correlation_id:
            context_parts.append(f"[{correlation_id[:8]}]")
        if session_id:
            context_parts.append(f"[{session_id[:8]}]")

        context_prefix = "".join(context_parts)

        # Format base message
        base_message = super().format(record)

        # Insert context after level
        if context_prefix:
            parts = base_message.split(" - ", 3)
            if len(parts) >= 3:
                return f"{parts[0]} - {parts[1]} - {parts[2]} - {context_prefix} - {parts[3] if len(parts) > 3 else ''}"

        return base_message
