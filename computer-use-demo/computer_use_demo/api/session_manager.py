"""Session manager: orchestrates agent loops, SSE streaming, and display lifecycle.

Each session runs its sampling_loop in its own asyncio.Task with a dedicated
virtual display, enabling true parallel execution of multiple agent sessions.
"""

import asyncio
import json
import logging
import os
from datetime import datetime, timezone
from typing import Any

import httpx
from anthropic.types.beta import BetaContentBlockParam, BetaTextBlockParam

from dataclasses import dataclass

from computer_use_demo.loop import APIProvider, sampling_loop
from computer_use_demo.tools import (
    TOOL_GROUPS_BY_VERSION,
    ToolCollection,
    ToolResult,
    ToolVersion,
)

from . import database as db
from .display_manager import DisplayAllocation, display_manager
from .models import SessionStatus, SSEEventType

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Default model configuration
DEFAULT_MODEL = os.environ.get("ANTHROPIC_MODEL", "claude-haiku-4-5-20251001")
DEFAULT_PROVIDER = APIProvider.ANTHROPIC
DEFAULT_TOOL_VERSION: ToolVersion = "computer_use_20250124"
DEFAULT_MAX_TOKENS = 4096 * 4


@dataclass
class ActiveSession:
    """Runtime state for an active agent session."""
    session_id: str
    display: DisplayAllocation
    messages: list  # Anthropic API message format
    event_queue: asyncio.Queue
    tool_collection: ToolCollection | None = None
    agent_task: asyncio.Task | None = None
    is_running: bool = False


