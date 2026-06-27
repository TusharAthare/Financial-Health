"""Unit tests for recurring detection domain logic."""

from datetime import date
from decimal import Decimal

from django.test import SimpleTestCase

from services.domain.recurring import TransactionSnapshot, detect_recurring_group


class RecurringDomainTests(SimpleTestCase):
    """Tests for pure recurring pattern detection."""

    def _monthly_debits(
        self,
        merchant: str,
        amount: str,
        count: int = 3,
    ) -> list[TransactionSnapshot]:
        """Build monthly debit snapshots."""
        base = date(2025, 1, 15)
        return [
            TransactionSnapshot(
                id=i + 1,
                transaction_date=date(base.year, base.month + i, 15)
                if base.month + i <= 12
                else date(base.year + 1, (base.month + i) - 12, 15),
                amount=Decimal(amount),
                normalized_merchant=merchant,
                raw_description=f"EMI {merchant}",
            )
            for i in range(count)
        ]

    def test_detects_monthly_emi_pattern(self) -> None:
        """Stable monthly debits with EMI keyword are detected."""
        txns = [
            TransactionSnapshot(
                id=1,
                transaction_date=date(2025, 1, 10),
                amount=Decimal("-15000.00"),
                normalized_merchant="HDFC LTD",
                raw_description="HOME LOAN EMI",
            ),
            TransactionSnapshot(
                id=2,
                transaction_date=date(2025, 2, 10),
                amount=Decimal("-15000.00"),
                normalized_merchant="HDFC LTD",
                raw_description="HOME LOAN EMI",
            ),
            TransactionSnapshot(
                id=3,
                transaction_date=date(2025, 3, 10),
                amount=Decimal("-15000.00"),
                normalized_merchant="HDFC LTD",
                raw_description="HOME LOAN EMI",
            ),
        ]
        result = detect_recurring_group(
            "HDFC LTD",
            txns,
            min_occurrences=3,
            gap_tolerance_days=5,
            max_amount_variance_pct=10.0,
        )
        self.assertIsNotNone(result)
        assert result is not None
        self.assertIn(result.pattern_type, ("emi", "loan"))
        self.assertEqual(result.cadence, "monthly")
        self.assertEqual(len(result.transaction_ids), 3)

    def test_rejects_unstable_amounts(self) -> None:
        """High amount variance prevents false-positive recurring detection."""
        txns = [
            TransactionSnapshot(
                id=1,
                transaction_date=date(2025, 1, 10),
                amount=Decimal("-100.00"),
                normalized_merchant="SHOP",
                raw_description="DEBIT",
            ),
            TransactionSnapshot(
                id=2,
                transaction_date=date(2025, 2, 10),
                amount=Decimal("-500.00"),
                normalized_merchant="SHOP",
                raw_description="DEBIT",
            ),
            TransactionSnapshot(
                id=3,
                transaction_date=date(2025, 3, 10),
                amount=Decimal("-50.00"),
                normalized_merchant="SHOP",
                raw_description="DEBIT",
            ),
        ]
        result = detect_recurring_group(
            "SHOP",
            txns,
            min_occurrences=3,
            gap_tolerance_days=5,
            max_amount_variance_pct=10.0,
        )
        self.assertIsNone(result)

    def test_requires_minimum_occurrences(self) -> None:
        """Fewer than min occurrences does not produce a pattern."""
        txns = self._monthly_debits("NETFLIX", "-499.00", count=2)
        result = detect_recurring_group(
            "NETFLIX",
            txns,
            min_occurrences=3,
            gap_tolerance_days=5,
            max_amount_variance_pct=10.0,
        )
        self.assertIsNone(result)
