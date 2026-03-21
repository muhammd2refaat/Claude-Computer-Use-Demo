"""Agent interaction and SSE streaming routes."""

import asyncio
import json
import logging

from fastapi import APIRouter, HTTPException, Request
from sse_starlette.sse import EventSourceResponse

from ..models import (
    MessageListResponse,
    MessageResponse,
    MessageSentResponse,
    SendMessageRequest,
)
from ..session_manager import session_manager

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/sessions/{session_id}", tags=["agent"])


@router.post("/messages", response_model=MessageSentResponse, status_code=202)
async def send_message(session_id: str, request: SendMessageRequest):
    """Send a user message to an active session, triggering the agent loop.

    The agent processes asynchronously; use the /stream endpoint for real-time updates.
    """
    try:
        message_id = await session_manager.send_message(session_id, request.text)
        return MessageSentResponse(message_id=message_id, status="processing")
    except KeyError:
        raise HTTPException(status_code=404, detail="Session not found or not active")
    except RuntimeError as e:
        raise HTTPException(status_code=409, detail=str(e))


@router.get("/messages", response_model=MessageListResponse)
async def get_messages(session_id: str):
    """Get chat history for a session."""
    try:
        messages = await session_manager.get_messages(session_id)
        items = [
            MessageResponse(
                id=m["id"],
                session_id=m["session_id"],
                role=m["role"],
                content=m["content"],
                created_at=m["created_at"],
            )
            for m in messages
        ]
        return MessageListResponse(messages=items, total=len(items))
    except KeyError:
        raise HTTPException(status_code=404, detail="Session not found")


@router.get("/stream")
async def stream_events(session_id: str, request: Request):
    """SSE endpoint for real-time agent progress updates.

    Connect with EventSource in the browser to receive events:
    - text: Agent text response
    - thinking: Agent thinking content
    - tool_use: Tool invocation details
    - tool_result: Tool execution results
    - status: Session status changes
    - error: Error messages
    - done: Agent loop completed
    """
    try:
        # Verify session exists
        session = await session_manager.get_session_info(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
    except KeyError:
        raise HTTPException(status_code=404, detail="Session not found")

    async def event_generator():
        try:
            async for event in session_manager.get_event_stream(session_id):
                if await request.is_disconnected():
                    break
                yield {
                    "event": event["type"],
                    "data": json.dumps(event["data"]),
                }
        except KeyError:
            yield {
                "event": "error",
                "data": json.dumps({"message": "Session not found"}),
            }
        except asyncio.CancelledError:
            pass

    return EventSourceResponse(event_generator())
