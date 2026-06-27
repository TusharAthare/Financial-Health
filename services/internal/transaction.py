"""Transaction query services with tenant scoping."""

from datetime import date

from django.db.models import Count, Q, QuerySet, Sum

from services.domain.transaction_summary import build_transaction_stats
from statements.models import Category, Transaction


class TransactionService:
    """List and filter user-scoped transactions."""

    def list_transactions(
        self,
        user_id: int,
        *,
        statement_id: int | None = None,
        category_id: int | None = None,
        date_from: date | None = None,
        date_to: date | None = None,
        direction: str | None = None,
        search: str | None = None,
        uncategorized_only: bool = False,
    ) -> QuerySet[Transaction]:
        """
        Return filtered transactions for the user, newest first.

        Uses select_related to avoid N+1 on category and account.
        """
        queryset = (
            Transaction.objects.filter(user_id=user_id)
            .select_related(
                "category",
                "account",
                "statement",
                "matched_rule",
                "recurring_pattern",
            )
            .order_by("-transaction_date", "-id")
        )

        if statement_id is not None:
            queryset = queryset.filter(statement_id=statement_id)
        if category_id is not None:
            queryset = queryset.filter(category_id=category_id)
        if date_from is not None:
            queryset = queryset.filter(transaction_date__gte=date_from)
        if date_to is not None:
            queryset = queryset.filter(transaction_date__lte=date_to)
        if direction == "credit":
            queryset = queryset.filter(amount__gt=0)
        elif direction == "debit":
            queryset = queryset.filter(amount__lt=0)
        if uncategorized_only:
            uncategorized_id = self._uncategorized_category_id()
            if uncategorized_id is not None:
                queryset = queryset.filter(category_id=uncategorized_id)
        if search:
            term = search.strip()
            if term:
                queryset = queryset.filter(
                    Q(raw_description__icontains=term)
                    | Q(normalized_merchant__icontains=term),
                )

        return queryset

    def summarize_transactions(self, queryset: QuerySet[Transaction]) -> dict:
        """
        Compute credited/debited totals for the full filtered queryset.

        Returns a JSON-serializable stats dict.
        """
        credits = queryset.filter(amount__gt=0).aggregate(
            total=Sum("amount"),
            count=Count("id"),
        )
        debits = queryset.filter(amount__lt=0).aggregate(
            total=Sum("amount"),
            count=Count("id"),
        )
        stats = build_transaction_stats(
            credited_total=credits["total"],
            credited_count=credits["count"] or 0,
            debited_total=debits["total"],
            debited_count=debits["count"] or 0,
        )
        return stats.to_dict()

    def _uncategorized_category_id(self) -> int | None:
        """Return the system uncategorized category id."""
        return (
            Category.objects.filter(user__isnull=True, slug="uncategorized")
            .values_list("id", flat=True)
            .first()
        )
