"""Domain-level exceptions (transport-agnostic)."""


class DomainValidationError(Exception):
    """Raised when business validation fails."""


class DomainPermissionDenied(Exception):
    """Raised when the user lacks permission for an action."""


class InvalidStateError(Exception):
    """Raised when an entity is in an invalid state for the requested action."""


class QuotaExceededError(Exception):
    """Raised when the user exceeds an upload or usage quota."""
