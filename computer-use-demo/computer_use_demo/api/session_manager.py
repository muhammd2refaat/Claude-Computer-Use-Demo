"""Session manager - Re-export from services layer.

DEPRECATED: This module is kept for backward compatibility.
Use computer_use_demo.services.session instead.
"""

# Re-export for backward compatibility
from computer_use_demo.services.session import (
    session_service as session_manager,
    session_service,
    ActiveSession,
)
from computer_use_demo.services.agent import agent_service
from computer_use_demo.services.display import DisplayAllocation

# Re-export ActiveSession for backward compatibility
__all__ = [
    "session_manager",
    "session_service",
    "ActiveSession",
    "agent_service",
    "DisplayAllocation",
]
