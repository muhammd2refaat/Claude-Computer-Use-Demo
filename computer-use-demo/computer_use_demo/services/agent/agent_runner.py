"""Agent Runner - Background Agent Loop Execution.

This module handles the execution of agent loops in the background.
It runs the sampling loop for a session, processes tool calls, and
streams events to connected clients via SSE.
"""

import asyncio
import os
import time
from typing import Any, cast

import httpx
from anthropic import (
    Anthropic,
    AnthropicBedrock,
    AnthropicVertex,
    APIError,
    APIResponseValidationError,
    APIStatusError,
)
from anthropic.types.beta import (
    BetaContentBlockParam,
    BetaTextBlockParam,
    BetaToolResultBlockParam,
    BetaToolUseBlockParam,
)

from computer_use_demo.config.settings import settings
from computer_use_demo.core.events import event_publisher
from computer_use_demo import db
from computer_use_demo.loop import (
    APIProvider,
    SYSTEM_PROMPT,
    PROMPT_CACHING_BETA_FLAG,
    _response_to_params,
    _maybe_filter_to_n_most_recent_images,
    _inject_prompt_caching,
    _make_api_tool_result,
)
from computer_use_demo.schemas.models import SSEEventType
from computer_use_demo.services.session.active_session import ActiveSession
from computer_use_demo.tools import TOOL_GROUPS_BY_VERSION, ToolResult
from computer_use_demo.utils.logger import setup_logger
from computer_use_demo.utils.log_context import set_session_id

logger = setup_logger(__name__)

# Default API provider
DEFAULT_PROVIDER = APIProvider.ANTHROPIC


