"""Unit tests for categorization domain rules."""

from django.test import SimpleTestCase

from services.domain.categorization import RuleMatchInput, match_rule, resolve_category


class CategorizationDomainTests(SimpleTestCase):
    """Tests for pure categorization rule matching."""

    def test_merchant_contains_match(self) -> None:
        """Merchant substring rule matches normalized merchant."""
        txn = RuleMatchInput(
            normalized_merchant="SWIGGY BANGALORE",
            raw_description="UPI-SWIGGY",
        )
        result = match_rule(1, "merchant_contains", "swiggy", 5, txn)
        self.assertIsNotNone(result)
        assert result is not None
        self.assertEqual(result.matched_field, "normalized_merchant")

    def test_keyword_match_in_description(self) -> None:
        """Keyword rule matches raw description."""
        txn = RuleMatchInput(
            normalized_merchant="NEFT CR",
            raw_description="SALARY CREDIT JAN 2025",
        )
        result = match_rule(2, "keyword", "salary", 3, txn)
        self.assertIsNotNone(result)
        assert result is not None
        self.assertEqual(result.matched_field, "raw_description")

    def test_resolve_applies_first_matching_rule(self) -> None:
        """Rules are applied in priority order; first match wins."""
        txn = RuleMatchInput(
            normalized_merchant="AMAZON PAY",
            raw_description="AMAZON IN",
        )
        rules = [
            (10, "merchant_contains", "amazon", 7),
            (11, "keyword", "amazon", 8),
        ]
        category_id, match = resolve_category(rules, txn)
        self.assertEqual(category_id, 7)
        self.assertIsNotNone(match)
        assert match is not None
        self.assertEqual(match.rule_id, 10)

    def test_no_match_returns_none(self) -> None:
        """Unknown merchant returns no category match."""
        txn = RuleMatchInput(
            normalized_merchant="UNKNOWN SHOP",
            raw_description="DEBIT",
        )
        category_id, match = resolve_category(
            [(1, "merchant_contains", "swiggy", 5)],
            txn,
        )
        self.assertIsNone(category_id)
        self.assertIsNone(match)
