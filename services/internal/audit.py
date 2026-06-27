"""Audit logging for sensitive user actions."""

from typing import Any

from core.models import AuditLog


class AuditService:
    """Record tenant-scoped audit events."""

    def log(
        self,
        user_id: int,
        action: str,
        *,
        target_type: str = "",
        target_id: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> AuditLog:
        """Persist an audit log entry for the given user."""
        return AuditLog.objects.create(
            user_id=user_id,
            action=action,
            target_type=target_type,
            target_id=target_id,
            metadata=metadata or {},
        )

    def list_for_user(self, user_id: int, *, limit: int = 50) -> list[AuditLog]:
        """Return recent audit entries for the user."""
        return list(
            AuditLog.objects.filter(user_id=user_id).order_by("-created_at")[:limit]
        )
