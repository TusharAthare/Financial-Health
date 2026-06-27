"""ICICI Bank PDF statement adapter."""

from decimal import Decimal
from typing import Any

from services.domain.exceptions import DomainValidationError
from services.domain.transaction_row import ParsedTransactionRow
from services.internal.pdf_adapters.base import BankPdfAdapter


class IciciPdfAdapter(BankPdfAdapter):
    """Parse ICICI account statement PDF tables."""

    name = "icici"
    identifiers = ("ICICI BANK", "ICICI Bank Limited")

    def parse_tables(
        self,
        tables: list[list[list[Any | None]]],
    ) -> list[ParsedTransactionRow]:
        """Extract transactions from ICICI-style table layouts."""
        rows: list[ParsedTransactionRow] = []

        for table in tables:
            header_idx = self._find_header_index(
                table,
                ("value date", "transaction remarks"),
            )
            if header_idx is None:
                header_idx = self._find_header_index(
                    table,
                    ("transaction date", "remarks"),
                )
            if header_idx is None:
                continue

            header = table[header_idx]
            date_col = self._column_index(
                header,
                ("value date", "transaction date", "date"),
            )
            desc_col = self._column_index(
                header,
                ("transaction remarks", "remarks", "description"),
            )
            debit_col = self._column_index(
                header,
                ("withdrawal amount", "withdrawal", "debit"),
            )
            credit_col = self._column_index(
                header,
                ("deposit amount", "deposit", "credit"),
            )
            balance_col = self._column_index(
                header,
                ("balance (inr)", "balance"),
            )

            if date_col is None or desc_col is None:
                continue
            if debit_col is None and credit_col is None:
                continue

            for raw_row in table[header_idx + 1:]:
                parsed = self._parse_data_row(
                    raw_row,
                    date_col,
                    desc_col,
                    debit_col,
                    credit_col,
                    balance_col,
                )
                if parsed is not None:
                    rows.append(parsed)

        if not rows:
            raise DomainValidationError(
                "Could not extract ICICI transactions. Check that the PDF is text-based."
            )

        return rows

    def _parse_data_row(
        self,
        raw_row: list[Any | None],
        date_col: int,
        desc_col: int,
        debit_col: int | None,
        credit_col: int | None,
        balance_col: int | None,
    ) -> ParsedTransactionRow | None:
        """Parse one ICICI data row."""
        if date_col >= len(raw_row):
            return None

        raw_date = self._normalize_cell(raw_row[date_col])
        if not raw_date or raw_date.lower().startswith("b/f"):
            return None

        desc = self._normalize_cell(raw_row[desc_col]) if desc_col < len(raw_row) else ""
        debit = (
            self._parse_optional_amount(self._normalize_cell(raw_row[debit_col]))
            if debit_col is not None and debit_col < len(raw_row)
            else None
        )
        credit = (
            self._parse_optional_amount(self._normalize_cell(raw_row[credit_col]))
            if credit_col is not None and credit_col < len(raw_row)
            else None
        )
        balance_val: Decimal | None = None
        if balance_col is not None and balance_col < len(raw_row):
            balance_val = self._parse_optional_amount(
                self._normalize_cell(raw_row[balance_col]),
            )

        try:
            txn_date = self._parse_indian_date(raw_date)
        except DomainValidationError:
            return None

        return self._build_row(txn_date, desc, debit, credit, balance_val)
