"""
Agent Service - Core Logic (LLM + Tools Loop)
"""
from typing import List, Dict, Any
from app.core.llm.client import LLMClient
from app.services.tools.executor import ToolExecutor
from app.services.agent.message_manager import MessageManager
from app.core.events.publisher import EventPublisher
from app.schemas.event import StreamEvent, EventType
from app.utils.logger import setup_logger

logger = setup_logger(__name__)


class AgentService:
    """
    Core agent service that implements the LLM + tools reasoning loop
    """

    def __init__(
        self,
        session_id: str,
        llm_client: LLMClient,
        tool_executor: ToolExecutor,
        event_publisher: EventPublisher
    ):
        self.session_id = session_id
        self.llm_client = llm_client
        self.tool_executor = tool_executor
        self.event_publisher = event_publisher
        self.message_manager = MessageManager()

    async def process_message(self, user_message: str, conversation_history: List[Dict]) -> str:
        """
        Process user message through the agent loop

        1. Add user message to history
        2. Call LLM with available tools
        3. Process tool calls (if any)
        4. Execute tools
        5. Feed results back to LLM
        6. Repeat until final response
        7. Emit events at each step
        """
        logger.info(f"Processing message for session {self.session_id}")

        # Add user message to history
        conversation_history = self.message_manager.add_user_message(
            conversation_history, user_message
        )

        max_iterations = 10
        iteration = 0

        while iteration < max_iterations:
            iteration += 1
            logger.debug(f"Agent iteration {iteration}/{max_iterations}")

            # Emit thinking event
            await self._emit_event(EventType.AGENT_THINKING, {
                "iteration": iteration,
                "status": "calling_llm"
            })

            # Call LLM
            try:
                response = await self.llm_client.create_message(
                    messages=conversation_history,
                    tools=self.tool_executor.get_tool_definitions()
                )
            except Exception as e:
                logger.error(f"LLM error: {e}")
                await self._emit_event(EventType.AGENT_ERROR, {"error": str(e)})
                raise

            # Check if LLM wants to use tools
            if response.stop_reason == "tool_use":
                # Process tool calls
                tool_calls = [
                    block for block in response.content
                    if block.type == "tool_use"
                ]

                for tool_call in tool_calls:
                    # Emit tool call event
                    await self._emit_event(EventType.TOOL_CALLED, {
                        "tool_name": tool_call.name,
                        "tool_input": tool_call.input
                    })

                    # Execute tool
                    try:
                        result = await self.tool_executor.execute(
                            tool_call.name,
                            tool_call.input
                        )

                        # Emit tool result event
                        await self._emit_event(EventType.TOOL_RESULT, {
                            "tool_name": tool_call.name,
                            "result": result
                        })

                    except Exception as e:
                        logger.error(f"Tool execution error: {e}")
                        result = {"error": str(e)}
                        await self._emit_event(EventType.TOOL_RESULT, {
                            "tool_name": tool_call.name,
                            "error": str(e)
                        })

                # Add assistant response and tool results to history
                conversation_history = self.message_manager.add_assistant_response(
                    conversation_history, response
                )

                # Continue loop to get final response
                continue

            else:
                # Final response
                final_text = self._extract_text(response)

                # Add to history
                conversation_history = self.message_manager.add_assistant_response(
                    conversation_history, response
                )

                # Emit final response event
                await self._emit_event(EventType.AGENT_RESPONSE, {
                    "response": final_text
                })

                logger.info(f"Agent completed after {iteration} iterations")
                return final_text

        # Max iterations reached
        logger.warning(f"Max iterations ({max_iterations}) reached")
        return "I apologize, but I've reached my maximum processing iterations. Please try rephrasing your request."

    def _extract_text(self, response) -> str:
        """Extract text content from LLM response"""
        text_blocks = [
            block.text for block in response.content
            if hasattr(block, 'text')
        ]
        return " ".join(text_blocks)

    async def _emit_event(self, event_type: EventType, data: Dict[str, Any]):
        """Emit event to subscribers"""
        event = StreamEvent(
            session_id=self.session_id,
            event_type=event_type,
            data=data
        )
        await self.event_publisher.publish(self.session_id, event)
