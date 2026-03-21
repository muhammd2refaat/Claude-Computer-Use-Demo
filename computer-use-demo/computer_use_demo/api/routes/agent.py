"""Agent interaction and SSE streaming routes."""

import asyncio
import json

from fastapi import APIRouter, HTTPException, Request
from sse_starlette.sse import EventSourceResponse

from computer_use_demo.schemas import (
    MessageListResponse,
    MessageResponse,
    MessageSentResponse,
    SendMessageRequest,
)
from computer_use_demo.services.agent import agent_service
from computer_use_demo.services.session import session_service
from computer_use_demo.utils.logger import setup_logger
from computer_use_demo.utils.log_context import set_session_id

logger = setup_logger(__name__, "api")
router = APIRouter(prefix="/api/sessions/{session_id}", tags=["agent"])


@router.post("/messages", response_model=MessageSentResponse, status_code=202)
async def send_message(session_id: str, request: SendMessageRequest):
    """Send a user message to an active session, triggering the agent loop.

    The agent processes asynchronously; use the /stream endpoint for real-time updates.
    """
    try:
        message_id = await agent_service.send_message(session_id, request.text)
        return MessageSentResponse(message_id=message_id, status="processing")
    except KeyError:
        raise HTTPException(status_code=404, detail="Session not found or not active")
    except RuntimeError as e:
        raise HTTPException(status_code=409, detail=str(e))


@router.get("/messages", response_model=MessageListResponse)
async def get_messages(session_id: str):
    """Get chat history for a session."""
    try:
        messages = await session_service.get_messages(session_id)
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
    set_session_id(session_id)

    # Log SSE connection establishment
    logger.info(
        "SSE connection established",
        extra={
            "extra_fields": {
                "session_id": session_id,
                "client_ip": request.client.host if request.client else "unknown",
            }
        }
    )

    try:
        # Verify session exists in DB
        session = await session_service.get_session_info(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")

        # Auto-restore session if not active in memory
        if not session_service.is_active(session_id):
            try:
                await session_service.restore_session(session_id)
            except Exception as e:
                logger.warning(f"Could not restore session {session_id}: {e}")
                # Still proceed — we'll just yield an empty stream
    except KeyError:
        raise HTTPException(status_code=404, detail="Session not found")

    async def event_generator():
        event_count = 0
        try:
            async for event in agent_service.get_event_stream(session_id):
                if await request.is_disconnected():
                    logger.info(
                        "SSE client disconnected",
                        extra={
                            "extra_fields": {
                                "session_id": session_id,
                                "events_sent": event_count,
                            }
                        }
                    )
                    break

                event_count += 1
                yield {
                    "event": event["type"],
                    "data": json.dumps(event["data"]),
                }
        except KeyError:
            # Session not active — just end the stream cleanly
            yield {
                "event": "status",
                "data": json.dumps({"status": "idle"}),
            }
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.exception(
                "SSE stream error",
                extra={
                    "extra_fields": {
                        "session_id": session_id,
                        "events_sent": event_count,
                        "error": str(e),
                    }
                }
            )
        finally:
            logger.info(
                "SSE connection closed",
                extra={
                    "extra_fields": {
                        "session_id": session_id,
                        "total_events": event_count,
                    }
                }
            )

    return EventSourceResponse(event_generator())


@router.post("/stop", status_code=200)
async def stop_agent(session_id: str):
    """Stop a running agent task for this session."""
    try:
        success = await agent_service.stop_agent(session_id)
        if success:
            return {"status": "stopped", "message": "Agent task cancelled"}
        else:
            return {"status": "idle", "message": "No running task to stop"}
    except KeyError:
        raise HTTPException(status_code=404, detail="Session not found")


@router.post("/restore", status_code=200)
async def restore_session(session_id: str):
    """Restore a session from database (reactivate it after restart)."""
    try:
        session = await session_service.restore_session(session_id)
        return {"status": "restored", "session": session}
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))
