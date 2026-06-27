"""Pure domain rules for transaction normalization."""

import re
from decimal import Decimal, InvalidOperation


_UPI_NOISE = re.compile(
    r"\b(UPI|IMPS|NEFT|RTGS|REF|TXN|TXNID|UTR|VPA|@[\w.]+)\b",
    re.IGNORECASE,
)
_REF_NUMBERS = re.compile(r"\b\d{10,}\b")
_WHITESPACE = re.compile(r"\s+")
_LEADING_PUNCT = re.compile(r"^[-/\s:|]+")


def normalize_merchant(raw_description: str) -> str:
    """
    Clean a raw bank description into a normalized merchant string.

    Strips UPI/reference noise and collapses whitespace.
    """
    text = raw_description.strip()
    text = _UPI_NOISE.sub(" ", text)
    text = _REF_NUMBERS.sub(" ", text)
    text = _WHITESPACE.sub(" ", text).strip()
    text = _LEADING_PUNCT.sub("", text).strip()
    return text or raw_description.strip()


def parse_amount(value: object) -> Decimal:
    """
    Parse a CSV cell into a signed Decimal amount.

    Raises ValueError when the value cannot be parsed.
    """
    if value is None or (isinstance(value, float) and str(value) == "nan"):
        raise ValueError("Amount is empty.")

    text = str(value).strip().replace(",", "")
    if not text or text.lower() in ("nan", "none", "-"):
        raise ValueError("Amount is empty.")

    try:
        return Decimal(text)
    except InvalidOperation as exc:
        raise ValueError(f"Invalid amount: {value}") from exc


def signed_amount(debit: Decimal | None, credit: Decimal | None) -> Decimal:
    """
    Compute signed amount from separate debit/credit columns.

    Debits are negative; credits are positive.
    """
    if debit is not None and debit != 0:
        return -abs(debit)
    if credit is not None and credit != 0:
        return abs(credit)
    raise ValueError("Both debit and credit are empty.")
