"""Request Logging Middleware - HTTP request/response tracking."""

import time
import uuid
from typing import Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from computer_use_demo.config.settings import settings
from computer_use_demo.utils.log_context import (
    clear_correlation_id,
    set_correlation_id,
)
from computer_use_demo.utils.logger import get_logger

logger = get_logger(__name__, "api")


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Middleware to log HTTP requests and responses with correlation IDs."""

    def __init__(self, app: ASGIApp):
        """Initialize middleware."""
        super().__init__(app)

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process request and log request/response information.

        Args:
            request: FastAPI request object
            call_next: Next middleware/route handler in chain

        Returns:
            Response object with correlation ID header
        """
        # Skip logging if disabled
        if not settings.ENABLE_API_REQUEST_LOGGING:
            return await call_next(request)

        # Generate correlation ID
        correlation_id = str(uuid.uuid4())
        set_correlation_id(correlation_id)

        # Add to request state
        request.state.correlation_id = correlation_id
        request.state.start_time = time.time()

        # Log incoming request
        logger.info(
            "HTTP Request",
            extra={
                "extra_fields": {
                    "method": request.method,
                    "url": str(request.url.path),
                    "query_params": str(request.url.query) if request.url.query else None,
                    "client_ip": request.client.host if request.client else "unknown",
                    "user_agent": request.headers.get("user-agent", "unknown"),
                }
            },
        )

        try:
            # Process request
            response = await call_next(request)
            duration = time.time() - request.state.start_time

            # Log successful response
            logger.info(
                "HTTP Response",
                extra={
                    "extra_fields": {
                        "status_code": response.status_code,
                        "duration_ms": round(duration * 1000, 2),
                    }
                },
            )

            # Inject correlation ID into response header
            response.headers["X-Correlation-ID"] = correlation_id

            return response

        except Exception as e:
            duration = time.time() - request.state.start_time

            # Log failed request
            logger.exception(
                "HTTP Request Failed",
                extra={
                    "extra_fields": {
                        "duration_ms": round(duration * 1000, 2),
                        "error_type": type(e).__name__,
                        "error": str(e),
                    }
                },
            )
            raise

        finally:
            # Clear correlation ID from context
            clear_correlation_id()
