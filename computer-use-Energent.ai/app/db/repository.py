"""
Repository - Data Access Layer
"""
from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import desc
from app.db.models import Session as SessionModel, Message, ToolCall
from datetime import datetime


class Repository:
    """
    Database repository for data access operations
    """

    def __init__(self, db: Session):
        self.db = db

    # Session operations
    async def create_session(
        self,
        session_id: str,
        name: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> SessionModel:
        """Create a new session"""
        session = SessionModel(
            id=session_id,
            name=name,
            metadata=metadata or {}
        )
        self.db.add(session)
        self.db.commit()
        self.db.refresh(session)
        return session

    async def get_session(self, session_id: str) -> Optional[SessionModel]:
        """Get session by ID"""
        return self.db.query(SessionModel).filter(SessionModel.id == session_id).first()

    async def list_sessions(self, skip: int = 0, limit: int = 100) -> List[SessionModel]:
        """List all sessions"""
        return (
            self.db.query(SessionModel)
            .order_by(desc(SessionModel.created_at))
            .offset(skip)
            .limit(limit)
            .all()
        )

    async def update_session_status(self, session_id: str, status: str):
        """Update session status"""
        session = await self.get_session(session_id)
        if session:
            session.status = status
            session.updated_at = datetime.utcnow()
            self.db.commit()

    async def delete_session(self, session_id: str):
        """Delete a session"""
        session = await self.get_session(session_id)
        if session:
            self.db.delete(session)
            self.db.commit()

    # Message operations
    async def save_message(
        self,
        session_id: str,
        role: str,
        content: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Message:
        """Save a message"""
        message = Message(
            session_id=session_id,
            role=role,
            content=content,
            metadata=metadata or {}
        )
        self.db.add(message)
        self.db.commit()
        self.db.refresh(message)
        return message

    async def get_conversation_history(self, session_id: str) -> List[Dict[str, Any]]:
        """Get conversation history for a session"""
        messages = (
            self.db.query(Message)
            .filter(Message.session_id == session_id)
            .order_by(Message.created_at)
            .all()
        )

        return [
            {
                "role": msg.role,
                "content": msg.content
            }
            for msg in messages
        ]

    # Tool call operations (optional)
    async def log_tool_call(
        self,
        session_id: str,
        tool_name: str,
        tool_input: Dict[str, Any]
    ) -> ToolCall:
        """Log a tool call"""
        tool_call = ToolCall(
            session_id=session_id,
            tool_name=tool_name,
            tool_input=tool_input
        )
        self.db.add(tool_call)
        self.db.commit()
        self.db.refresh(tool_call)
        return tool_call

    async def update_tool_call(
        self,
        tool_call_id: str,
        tool_output: Optional[Dict[str, Any]] = None,
        status: str = "success",
        error: Optional[str] = None
    ):
        """Update tool call result"""
        tool_call = self.db.query(ToolCall).filter(ToolCall.id == tool_call_id).first()
        if tool_call:
            tool_call.tool_output = tool_output
            tool_call.status = status
            tool_call.error = error
            tool_call.completed_at = datetime.utcnow()
            self.db.commit()
