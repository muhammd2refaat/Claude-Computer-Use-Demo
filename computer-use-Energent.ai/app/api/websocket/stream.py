"""
WebSocket Streaming Endpoint
"""
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from app.core.events.publisher import EventPublisher
from app.utils.logger import setup_logger

logger = setup_logger(__name__)
router = APIRouter()

# Global event publisher
event_publisher = EventPublisher()


@router.websocket("/{session_id}")
async def websocket_endpoint(websocket: WebSocket, session_id: str):
    """
    WebSocket endpoint for streaming agent events in real-time
    """
    await websocket.accept()
    logger.info(f"WebSocket connection established for session: {session_id}")

    try:
        # Subscribe to events for this session
        async def event_handler(event):
            """Send events to WebSocket client"""
            await websocket.send_json(event.dict())

        event_publisher.subscribe(session_id, event_handler)

        # Keep connection alive and handle incoming messages
        while True:
            data = await websocket.receive_text()
            logger.debug(f"Received WebSocket message: {data}")
            # Handle ping/pong or other client messages if needed

    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected for session: {session_id}")
        event_publisher.unsubscribe(session_id, event_handler)
    except Exception as e:
        logger.error(f"WebSocket error for session {session_id}: {e}")
        event_publisher.unsubscribe(session_id, event_handler)
        await websocket.close()