class SessionManager:
    """Manages the lifecycle of agent sessions.

    Handles session creation/deletion, display allocation, agent loop execution,
    and SSE event broadcasting.
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
        allocation = await display_manager.allocate_display()

        # Create DB record
        session = await db.create_session(
            title=title or f"Task {datetime.now(timezone.utc).strftime('%H:%M')}",
            display_num=allocation.display_num,
            vnc_port=allocation.ws_port,
        )

        # Pre-create tools with the correct display environment
        # This is done under a lock to prevent concurrent env manipulation
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
                "WIDTH": str(os.getenv("WIDTH", "1024")),
                "HEIGHT": str(os.getenv("HEIGHT", "768")),
            }
            for key, value in env_override.items():
                original_env[key] = os.environ.get(key)
                os.environ[key] = value

            try:
                tool_group = TOOL_GROUPS_BY_VERSION[DEFAULT_TOOL_VERSION]
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
            await display_manager.release_display(active.display.display_num)

            # Signal SSE clients to disconnect
            await active.event_queue.put(None)

        # Delete from DB
        return await db.delete_session(session_id)

    async def send_message(self, session_id: str, text: str) -> str:
        """Send a user message to an active session, triggering the agent loop.

        Returns the message ID.
        """
        active = self._get_active_session(session_id)

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
        await db.update_session_status(session_id, SessionStatus.RUNNING)

        # Push status event
        await self._push_event(active, SSEEventType.STATUS, {"status": "running"})

        # Launch agent loop as a background task
        active.agent_task = asyncio.create_task(
            self._run_agent_loop(active),
            name=f"agent-{session_id[:8]}",
        )

        return msg["id"]

    async def get_event_stream(self, session_id: str):
        """Async generator yielding SSE events for a session.

        Yields (event_type, data_json) tuples. Yields None when session ends.
        """
        active = self._get_active_session(session_id)

        while True:
            event = await active.event_queue.get()
            if event is None:
                break
            yield event

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

    def _get_active_session(self, session_id: str) -> ActiveSession:
        """Get an active session or raise."""
        active = self._active_sessions.get(session_id)
        if not active:
            raise KeyError(f"Session {session_id} is not active")
        return active

    # --- Agent Loop Integration ---

    async def _run_agent_loop(self, active: ActiveSession) -> None:
        """Run the sampling loop for a session in the background.

        This wraps the existing loop.py::sampling_loop with our own callbacks
        that push events to the SSE queue and persist messages to the DB.

        CONCURRENCY: Tools are pre-created per-session during create_session()
        with the correct DISPLAY_NUM. The sampling_loop's internal tool creation
        is bypassed by using our own _run_agent_sampling method.
        """
        active.is_running = True
        session_id = active.session_id
        print(f"[DEBUG] Starting agent loop for session {session_id}", flush=True)

        try:
            # Prioritize Anthropic API key over Gemini
            api_key = os.environ.get("ANTHROPIC_API_KEY", "") or os.environ.get("GEMINI_API_KEY", "")
            if not api_key:
                print("[DEBUG] ERROR: No API key found", flush=True)
                await self._push_event(
                    active, SSEEventType.ERROR,
                    {"message": "ANTHROPIC_API_KEY not set"}
                )
                return

            print(f"[DEBUG] Using API key starting with: {api_key[:15]}...", flush=True)

            active.messages = await self._run_agent_sampling(active, api_key)

            await db.update_session_status(session_id, SessionStatus.IDLE)
            await self._push_event(active, SSEEventType.DONE, {"status": "completed"})

        except asyncio.CancelledError:
            logger.info(f"Agent loop cancelled for session {session_id}")
            await db.update_session_status(session_id, SessionStatus.IDLE)
        except Exception as e:
            logger.exception(f"Agent loop error for session {session_id}")
            await db.update_session_status(session_id, SessionStatus.ERROR)
            await self._push_event(
                active, SSEEventType.ERROR, {"message": str(e)}
            )
        finally:
            active.is_running = False

    async def _run_agent_sampling(
        self, active: ActiveSession, api_key: str
    ) -> list:
        """Run the agent sampling loop using session-specific pre-built tools.

        This reimplements the core of loop.py::sampling_loop but uses the
        pre-created tool_collection from the session, avoiding the need to
        manipulate os.environ at runtime and enabling true parallelism.
        """
        from anthropic import (
            Anthropic,
            AnthropicBedrock,
            AnthropicVertex,
            APIError,
            APIResponseValidationError,
            APIStatusError,
        )
        from anthropic.types.beta import (
            BetaCacheControlEphemeralParam,
            BetaTextBlockParam,
            BetaToolResultBlockParam,
            BetaToolUseBlockParam,
        )
        from computer_use_demo.loop import (
            SYSTEM_PROMPT,
            PROMPT_CACHING_BETA_FLAG,
            _response_to_params,
            _maybe_filter_to_n_most_recent_images,
            _inject_prompt_caching,
            _make_api_tool_result,
        )

        tool_collection = active.tool_collection
        messages = active.messages
        only_n_most_recent_images = 3
        tool_group = TOOL_GROUPS_BY_VERSION[DEFAULT_TOOL_VERSION]
        
        # Rewrite Anthropic's hardcoded DISPLAY=:1 to dynamically match the concurrent session's isolated display buffer
        dynamic_system_prompt = SYSTEM_PROMPT.replace("DISPLAY=:1", f"DISPLAY=:{active.display.display_num}")

        system = BetaTextBlockParam(type="text", text=dynamic_system_prompt)

        while True:
            enable_prompt_caching = False
            betas = [tool_group.beta_flag] if tool_group.beta_flag else []
            image_truncation_threshold = only_n_most_recent_images or 0

            if DEFAULT_PROVIDER == APIProvider.ANTHROPIC:
                base_url = os.environ.get("ANTHROPIC_BASE_URL")
                if base_url:
                    client = Anthropic(api_key=api_key, base_url=base_url, max_retries=4)
                else:
                    client = Anthropic(api_key=api_key, max_retries=4)
                enable_prompt_caching = True
            elif DEFAULT_PROVIDER == APIProvider.VERTEX:
                client = AnthropicVertex()
            elif DEFAULT_PROVIDER == APIProvider.BEDROCK:
                client = AnthropicBedrock()

            if enable_prompt_caching:
                betas.append(PROMPT_CACHING_BETA_FLAG)
                _inject_prompt_caching(messages)
                only_n_most_recent_images = 0
                system["cache_control"] = {"type": "ephemeral"}

            current_images_to_keep = only_n_most_recent_images
            if current_images_to_keep:
                _maybe_filter_to_n_most_recent_images(
                    messages,
                    current_images_to_keep,
                    min_removal_threshold=image_truncation_threshold,
                )

            # Use Gemini only if the API key starts with "AIza" (Google API key format)
            use_gemini = api_key.startswith("AIza")

            if use_gemini:
                logger.info("Using Gemini API")
                from .gemini_wrapper import run_gemini_sampling
                try:
                    # Pass system prompt so Gemini knows it has tools
                    response_params = await run_gemini_sampling(messages, tool_collection, api_key, system=system)
                except Exception as e:
                    import traceback
                    traceback.print_exc()
                    await self._push_event(
                        active, SSEEventType.ERROR,
                        {"message": f"Gemini API Error: {str(e)}"}
                    )
                    return messages
                messages.append({"role": "assistant", "content": response_params})
            else:
                logger.info(f"Using Anthropic API with model: {DEFAULT_MODEL}")
                print(f"[DEBUG] Using Anthropic API with model: {DEFAULT_MODEL}", flush=True)
                print(f"[DEBUG] API Key prefix: {api_key[:20]}...", flush=True)
                print(f"[DEBUG] Base URL: {os.environ.get('ANTHROPIC_BASE_URL', 'default')}", flush=True)
                try:
                    raw_response = client.beta.messages.with_raw_response.create(
                        max_tokens=DEFAULT_MAX_TOKENS,
                        messages=messages,
                        model=DEFAULT_MODEL,
                        system=[system],
                        tools=tool_collection.to_params(),
                        betas=betas,
                    )
                    print(f"[DEBUG] Got response from Anthropic API", flush=True)
                except (APIStatusError, APIResponseValidationError) as e:
                    print(f"[DEBUG] APIStatusError: {e}", flush=True)
                    await self._on_api_response(active, e.request, e.response, e)
                    return messages
                except APIError as e:
                    print(f"[DEBUG] APIError: {e}", flush=True)
                    await self._on_api_response(active, e.request, e.body, e)
                    return messages
                except Exception as e:
                    print(f"[DEBUG] Unexpected error: {type(e).__name__}: {e}", flush=True)
                    import traceback
                    traceback.print_exc()
                    await self._push_event(
                        active, SSEEventType.ERROR,
                        {"message": f"API Error: {str(e)}"}
                    )
                    return messages
    
                await self._on_api_response(
                    active,
                    raw_response.http_response.request,
                    raw_response.http_response,
                    None,
                )
    
                response = raw_response.parse()
                response_params = _response_to_params(response)
                messages.append({"role": "assistant", "content": response_params})

            tool_result_content: list[BetaToolResultBlockParam] = []
            for content_block in response_params:
                await self._on_output(active, content_block)
                if (
                    isinstance(content_block, dict)
                    and content_block.get("type") == "tool_use"
                ):
                    from typing import cast
                    tool_use_block = cast(BetaToolUseBlockParam, content_block)
                    result = await tool_collection.run(
                        name=tool_use_block["name"],
                        tool_input=cast(dict[str, Any], tool_use_block.get("input", {})),
                    )
                    tool_result_content.append(
                        _make_api_tool_result(result, tool_use_block["id"])
                    )
                    await self._on_tool_output(active, result, tool_use_block["id"])

            if not tool_result_content:
                return messages

            messages.append({"content": tool_result_content, "role": "user"})

    # --- Callbacks ---

    async def _on_output(
        self, active: ActiveSession, block: BetaContentBlockParam
    ) -> None:
        """Handle an output block from the agent."""
        if isinstance(block, dict):
            block_type = block.get("type", "unknown")

            if block_type == "text":
                await self._push_event(
                    active, SSEEventType.TEXT, {"text": block.get("text", "")}
                )
                await db.add_message(
                    active.session_id, "assistant", {"type": "text", "text": block.get("text", "")}
                )

            elif block_type == "thinking":
                await self._push_event(
                    active, SSEEventType.THINKING,
                    {"thinking": block.get("thinking", "")}
                )

            elif block_type == "tool_use":
                await self._push_event(
                    active, SSEEventType.TOOL_USE,
                    {
                        "tool_id": block.get("id", ""),
                        "name": block.get("name", ""),
                        "input": block.get("input", {}),
                    }
                )
                await db.add_message(
                    active.session_id, "assistant",
                    {"type": "tool_use", "name": block.get("name"), "input": block.get("input")}
                )

    async def _on_tool_output(
        self, active: ActiveSession, result: ToolResult, tool_id: str
    ) -> None:
        """Handle a tool execution result."""
        event_data: dict[str, Any] = {"tool_id": tool_id}

        if result.output:
            event_data["output"] = result.output
        if result.error:
            event_data["error"] = result.error
        if result.base64_image:
            # Send a truncated indicator; full image available via VNC
            event_data["has_screenshot"] = True

        await self._push_event(active, SSEEventType.TOOL_RESULT, event_data)

        # Store without the base64 image to save DB space
        db_content = {
            "type": "tool_result",
            "tool_id": tool_id,
            "output": result.output,
            "error": result.error,
        }
        await db.add_message(active.session_id, "tool", db_content)

    async def _on_api_response(
        self,
        active: ActiveSession,
        request: httpx.Request,
        response: httpx.Response | object | None,
        error: Exception | None,
    ) -> None:
        """Handle API response/error logging."""
        if error:
            await self._push_event(
                active, SSEEventType.ERROR,
                {"message": f"API Error: {str(error)}"}
            )

    async def _push_event(
        self, active: ActiveSession, event_type: SSEEventType, data: dict
    ) -> None:
        """Push an event to the session's SSE queue."""
        event = {
            "type": event_type,
            "data": data,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        await active.event_queue.put(event)


# Global singleton
session_manager = SessionManager()
