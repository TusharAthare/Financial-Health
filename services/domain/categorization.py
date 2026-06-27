"""Pure categorization rule matching (transport-agnostic)."""

import re
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class RuleMatchInput:
    """Transaction fields used for rule matching."""

    normalized_merchant: str
    raw_description: str


@dataclass(frozen=True)
class RuleMatchResult:
    """Outcome of applying a single rule."""

    rule_id: int
    rule_pattern: str
    rule_type: str
    matched_field: str
    matched_text: str


def build_evidence(result: RuleMatchResult) -> dict[str, Any]:
    """Build JSON-serializable evidence from a rule match."""
    return {
        "rule_id": result.rule_id,
        "rule_pattern": result.rule_pattern,
        "rule_type": result.rule_type,
        "matched_field": result.matched_field,
        "matched_text": result.matched_text,
    }


def match_rule(
    rule_id: int,
    rule_type: str,
    pattern: str,
    category_id: int,
    txn: RuleMatchInput,
) -> RuleMatchResult | None:
    """
    Try to match one rule against transaction text.

    Returns RuleMatchResult when the rule matches, else None.
    """
    pattern_lower = pattern.lower().strip()
    if not pattern_lower:
        return None

    merchant_lower = txn.normalized_merchant.lower()
    description_lower = txn.raw_description.lower()

    if rule_type == "merchant_contains":
        if pattern_lower in merchant_lower:
            return RuleMatchResult(
                rule_id=rule_id,
                rule_pattern=pattern,
                rule_type=rule_type,
                matched_field="normalized_merchant",
                matched_text=txn.normalized_merchant,
            )
        return None

    if rule_type == "keyword":
        if _keyword_matches(pattern_lower, description_lower):
            return RuleMatchResult(
                rule_id=rule_id,
                rule_pattern=pattern,
                rule_type=rule_type,
                matched_field="raw_description",
                matched_text=txn.raw_description,
            )
        if _keyword_matches(pattern_lower, merchant_lower):
            return RuleMatchResult(
                rule_id=rule_id,
                rule_pattern=pattern,
                rule_type=rule_type,
                matched_field="normalized_merchant",
                matched_text=txn.normalized_merchant,
            )
        return None

    if rule_type == "regex":
        try:
            if re.search(pattern, txn.raw_description, re.IGNORECASE):
                return RuleMatchResult(
                    rule_id=rule_id,
                    rule_pattern=pattern,
                    rule_type=rule_type,
                    matched_field="raw_description",
                    matched_text=txn.raw_description,
                )
        except re.error:
            return None
        return None

    return None


def resolve_category(
    rules: list[tuple[int, str, str, int]],
    txn: RuleMatchInput,
) -> tuple[int | None, RuleMatchResult | None]:
    """
    Apply ordered rules and return (category_id, match_result).

    rules: list of (rule_id, rule_type, pattern, category_id) in priority order.
    """
    for rule_id, rule_type, pattern, category_id in rules:
        result = match_rule(rule_id, rule_type, pattern, category_id, txn)
        if result is not None:
            return category_id, result
    return None, None


def _keyword_matches(pattern_lower: str, text_lower: str) -> bool:
    """Match keywords with word boundaries for short patterns."""
    if not pattern_lower or not text_lower:
        return False
    if len(pattern_lower) <= 4:
        return bool(re.search(rf"\b{re.escape(pattern_lower)}\b", text_lower))
    return pattern_lower in text_lower
