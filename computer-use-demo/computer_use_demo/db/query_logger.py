"""Database Query Logger - Execution timing and logging."""

import time
from typing import Any, Tuple

from computer_use_demo.config.settings import settings
from computer_use_demo.utils.logger import get_logger

logger = get_logger(__name__, "database")


async def log_query_execution(
    cursor,
    query: str,
    params: Tuple[Any, ...] = None,
):
    """Execute and log a database query with timing.

    Args:
        cursor: Database cursor object
        query: SQL query string
        params: Query parameters tuple

    Returns:
        Cursor result after execution
    """
    # Skip logging if disabled
    if not settings.ENABLE_DATABASE_QUERY_LOGGING:
        if params:
            return await cursor.execute(query, params)
        else:
            return await cursor.execute(query)

    start_time = time.time()

    try:
        if params:
            result = await cursor.execute(query, params)
        else:
            result = await cursor.execute(query)

        duration = time.time() - start_time

        logger.debug(
            "Query executed",
            extra={
                "extra_fields": {
                    "query": query[:200],  # Truncate long queries
                    "duration_ms": round(duration * 1000, 2),
                    "has_params": bool(params),
                }
            },
        )

        return result
    except Exception as e:
        duration = time.time() - start_time
        logger.error(
            "Query failed",
            extra={
                "extra_fields": {
                    "query": query[:200],
                    "duration_ms": round(duration * 1000, 2),
                    "error": str(e),
                }
            },
        )
        raise
