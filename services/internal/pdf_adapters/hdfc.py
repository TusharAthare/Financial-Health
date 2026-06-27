"""HDFC Bank PDF statement adapter."""

import re
from decimal import Decimal
from typing import Any

from services.domain.exceptions import DomainValidationError
from services.domain.transaction_row import ParsedTransactionRow
from services.internal.pdf_adapters.base import BankPdfAdapter

_DATE_TOKEN = r"\d{2}/\d{2}/\d{2}"
_AMOUNT_TOKEN = r"[\d,]+\.\d{2}"
_TXN_END_RE = re.compile(
    rf"({_DATE_TOKEN})\s+"
    rf"((?:{_AMOUNT_TOKEN}\s+)?(?:{_AMOUNT_TOKEN}\s+)?{_AMOUNT_TOKEN})$",
)
_TXN_START_RE = re.compile(rf"^({_DATE_TOKEN})\s+(.*)$")
_REF_TOKEN_RE = re.compile(r"^[A-Z0-9]{6,}$")
_SKIP_LINE_MARKERS = (
    "PAGENO",
    "ACCOUNTBRANCH",
    "STATEMENTOF ACCOUNT",
    "DATE NARRATION",
    "JOINTHOLDERS",
    "NOMINATION",
)


class HdfcPdfAdapter(BankPdfAdapter):
    """Parse HDFC account statement PDF tables and text layouts."""

    name = "hdfc"
    identifiers = (
        "HDFC BANK",
        "HDFC Bank Limited",
        "HDFCBANK",
        "HDFC000",
        "Statementof account",
    )
    _CREDIT_HINTS = (
        "NEFTCR",
        "CREDIT",
        "SALARY",
        "INTEREST",
        "DEPOSIT",
        "CR-",
        "REFUND",
    )

    def parse(
        self,
        document_text: str,
        tables: list[list[list[Any | None]]],
    ) -> list[ParsedTransactionRow]:
        """Parse structured tables or fall back to line-based text extraction."""
        if not self._tables_are_merged(tables):
            rows = self._parse_structured_tables(tables)
            if rows:
                return rows
        return self.parse_text(document_text)

    def parse_tables(
        self,
        tables: list[list[list[Any | None]]],
    ) -> list[ParsedTransactionRow]:
        """Parse pdfplumber tables (legacy entry point)."""
        rows = self._parse_structured_tables(tables)
        if not rows:
            raise DomainValidationError(
                "Could not extract HDFC transactions. Check that the PDF is text-based."
            )
        return rows

    def parse_text(self, document_text: str) -> list[ParsedTransactionRow]:
        """Parse HDFC statements where transactions appear as text lines."""
        rows: list[ParsedTransactionRow] = []
        pending_line = ""
        previous_balance: Decimal | None = None

        for raw_line in document_text.splitlines():
            line = raw_line.strip()
            if not line:
                continue
            if self._should_skip_line(line):
                pending_line = ""
                continue

            if pending_line:
                line = f"{pending_line} {line}".strip()

            if not _TXN_START_RE.match(line):
                pending_line = ""
                continue

            match = _TXN_END_RE.search(line)
            if match is None:
                pending_line = line
                continue

            parsed = self._parse_text_line(line, match, previous_balance)
            if parsed is None:
                pending_line = line
                continue

            rows.append(parsed)
            previous_balance = parsed.balance
            pending_line = ""

        if not rows:
            raise DomainValidationError(
                "Could not extract HDFC transactions from PDF text."
            )

        return rows

    def _parse_structured_tables(
        self,
        tables: list[list[list[Any | None]]],
    ) -> list[ParsedTransactionRow]:
        """Extract transactions from HDFC-style table layouts."""
        rows: list[ParsedTransactionRow] = []

        for table in tables:
            header_idx = self._find_header_index(
                table,
                ("date", "narration"),
            )
            if header_idx is None:
                continue

            header = table[header_idx]
            date_col = self._column_index(header, ("date",))
            desc_col = self._column_index(header, ("narration", "description"))
            debit_col = self._column_index(
                header,
                ("withdrawal", "debit"),
            )
            credit_col = self._column_index(
                header,
                ("deposit", "credit"),
            )
            balance_col = self._column_index(
                header,
                ("closing balance", "balance"),
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

        return rows

    def _tables_are_merged(self, tables: list[list[list[Any | None]]]) -> bool:
        """Return True when pdfplumber collapsed multiple rows into one cell."""
        for table in tables:
            for row in table:
                for cell in row:
                    if cell is not None and str(cell).count("\n") > 2:
                        return True
        return False

    def _should_skip_line(self, line: str) -> bool:
        """Return True for page headers and non-transaction metadata lines."""
        upper = line.upper().replace(" ", "")
        return any(marker.replace(" ", "") in upper for marker in _SKIP_LINE_MARKERS)

    def _parse_text_line(
        self,
        line: str,
        end_match: re.Match[str],
        previous_balance: Decimal | None,
    ) -> ParsedTransactionRow | None:
        """Parse one HDFC text transaction line."""
        prefix = line[: end_match.start()].strip()
        start_match = _TXN_START_RE.match(prefix)
        if start_match is None:
            return None

        txn_date = self._parse_indian_date(start_match.group(1))
        narration, _ref = self._split_narration_and_ref(start_match.group(2).strip())

        tail_parts = end_match.group(0).split()
        amount_tokens = tail_parts[1:]
        balance = self._parse_optional_amount(amount_tokens[-1])
        prior_amounts = amount_tokens[:-1]

        debit: Decimal | None = None
        credit: Decimal | None = None
        if len(prior_amounts) == 2:
            debit = self._parse_optional_amount(prior_amounts[0])
            credit = self._parse_optional_amount(prior_amounts[1])
        elif len(prior_amounts) == 1:
            amount = self._parse_optional_amount(prior_amounts[0])
            if amount is None:
                return None
            debit, credit = self._classify_single_amount(
                amount,
                narration,
                balance,
                previous_balance,
            )

        return self._build_row(txn_date, narration, debit, credit, balance)

    def _split_narration_and_ref(self, middle: str) -> tuple[str, str]:
        """Separate narration text from the trailing cheque/reference token."""
        tokens = middle.split()
        if len(tokens) >= 2 and _REF_TOKEN_RE.match(tokens[-1]):
            return " ".join(tokens[:-1]), tokens[-1]
        if (
            len(tokens) >= 3
            and _REF_TOKEN_RE.match(tokens[-1])
            and _REF_TOKEN_RE.match(tokens[-2])
        ):
            return " ".join(tokens[:-2]), f"{tokens[-2]}{tokens[-1]}"
        return middle, ""

    def _classify_single_amount(
        self,
        amount: Decimal,
        narration: str,
        balance: Decimal | None,
        previous_balance: Decimal | None,
    ) -> tuple[Decimal | None, Decimal | None]:
        """Decide debit vs credit when only one amount column is present."""
        upper = narration.upper()
        if any(hint in upper for hint in self._CREDIT_HINTS):
            return None, amount

        if balance is not None and previous_balance is not None:
            if balance > previous_balance:
                return None, amount
            if balance < previous_balance:
                return amount, None

        return amount, None

    def _parse_data_row(
        self,
        raw_row: list[Any | None],
        date_col: int,
        desc_col: int,
        debit_col: int | None,
        credit_col: int | None,
        balance_col: int | None,
    ) -> ParsedTransactionRow | None:
        """Parse one HDFC structured table row."""
        if date_col >= len(raw_row):
            return None

        raw_date = self._normalize_cell(raw_row[date_col])
        if not raw_date or raw_date.lower().startswith("opening"):
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
