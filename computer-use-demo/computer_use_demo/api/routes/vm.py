"""VM and VNC management routes."""

import logging

from fastapi import APIRouter, HTTPException

from ..models import VNCInfo
from ..session_manager import session_manager

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/sessions/{session_id}", tags=["vm"])


@router.get("/vnc", response_model=VNCInfo)
async def get_vnc_info(session_id: str):
    """Get VNC connection info for a session's virtual display.

    Returns the VNC port and noVNC URL for embedding in an iframe.
    """
    session = await session_manager.get_session_info(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    if not session.get("display_num") or not session.get("vnc_port"):
        raise HTTPException(
            status_code=503, detail="Display not yet allocated for this session"
        )

    return VNCInfo(
        display_num=session["display_num"],
        vnc_port=session["vnc_port"],
        novnc_url=f"/vnc/?port={session['vnc_port']}&autoconnect=true&resize=scale",
    )
