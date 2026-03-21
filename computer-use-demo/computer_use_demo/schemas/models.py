"""Pydantic request/response models for the Computer Use API."""

from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


# --- Enums ---

class SessionStatus(StrEnum):
    CREATED = "created"
    RUNNING = "running"
    IDLE = "idle"
    COMPLETED = "completed"
    ERROR = "error"


class MessageRole(StrEnum):
    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"


class SSEEventType(StrEnum):
    TEXT = "text"
    THINKING = "thinking"
    TOOL_USE = "tool_use"
    TOOL_RESULT = "tool_result"
    ERROR = "error"
    STATUS = "status"
    DONE = "done"


# --- Requests ---

class CreateSessionRequest(BaseModel):
    title: str | None = Field(None, description="Optional session title")


class SendMessageRequest(BaseModel):
    text: str = Field(..., min_length=1, description="User message to send to the agent")


# --- Responses ---

class VNCInfo(BaseModel):
    display_num: int
    vnc_port: int
    novnc_url: str = Field(description="noVNC websocket URL for browser embedding")


class SessionResponse(BaseModel):
    id: str
    title: str
    status: SessionStatus
    created_at: datetime
    updated_at: datetime
    vnc_info: VNCInfo | None = None


class SessionListResponse(BaseModel):
    sessions: list[SessionResponse]
    total: int


class MessageResponse(BaseModel):
    id: str
    session_id: str
    role: MessageRole
    content: Any  # Can be string or structured content blocks
    created_at: datetime


class MessageListResponse(BaseModel):
    messages: list[MessageResponse]
    total: int


class MessageSentResponse(BaseModel):
    message_id: str
    status: str = "processing"


class SSEEvent(BaseModel):
    """Represents a Server-Sent Event payload."""
    type: SSEEventType
    data: Any
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class ErrorResponse(BaseModel):
    detail: str
    code: str | None = None
