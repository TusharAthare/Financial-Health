"""Request logging middleware for observability."""

import logging
import time
import uuid

logger = logging.getLogger("api.request")


class RequestLoggingMiddleware:
    """Log request start/end with duration, status, and request id."""

    def __init__(self, get_response) -> None:
        """Store the next middleware or view callable."""
        self.get_response = get_response

    def __call__(self, request):
        """Process the request and log timing metadata."""
        request_id = request.headers.get("X-Request-ID", uuid.uuid4().hex[:16])
        request.request_id = request_id
        start = time.perf_counter()

        response = self.get_response(request)

        duration_ms = (time.perf_counter() - start) * 1000
        user_id = getattr(getattr(request, "user", None), "id", None)
        log_level = logging.ERROR if response.status_code >= 500 else logging.INFO

        logger.log(
            log_level,
            "request completed method=%s path=%s status=%s duration_ms=%.1f "
            "user_id=%s request_id=%s",
            request.method,
            request.path,
            response.status_code,
            duration_ms,
            user_id,
            request_id,
        )
        response["X-Request-ID"] = request_id
        return response
