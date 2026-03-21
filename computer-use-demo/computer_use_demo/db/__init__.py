"""Database layer - connection pooling and repository operations."""

from computer_use_demo.db.database import (
    ConnectionPool,
    get_pool,
    get_connection,
    init_db,
    close_db,
    get_pool_stats,
)
from computer_use_demo.db.repository import (
    create_session,
    get_session,
    list_sessions,
    update_session_status,
    update_session_display,
    delete_session,
    add_message,
    get_messages,
)

__all__ = [
    # Database
    "ConnectionPool",
    "get_pool",
    "get_connection",
    "init_db",
    "close_db",
    "get_pool_stats",
    # Repository
    "create_session",
    "get_session",
    "list_sessions",
    "update_session_status",
    "update_session_display",
    "delete_session",
    "add_message",
    "get_messages",
]
