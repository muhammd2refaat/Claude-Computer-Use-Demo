"""Session Service - Session Lifecycle Management.

This module handles the lifecycle of agent sessions including creation,
deletion, restoration, and querying. It coordinates with the display
service for virtual display allocation and the database layer for
persistence.
"""

import asyncio
import os
from datetime import datetime, timezone
from typing import Any

from anthropic.types.beta import BetaTextBlockParam

from computer_use_demo import db
from computer_use_demo.config.settings import settings
from computer_use_demo.services.display import display_service, DisplayAllocation
from computer_use_demo.services.session.active_session import ActiveSession
from computer_use_demo.tools import TOOL_GROUPS_BY_VERSION, ToolCollection
from computer_use_demo.utils.logger import setup_logger

logger = setup_logger(__name__)


class SessionService:
    """Manages the lifecycle of agent sessions.

    Handles session creation/deletion, display allocation, and maintains
    the active session registry. The agent loop execution is delegated
    to the AgentRunner service.
    """

    def __init__(self):
        self._active_sessions: dict[str, ActiveSession] = {}
        self._lock = asyncio.Lock()
        self._env_lock = asyncio.Lock()

    async def create_session(self, title: str | None = None) -> dict:
        """Create a new session with its own virtual display and VNC.

        Returns the session record dict with VNC connection info.
        """
        # Allocate a virtual display
        allocation = await display_service.allocate_display()

        # Create DB record
        session = await db.create_session(
            title=title or f"Task {datetime.now(timezone.utc).strftime('%H:%M')}",
            display_num=allocation.display_num,
            vnc_port=allocation.ws_port,
        )

        # Pre-create tools with the correct display environment
        tool_collection = await self._create_tools_for_display(
            allocation.display_num
        )

        # Create runtime state
        active = ActiveSession(
            session_id=session["id"],
            display=allocation,
            messages=[],
            event_queue=asyncio.Queue(),
            tool_collection=tool_collection,
        )

        async with self._lock:
            self._active_sessions[session["id"]] = active

        logger.info(
            f"Session {session['id']} created with display :{allocation.display_num}"
        )
        return session

    async def _create_tools_for_display(
        self, display_num: int
    ) -> ToolCollection:
        """Create a ToolCollection with tools bound to a specific display.

        Uses _env_lock to safely manipulate os.environ during synchronous
        tool __init__ calls (which read DISPLAY_NUM, WIDTH, HEIGHT from env).
        """
        async with self._env_lock:
            original_env = {}
            env_override = {
                "DISPLAY_NUM": str(display_num),
                "DISPLAY": f":{display_num}",
                "WIDTH": str(settings.WIDTH),
                "HEIGHT": str(settings.HEIGHT),
            }
            for key, value in env_override.items():
                original_env[key] = os.environ.get(key)
                os.environ[key] = value

            try:
                tool_group = TOOL_GROUPS_BY_VERSION[settings.DEFAULT_TOOL_VERSION]
                tool_collection = ToolCollection(
                    *(ToolCls() for ToolCls in tool_group.tools)
                )
            finally:
                # Restore env immediately — tool instances store their own state
                for key, original_val in original_env.items():
                    if original_val is None:
                        os.environ.pop(key, None)
                    else:
                        os.environ[key] = original_val

        return tool_collection

    async def delete_session(self, session_id: str) -> bool:
        """Delete a session and clean up its resources."""
        async with self._lock:
            active = self._active_sessions.pop(session_id, None)

        if active:
            # Cancel any running agent task
            if active.agent_task and not active.agent_task.done():
                active.agent_task.cancel()
                try:
                    await active.agent_task
                except asyncio.CancelledError:
                    pass

            # Release the display
            await display_service.release_display(active.display.display_num)

            # Signal SSE clients to disconnect
            await active.event_queue.put(None)

        # Delete from DB
        return await db.delete_session(session_id)

    async def restore_session(self, session_id: str) -> dict:
        """Restore a session from DB (reactivate it).

        This is used when a session exists in DB but not in active memory
        (e.g., after server restart).
        """
        # Check if already active
        if session_id in self._active_sessions:
            return await self.get_session_info(session_id)

        # Get from DB
        session = await db.get_session(session_id)
        if not session:
            raise KeyError(f"Session {session_id} not found in database")

        # Allocate new display (old one is gone after restart)
        allocation = await display_service.allocate_display()

        # Update DB with new display info
        await db.update_session_display(
            session_id,
            display_num=allocation.display_num,
            vnc_port=allocation.ws_port
        )

        # Create tools
        tool_collection = await self._create_tools_for_display(allocation.display_num)

        # Load historical messages
        messages = await db.get_messages(session_id)
        anthropic_messages = []
        for msg in messages:
            if msg["role"] == "user":
                anthropic_messages.append({
                    "role": "user",
                    "content": [BetaTextBlockParam(type="text", text=msg["content"])]
                })

        # Create active session
        active = ActiveSession(
            session_id=session_id,
            display=allocation,
            messages=anthropic_messages,
            event_queue=asyncio.Queue(),
            tool_collection=tool_collection,
        )

        async with self._lock:
            self._active_sessions[session_id] = active

        # Update status to idle (restored)
        await db.update_session_status(session_id, "idle")

        logger.info(f"Restored session {session_id} with new display :{allocation.display_num}")

        # Return updated session info
        return await db.get_session(session_id)

    async def get_session_info(self, session_id: str) -> dict | None:
        """Get session info from DB."""
        return await db.get_session(session_id)

    async def list_sessions(self) -> list[dict]:
        """List all sessions."""
        return await db.list_sessions()

    async def get_messages(self, session_id: str) -> list[dict]:
        """Get message history for a session."""
        return await db.get_messages(session_id)

    async def shutdown(self):
        """Gracefully shut down all sessions."""
        async with self._lock:
            session_ids = list(self._active_sessions.keys())

        for sid in session_ids:
            await self.delete_session(sid)

    def get_active_session(self, session_id: str) -> ActiveSession:
        """Get an active session or raise."""
        active = self._active_sessions.get(session_id)
        if not active:
            raise KeyError(f"Session {session_id} is not active")
        return active

    def is_active(self, session_id: str) -> bool:
        """Check if a session is active in memory."""
        return session_id in self._active_sessions

    def get_active_sessions(self) -> dict[str, ActiveSession]:
        """Get all active sessions."""
        return self._active_sessions


# Global singleton
session_service = SessionService()
