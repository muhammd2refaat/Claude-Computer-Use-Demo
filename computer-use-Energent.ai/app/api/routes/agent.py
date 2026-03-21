"""
Agent Message Routes
"""
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.schemas.agent import MessageRequest, MessageResponse
from app.services.agent.agent_runner import AgentRunner
from app.services.session.session_manager import SessionManager

router = APIRouter()


@router.post("/message", response_model=MessageResponse)
async def send_message(
    message_request: MessageRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """
    Send a message to the agent.
    Processing happens asynchronously. Connect to WebSocket for real-time updates.
    """
    session_manager = SessionManager(db)
    session = await session_manager.get_session(message_request.session_id)

    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    # Run agent in background
    agent_runner = AgentRunner(db)
    background_tasks.add_task(
        agent_runner.process_message,
        session_id=message_request.session_id,
        user_message=message_request.message
    )

    return MessageResponse(
        session_id=message_request.session_id,
        status="processing",
        message="Message received and being processed"
    )
