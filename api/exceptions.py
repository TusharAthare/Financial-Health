"""Custom DRF exception handler with consistent error envelope."""

import logging

from django.core.exceptions import PermissionDenied as DjangoPermissionDenied
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import exception_handler

from services.domain.exceptions import (
    DomainPermissionDenied,
    DomainValidationError,
    InvalidStateError,
    QuotaExceededError,
)

logger = logging.getLogger(__name__)

EXCEPTION_MAP = {
    DomainValidationError: (status.HTTP_400_BAD_REQUEST, "validation_error"),
    DomainPermissionDenied: (status.HTTP_403_FORBIDDEN, "forbidden"),
    InvalidStateError: (status.HTTP_409_CONFLICT, "invalid_state"),
    QuotaExceededError: (status.HTTP_429_TOO_MANY_REQUESTS, "quota_exceeded"),
    DjangoPermissionDenied: (status.HTTP_403_FORBIDDEN, "forbidden"),
}


def custom_exception_handler(exc, context):
    """Map domain exceptions and DRF errors to a consistent JSON envelope."""
    for exc_type, (http_status, code) in EXCEPTION_MAP.items():
        if isinstance(exc, exc_type):
            return Response(
                {"error": {"code": code, "message": str(exc)}},
                status=http_status,
            )

    response = exception_handler(exc, context)
    if response is not None:
        if isinstance(response.data, dict) and "detail" in response.data:
            response.data = {
                "error": {
                    "code": "error",
                    "message": str(response.data["detail"]),
                }
            }
        elif isinstance(response.data, dict):
            response.data = {
                "error": {
                    "code": "validation_error",
                    "message": "Invalid input",
                    "details": response.data,
                }
            }
        if response.status_code >= 500:
            request = context.get("request")
            logger.error(
                "Unhandled API error",
                extra={
                    "path": getattr(request, "path", None),
                    "user_id": getattr(getattr(request, "user", None), "id", None),
                },
                exc_info=exc,
            )
    return response
