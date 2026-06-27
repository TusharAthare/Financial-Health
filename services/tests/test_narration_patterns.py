"""Unit tests for bank narration pattern enrichment."""

from django.test import SimpleTestCase

from services.domain.narration_patterns import enrich_merchant_from_narration
from services.domain.categorization import RuleMatchInput, resolve_category


class NarrationPatternTests(SimpleTestCase):
    """Tests for AUTOPAY and credit card narration detection."""

    def test_cc_autopay_enrichment(self) -> None:
        """Credit card autopay narration adds autopay label."""
        raw = "CC000552260XXXXXX6259AUTOPAYSI-TAD"
        enriched = enrich_merchant_from_narration(raw, raw.lower())
        self.assertIn("autopay", enriched.lower())
        self.assertIn("credit card", enriched.lower())

    def test_autopay_matches_emi_rule(self) -> None:
        """Autopay keyword rule categorizes CC autopay debits."""
        raw = "CC000552260XXXXXX6259AUTOPAYSI-TAD"
        enriched = enrich_merchant_from_narration(raw, raw.lower())
        rules = [(1, "keyword", "autopay", 99)]
        category_id, result = resolve_category(
            rules,
            RuleMatchInput(normalized_merchant=enriched, raw_description=raw),
        )
        self.assertEqual(category_id, 99)
        self.assertIsNotNone(result)

    def test_interest_paid_enrichment(self) -> None:
        """Interest credit narration is labeled for income rules."""
        raw = "INTERESTPAIDTILL31-MAR-2026"
        enriched = enrich_merchant_from_narration(raw, raw.lower())
        self.assertIn("interest paid", enriched.lower())
