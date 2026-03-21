"""Active Session - Runtime state for agent sessions.

This module contains the ActiveSession dataclass that tracks the runtime
state for active agent sessions, including display allocation, message
history, and event queues.
"""

import asyncio
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from computer_use_demo.services.display.display_service import DisplayAllocation
    from computer_use_demo.tools import ToolCollection


@dataclass
class ActiveSession:
    """Runtime state for an active agent session.

    Attributes:
        session_id: Unique identifier for the session
        display: Display allocation with Xvfb/VNC info
        messages: Anthropic API message format history
        event_queue: Queue for SSE events
        tool_collection: Pre-created tools bound to this session's display
        agent_task: Background task running the agent loop
        is_running: Whether the agent is currently processing
    """
    session_id: str
    display: "DisplayAllocation"
    messages: list = field(default_factory=list)
    event_queue: asyncio.Queue = field(default_factory=asyncio.Queue)
    tool_collection: "ToolCollection | None" = None
    agent_task: asyncio.Task | None = None
    is_running: bool = False
