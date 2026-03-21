"""
Event Publisher - Event Emitter for WebSocket Streaming
"""
from typing import Dict, Callable, List, Any
import asyncio
from app.schemas.event import StreamEvent
from app.utils.logger import setup_logger

logger = setup_logger(__name__)


class EventPublisher:
    """
    Event publisher for streaming agent events to WebSocket clients
    """

    def __init__(self):
        # Session ID -> List of event handlers
        self._subscribers: Dict[str, List[Callable]] = {}

    def subscribe(self, session_id: str, handler: Callable):
        """
        Subscribe to events for a session

        Args:
            session_id: Session ID to subscribe to
            handler: Async callback function to handle events
        """
        if session_id not in self._subscribers:
            self._subscribers[session_id] = []

        self._subscribers[session_id].append(handler)
        logger.debug(f"Handler subscribed to session: {session_id}")

    def unsubscribe(self, session_id: str, handler: Callable):
        """
        Unsubscribe from events for a session

        Args:
            session_id: Session ID to unsubscribe from
            handler: Handler to remove
        """
        if session_id in self._subscribers:
            if handler in self._subscribers[session_id]:
                self._subscribers[session_id].remove(handler)
                logger.debug(f"Handler unsubscribed from session: {session_id}")

            # Clean up empty subscriber lists
            if not self._subscribers[session_id]:
                del self._subscribers[session_id]

    async def publish(self, session_id: str, event: StreamEvent):
        """
        Publish an event to all subscribers of a session

        Args:
            session_id: Session ID to publish to
            event: Event to publish
        """
        if session_id not in self._subscribers:
            logger.debug(f"No subscribers for session: {session_id}")
            return

        logger.debug(f"Publishing event to {len(self._subscribers[session_id])} subscribers")

        # Call all handlers
        tasks = []
        for handler in self._subscribers[session_id]:
            try:
                task = asyncio.create_task(handler(event))
                tasks.append(task)
            except Exception as e:
                logger.error(f"Error calling event handler: {e}", exc_info=True)

        # Wait for all handlers to complete
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    def get_subscriber_count(self, session_id: str) -> int:
        """
        Get number of subscribers for a session

        Args:
            session_id: Session ID

        Returns:
            Number of subscribers
        """
        return len(self._subscribers.get(session_id, []))
