"""Collection classes for managing multiple tools."""

import time
from typing import Any, cast

from anthropic.types.beta import BetaToolUnionParam

from computer_use_demo.config.settings import settings
from computer_use_demo.utils.logger import get_logger
from .base import (
    BaseAnthropicTool,
    ToolError,
    ToolFailure,
    ToolResult,
)

logger = get_logger(__name__, "tools")


class ToolCollection:
    """A collection of anthropic-defined tools."""

    def __init__(self, *tools: BaseAnthropicTool):
        self.tools = tools
        self.tool_map = {
            cast(dict[str, Any], tool.to_params())["name"]: tool for tool in tools
        }

    def to_params(
        self,
    ) -> list[BetaToolUnionParam]:
        return [tool.to_params() for tool in self.tools]

    async def run(self, *, name: str, tool_input: dict[str, Any]) -> ToolResult:
        """Execute a tool with comprehensive logging.

        Args:
            name: Tool name to execute
            tool_input: Input parameters for the tool

        Returns:
            ToolResult with output or error
        """
        tool = self.tool_map.get(name)

        if not tool:
            # Log tool not found
            if settings.ENABLE_TOOL_EXECUTION_LOGGING:
                logger.warning(
                    f"Tool not found: {name}",
                    extra={
                        "extra_fields": {
                            "tool_name": name,
                            "available_tools": list(self.tool_map.keys()),
                        }
                    },
                )
            return ToolFailure(error=f"Tool {name} is invalid")

        # Start timing
        start_time = time.time()

        # Log tool execution start
        if settings.ENABLE_TOOL_EXECUTION_LOGGING:
            logger.info(
                f"Tool execution started: {name}",
                extra={
                    "extra_fields": {
                        "tool_name": name,
                        "input": str(tool_input)[:200],  # Truncate to avoid huge logs
                    }
                },
            )

        try:
            result = await tool(**tool_input)
            duration = time.time() - start_time

            # Log successful execution
            if settings.ENABLE_TOOL_EXECUTION_LOGGING:
                logger.info(
                    f"Tool execution completed: {name}",
                    extra={
                        "extra_fields": {
                            "tool_name": name,
                            "duration_ms": round(duration * 1000, 2),
                            "has_output": bool(result.output),
                            "has_error": bool(result.error),
                            "has_image": bool(result.base64_image),
                        }
                    },
                )

            return result

        except ToolError as e:
            duration = time.time() - start_time

            # Log tool error
            if settings.ENABLE_TOOL_EXECUTION_LOGGING:
                logger.error(
                    f"Tool execution failed: {name}",
                    extra={
                        "extra_fields": {
                            "tool_name": name,
                            "duration_ms": round(duration * 1000, 2),
                            "error": e.message,
                        }
                    },
                )

            return ToolFailure(error=e.message)

        except Exception as e:
            duration = time.time() - start_time

            # Log unexpected exception
            if settings.ENABLE_TOOL_EXECUTION_LOGGING:
                logger.exception(
                    f"Tool execution exception: {name}",
                    extra={
                        "extra_fields": {
                            "tool_name": name,
                            "duration_ms": round(duration * 1000, 2),
                            "error_type": type(e).__name__,
                            "error": str(e),
                        }
                    },
                )

            return ToolFailure(error=f"Unexpected error: {str(e)}")
