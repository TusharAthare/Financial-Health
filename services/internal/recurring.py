"""Recurring/autopay/EMI detection service."""

import logging

from django.conf import settings
from django.db import transaction
from django.db.models import Count

from analysis.models import RecurringPattern
from services.domain.recurring import TransactionSnapshot, detect_recurring_group
from statements.models import Transaction

logger = logging.getLogger(__name__)


class RecurringDetectionService:
    """Detect and persist recurring transaction patterns."""

    def list_patterns(self, user_id: int) -> list[RecurringPattern]:
        """Return active recurring patterns for the user."""
        return list(
            RecurringPattern.objects.filter(user_id=user_id, is_active=True)
            .order_by("pattern_type", "normalized_merchant")
        )

    def detect_for_user(
        self,
        user_id: int,
        *,
        statement_id: int | None = None,
    ) -> int:
        """
        Run recurring detection for a user (optionally scoped to one statement).

        Returns the number of patterns upserted.
        """
        queryset = Transaction.objects.filter(user_id=user_id, amount__lt=0)
        if statement_id is not None:
            queryset = queryset.filter(statement_id=statement_id)

        merchant_groups = (
            queryset.exclude(normalized_merchant="")
            .values("normalized_merchant")
            .annotate(txn_count=Count("id"))
            .filter(txn_count__gte=settings.RECURRING_MIN_OCCURRENCES)
        )

        merchant_names = [row["normalized_merchant"] for row in merchant_groups]
        if not merchant_names:
            return 0

        all_txns = list(
            queryset.filter(normalized_merchant__in=merchant_names)
            .only(
                "id",
                "transaction_date",
                "amount",
                "normalized_merchant",
                "raw_description",
            )
            .order_by("normalized_merchant", "transaction_date")
        )

        grouped: dict[str, list[TransactionSnapshot]] = {}
        for txn in all_txns:
            snapshot = TransactionSnapshot(
                id=txn.id,
                transaction_date=txn.transaction_date,
                amount=txn.amount,
                normalized_merchant=txn.normalized_merchant,
                raw_description=txn.raw_description,
            )
            grouped.setdefault(txn.normalized_merchant, []).append(snapshot)

        detected_count = 0
        for merchant, snapshots in grouped.items():
            pattern = detect_recurring_group(
                merchant,
                snapshots,
                min_occurrences=settings.RECURRING_MIN_OCCURRENCES,
                gap_tolerance_days=settings.RECURRING_GAP_TOLERANCE_DAYS,
                max_amount_variance_pct=settings.RECURRING_MAX_AMOUNT_VARIANCE_PCT,
            )
            if pattern is not None:
                self._upsert_pattern(user_id, pattern)
                detected_count += 1

        logger.info(
            "Recurring detection user_id=%s patterns=%s statement_id=%s",
            user_id,
            detected_count,
            statement_id,
        )
        return detected_count

    @transaction.atomic
    def _upsert_pattern(self, user_id: int, detected) -> RecurringPattern:
        """Persist a detected pattern and link member transactions."""
        pattern_obj, _ = RecurringPattern.objects.update_or_create(
            user_id=user_id,
            normalized_merchant=detected.normalized_merchant,
            pattern_type=detected.pattern_type,
            defaults={
                "cadence": detected.cadence,
                "expected_amount": detected.expected_amount,
                "amount_variance_pct": detected.amount_variance_pct,
                "next_expected_date": detected.next_expected_date,
                "evidence": detected.evidence,
                "is_active": True,
            },
        )

        Transaction.objects.filter(
            id__in=detected.transaction_ids,
            user_id=user_id,
        ).update(is_recurring=True, recurring_pattern=pattern_obj)

        return pattern_obj
