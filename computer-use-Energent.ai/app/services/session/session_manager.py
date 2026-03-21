"""
Session Manager - Session Lifecycle Management
"""
from typing import List, Optional
from sqlalchemy.orm import Session
import uuid
from datetime import datetime

from app.db.repository import Repository
from app.db.models import Session as SessionModel
from app.schemas.session import SessionCreate, SessionResponse
from app.utils.logger import setup_logger

logger = setup_logger(__name__)


class SessionManager:
    """
    Manages agent session lifecycle
    """

    def __init__(self, db: Session):
        self.db = db
        self.repository = Repository(db)

    async def create_session(self, session_data: SessionCreate) -> SessionResponse:
        """Create a new agent session"""
        session_id = str(uuid.uuid4())

        logger.info(f"Creating new session: {session_id}")

        session = await self.repository.create_session(
            session_id=session_id,
            name=session_data.name,
            metadata=session_data.metadata
        )

        return SessionResponse(
            id=session.id,
            name=session.name,
            status=session.status,
            created_at=session.created_at,
            metadata=session.metadata
        )

    async def get_session(self, session_id: str) -> Optional[SessionResponse]:
        """Get session by ID"""
        session = await self.repository.get_session(session_id)

        if not session:
            return None

        return SessionResponse(
            id=session.id,
            name=session.name,
            status=session.status,
            created_at=session.created_at,
            updated_at=session.updated_at,
            metadata=session.metadata
        )

    async def list_sessions(self, skip: int = 0, limit: int = 100) -> List[SessionResponse]:
        """List all sessions"""
        sessions = await self.repository.list_sessions(skip=skip, limit=limit)

        return [
            SessionResponse(
                id=session.id,
                name=session.name,
                status=session.status,
                created_at=session.created_at,
                updated_at=session.updated_at,
                metadata=session.metadata
            )
            for session in sessions
        ]

    async def update_session_status(self, session_id: str, status: str):
        """Update session status"""
        await self.repository.update_session_status(session_id, status)
        logger.info(f"Session {session_id} status updated to: {status}")

    async def delete_session(self, session_id: str):
        """Delete a session"""
        await self.repository.delete_session(session_id)
        logger.info(f"Session {session_id} deleted")
