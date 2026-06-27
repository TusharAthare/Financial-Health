"""Report aggregation and insight generation service."""

import logging
from decimal import Decimal

from django.conf import settings
from django.db import transaction
from django.db.models import Sum

from analysis.models import Insight, Report
from services.domain.exceptions import DomainValidationError
from services.domain.insights import generate_insights
from services.domain.report_aggregation import ReportAggregates, TransactionAggregateRow, aggregate_transactions
from statements.models import Statement, Transaction

logger = logging.getLogger(__name__)


class ReportService:
    """Build report snapshots and explainable insights for statements."""

    def get_report(self, user_id: int, statement_id: int) -> Report | None:
        """Return a report owned by the user for the given statement."""
        return (
            Report.objects.filter(user_id=user_id, statement_id=statement_id)
            .select_related("statement", "statement__account")
            .first()
        )

    def list_summary(self, user_id: int) -> list[Report]:
        """Return all reports ordered by period for cross-statement trends."""
        self.ensure_reports_for_user(user_id)
        return list(
            Report.objects.filter(user_id=user_id)
            .select_related("statement", "statement__account")
            .order_by("period_start", "id")
        )

    def ensure_reports_for_user(self, user_id: int) -> None:
        """Build missing reports for parsed statements owned by the user."""
        parsed_statements = Statement.objects.filter(
            user_id=user_id,
            status=Statement.Status.PARSED,
        ).order_by("period_start", "id")

        existing_ids = set(
            Report.objects.filter(user_id=user_id).values_list(
                "statement_id",
                flat=True,
            )
        )
        for statement in parsed_statements:
            if statement.id not in existing_ids:
                self.build_for_statement(
                    user_id=user_id,
                    statement_id=statement.id,
                )

    def list_insights(
        self,
        user_id: int,
        *,
        statement_id: int | None = None,
    ) -> list[Insight]:
        """Return insights for the user, optionally scoped to one statement."""
        queryset = Insight.objects.filter(user_id=user_id).select_related(
            "statement",
            "report",
        )
        if statement_id is not None:
            queryset = queryset.filter(statement_id=statement_id)
        return list(queryset.order_by("priority", "id"))

    @transaction.atomic
    def build_for_statement(self, user_id: int, statement_id: int) -> Report:
        """
        Aggregate transactions, persist a report snapshot, and regenerate insights.

        Raises if the statement is missing or not owned by the user.
        """
        statement = (
            Statement.objects.filter(
                id=statement_id,
                user_id=user_id,
                status=Statement.Status.PARSED,
            )
            .select_related("account")
            .first()
        )
        if statement is None:
            raise DomainValidationError("Parsed statement not found for user.")

        aggregates = self._compute_aggregates(user_id, statement)
        prior_report = self._get_prior_report(user_id, statement)

        report, _ = Report.objects.update_or_create(
            user_id=user_id,
            statement=statement,
            defaults={
                "period_start": statement.period_start,
                "period_end": statement.period_end,
                "aggregates": aggregates.to_dict(),
            },
        )

        Insight.objects.filter(user_id=user_id, statement=statement).delete()

        subscription_merchants = self._active_subscription_merchants(user_id)
        generated = generate_insights(
            aggregates=aggregates.to_dict(),
            prior_aggregates=prior_report.aggregates if prior_report else None,
            low_savings_threshold_pct=settings.INSIGHT_LOW_SAVINGS_THRESHOLD_PCT,
            high_emi_threshold_pct=settings.INSIGHT_HIGH_EMI_THRESHOLD_PCT,
            rising_spend_threshold_pct=settings.INSIGHT_RISING_SPEND_THRESHOLD_PCT,
            good_savings_threshold_pct=settings.INSIGHT_GOOD_SAVINGS_THRESHOLD_PCT,
            duplicate_subscription_types=subscription_merchants,
        )

        if generated:
            Insight.objects.bulk_create(
                [
                    Insight(
                        user_id=user_id,
                        report=report,
                        statement=statement,
                        insight_type=item.insight_type,
                        priority=item.priority,
                        title=item.title,
                        message=item.message,
                        evidence=item.evidence,
                        period_start=statement.period_start,
                        period_end=statement.period_end,
                    )
                    for item in generated
                ]
            )

        logger.info(
            "Report built statement_id=%s user_id=%s insights=%s",
            statement_id,
            user_id,
            len(generated),
        )
        return report

    def _compute_aggregates(
        self,
        user_id: int,
        statement: Statement,
    ) -> ReportAggregates:
        """Load transactions once and compute report aggregates."""
        txns = list(
            Transaction.objects.filter(
                user_id=user_id,
                statement_id=statement.id,
            )
            .select_related("category")
            .only(
                "amount",
                "category_id",
                "category__name",
                "category__slug",
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

        emi_total, subscription_total = self._recurring_totals(user_id, statement.id)

        return aggregate_transactions(
            rows,
            emi_total=emi_total,
            subscription_total=subscription_total,
        )

    def _recurring_totals(
        self,
        user_id: int,
        statement_id: int,
    ) -> tuple[Decimal, Decimal]:
        """Sum EMI and subscription debits linked to the statement."""
        from analysis.models import RecurringPattern

        emi_total = (
            Transaction.objects.filter(
                user_id=user_id,
                statement_id=statement_id,
                is_recurring=True,
                recurring_pattern__pattern_type__in=[
                    RecurringPattern.PatternType.EMI,
                    RecurringPattern.PatternType.LOAN,
                ],
            ).aggregate(total=Sum("amount"))["total"]
            or Decimal("0")
        )
        subscription_total = (
            Transaction.objects.filter(
                user_id=user_id,
                statement_id=statement_id,
                is_recurring=True,
                recurring_pattern__pattern_type__in=[
                    RecurringPattern.PatternType.SUBSCRIPTION,
                    RecurringPattern.PatternType.AUTOPAY,
                ],
            ).aggregate(total=Sum("amount"))["total"]
            or Decimal("0")
        )
        return abs(emi_total), abs(subscription_total)

    def _get_prior_report(
        self,
        user_id: int,
        statement: Statement,
    ) -> Report | None:
        """Return the report for the most recent prior parsed statement."""
        if statement.period_start is None:
            return None

        prior_statement = (
            Statement.objects.filter(
                user_id=user_id,
                status=Statement.Status.PARSED,
                period_end__lt=statement.period_start,
            )
            .order_by("-period_end")
            .first()
        )
        if prior_statement is None:
            return None

        return Report.objects.filter(
            user_id=user_id,
            statement_id=prior_statement.id,
        ).first()

    def _active_subscription_merchants(self, user_id: int) -> list[str]:
        """Return merchants with active subscription recurring patterns."""
        from analysis.models import RecurringPattern

        return list(
            RecurringPattern.objects.filter(
                user_id=user_id,
                is_active=True,
                pattern_type=RecurringPattern.PatternType.SUBSCRIPTION,
            )
            .order_by("normalized_merchant")
            .values_list("normalized_merchant", flat=True)
        )
