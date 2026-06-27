"""Pure helpers for transaction list summaries."""

from dataclasses import dataclass
from decimal import Decimal
from typing import Any


@dataclass(frozen=True)
class TransactionListStats:
    """Aggregated credit/debit totals for a filtered transaction set."""

    transaction_count: int
    credited_count: int
    debited_count: int
    credited_total: Decimal
    debited_total: Decimal
    net_total: Decimal

    def to_dict(self) -> dict[str, Any]:
        """Serialize stats for API responses."""
        return {
            "transaction_count": self.transaction_count,
            "credited_count": self.credited_count,
            "debited_count": self.debited_count,
            "credited_total": str(self.credited_total),
            "debited_total": str(self.debited_total),
            "net_total": str(self.net_total),
        }


def build_transaction_stats(
    *,
    credited_total: Decimal | None,
    credited_count: int,
    debited_total: Decimal | None,
    debited_count: int,
) -> TransactionListStats:
    """Build stats from ORM aggregate values."""
    credit_sum = credited_total or Decimal("0")
    debit_sum = abs(debited_total or Decimal("0"))
    return TransactionListStats(
        transaction_count=credited_count + debited_count,
        credited_count=credited_count,
        debited_count=debited_count,
        credited_total=credit_sum,
        debited_total=debit_sum,
        net_total=credit_sum - debit_sum,
    )
