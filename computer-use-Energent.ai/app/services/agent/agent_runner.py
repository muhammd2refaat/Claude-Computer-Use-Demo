"""
Agent Runner - Background Task Runner
"""
import asyncio
from sqlalchemy.orm import Session

from app.services.agent.agent_service import AgentService
from app.core.llm.client import LLMClient
from app.services.tools.executor import ToolExecutor
from app.core.events.publisher import EventPublisher
from app.db.repository import Repository
from app.utils.logger import setup_logger

logger = setup_logger(__name__)


class AgentRunner:
    """
    Runs agent processing asynchronously in background
    """

    def __init__(self, db: Session):
        self.db = db
        self.repository = Repository(db)

    async def process_message(self, session_id: str, user_message: str):
        """
        Process a message asynchronously
        """
        try:
            logger.info(f"Starting background processing for session {session_id}")

            # Get session from DB
            session = await self.repository.get_session(session_id)
            if not session:
                logger.error(f"Session {session_id} not found")
                return

            # Get conversation history
            conversation_history = await self.repository.get_conversation_history(session_id)

            # Initialize dependencies
            llm_client = LLMClient()
            tool_executor = ToolExecutor()
            event_publisher = EventPublisher()

            # Create agent service
            agent_service = AgentService(
                session_id=session_id,
                llm_client=llm_client,
                tool_executor=tool_executor,
                event_publisher=event_publisher
            )

            # Process message
            response = await agent_service.process_message(
                user_message=user_message,
                conversation_history=conversation_history
            )

            # Save updated conversation history
            await self.repository.save_message(
                session_id=session_id,
                role="user",
                content=user_message
            )
            await self.repository.save_message(
                session_id=session_id,
                role="assistant",
                content=response
            )

            logger.info(f"Background processing completed for session {session_id}")

        except Exception as e:
            logger.error(f"Error in background processing: {e}", exc_info=True)
            # Emit error event
            event_publisher = EventPublisher()
            from app.schemas.event import StreamEvent, EventType
            event = StreamEvent(
                session_id=session_id,
                event_type=EventType.AGENT_ERROR,
                data={"error": str(e)}
            )
            await event_publisher.publish(session_id, event)
