"""Shared DRF permission classes."""

from rest_framework.permissions import BasePermission


class IsOwner(BasePermission):
    """Allow access only when the object belongs to the authenticated user."""

    def has_object_permission(self, request, view, obj) -> bool:
        """Check object ownership via user attribute or user_id field."""
        owner = getattr(obj, "user", None)
        if owner is not None:
            return owner == request.user
        owner_id = getattr(obj, "user_id", None)
        return owner_id == request.user.id
