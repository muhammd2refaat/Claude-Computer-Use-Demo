"""Agent Service - Agent Orchestration.

This module provides the main orchestration layer for agent operations.
It coordinates between the session service and agent runner to process
messages and manage agent state.
"""

import asyncio

from anthropic.types.beta import BetaTextBlockParam

from computer_use_demo import db
from computer_use_demo.schemas.models import SSEEventType
from computer_use_demo.services.agent.agent_runner import agent_runner
from computer_use_demo.services.session import session_service
from computer_use_demo.utils.logger import setup_logger

logger = setup_logger(__name__)


class AgentService:
    """Orchestrates agent operations for sessions.

    Provides methods to send messages to agents, stop running agents,
    and stream events from active sessions.
    """

    def __init__(self):
        pass

    async def send_message(self, session_id: str, text: str) -> str:
        """Send a user message to an active session, triggering the agent loop.

        Returns the message ID.
        """
        # Try to restore session if not active
        if not session_service.is_active(session_id):
            await session_service.restore_session(session_id)

        active = session_service.get_active_session(session_id)

        if active.is_running:
            raise RuntimeError("Agent is already processing a request in this session")

        # Store user message
        msg = await db.add_message(session_id, "user", text)

        # Add to Anthropic message format
        active.messages.append({
            "role": "user",
            "content": [BetaTextBlockParam(type="text", text=text)],
        })

        # Update session status
        await db.update_session_status(session_id, "running")

        # Push status event
        from computer_use_demo.core.events import event_publisher
        await event_publisher.publish_to_queue(
            active.event_queue, SSEEventType.STATUS, {"status": "running"}
        )

        # Launch agent loop as a background task
        active.agent_task = asyncio.create_task(
            agent_runner.run_agent_loop(active),
            name=f"agent-{session_id[:8]}",
        )

        return msg["id"]

    async def stop_agent(self, session_id: str) -> bool:
        """Stop a running agent task."""
        if not session_service.is_active(session_id):
            return False

        active = session_service.get_active_session(session_id)

        if active.agent_task and not active.agent_task.done():
            active.agent_task.cancel()
            active.is_running = False
            await db.update_session_status(session_id, "idle")

            from computer_use_demo.core.events import event_publisher
            await event_publisher.publish_to_queue(
                active.event_queue, SSEEventType.STATUS, {"status": "stopped"}
            )

            logger.info(f"Stopped agent task for session {session_id}")
            return True

        return False

    async def get_event_stream(self, session_id: str):
        """Async generator yielding SSE events for a session.

        Yields (event_type, data_json) tuples. Yields None when session ends.
        """
        active = session_service.get_active_session(session_id)

        while True:
            event = await active.event_queue.get()
            if event is None:
                break
            yield event


# Global singleton
agent_service = AgentService()
