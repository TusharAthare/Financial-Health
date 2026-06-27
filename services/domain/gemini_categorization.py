"""Pure helpers for Gemini batch transaction categorization."""

import json
import re
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from services.domain.normalization import normalize_merchant

_TOKEN_RE = re.compile(r"[a-z0-9]+", re.IGNORECASE)
_NOISE_TOKENS = frozenset({
    "dr", "cr", "paid", "payment", "to", "from", "by", "upi", "neft", "imps",
})


@dataclass(frozen=True)
class MerchantBatchItem:
    """One unique merchant sent to Gemini in a batch."""

    key: str
    normalized_merchant: str
    sample_description: str
    direction: str  # "credit" or "debit"


def merchant_key(normalized_merchant: str, raw_description: str) -> str:
    """Build a stable dedupe key for grouping transactions."""
    merchant = normalized_merchant.strip().lower()
    if merchant:
        return merchant[:120]
    return raw_description.strip().lower()[:120]


def gemini_group_key(normalized_merchant: str, raw_description: str) -> str:
    """
    Coarser merchant key for Gemini batching.

    Collapses UPI rows that differ only by reference numbers into one group.
    """
    text = normalize_merchant(normalized_merchant or raw_description).lower()
    tokens: list[str] = []
    for token in _TOKEN_RE.findall(text):
        if token.isdigit() and len(token) >= 5:
            continue
        if token in _NOISE_TOKENS:
            continue
        tokens.append(token)
        if len(tokens) >= 4:
            break
    if tokens:
        return " ".join(tokens)
    return merchant_key(normalized_merchant, raw_description)


def direction_label(amount: Decimal) -> str:
    """Return credit/debit label for prompt context."""
    return "credit" if amount > 0 else "debit"


def truncate_text(text: str, max_len: int = 80) -> str:
    """Truncate text for compact prompts."""
    cleaned = re.sub(r"\s+", " ", text.strip())
    if len(cleaned) <= max_len:
        return cleaned
    return cleaned[: max_len - 3] + "..."


def build_categorization_prompt(
    items: list[MerchantBatchItem],
    categories: list[tuple[str, str]],
) -> str:
    """
    Build a compact categorization prompt for one Gemini batch call.

    categories: list of (slug, name) pairs.
    """
    category_lines = ", ".join(f"{slug}:{name}" for slug, name in categories)
    merchant_lines = "\n".join(
        f'{item.key}|{item.direction}|{truncate_text(item.sample_description)}'
        for item in items
    )
    return (
        "Categorize Indian bank transactions. Reply with ONLY a JSON array, no markdown.\n"
        'Format: [{"key":"<merchant_key>","slug":"<category_slug>"}]\n'
        f"Valid slugs: {category_lines}\n"
        "Use income for salary/credits. Use transfer for P2P/UPI transfers unless "
        "clearly a merchant purchase. Use emi-loan for EMIs, NACH, credit card "
        "autopay/SI-TAD debits.\n"
        "Lines are key|credit_or_debit|sample_description:\n"
        f"{merchant_lines}"
    )


def parse_categorization_response(
    raw_text: str,
    valid_slugs: frozenset[str],
    expected_keys: frozenset[str],
) -> dict[str, str]:
    """
    Parse Gemini JSON response into merchant_key -> category_slug.

    Ignores unknown slugs and keys not in expected_keys.
    """
    text = raw_text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)

    try:
        payload: Any = json.loads(text)
    except json.JSONDecodeError:
        return {}

    if isinstance(payload, dict):
        entries = payload.get("results") or payload.get("items") or []
    elif isinstance(payload, list):
        entries = payload
    else:
        return {}

    mapping: dict[str, str] = {}
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        key = str(entry.get("key", "")).strip().lower()
        slug = str(entry.get("slug", "")).strip().lower()
        if not key or key not in expected_keys:
            continue
        if slug not in valid_slugs or slug == "uncategorized":
            continue
        mapping[key] = slug
    return mapping
