"""CSV bank-statement parser with column-profile adapters."""

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

import pandas as pd

from services.domain.exceptions import DomainValidationError
from services.domain.normalization import parse_amount, signed_amount
from services.domain.upi_remark import resolve_normalized_merchant
from services.domain.transaction_row import ParsedTransactionRow


@dataclass(frozen=True)
class CsvColumnProfile:
    """Column mapping for a bank CSV export format."""

    name: str
    date_columns: tuple[str, ...]
    description_columns: tuple[str, ...]
    debit_columns: tuple[str, ...]
    credit_columns: tuple[str, ...]
    amount_columns: tuple[str, ...]
    balance_columns: tuple[str, ...]
    date_format: str | None = None


GENERIC_INR_PROFILE = CsvColumnProfile(
    name="generic_inr",
    date_columns=("Date", "Transaction Date", "Txn Date", "Value Date", "Value Dt"),
    description_columns=(
        "Description",
        "Narration",
        "Particulars",
        "Remarks",
        "Transaction Details",
        "Transaction Remarks",
    ),
    debit_columns=("Debit", "Withdrawal", "Dr", "Debit Amount", "Withdrawal Amt."),
    credit_columns=("Credit", "Deposit", "Cr", "Credit Amount", "Deposit Amt."),
    amount_columns=("Amount", "Transaction Amount"),
    balance_columns=("Balance", "Closing Balance", "Available Balance"),
    date_format="%d-%m-%Y",
)

CSV_PROFILES: tuple[CsvColumnProfile, ...] = (GENERIC_INR_PROFILE,)


class CsvParserService:
    """Parse bank CSV exports into normalized transaction rows."""

    def parse_file(self, file_path: Path, profile: CsvColumnProfile | None = None) -> list[ParsedTransactionRow]:
        """
        Parse a CSV file using the given or auto-detected column profile.

        Raises DomainValidationError on parse failures.
        """
        if profile is None:
            profile = self.detect_profile(file_path)

        try:
            dataframe = pd.read_csv(file_path, dtype=str, keep_default_na=False)
        except Exception as exc:
            raise DomainValidationError(f"Could not read CSV file: {exc}") from exc

        if dataframe.empty:
            raise DomainValidationError("CSV file contains no data rows.")

        return self._parse_dataframe(dataframe, profile)

    def detect_profile(self, file_path: Path) -> CsvColumnProfile:
        """
        Pick the first profile whose required columns exist in the CSV header.

        Raises DomainValidationError when no profile matches.
        """
        try:
            header = pd.read_csv(file_path, nrows=0).columns.tolist()
        except Exception as exc:
            raise DomainValidationError(f"Could not read CSV header: {exc}") from exc

        return self.detect_profile_from_headers(header)

    def detect_profile_from_headers(self, headers: list[str]) -> CsvColumnProfile:
        """
        Pick the first profile whose required columns exist in the header.

        Raises DomainValidationError when no profile matches.
        """
        header_set = {col.strip() for col in headers if col.strip()}
        for profile in CSV_PROFILES:
            if self._profile_matches(header_set, profile):
                return profile

        raise DomainValidationError(
            "Unsupported CSV format. Expected columns like Date, Description, Debit/Credit."
        )

    def _profile_matches(self, header: set[str], profile: CsvColumnProfile) -> bool:
        """Return True when the profile has date, description, and amount columns."""
        return (
            self._headers_include(header, profile.date_columns)
            and self._headers_include(header, profile.description_columns)
            and (
                self._headers_include(header, profile.amount_columns)
                or (
                    self._headers_include(header, profile.debit_columns)
                    and self._headers_include(header, profile.credit_columns)
                )
            )
        )

    def _headers_include(
        self,
        header: set[str],
        candidates: tuple[str, ...],
    ) -> bool:
        """Return True when any header cell contains a candidate label."""
        header_lower = [name.lower() for name in header]
        for candidate in candidates:
            needle = candidate.lower()
            if any(needle in name for name in header_lower):
                return True
        return False

    def _parse_dataframe(
        self,
        dataframe: pd.DataFrame,
        profile: CsvColumnProfile,
    ) -> list[ParsedTransactionRow]:
        """Convert a dataframe into parsed transaction rows."""
        rows: list[ParsedTransactionRow] = []
        for _, series in dataframe.iterrows():
            row_dict = {str(k).strip(): v for k, v in series.items()}
            parsed = self._parse_row(row_dict, profile)
            if parsed is not None:
                rows.append(parsed)

        if not rows:
            raise DomainValidationError("No valid transaction rows found in CSV.")

        return rows

    def _parse_row(
        self,
        row: dict[str, Any],
        profile: CsvColumnProfile,
    ) -> ParsedTransactionRow | None:
        """Parse a single CSV row; return None for blank rows."""
        date_col = self._first_present(row, profile.date_columns)
        desc_col = self._first_present(row, profile.description_columns)
        if date_col is None or desc_col is None:
            return None

        raw_date = str(row.get(date_col, "")).strip()
        raw_desc = str(row.get(desc_col, "")).strip()
        if not raw_date or not raw_desc or raw_date.startswith("*"):
            return None

        try:
            txn_date = self._parse_date(raw_date, profile.date_format)
        except DomainValidationError:
            return None
        amount = self._parse_row_amount(row, profile)
        balance = self._parse_optional_amount(row, profile.balance_columns)

        return ParsedTransactionRow(
            transaction_date=txn_date,
            amount=amount,
            raw_description=raw_desc,
            normalized_merchant=resolve_normalized_merchant(raw_desc),
            balance=balance,
        )

    def _first_present(self, row: dict[str, Any], candidates: tuple[str, ...]) -> str | None:
        """Return the row key matching any candidate column label."""
        for col in candidates:
            if col in row:
                return col

        for key in row:
            key_lower = str(key).lower()
            for col in candidates:
                if col.lower() in key_lower:
                    return str(key)
        return None

    def _parse_date(self, value: str, fmt: str | None) -> date:
        """Parse a date string using the profile format or pandas inference."""
        if fmt:
            try:
                return datetime.strptime(value, fmt).date()
            except ValueError:
                pass

        parsed = pd.to_datetime(value, dayfirst=True, errors="coerce")
        if pd.isna(parsed):
            raise DomainValidationError(f"Invalid date value: {value}")
        return parsed.date()

    def _parse_row_amount(self, row: dict[str, Any], profile: CsvColumnProfile) -> Decimal:
        """Extract signed amount from amount or debit/credit columns."""
        amount_col = self._first_present(row, profile.amount_columns)
        if amount_col is not None:
            return parse_amount(row.get(amount_col))

        debit_col = self._first_present(row, profile.debit_columns)
        credit_col = self._first_present(row, profile.credit_columns)
        debit = self._optional_amount(row, debit_col)
        credit = self._optional_amount(row, credit_col)
        return signed_amount(debit, credit)

    def _optional_amount(self, row: dict[str, Any], col: str | None) -> Decimal | None:
        """Parse an optional amount column, returning None when empty."""
        if col is None:
            return None
        raw = str(row.get(col, "")).strip()
        if not raw or raw.lower() in ("-", "nan", "none"):
            return None
        return parse_amount(raw)

    def _parse_optional_amount(
        self,
        row: dict[str, Any],
        candidates: tuple[str, ...],
    ) -> Decimal | None:
        """Parse balance from the first matching column."""
        col = self._first_present(row, candidates)
        return self._optional_amount(row, col)
