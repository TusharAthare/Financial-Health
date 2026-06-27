"""Calendar-month financial summaries across statements."""

import logging
from calendar import monthrange
from datetime import date
from decimal import Decimal

from django.db.models import Count, Min, Max
from django.db.models.functions import TruncMonth

from services.domain.insights import GeneratedInsight, generate_insights
from services.domain.report_aggregation import (
    ReportAggregates,
    TransactionAggregateRow,
    aggregate_transactions,
)
from statements.models import Transaction

logger = logging.getLogger(__name__)


class MonthlyReportService:
    """Aggregate transactions by calendar month for dashboard views."""

    def list_available_months(self, user_id: int) -> list[dict]:
        """
        Return months that have at least one transaction, newest first.

        Each item: year, month, label, transaction_count, period_start, period_end.
        """
        months = (
            Transaction.objects.filter(user_id=user_id)
            .annotate(month=TruncMonth("transaction_date"))
            .values("month")
            .annotate(
                transaction_count=Count("id"),
                period_start=Min("transaction_date"),
                period_end=Max("transaction_date"),
            )
            .order_by("-month")
        )
        items: list[dict] = []
        for row in months:
            month_date = row["month"]
            if month_date is None:
                continue
            items.append(
                {
                    "year": month_date.year,
                    "month": month_date.month,
                    "label": month_date.strftime("%b %Y"),
                    "transaction_count": row["transaction_count"],
                    "period_start": row["period_start"],
                    "period_end": row["period_end"],
                }
            )
        return items

    def get_summary(
        self,
        user_id: int,
        *,
        year: int,
        month: int,
    ) -> dict:
        """
        Build aggregates and on-the-fly insights for a calendar month.

        Compares against the prior calendar month when data exists.
        """
        period_start, period_end = self._month_bounds(year, month)
        aggregates = self._compute_month_aggregates(
            user_id,
            period_start=period_start,
            period_end=period_end,
        )

        prior_start, prior_end = self._prior_month_bounds(year, month)
        prior_aggregates = None
        if Transaction.objects.filter(
            user_id=user_id,
            transaction_date__gte=prior_start,
            transaction_date__lte=prior_end,
        ).exists():
            prior = self._compute_month_aggregates(
                user_id,
                period_start=prior_start,
                period_end=prior_end,
            )
            prior_aggregates = prior.to_dict()

        from django.conf import settings

        insights = generate_insights(
            aggregates=aggregates.to_dict(),
            prior_aggregates=prior_aggregates,
            low_savings_threshold_pct=settings.INSIGHT_LOW_SAVINGS_THRESHOLD_PCT,
            high_emi_threshold_pct=settings.INSIGHT_HIGH_EMI_THRESHOLD_PCT,
            rising_spend_threshold_pct=settings.INSIGHT_RISING_SPEND_THRESHOLD_PCT,
            good_savings_threshold_pct=settings.INSIGHT_GOOD_SAVINGS_THRESHOLD_PCT,
            duplicate_subscription_types=[],
        )

        return {
            "year": year,
            "month": month,
            "label": period_start.strftime("%B %Y"),
            "period_start": period_start,
            "period_end": period_end,
            "aggregates": aggregates.to_dict(),
            "insights": [self._insight_to_dict(item) for item in insights],
        }

    def _compute_month_aggregates(
        self,
        user_id: int,
        *,
        period_start: date,
        period_end: date,
    ) -> ReportAggregates:
        """Load month transactions and compute aggregates."""
        txns = list(
            Transaction.objects.filter(
                user_id=user_id,
                transaction_date__gte=period_start,
                transaction_date__lte=period_end,
            )
            .select_related("category")
            .only(
                "amount",
                "category_id",
                "category__name",
                "category__slug",
                "is_recurring",
            )
        )

        rows = [
            TransactionAggregateRow(
                amount=txn.amount,
                category_id=txn.category_id,
                category_name=txn.category.name if txn.category else "Uncategorized",
                category_slug=txn.category.slug if txn.category else "uncategorized",
            )
            for txn in txns
        ]

        emi_total = Decimal("0")
        subscription_total = Decimal("0")
        for txn in txns:
            if txn.amount >= 0:
                continue
            debit = abs(txn.amount)
            slug = txn.category.slug if txn.category else ""
            if slug == "emi-loan":
                emi_total += debit
            elif txn.is_recurring and slug not in ("transfer", "income"):
                subscription_total += debit

        return aggregate_transactions(
            rows,
            emi_total=emi_total,
            subscription_total=subscription_total,
        )

    def _month_bounds(self, year: int, month: int) -> tuple[date, date]:
        """Return inclusive start/end dates for a calendar month."""
        last_day = monthrange(year, month)[1]
        return date(year, month, 1), date(year, month, last_day)

    def _prior_month_bounds(self, year: int, month: int) -> tuple[date, date]:
        """Return bounds for the month before the given year/month."""
        if month == 1:
            return self._month_bounds(year - 1, 12)
        return self._month_bounds(year, month - 1)

    def _insight_to_dict(self, item: GeneratedInsight) -> dict:
        """Serialize a generated insight for API output."""
        return {
            "insight_type": item.insight_type,
            "priority": item.priority,
            "title": item.title,
            "message": item.message,
            "evidence": item.evidence,
        }
