"""Extract user-written UPI payment notes from bank narrations."""

import re

_IFSC_RE = re.compile(r"^[A-Z]{4}0[A-Z0-9]{6}$", re.IGNORECASE)
_RAIL_TOKENS = frozenset({
    "gpay", "googlepay", "phonepe", "paytm", "bharatpe", "bhim", "upi",
    "imps", "neft", "rtgs", "pay", "qr", "okbizaxis", "okbizax", "is",
    "yes", "ybl", "axis", "hdfc", "icici", "sbi", "kotak", "pnb",
})
_NUMERIC_REF_RE = re.compile(r"^\d{8,}$")
_REMARK_RE = re.compile(r"^[A-Za-z][A-Za-z0-9 ]{1,47}$")


def extract_upi_remark(raw_description: str) -> str | None:
    """
    Return the user-written UPI note from a narration, if present.

    Handles narrations like:
    UPI-KADAM DAIRY-GPAY-...@OKBIZAX IS-UTIB0000553-764821284164-PANNER
    where the trailing segment (PANNER) is the payer's message.
    """
    text = raw_description.strip()
    if "upi" not in text.lower():
        return None

    if "-" not in text:
        return None

    candidate = text.rsplit("-", 1)[-1].strip()
    previous = text.rsplit("-", 2)[-2].strip() if text.count("-") >= 2 else ""
    # User notes follow a numeric reference: ...-764821284164-PANNER
    if not _NUMERIC_REF_RE.match(previous):
        return None
    if not _is_valid_remark(candidate):
        return None

    return _normalize_remark(candidate)


def resolve_normalized_merchant(raw_description: str) -> str:
    """
    Prefer the UPI user note for categorization; else clean the payee text.

    Keeps raw_description unchanged on the transaction; only affects matching.
    """
    from services.domain.normalization import normalize_merchant

    remark = extract_upi_remark(raw_description)
    if remark:
        return remark
    return normalize_merchant(raw_description)


def _is_valid_remark(candidate: str) -> bool:
    """Return True when the trailing segment looks like a user note."""
    if not candidate or len(candidate) < 2 or len(candidate) > 48:
        return False
    if candidate.isdigit():
        return False
    if _IFSC_RE.match(candidate):
        return False
    if "@" in candidate:
        return False
    if not _REMARK_RE.match(candidate):
        return False
    lowered = candidate.lower().replace(" ", "")
    if lowered in _RAIL_TOKENS:
        return False
    if any(ch.isdigit() for ch in candidate):
        return False
    return True


def _normalize_remark(candidate: str) -> str:
    """Normalize remark text for storage and rule matching."""
    return re.sub(r"\s+", " ", candidate.strip().lower())
