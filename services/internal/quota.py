"""Upload quotas and rate-limit checks."""

from datetime import timedelta

from django.conf import settings
from django.utils import timezone

from services.domain.exceptions import QuotaExceededError
from statements.models import Statement


class QuotaService:
    """Enforce per-user statement upload quotas."""

    def check_upload_allowed(self, user_id: int) -> None:
        """
        Verify the user may upload another statement.

        Raises QuotaExceededError when a quota limit is exceeded.
        """
        max_statements = settings.MAX_STATEMENTS_PER_USER
        total = Statement.objects.filter(user_id=user_id).count()
        if total >= max_statements:
            raise QuotaExceededError(
                f"Maximum of {max_statements} statements reached. "
                "Delete old data or contact support."
            )

        max_daily = settings.MAX_UPLOADS_PER_DAY
        if max_daily <= 0:
            return

        since = timezone.now() - timedelta(days=1)
        daily_count = Statement.objects.filter(
            user_id=user_id,
            created_at__gte=since,
        ).count()
        if daily_count >= max_daily:
            raise QuotaExceededError(
                f"Daily upload limit of {max_daily} reached. Try again tomorrow."
            )