class AgentRunner:
    """Runs agent processing asynchronously in background.

    Handles the LLM + tools loop, executing tool calls and streaming
    results back to clients via events.
    """

    def __init__(self):
        pass

    async def run_agent_loop(self, active: ActiveSession) -> None:
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
            api_key = settings.get_api_key()
            if not api_key:
                print("[DEBUG] ERROR: No API key found", flush=True)
                await self._push_event(
                    active, SSEEventType.ERROR,
                    {"message": "ANTHROPIC_API_KEY not set"}
                )
                return

            print(f"[DEBUG] Using API key starting with: {api_key[:15]}...", flush=True)

            active.messages = await self._run_agent_sampling(active, api_key)

            await db.update_session_status(session_id, "idle")
            await self._push_event(active, SSEEventType.DONE, {"status": "completed"})

        except asyncio.CancelledError:
            logger.info(f"Agent loop cancelled for session {session_id}")
            await db.update_session_status(session_id, "idle")
        except Exception as e:
            logger.exception(f"Agent loop error for session {session_id}")
            await db.update_session_status(session_id, "error")
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
        tool_collection = active.tool_collection
        messages = active.messages
        only_n_most_recent_images = 3
        tool_group = TOOL_GROUPS_BY_VERSION[settings.DEFAULT_TOOL_VERSION]

        # Rewrite Anthropic's hardcoded DISPLAY=:1 to dynamically match the concurrent session's isolated display buffer
        dynamic_system_prompt = SYSTEM_PROMPT.replace("DISPLAY=:1", f"DISPLAY=:{active.display.display_num}")

        system = BetaTextBlockParam(type="text", text=dynamic_system_prompt)

        while True:
            enable_prompt_caching = False
            betas = [tool_group.beta_flag] if tool_group.beta_flag else []
            image_truncation_threshold = only_n_most_recent_images or 0

            if DEFAULT_PROVIDER == APIProvider.ANTHROPIC:
                base_url = settings.ANTHROPIC_BASE_URL
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
            use_gemini = settings.is_using_gemini()

            if use_gemini:
                api_start_time = time.time()

                logger.info(
                    "Gemini API request starting",
                    extra={
                        "extra_fields": {
                            "session_id": active.session_id,
                            "provider": "gemini",
                            "message_count": len(messages),
                        }
                    }
                )

                from computer_use_demo.api.gemini_wrapper import run_gemini_sampling
                try:
                    # Pass system prompt so Gemini knows it has tools
                    response_params = await run_gemini_sampling(messages, tool_collection, api_key, system=system)

                    api_duration = time.time() - api_start_time
                    logger.info(
                        "Gemini API call completed",
                        extra={
                            "extra_fields": {
                                "session_id": active.session_id,
                                "provider": "gemini",
                                "duration_ms": round(api_duration * 1000, 2),
                            }
                        }
                    )

                except Exception as e:
                    api_duration = time.time() - api_start_time
                    logger.error(
                        "Gemini API call failed",
                        extra={
                            "extra_fields": {
                                "session_id": active.session_id,
                                "provider": "gemini",
                                "duration_ms": round(api_duration * 1000, 2),
                                "error": str(e),
                            }
                        }
                    )

                    import traceback
                    traceback.print_exc()
                    await self._push_event(
                        active, SSEEventType.ERROR,
                        {"message": f"Gemini API Error: {str(e)}"}
                    )
                    return messages
                messages.append({"role": "assistant", "content": response_params})
            else:
                api_start_time = time.time()

                logger.info(
                    "Anthropic API request starting",
                    extra={
                        "extra_fields": {
                            "session_id": active.session_id,
                            "provider": "anthropic",
                            "model": settings.ANTHROPIC_MODEL,
                            "message_count": len(messages),
                        }
                    }
                )

                print(f"[DEBUG] Using Anthropic API with model: {settings.ANTHROPIC_MODEL}", flush=True)
                print(f"[DEBUG] API Key prefix: {api_key[:20]}...", flush=True)
                print(f"[DEBUG] Base URL: {settings.ANTHROPIC_BASE_URL or 'default'}", flush=True)
                try:
                    raw_response = client.beta.messages.with_raw_response.create(
                        max_tokens=settings.DEFAULT_MAX_TOKENS,
                        messages=messages,
                        model=settings.ANTHROPIC_MODEL,
                        system=[system],
                        tools=tool_collection.to_params(),
                        betas=betas,
                    )
                    print(f"[DEBUG] Got response from Anthropic API", flush=True)

                    api_duration = time.time() - api_start_time
                    response = raw_response.parse()

                    logger.info(
                        "Anthropic API call completed",
                        extra={
                            "extra_fields": {
                                "session_id": active.session_id,
                                "provider": "anthropic",
                                "model": settings.ANTHROPIC_MODEL,
                                "duration_ms": round(api_duration * 1000, 2),
                                "stop_reason": response.stop_reason,
                                "input_tokens": response.usage.input_tokens,
                                "output_tokens": response.usage.output_tokens,
                            }
                        }
                    )

                except (APIStatusError, APIResponseValidationError) as e:
                    api_duration = time.time() - api_start_time

                    logger.error(
                        "Anthropic API call failed",
                        extra={
                            "extra_fields": {
                                "session_id": active.session_id,
                                "provider": "anthropic",
                                "duration_ms": round(api_duration * 1000, 2),
                                "status_code": getattr(e, 'status_code', None),
                                "error": str(e),
                            }
                        }
                    )

                    print(f"[DEBUG] APIStatusError: {e}", flush=True)
                    await self._on_api_response(active, e.request, e.response, e)
                    return messages
                except APIError as e:
                    api_duration = time.time() - api_start_time

                    logger.error(
                        "Anthropic API error",
                        extra={
                            "extra_fields": {
                                "session_id": active.session_id,
                                "provider": "anthropic",
                                "duration_ms": round(api_duration * 1000, 2),
                                "error": str(e),
                            }
                        }
                    )

                    print(f"[DEBUG] APIError: {e}", flush=True)
                    await self._on_api_response(active, e.request, e.body, e)
                    return messages
                except Exception as e:
                    api_duration = time.time() - api_start_time

                    logger.exception(
                        "Anthropic API exception",
                        extra={
                            "extra_fields": {
                                "session_id": active.session_id,
                                "provider": "anthropic",
                                "duration_ms": round(api_duration * 1000, 2),
                                "error_type": type(e).__name__,
                                "error": str(e),
                            }
                        }
                    )

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

                response_params = _response_to_params(response)
                messages.append({"role": "assistant", "content": response_params})

            tool_result_content: list[BetaToolResultBlockParam] = []
            for content_block in response_params:
                await self._on_output(active, content_block)
                if (
                    isinstance(content_block, dict)
                    and content_block.get("type") == "tool_use"
                ):
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
        await event_publisher.publish_to_queue(
            active.event_queue, event_type, data
        )


# Global singleton
agent_runner = AgentRunner()
