"""Schemas module - Pydantic request/response models."""
from .session import (
    SessionStatus,
    VNCInfo,
    CreateSessionRequest,
    SessionResponse,
    SessionListResponse,
)
from .event import (
    SSEEventType,
    SSEEvent,
    ErrorResponse,
)
from .message import (
    MessageRole,
    SendMessageRequest,
    MessageResponse,
    MessageListResponse,
    MessageSentResponse,
)
# Also export from models.py for convenience
from .models import (
    SessionStatus as SessionStatusModel,
    MessageRole as MessageRoleModel,
    SSEEventType as SSEEventTypeModel,
)

__all__ = [
    # Session
    "SessionStatus",
    "VNCInfo",
    "CreateSessionRequest",
    "SessionResponse",
    "SessionListResponse",
    # Event
    "SSEEventType",
    "SSEEvent",
    "ErrorResponse",
    # Message
    "MessageRole",
    "SendMessageRequest",
    "MessageResponse",
    "MessageListResponse",
    "MessageSentResponse",
]
