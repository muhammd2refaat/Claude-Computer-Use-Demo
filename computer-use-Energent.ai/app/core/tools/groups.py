"""
Tool Groups - Organize Tools into Logical Groups
"""
from typing import List, Dict
from enum import Enum


class ToolGroup(str, Enum):
    """Tool group categories"""
    BASH = "bash"
    COMPUTER = "computer"
    EDIT = "edit"
    ALL = "all"


class ToolGroups:
    """
    Organize tools into logical groups for easier management
    """

    GROUPS: Dict[ToolGroup, List[str]] = {
        ToolGroup.BASH: ["bash"],
        ToolGroup.COMPUTER: ["computer"],
        ToolGroup.EDIT: ["edit"],
        ToolGroup.ALL: ["bash", "computer", "edit"]
    }

    @classmethod
    def get_tools_for_group(cls, group: ToolGroup) -> List[str]:
        """
        Get list of tool names in a group

        Args:
            group: Tool group

        Returns:
            List of tool names
        """
        return cls.GROUPS.get(group, [])

    @classmethod
    def get_all_tools(cls) -> List[str]:
        """
        Get all available tool names

        Returns:
            List of all tool names
        """
        return cls.GROUPS[ToolGroup.ALL]

    @classmethod
    def is_tool_in_group(cls, tool_name: str, group: ToolGroup) -> bool:
        """
        Check if a tool belongs to a group

        Args:
            tool_name: Name of tool
            group: Tool group

        Returns:
            True if tool is in group
        """
        return tool_name in cls.GROUPS.get(group, [])
