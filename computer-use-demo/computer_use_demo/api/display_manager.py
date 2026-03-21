"""Display manager - Re-export from services layer.

DEPRECATED: This module is kept for backward compatibility.
Use computer_use_demo.services.display instead.
"""

# Re-export for backward compatibility
from computer_use_demo.services.display import (
    display_service as display_manager,
    display_service,
    DisplayAllocation,
    DisplayService,
)

__all__ = [
    "display_manager",
    "display_service",
    "DisplayAllocation",
    "DisplayService",
]
