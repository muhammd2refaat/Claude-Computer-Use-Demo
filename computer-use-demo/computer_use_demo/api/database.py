"""Async SQLite database layer for session and message persistence."""

import json
import uuid
from datetime import datetime, timezone

import aiosqlite

DB_PATH = "/data/sessions.db"

_db: aiosqlite.Connection | None = None


async def get_db() -> aiosqlite.Connection:
    """Get the singleton database connection."""
    global _db
    if _db is None:
        _db = await aiosqlite.connect(DB_PATH)
        _db.row_factory = aiosqlite.Row
        await _db.execute("PRAGMA journal_mode=WAL")
        await _db.execute("PRAGMA foreign_keys=ON")
    return _db


async def init_db():
    """Initialize the database schema."""
    db = await get_db()
    await db.executescript("""
        CREATE TABLE IF NOT EXISTS sessions (
            id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'created',
            display_num INTEGER,
            vnc_port INTEGER,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS messages (
            id TEXT PRIMARY KEY,
            session_id TEXT NOT NULL,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE
        );

        CREATE INDEX IF NOT EXISTS idx_messages_session_id
        ON messages(session_id, created_at);
    """)
    await db.commit()


async def close_db():
    """Close the database connection."""
    global _db
    if _db is not None:
        await _db.close()
        _db = None


# --- Session CRUD ---

async def create_session(
    title: str,
    display_num: int | None = None,
    vnc_port: int | None = None,
) -> dict:
    """Create a new session record."""
    db = await get_db()
    session_id = uuid.uuid4().hex
    now = datetime.now(timezone.utc).isoformat()
    title = title or f"Session {session_id[:8]}"

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
    db = await get_db()
    cursor = await db.execute("SELECT * FROM sessions WHERE id = ?", (session_id,))
    row = await cursor.fetchone()
    return dict(row) if row else None


async def list_sessions() -> list[dict]:
    """List all sessions, newest first."""
    db = await get_db()
    cursor = await db.execute("SELECT * FROM sessions ORDER BY created_at DESC")
    rows = await cursor.fetchall()
    return [dict(row) for row in rows]


async def update_session_status(session_id: str, status: str) -> dict | None:
    """Update a session's status."""
    db = await get_db()
    now = datetime.now(timezone.utc).isoformat()
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
    db = await get_db()
    now = datetime.now(timezone.utc).isoformat()
    await db.execute(
        "UPDATE sessions SET display_num = ?, vnc_port = ?, updated_at = ? WHERE id = ?",
        (display_num, vnc_port, now, session_id),
    )
    await db.commit()
    return await get_session(session_id)


async def delete_session(session_id: str) -> bool:
    """Delete a session and its messages."""
    db = await get_db()
    cursor = await db.execute("DELETE FROM sessions WHERE id = ?", (session_id,))
    await db.commit()
    return cursor.rowcount > 0


# --- Message CRUD ---

async def add_message(session_id: str, role: str, content: any) -> dict:
    """Add a message to a session."""
    db = await get_db()
    message_id = uuid.uuid4().hex
    now = datetime.now(timezone.utc).isoformat()

    # Serialize content to JSON if it's not a simple string
    content_str = json.dumps(content) if not isinstance(content, str) else content

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
    db = await get_db()
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
