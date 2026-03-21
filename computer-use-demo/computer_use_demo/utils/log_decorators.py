"""Log Decorators - Automatic operation logging for async methods."""

import functools
import time
from typing import Any, Callable, Optional

from computer_use_demo.utils.logger import get_logger


def log_async_operation(
    operation_name: Optional[str] = None,
    log_args: bool = False,
    log_result: bool = False,
):
    """Decorator for logging async service operations.

    Args:
        operation_name: Custom operation name (defaults to function name)
        log_args: Whether to log function arguments
        log_result: Whether to log function result

    Example:
        @log_async_operation("create_session", log_result=True)
        async def create_session(self, title: str) -> dict:
            ...
    """

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            logger = get_logger(func.__module__)
            name = operation_name or func.__name__

            start_time = time.time()

            # Build log extra fields
            extra_fields = {"operation": name}

            if log_args and len(args) > 1:  # Skip self
                extra_fields["args"] = str(args[1:])[:200]  # Truncate
            if log_args and kwargs:
                extra_fields["kwargs"] = str(kwargs)[:200]  # Truncate

            logger.info(f"Starting {name}", extra={"extra_fields": extra_fields})

            try:
                result = await func(*args, **kwargs)
                duration = time.time() - start_time

                result_extra = {
                    "operation": name,
                    "duration_ms": round(duration * 1000, 2),
                    "status": "success",
                }

                if log_result:
                    result_extra["result"] = str(result)[:200]  # Truncate

                logger.info(
                    f"Completed {name}", extra={"extra_fields": result_extra}
                )

                return result
            except Exception as e:
                duration = time.time() - start_time

                error_extra = {
                    "operation": name,
                    "duration_ms": round(duration * 1000, 2),
                    "status": "failed",
                    "error": str(e),
                }

                logger.exception(
                    f"Failed {name}", extra={"extra_fields": error_extra}
                )
                raise

        return wrapper

    return decorator
