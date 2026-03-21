"""Repository layer for session and message CRUD operations."""

import json
import uuid
from datetime import datetime, timezone
from typing import Any

from computer_use_demo.db.database import get_connection
from computer_use_demo.utils.logger import get_logger

logger = get_logger(__name__)


# --- Session Repository ---

async def create_session(
    title: str,
    display_num: int | None = None,
    vnc_port: int | None = None,
) -> dict:
    """Create a new session record."""
    session_id = uuid.uuid4().hex
    now = datetime.now(timezone.utc).isoformat()
    title = title or f"Session {session_id[:8]}"

    async with get_connection() as db:
        await db.execute(
            """INSERT INTO sessions (id, title, status, display_num, vnc_port, created_at, updated_at)
               VALUES (?, ?, 'created', ?, ?, ?, ?)""",
            (session_id, title, display_num, vnc_port, now, now),
        )
        await db.commit()

    return {
        "id": session_id,
        "title": title,
        "status": "created",
        "display_num": display_num,
        "vnc_port": vnc_port,
        "created_at": now,
        "updated_at": now,
    }


async def get_session(session_id: str) -> dict | None:
    """Get a session by ID."""
    async with get_connection() as db:
        cursor = await db.execute("SELECT * FROM sessions WHERE id = ?", (session_id,))
        row = await cursor.fetchone()
        return dict(row) if row else None


async def list_sessions() -> list[dict]:
    """List all sessions, newest first."""
    async with get_connection() as db:
        cursor = await db.execute("SELECT * FROM sessions ORDER BY created_at DESC")
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]


async def update_session_status(session_id: str, status: str) -> dict | None:
    """Update a session's status."""
    now = datetime.now(timezone.utc).isoformat()

    async with get_connection() as db:
        await db.execute(
            "UPDATE sessions SET status = ?, updated_at = ? WHERE id = ?",
            (status, now, session_id),
        )
        await db.commit()

    return await get_session(session_id)


async def update_session_display(
    session_id: str,
    display_num: int,
    vnc_port: int,
) -> dict | None:
    """Update a session's display and VNC info."""
    now = datetime.now(timezone.utc).isoformat()

    async with get_connection() as db:
        await db.execute(
            "UPDATE sessions SET display_num = ?, vnc_port = ?, updated_at = ? WHERE id = ?",
            (display_num, vnc_port, now, session_id),
        )
        await db.commit()

    return await get_session(session_id)


async def delete_session(session_id: str) -> bool:
    """Delete a session and its messages."""
    async with get_connection() as db:
        cursor = await db.execute("DELETE FROM sessions WHERE id = ?", (session_id,))
        await db.commit()
        return cursor.rowcount > 0


# --- Message Repository ---

async def add_message(session_id: str, role: str, content: Any) -> dict:
    """Add a message to a session."""
    message_id = uuid.uuid4().hex
    now = datetime.now(timezone.utc).isoformat()

    # Serialize content to JSON if it's not a simple string
    content_str = json.dumps(content) if not isinstance(content, str) else content

    async with get_connection() as db:
        await db.execute(
            """INSERT INTO messages (id, session_id, role, content, created_at)
               VALUES (?, ?, ?, ?, ?)""",
            (message_id, session_id, role, content_str, now),
        )
        await db.commit()

    return {
        "id": message_id,
        "session_id": session_id,
        "role": role,
        "content": content,
        "created_at": now,
    }


async def get_messages(session_id: str) -> list[dict]:
    """Get all messages for a session, in chronological order."""
    async with get_connection() as db:
        cursor = await db.execute(
            "SELECT * FROM messages WHERE session_id = ? ORDER BY created_at ASC",
            (session_id,),
        )
        rows = await cursor.fetchall()

    result = []
    for row in rows:
        msg = dict(row)
        # Try to deserialize JSON content
        try:
            msg["content"] = json.loads(msg["content"])
        except (json.JSONDecodeError, TypeError):
            pass
        result.append(msg)
    return result
