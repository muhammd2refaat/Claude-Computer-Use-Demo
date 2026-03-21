"""
Agent Schemas - Request/Response Models
"""
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any


class MessageRequest(BaseModel):
    """Request model for sending a message to the agent"""
    session_id: str = Field(..., description="Session ID")
    message: str = Field(..., description="User message")


class MessageResponse(BaseModel):
    """Response model for message submission"""
    session_id: str
    status: str
    message: str


class ToolCallSchema(BaseModel):
    """Schema for tool execution details"""
    tool_name: str
    tool_input: Dict[str, Any]
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
