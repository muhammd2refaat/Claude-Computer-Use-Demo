"""
Tool Executor - Wraps ToolCollection
"""
from typing import Dict, Any, List
from app.core.tools.collection import ToolCollection
from app.core.tools.groups import ToolGroups
from app.services.tools.bash import BashTool
from app.services.tools.computer import ComputerTool
from app.services.tools.edit import EditTool
from app.utils.logger import setup_logger

logger = setup_logger(__name__)


class ToolExecutor:
    """
    Executes tool calls from LLM responses
    """

    def __init__(self):
        self.tool_collection = ToolCollection()
        self._register_tools()

    def _register_tools(self):
        """Register all available tools"""
        # Register tools
        self.tool_collection.register(BashTool())
        self.tool_collection.register(ComputerTool())
        self.tool_collection.register(EditTool())

        logger.info(f"Registered {len(self.tool_collection.tools)} tools")

    async def execute(self, tool_name: str, tool_input: Dict[str, Any]) -> Any:
        """
        Execute a tool by name with given input
        """
        logger.info(f"Executing tool: {tool_name}")
        logger.debug(f"Tool input: {tool_input}")

        try:
            result = await self.tool_collection.execute(tool_name, tool_input)
            logger.debug(f"Tool result: {result}")
            return result
        except Exception as e:
            logger.error(f"Tool execution failed: {e}", exc_info=True)
            return {"error": str(e), "tool": tool_name}

    def get_tool_definitions(self) -> List[Dict[str, Any]]:
        """
        Get tool definitions for LLM
        """
        return self.tool_collection.get_definitions()

    def get_available_tools(self) -> List[str]:
        """Get list of available tool names"""
        return list(self.tool_collection.tools.keys())
