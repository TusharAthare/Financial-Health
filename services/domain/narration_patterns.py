"""Detect common Indian bank narration patterns for categorization."""

import re

_CC_AUTOPAY_RE = re.compile(
    r"CC\d{4,}X+AUTOPAY|AUTOPAYSI|AUTOPAY\s*SI",
    re.IGNORECASE,
)
_AUTOPAY_RE = re.compile(r"AUTO\s*PAY|AUTOPAY|AUTO\s*DEBIT", re.IGNORECASE)
_SI_RE = re.compile(r"SI-?TAD|STANDING\s*INSTR|E-?MANDATE", re.IGNORECASE)
_CC_RE = re.compile(r"\bCC\d{4,}|CREDIT\s*CARD|CARD\s*PAYMENT", re.IGNORECASE)
_INTEREST_RE = re.compile(
    r"INTEREST\s*PAID|INTERESTPAID|INT\.?\s*PD|INT\s*PAID",
    re.IGNORECASE,
)
_NACH_RE = re.compile(r"\bNACH\b", re.IGNORECASE)


def enrich_merchant_from_narration(
    raw_description: str,
    normalized_merchant: str,
) -> str:
    """
    Append searchable tokens from narration patterns for rule matching.

    Keeps the original normalized merchant; adds labels like ``autopay``
    or ``credit card`` when detected in the raw narration.
    """
    text = raw_description.strip()
    if not text:
        return normalized_merchant

    labels: list[str] = []
    if _CC_AUTOPAY_RE.search(text) or _AUTOPAY_RE.search(text):
        labels.append("autopay")
    if _CC_RE.search(text):
        labels.append("credit card")
    if _SI_RE.search(text):
        labels.append("standing instruction")
    if _NACH_RE.search(text):
        labels.append("nach")
    if _INTEREST_RE.search(text):
        labels.append("interest paid")

    if not labels:
        return normalized_merchant

    suffix = " ".join(dict.fromkeys(labels))
    base = normalized_merchant.strip()
    if not base:
        return suffix
    if suffix.lower() in base.lower():
        return base
    return f"{base} {suffix}"
