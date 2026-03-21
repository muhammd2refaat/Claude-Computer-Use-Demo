"""Session-related Pydantic models."""
from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field


class SessionStatus(StrEnum):
    """Session lifecycle status."""
    CREATED = "created"
    RUNNING = "running"
    IDLE = "idle"
    COMPLETED = "completed"
    ERROR = "error"


class VNCInfo(BaseModel):
    """VNC connection information."""
    display_num: int
    vnc_port: int
    novnc_url: str = Field(description="noVNC websocket URL for browser embedding")


class CreateSessionRequest(BaseModel):
    """Request to create a new session."""
    title: str | None = Field(None, description="Optional session title")


class SessionResponse(BaseModel):
    """Session response model."""
    id: str
    title: str
    status: SessionStatus
    created_at: datetime
    updated_at: datetime
    vnc_info: VNCInfo | None = None


class SessionListResponse(BaseModel):
    """List of sessions response."""
    sessions: list[SessionResponse]
    total: int
