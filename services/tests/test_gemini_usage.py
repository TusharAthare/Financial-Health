"""Unit tests for Gemini cost and usage serialization."""

from decimal import Decimal

from django.test import SimpleTestCase

from services.domain.gemini_cost import estimate_gemini_cost_usd
from services.domain.gemini_usage import extract_usage_fields, serialize_sdk_object


class GeminiCostTests(SimpleTestCase):
    """Tests for token cost estimation."""

    def test_estimates_input_and_output_cost(self) -> None:
        """Cost scales with prompt and candidate token counts."""
        cost = estimate_gemini_cost_usd(
            prompt_tokens=1000,
            candidates_tokens=200,
            thoughts_tokens=50,
            input_cost_per_million=Decimal("0.15"),
            output_cost_per_million=Decimal("0.60"),
        )
        expected = Decimal("0.00015") + Decimal("0.00015")
        self.assertEqual(cost, expected)


class GeminiUsageSerializationTests(SimpleTestCase):
    """Tests for usage metadata normalization."""

    def test_extract_usage_fields(self) -> None:
        """Token fields are coerced to integers."""
        fields = extract_usage_fields(
            {
                "prompt_token_count": 1200,
                "candidates_token_count": 80,
                "total_token_count": 1280,
            },
        )
        self.assertEqual(fields["prompt_token_count"], 1200)
        self.assertEqual(fields["total_token_count"], 1280)

    def test_serialize_sdk_dict(self) -> None:
        """Dict usage metadata passes through unchanged."""
        payload = {"prompt_token_count": 10}
        self.assertEqual(serialize_sdk_object(payload), payload)
