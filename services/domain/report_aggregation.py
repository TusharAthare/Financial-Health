"""Pure report aggregation from transaction snapshots."""

from dataclasses import dataclass
from decimal import Decimal
from typing import Any


@dataclass(frozen=True)
class TransactionAggregateRow:
    """Minimal transaction row for aggregation."""

    amount: Decimal
    category_id: int | None
    category_name: str
    category_slug: str


@dataclass(frozen=True)
class ReportAggregates:
    """Computed financial aggregates for a statement period."""

    income: Decimal
    expense: Decimal
    net_cash_flow: Decimal
    savings_rate: float | None
    transaction_count: int
    category_totals: list[dict[str, Any]]
    emi_total: Decimal
    subscription_total: Decimal
    recurring_debit_total: Decimal

    def to_dict(self) -> dict[str, Any]:
        """Serialize aggregates for JSON storage."""
        return {
            "income": str(self.income),
            "expense": str(self.expense),
            "net_cash_flow": str(self.net_cash_flow),
            "savings_rate": self.savings_rate,
            "transaction_count": self.transaction_count,
            "category_totals": self.category_totals,
            "emi_total": str(self.emi_total),
            "subscription_total": str(self.subscription_total),
            "recurring_debit_total": str(self.recurring_debit_total),
        }


def aggregate_transactions(
    rows: list[TransactionAggregateRow],
    *,
    emi_total: Decimal = Decimal("0"),
    subscription_total: Decimal = Decimal("0"),
) -> ReportAggregates:
    """
    Compute income, expense, savings rate, and category totals.

    Expense categories exclude transfer/income; positive amounts count as income.
    """
    income = Decimal("0")
    expense = Decimal("0")
    category_map: dict[int, dict[str, Any]] = {}

    for row in rows:
        if row.amount > 0:
            income += row.amount
            continue

        debit = abs(row.amount)
        expense += debit

        if row.category_slug in ("transfer", "income"):
            continue

        bucket = category_map.setdefault(
            row.category_id or 0,
            {
                "category_id": row.category_id,
                "category_name": row.category_name,
                "category_slug": row.category_slug,
                "total": Decimal("0"),
                "transaction_count": 0,
            },
        )
        bucket["total"] += debit
        bucket["transaction_count"] += 1

    category_totals = sorted(
        [
            {
                "category_id": item["category_id"],
                "category_name": item["category_name"],
                "category_slug": item["category_slug"],
                "total": str(item["total"]),
                "transaction_count": item["transaction_count"],
            }
            for item in category_map.values()
        ],
        key=lambda item: Decimal(item["total"]),
        reverse=True,
    )

    net_cash_flow = income - expense
    savings_rate: float | None = None
    if income > 0:
        savings_rate = float((net_cash_flow / income) * 100)

    recurring_debit_total = emi_total + subscription_total

    return ReportAggregates(
        income=income,
        expense=expense,
        net_cash_flow=net_cash_flow,
        savings_rate=savings_rate,
        transaction_count=len(rows),
        category_totals=category_totals,
        emi_total=emi_total,
        subscription_total=subscription_total,
        recurring_debit_total=recurring_debit_total,
    )
