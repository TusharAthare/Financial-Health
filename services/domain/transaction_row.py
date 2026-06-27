"""Shared parsed-transaction row type for CSV and PDF parsers."""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal


@dataclass(frozen=True)
class ParsedTransactionRow:
    """Normalized row extracted from a bank statement."""

    transaction_date: date
    amount: Decimal
    raw_description: str
    normalized_merchant: str
    balance: Decimal | None
