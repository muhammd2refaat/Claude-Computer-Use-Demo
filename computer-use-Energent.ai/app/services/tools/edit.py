"""
Edit Tool - File Editing
"""
from typing import Any, Dict
from app.core.tools.base import BaseTool
import os


class EditTool(BaseTool):
    """
    File editing tool
    """

    @property
    def name(self) -> str:
        return "edit"

    @property
    def description(self) -> str:
        return "Edit text files"

    @property
    def input_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["read", "write", "append"],
                    "description": "The editing action to perform"
                },
                "path": {
                    "type": "string",
                    "description": "File path"
                },
                "content": {
                    "type": "string",
                    "description": "Content to write/append"
                }
            },
            "required": ["action", "path"]
        }

    async def execute(self, **kwargs) -> Dict[str, Any]:
        """Execute file editing action"""
        action = kwargs.get("action")
        path = kwargs.get("path")
        content = kwargs.get("content", "")

        if action == "read":
            return await self._read_file(path)
        elif action == "write":
            return await self._write_file(path, content)
        elif action == "append":
            return await self._append_file(path, content)
        else:
            return {"error": f"Unknown action: {action}"}

    async def _read_file(self, path: str) -> Dict[str, Any]:
        """Read file contents"""
        try:
            with open(path, 'r') as f:
                content = f.read()
            return {
                "action": "read",
                "path": path,
                "content": content,
                "success": True
            }
        except Exception as e:
            return {
                "action": "read",
                "path": path,
                "error": str(e),
                "success": False
            }

    async def _write_file(self, path: str, content: str) -> Dict[str, Any]:
        """Write content to file"""
        try:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, 'w') as f:
                f.write(content)
            return {
                "action": "write",
                "path": path,
                "success": True
            }
        except Exception as e:
            return {
                "action": "write",
                "path": path,
                "error": str(e),
                "success": False
            }

    async def _append_file(self, path: str, content: str) -> Dict[str, Any]:
        """Append content to file"""
        try:
            with open(path, 'a') as f:
                f.write(content)
            return {
                "action": "append",
                "path": path,
                "success": True
            }
        except Exception as e:
            return {
                "action": "append",
                "path": path,
                "error": str(e),
                "success": False
            }
