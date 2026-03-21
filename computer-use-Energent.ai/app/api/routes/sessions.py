"""
Session Management Routes
"""
from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.schemas.session import SessionCreate, SessionResponse
from app.services.session.session_manager import SessionManager

router = APIRouter()


@router.post("/sessions", response_model=SessionResponse, status_code=201)
async def create_session(
    session_data: SessionCreate,
    db: Session = Depends(get_db)
):
    """Create a new agent session"""
    session_manager = SessionManager(db)
    session = await session_manager.create_session(session_data)
    return session


@router.get("/sessions", response_model=List[SessionResponse])
async def list_sessions(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    """List all sessions"""
    session_manager = SessionManager(db)
    sessions = await session_manager.list_sessions(skip=skip, limit=limit)
    return sessions


@router.get("/sessions/{session_id}", response_model=SessionResponse)
async def get_session(
    session_id: str,
    db: Session = Depends(get_db)
):
    """Get session details by ID"""
    session_manager = SessionManager(db)
    session = await session_manager.get_session(session_id)

    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    return session
