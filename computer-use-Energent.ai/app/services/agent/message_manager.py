"""
Message Manager - Message Formatting & History
"""
from typing import List, Dict, Any


class MessageManager:
    """
    Manages message formatting and conversation history
    """

    def __init__(self, system_prompt: str = None):
        self.system_prompt = system_prompt or self._default_system_prompt()

    def _default_system_prompt(self) -> str:
        """Default system prompt for the agent"""
        return """You are a helpful AI assistant with access to computer control tools.
You can interact with the computer through bash commands, screen viewing, and input controls.
Be helpful, accurate, and safe in your interactions."""

    def add_user_message(
        self,
        conversation_history: List[Dict],
        message: str
    ) -> List[Dict]:
        """Add user message to conversation history"""
        conversation_history.append({
            "role": "user",
            "content": message
        })
        return conversation_history

    def add_assistant_response(
        self,
        conversation_history: List[Dict],
        response: Any
    ) -> List[Dict]:
        """Add assistant response to conversation history"""
        # Format response content
        content = []

        for block in response.content:
            if hasattr(block, 'text'):
                content.append({
                    "type": "text",
                    "text": block.text
                })
            elif hasattr(block, 'name'):  # tool_use block
                content.append({
                    "type": "tool_use",
                    "id": block.id,
                    "name": block.name,
                    "input": block.input
                })

        conversation_history.append({
            "role": "assistant",
            "content": content
        })

        return conversation_history

    def add_tool_result(
        self,
        conversation_history: List[Dict],
        tool_use_id: str,
        result: Any
    ) -> List[Dict]:
        """Add tool result to conversation history"""
        conversation_history.append({
            "role": "user",
            "content": [{
                "type": "tool_result",
                "tool_use_id": tool_use_id,
                "content": str(result)
            }]
        })
        return conversation_history

    def format_for_api(self, conversation_history: List[Dict]) -> Dict[str, Any]:
        """Format conversation history for Anthropic API"""
        return {
            "system": self.system_prompt,
            "messages": conversation_history
        }
