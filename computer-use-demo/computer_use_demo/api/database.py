"""Async SQLite database layer with connection pooling for high concurrency.

Features:
- Connection pool with configurable size (default: 10 connections)
- Automatic connection health checks
- Context manager for safe acquire/release
- WAL mode for concurrent read/write operations
- Graceful shutdown with proper cleanup
"""

import asyncio
import json
import logging
import os
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Any

import aiosqlite

logger = logging.getLogger(__name__)

DB_PATH = "/data/sessions.db"

# Pool configuration from environment or defaults
POOL_MIN_SIZE = int(os.getenv("DB_POOL_MIN_SIZE", "2"))
POOL_MAX_SIZE = int(os.getenv("DB_POOL_MAX_SIZE", "10"))
POOL_ACQUIRE_TIMEOUT = float(os.getenv("DB_POOL_ACQUIRE_TIMEOUT", "30.0"))


class ConnectionPool:
    """Async connection pool for SQLite with aiosqlite.

    Maintains a pool of reusable database connections to handle
    high concurrency without creating new connections for each request.

    Usage:
        pool = ConnectionPool(db_path, min_size=2, max_size=10)
        await pool.initialize()

        async with pool.acquire() as conn:
            await conn.execute("SELECT * FROM sessions")

        await pool.close()
    """

    def __init__(
        self,
        db_path: str,
        min_size: int = POOL_MIN_SIZE,
        max_size: int = POOL_MAX_SIZE,
        acquire_timeout: float = POOL_ACQUIRE_TIMEOUT,
    ):
        self.db_path = db_path
        self.min_size = min_size
        self.max_size = max_size
        self.acquire_timeout = acquire_timeout

        self._pool: asyncio.Queue[aiosqlite.Connection] = asyncio.Queue(maxsize=max_size)
        self._size = 0  # Current number of connections created
        self._lock = asyncio.Lock()
        self._initialized = False
        self._closed = False

        # Statistics for monitoring
        self._stats = {
            "acquired": 0,
            "released": 0,
            "created": 0,
            "health_checks": 0,
            "health_failures": 0,
        }

    async def _create_connection(self) -> aiosqlite.Connection:
        """Create a new database connection with optimized settings."""
        conn = await aiosqlite.connect(self.db_path)
        conn.row_factory = aiosqlite.Row

        # Optimize for concurrent access
        await conn.execute("PRAGMA journal_mode=WAL")
        await conn.execute("PRAGMA foreign_keys=ON")
        await conn.execute("PRAGMA synchronous=NORMAL")  # Faster with WAL
        await conn.execute("PRAGMA cache_size=-64000")   # 64MB cache
        await conn.execute("PRAGMA busy_timeout=30000")  # 30s busy timeout

        self._stats["created"] += 1
        logger.debug(f"Created new database connection (total: {self._size + 1})")
        return conn

    async def _check_connection_health(self, conn: aiosqlite.Connection) -> bool:
        """Check if a connection is still valid."""
        self._stats["health_checks"] += 1
        try:
            await conn.execute("SELECT 1")
            return True
        except Exception as e:
            self._stats["health_failures"] += 1
            logger.warning(f"Connection health check failed: {e}")
            return False

    async def initialize(self) -> None:
        """Initialize the connection pool with minimum connections."""
        if self._initialized:
            return

        async with self._lock:
            if self._initialized:
                return

            logger.info(f"Initializing connection pool (min={self.min_size}, max={self.max_size})")

            # Pre-create minimum connections
            for _ in range(self.min_size):
                conn = await self._create_connection()
                await self._pool.put(conn)
                self._size += 1

            self._initialized = True
            logger.info(f"Connection pool initialized with {self._size} connections")

    @asynccontextmanager
    async def acquire(self):
        """Acquire a connection from the pool.

        Usage:
            async with pool.acquire() as conn:
                await conn.execute(...)

        Raises:
            asyncio.TimeoutError: If no connection available within timeout
            RuntimeError: If pool is closed or not initialized
        """
        if self._closed:
            raise RuntimeError("Connection pool is closed")

        if not self._initialized:
            await self.initialize()

        conn = None

        try:
            # Try to get an existing connection from the pool
            try:
                conn = self._pool.get_nowait()
            except asyncio.QueueEmpty:
                # Pool is empty, try to create a new connection or wait
                async with self._lock:
                    if self._size < self.max_size:
                        # Create a new connection
                        conn = await self._create_connection()
                        self._size += 1

                if conn is None:
                    # Pool is at max capacity, wait for a connection
                    try:
                        conn = await asyncio.wait_for(
                            self._pool.get(),
                            timeout=self.acquire_timeout
                        )
                    except asyncio.TimeoutError:
                        logger.error(
                            f"Timeout acquiring connection after {self.acquire_timeout}s "
                            f"(pool size: {self._size}, waiting: {self._pool.qsize()})"
                        )
                        raise

            # Health check the connection
            if not await self._check_connection_health(conn):
                logger.warning("Replacing unhealthy connection")
                try:
                    await conn.close()
                except Exception:
                    pass
                async with self._lock:
                    self._size -= 1
                conn = await self._create_connection()
                async with self._lock:
                    self._size += 1

            self._stats["acquired"] += 1
            yield conn

        finally:
            # Return connection to the pool
            if conn is not None:
                try:
                    await self._pool.put(conn)
                    self._stats["released"] += 1
                except asyncio.QueueFull:
                    # Pool is somehow full, close the connection
                    logger.warning("Pool full, closing extra connection")
                    await conn.close()
                    async with self._lock:
                        self._size -= 1

    async def close(self) -> None:
        """Close the pool and all connections."""
        if self._closed:
            return

        async with self._lock:
            if self._closed:
                return

            self._closed = True
            logger.info(f"Closing connection pool (size: {self._size})")

            # Close all connections in the pool
            closed = 0
            while not self._pool.empty():
                try:
                    conn = self._pool.get_nowait()
                    await conn.close()
                    closed += 1
                except asyncio.QueueEmpty:
                    break
                except Exception as e:
                    logger.warning(f"Error closing connection: {e}")

            self._size = 0
            logger.info(f"Connection pool closed ({closed} connections)")

    def get_stats(self) -> dict[str, Any]:
        """Get pool statistics for monitoring."""
        return {
            **self._stats,
            "pool_size": self._size,
            "available": self._pool.qsize(),
            "in_use": self._size - self._pool.qsize(),
            "max_size": self.max_size,
        }


# Global connection pool instance
_pool: ConnectionPool | None = None


async def get_pool() -> ConnectionPool:
    """Get the global connection pool instance."""
    global _pool
    if _pool is None:
        _pool = ConnectionPool(DB_PATH)
        await _pool.initialize()
    return _pool


@asynccontextmanager
async def get_connection():
    """Get a database connection from the pool.

    Usage:
        async with get_connection() as db:
            await db.execute(...)
    """
    pool = await get_pool()
    async with pool.acquire() as conn:
        yield conn


async def init_db() -> None:
    """Initialize the database schema and connection pool."""
    pool = await get_pool()

    async with pool.acquire() as db:
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

    logger.info("Database schema initialized")


async def close_db() -> None:
    """Close the database connection pool."""
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None


def get_pool_stats() -> dict[str, Any] | None:
    """Get connection pool statistics (for health checks/monitoring)."""
    if _pool is not None:
        return _pool.get_stats()
    return None


# --- Session CRUD ---

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


# --- Message CRUD ---

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
