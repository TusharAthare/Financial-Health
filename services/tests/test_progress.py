"""Tests for cross-period progress domain helpers."""

from decimal import Decimal

from django.test import SimpleTestCase

from services.domain.progress import compute_category_drift, compute_emi_burden_pct


class ProgressDomainTests(SimpleTestCase):
    """Verify EMI burden and category drift calculations."""

    def test_emi_burden_pct(self) -> None:
        """EMI burden is EMI total divided by income."""
        result = compute_emi_burden_pct("100000", "40000")
        self.assertAlmostEqual(result, 40.0)

    def test_emi_burden_none_when_no_income(self) -> None:
        """EMI burden returns None when income is zero."""
        self.assertIsNone(compute_emi_burden_pct("0", "5000"))

    def test_category_drift_detects_change(self) -> None:
        """Category drift compares current and prior period totals."""
        prior = [
            {
                "category_slug": "food",
                "category_name": "Food",
                "total": "1000",
            },
        ]
        current = [
            {
                "category_slug": "food",
                "category_name": "Food",
                "total": "1500",
            },
            {
                "category_slug": "travel",
                "category_name": "Travel",
                "total": "500",
            },
        ]
        drift = compute_category_drift(current, prior)
        self.assertEqual(len(drift), 2)
        food = next(item for item in drift if item["category_slug"] == "food")
        self.assertAlmostEqual(food["change_pct"], 50.0)
        self.assertEqual(Decimal(food["current_total"]), Decimal("1500"))

    def test_category_drift_empty_without_prior(self) -> None:
        """Category drift is empty when no prior period exists."""
        current = [{"category_slug": "food", "category_name": "Food", "total": "100"}]
        self.assertEqual(compute_category_drift(current, None), [])
