"""Event Publisher - SSE Event Broadcasting System.

This module provides event publishing capabilities for Server-Sent Events (SSE)
streaming to connected clients. It manages event queues and broadcasts events
to active sessions.
"""

import asyncio
from datetime import datetime, timezone
from typing import Any

from computer_use_demo.utils.logger import setup_logger

logger = setup_logger(__name__)


class EventPublisher:
    """Event publisher for streaming agent events to SSE clients.

    Manages event queues per session and provides methods to push events
    that will be streamed to connected clients.
    """

    def __init__(self):
        self._event_queues: dict[str, asyncio.Queue] = {}
        self._lock = asyncio.Lock()

    async def register_session(self, session_id: str, event_queue: asyncio.Queue) -> None:
        """Register an event queue for a session.

        Args:
            session_id: Session ID to register
            event_queue: Queue to receive events
        """
        async with self._lock:
            self._event_queues[session_id] = event_queue
            logger.debug(f"Registered event queue for session: {session_id}")

    async def unregister_session(self, session_id: str) -> None:
        """Unregister an event queue for a session.

        Args:
            session_id: Session ID to unregister
        """
        async with self._lock:
            if session_id in self._event_queues:
                del self._event_queues[session_id]
                logger.debug(f"Unregistered event queue for session: {session_id}")

    async def publish(
        self,
        session_id: str,
        event_type: str,
        data: dict[str, Any],
        event_queue: asyncio.Queue | None = None
    ) -> None:
        """Publish an event to a session's event queue.

        Args:
            session_id: Session ID to publish to
            event_type: Type of the event (e.g., 'text', 'tool_use', 'error')
            data: Event data payload
            event_queue: Optional direct queue reference (bypasses lookup)
        """
        event = {
            "type": event_type,
            "data": data,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        # Use provided queue or look up registered queue
        queue = event_queue or self._event_queues.get(session_id)

        if queue is not None:
            await queue.put(event)
            logger.debug(f"Published {event_type} event to session: {session_id}")
        else:
            logger.warning(f"No event queue registered for session: {session_id}")

    async def publish_to_queue(
        self,
        event_queue: asyncio.Queue,
        event_type: str,
        data: dict[str, Any]
    ) -> None:
        """Publish an event directly to a queue.

        Args:
            event_queue: Queue to publish to
            event_type: Type of the event
            data: Event data payload
        """
        event = {
            "type": event_type,
            "data": data,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        await event_queue.put(event)

    async def signal_end(self, session_id: str, event_queue: asyncio.Queue | None = None) -> None:
        """Signal the end of events for a session.

        Args:
            session_id: Session ID to signal
            event_queue: Optional direct queue reference
        """
        queue = event_queue or self._event_queues.get(session_id)
        if queue is not None:
            await queue.put(None)  # None signals end of stream
            logger.debug(f"Signaled end of events for session: {session_id}")

    def get_subscriber_count(self) -> int:
        """Get number of registered sessions.

        Returns:
            Number of registered event queues
        """
        return len(self._event_queues)


# Global singleton instance
event_publisher = EventPublisher()
