"""Message-related Pydantic models."""
from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class MessageRole(StrEnum):
    """Message sender role."""
    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"


class SendMessageRequest(BaseModel):
    """Request to send a message to the agent."""
    text: str = Field(..., min_length=1, description="User message to send to the agent")


class MessageResponse(BaseModel):
    """Message response model."""
    id: str
    session_id: str
    role: MessageRole
    content: Any  # Can be string or structured content blocks
    created_at: datetime


class MessageListResponse(BaseModel):
    """List of messages response."""
    messages: list[MessageResponse]
    total: int


class MessageSentResponse(BaseModel):
    """Response after sending a message."""
    message_id: str
    status: str = "processing"
