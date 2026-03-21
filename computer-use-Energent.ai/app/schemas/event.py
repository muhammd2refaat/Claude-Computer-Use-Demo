"""
Event Schemas - Streaming Event Models
"""
from pydantic import BaseModel, Field
from typing import Dict, Any
from enum import Enum
from datetime import datetime


class EventType(str, Enum):
    """Event types for streaming"""
    AGENT_THINKING = "agent.thinking"
    TOOL_CALLED = "tool.called"
    TOOL_RESULT = "tool.result"
    AGENT_RESPONSE = "agent.response"
    AGENT_ERROR = "agent.error"


class StreamEvent(BaseModel):
    """Streaming event model"""
    session_id: str = Field(..., description="Session ID")
    event_type: EventType = Field(..., description="Event type")
    data: Dict[str, Any] = Field(..., description="Event payload")
    timestamp: datetime = Field(default_factory=datetime.now, description="Event timestamp")

    class Config:
        use_enum_values = True
