"""
Session Schemas
"""
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any
from datetime import datetime


class SessionCreate(BaseModel):
    """Request model for creating a session"""
    name: Optional[str] = Field(None, description="Session name")
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Additional metadata")


class SessionResponse(BaseModel):
    """Response model for session details"""
    id: str
    name: Optional[str] = None
    status: str
    created_at: datetime
    updated_at: Optional[datetime] = None
    metadata: Optional[Dict[str, Any]] = None

    class Config:
        from_attributes = True
