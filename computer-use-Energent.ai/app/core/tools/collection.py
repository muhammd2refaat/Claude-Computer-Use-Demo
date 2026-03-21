"""
Tool Collection - Registry and Executor
"""
from typing import Dict, List, Any
from app.core.tools.base import BaseTool
from app.utils.logger import setup_logger

logger = setup_logger(__name__)


class ToolCollection:
    """
    Registry of available tools with execution capabilities
    """

    def __init__(self):
        self.tools: Dict[str, BaseTool] = {}

    def register(self, tool: BaseTool):
        """
        Register a tool

        Args:
            tool: Tool instance to register
        """
        self.tools[tool.name] = tool
        logger.info(f"Registered tool: {tool.name}")

    def unregister(self, tool_name: str):
        """
        Unregister a tool by name

        Args:
            tool_name: Name of tool to unregister
        """
        if tool_name in self.tools:
            del self.tools[tool_name]
            logger.info(f"Unregistered tool: {tool_name}")

    def get_tool(self, tool_name: str) -> BaseTool:
        """
        Get tool by name

        Args:
            tool_name: Name of tool to retrieve

        Returns:
            Tool instance

        Raises:
            KeyError: If tool not found
        """
        if tool_name not in self.tools:
            raise KeyError(f"Tool not found: {tool_name}")
        return self.tools[tool_name]

    async def execute(self, tool_name: str, tool_input: Dict[str, Any]) -> Any:
        """
        Execute a tool by name

        Args:
            tool_name: Name of tool to execute
            tool_input: Input parameters for tool

        Returns:
            Tool execution result

        Raises:
            KeyError: If tool not found
        """
        tool = self.get_tool(tool_name)
        logger.debug(f"Executing tool: {tool_name}")

        try:
            result = await tool.execute(**tool_input)
            return result
        except Exception as e:
            logger.error(f"Tool execution error: {e}", exc_info=True)
            raise

    def get_definitions(self) -> List[Dict[str, Any]]:
        """
        Get all tool definitions for LLM

        Returns:
            List of tool definitions
        """
        return [tool.to_dict() for tool in self.tools.values()]

    def list_tools(self) -> List[str]:
        """
        List all registered tool names

        Returns:
            List of tool names
        """
        return list(self.tools.keys())
