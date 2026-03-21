"""
Bash Tool - Stateless Implementation
"""
from typing import Any, Dict
from app.core.tools.base import BaseTool
from app.core.execution.run import CommandExecutor


class BashTool(BaseTool):
    """
    Execute bash commands
    """

    @property
    def name(self) -> str:
        return "bash"

    @property
    def description(self) -> str:
        return "Execute bash commands in the terminal"

    @property
    def input_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "description": "The bash command to execute"
                },
                "timeout": {
                    "type": "number",
                    "description": "Timeout in seconds (default: 30)",
                    "default": 30
                }
            },
            "required": ["command"]
        }

    async def execute(self, **kwargs) -> Dict[str, Any]:
        """Execute bash command"""
        command = kwargs.get("command")
        timeout = kwargs.get("timeout", 30)

        executor = CommandExecutor()
        result = await executor.run_command(command, timeout=timeout)

        return {
            "stdout": result.get("stdout", ""),
            "stderr": result.get("stderr", ""),
            "exit_code": result.get("exit_code", 0),
            "success": result.get("exit_code", 0) == 0
        }
