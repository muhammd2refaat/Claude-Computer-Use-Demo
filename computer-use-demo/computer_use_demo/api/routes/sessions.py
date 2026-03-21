"""Session management API routes."""

import logging

from fastapi import APIRouter, HTTPException

from ..models import (
    CreateSessionRequest,
    SessionListResponse,
    SessionResponse,
    SessionStatus,
    VNCInfo,
)
from ..session_manager import session_manager

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/sessions", tags=["sessions"])


def _session_to_response(session: dict) -> SessionResponse:
    """Convert a DB session dict to a SessionResponse."""
    vnc_info = None
    if session.get("display_num") is not None and session.get("vnc_port") is not None:
        vnc_info = VNCInfo(
            display_num=session["display_num"],
            vnc_port=session["vnc_port"],
            novnc_url=f"/vnc/?host=localhost&port={session['vnc_port']}&autoconnect=true&resize=scale",
        )
    return SessionResponse(
        id=session["id"],
        title=session["title"],
        status=SessionStatus(session["status"]),
        created_at=session["created_at"],
        updated_at=session["updated_at"],
        vnc_info=vnc_info,
    )


@router.post("", response_model=SessionResponse, status_code=201)
async def create_session(request: CreateSessionRequest = CreateSessionRequest()):
    """Create a new agent task session with its own virtual display."""
    try:
        session = await session_manager.create_session(title=request.title)
        return _session_to_response(session)
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))


@router.get("", response_model=SessionListResponse)
async def list_sessions():
    """List all sessions."""
    sessions = await session_manager.list_sessions()
    items = [_session_to_response(s) for s in sessions]
    return SessionListResponse(sessions=items, total=len(items))


@router.get("/{session_id}", response_model=SessionResponse)
async def get_session(session_id: str):
    """Get details of a specific session."""
    session = await session_manager.get_session_info(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return _session_to_response(session)


@router.delete("/{session_id}", status_code=204)
async def delete_session(session_id: str):
    """Delete a session and clean up its resources."""
    deleted = await session_manager.delete_session(session_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Session not found")
