"""SSE Event-related Pydantic models."""
from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class SSEEventType(StrEnum):
    """Server-Sent Event types."""
    TEXT = "text"
    THINKING = "thinking"
    TOOL_USE = "tool_use"
    TOOL_RESULT = "tool_result"
    ERROR = "error"
    STATUS = "status"
    DONE = "done"


class SSEEvent(BaseModel):
    """Represents a Server-Sent Event payload."""
    type: SSEEventType
    data: Any
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class ErrorResponse(BaseModel):
    """Error response model."""
    detail: str
    code: str | None = None
