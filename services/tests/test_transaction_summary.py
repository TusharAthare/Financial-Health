"""Unit tests for transaction list stats."""

from decimal import Decimal

from django.test import SimpleTestCase

from services.domain.transaction_summary import build_transaction_stats


class TransactionSummaryTests(SimpleTestCase):
    """Tests for credit/debit aggregation helpers."""

    def test_builds_credit_debit_net(self) -> None:
        """Stats sum credits and absolute debits with net cash flow."""
        stats = build_transaction_stats(
            credited_total=Decimal("5000"),
            credited_count=2,
            debited_total=Decimal("-3200"),
            debited_count=3,
        )
        self.assertEqual(stats.credited_count, 2)
        self.assertEqual(stats.debited_count, 3)
        self.assertEqual(stats.credited_total, Decimal("5000"))
        self.assertEqual(stats.debited_total, Decimal("3200"))
        self.assertEqual(stats.net_total, Decimal("1800"))
