"""DRF throttle classes for upload and API rate limiting."""

from rest_framework.throttling import UserRateThrottle


class UploadRateThrottle(UserRateThrottle):
    """Rate limit statement upload POST requests per authenticated user."""

    scope = "upload"


class ApiUserRateThrottle(UserRateThrottle):
    """General authenticated API rate limit."""

    scope = "user"
