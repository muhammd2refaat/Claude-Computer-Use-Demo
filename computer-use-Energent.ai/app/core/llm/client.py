"""
LLM Client - Anthropic API Wrapper
"""
from typing import List, Dict, Any, Optional
from anthropic import AsyncAnthropic
from app.config.settings import settings
from app.utils.logger import setup_logger

logger = setup_logger(__name__)


class LLMClient:
    """
    Wrapper for Anthropic Claude API
    """

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or settings.ANTHROPIC_API_KEY
        self.client = AsyncAnthropic(api_key=self.api_key)
        self.model = settings.CLAUDE_MODEL

    async def create_message(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
        max_tokens: int = 4096,
        temperature: float = 0.7,
        system: Optional[str] = None
    ):
        """
        Create a message using Claude API

        Args:
            messages: Conversation history
            tools: Available tools for the model
            max_tokens: Maximum tokens in response
            temperature: Sampling temperature
            system: System prompt

        Returns:
            Response from Claude
        """
        try:
            request_params = {
                "model": self.model,
                "messages": messages,
                "max_tokens": max_tokens,
                "temperature": temperature
            }

            if system:
                request_params["system"] = system

            if tools:
                request_params["tools"] = tools

            logger.debug(f"Calling Claude API with {len(messages)} messages")

            response = await self.client.messages.create(**request_params)

            logger.debug(f"Received response: stop_reason={response.stop_reason}")

            return response

        except Exception as e:
            logger.error(f"Error calling Claude API: {e}", exc_info=True)
            raise

    async def stream_message(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
        max_tokens: int = 4096,
        temperature: float = 0.7,
        system: Optional[str] = None
    ):
        """
        Stream a message using Claude API

        Args:
            messages: Conversation history
            tools: Available tools for the model
            max_tokens: Maximum tokens in response
            temperature: Sampling temperature
            system: System prompt

        Yields:
            Streaming response chunks
        """
        try:
            request_params = {
                "model": self.model,
                "messages": messages,
                "max_tokens": max_tokens,
                "temperature": temperature,
                "stream": True
            }

            if system:
                request_params["system"] = system

            if tools:
                request_params["tools"] = tools

            logger.debug(f"Streaming from Claude API with {len(messages)} messages")

            async with self.client.messages.stream(**request_params) as stream:
                async for chunk in stream:
                    yield chunk

        except Exception as e:
            logger.error(f"Error streaming from Claude API: {e}", exc_info=True)
            raise
