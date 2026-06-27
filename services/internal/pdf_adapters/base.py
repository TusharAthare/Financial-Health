"""Shared helpers for bank-specific PDF statement adapters."""

import re
from abc import ABC, abstractmethod
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from services.domain.exceptions import DomainValidationError
from services.domain.normalization import parse_amount, signed_amount
from services.domain.upi_remark import resolve_normalized_merchant
from services.domain.transaction_row import ParsedTransactionRow

_DATE_PATTERNS = (
    "%d/%m/%Y",
    "%d-%m-%Y",
    "%d/%m/%y",
    "%d-%m-%y",
    "%d %b %Y",
    "%d-%b-%Y",
)
_AMOUNT_CLEAN = re.compile(r"[^\d.\-]")


class BankPdfAdapter(ABC):
    """Base class for per-bank PDF statement templates."""

    name: str
    identifiers: tuple[str, ...]

    def matches(self, document_text: str) -> bool:
        """Return True when document text indicates this bank format."""
        upper = document_text.upper()
        return any(marker.upper() in upper for marker in self.identifiers)

    @abstractmethod
    def parse_tables(
        self,
        tables: list[list[list[Any | None]]],
    ) -> list[ParsedTransactionRow]:
        """Parse pdfplumber table matrices into transaction rows."""

    def parse(
        self,
        document_text: str,
        tables: list[list[list[Any | None]]],
    ) -> list[ParsedTransactionRow]:
        """Parse using tables by default; adapters may override for text fallback."""
        return self.parse_tables(tables)

    def _normalize_cell(self, value: Any | None) -> str:
        """Return a cleaned string from a table cell."""
        if value is None:
            return ""
        return re.sub(r"\s+", " ", str(value)).strip()

    def _find_header_index(
        self,
        table: list[list[Any | None]],
        required: tuple[str, ...],
    ) -> int | None:
        """Return the row index whose cells contain all required header tokens."""
        for idx, row in enumerate(table):
            row_text = " ".join(self._normalize_cell(cell).lower() for cell in row)
            if all(token.lower() in row_text for token in required):
                return idx
        return None

    def _column_index(
        self,
        header_row: list[Any | None],
        candidates: tuple[str, ...],
    ) -> int | None:
        """Return the column index matching any candidate header label."""
        for idx, cell in enumerate(header_row):
            cell_text = self._normalize_cell(cell).lower()
            for candidate in candidates:
                if candidate.lower() in cell_text:
                    return idx
        return None

    def _parse_indian_date(self, value: str) -> date:
        """Parse common Indian bank statement date formats."""
        text = value.strip()
        if not text:
            raise DomainValidationError("Transaction date is empty.")

        for fmt in _DATE_PATTERNS:
            try:
                return datetime.strptime(text, fmt).date()
            except ValueError:
                continue

        raise DomainValidationError(f"Unrecognized date format: {value}")

    def _parse_optional_amount(self, value: str) -> Decimal | None:
        """Parse a debit/credit/balance cell; return None when blank."""
        text = _AMOUNT_CLEAN.sub("", value.strip())
        if not text or text in ("-", ".", "-."):
            return None
        return parse_amount(text)

    def _build_row(
        self,
        txn_date: date,
        description: str,
        debit: Decimal | None,
        credit: Decimal | None,
        balance: Decimal | None,
    ) -> ParsedTransactionRow | None:
        """Build a parsed row; return None when description is empty."""
        desc = description.strip()
        if not desc:
            return None

        amount = signed_amount(debit, credit)
        return ParsedTransactionRow(
            transaction_date=txn_date,
            amount=amount,
            raw_description=desc,
            normalized_merchant=resolve_normalized_merchant(desc),
            balance=balance,
        )
