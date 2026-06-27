"""Pure helpers for Gemini token cost estimation."""

from decimal import Decimal


def estimate_gemini_cost_usd(
    *,
    prompt_tokens: int,
    candidates_tokens: int,
    thoughts_tokens: int = 0,
    input_cost_per_million: Decimal,
    output_cost_per_million: Decimal,
) -> Decimal:
    """
    Estimate USD cost from token counts and configured per-million rates.

    Output-priced tokens include candidate and thought tokens.
    """
    prompt = max(prompt_tokens, 0)
    output_tokens = max(candidates_tokens, 0) + max(thoughts_tokens, 0)
    million = Decimal("1000000")
    input_cost = (Decimal(prompt) / million) * input_cost_per_million
    output_cost = (Decimal(output_tokens) / million) * output_cost_per_million
    return input_cost + output_cost
