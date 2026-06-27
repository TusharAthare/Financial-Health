"""Excel (XLS/XLSX) bank-statement parser reusing CSV column profiles."""

from pathlib import Path

import pandas as pd

from django.conf import settings

from services.domain.exceptions import DomainValidationError
from services.domain.transaction_row import ParsedTransactionRow
from services.internal.csv_parser import CsvColumnProfile, CsvParserService

_EXCEL_ENGINES = {
    ".xls": "xlrd",
    ".xlsx": "openpyxl",
    ".xlsm": "openpyxl",
}


class XlsxParserService:
    """Parse bank Excel exports (.xls and .xlsx) into normalized transaction rows."""

    def __init__(self) -> None:
        """Initialize the shared tabular parser."""
        self._tabular = CsvParserService()

    def parse_file(self, file_path: Path) -> list[ParsedTransactionRow]:
        """
        Parse an Excel file using auto-detected column profile.

        Raises DomainValidationError on parse failures.
        """
        dataframe, profile = self._load_statement_table(file_path)
        if dataframe.empty:
            raise DomainValidationError("Excel file contains no data rows.")
        return self._tabular._parse_dataframe(dataframe, profile)

    def _excel_engine(self, file_path: Path) -> str:
        """Return the pandas engine name for the given Excel file extension."""
        ext = file_path.suffix.lower()
        engine = _EXCEL_ENGINES.get(ext)
        if engine is None:
            raise DomainValidationError(
                f"Unsupported Excel extension '{ext}'. Allowed: .xls, .xlsx."
            )
        return engine

    def _load_statement_table(
        self,
        file_path: Path,
    ) -> tuple[pd.DataFrame, CsvColumnProfile]:
        """Locate the transaction header row and return a typed dataframe."""
        scan_limit = settings.XLSX_HEADER_SCAN_ROWS
        engine = self._excel_engine(file_path)
        try:
            raw = pd.read_excel(
                file_path,
                sheet_name=0,
                header=None,
                dtype=str,
                engine=engine,
            )
        except Exception as exc:
            raise DomainValidationError(f"Could not read Excel file: {exc}") from exc

        if raw.empty:
            raise DomainValidationError("Excel file is empty.")

        header_idx, profile = self._find_header_row(raw, scan_limit)
        header_cells = [
            str(value).strip() if pd.notna(value) else ""
            for value in raw.iloc[header_idx].tolist()
        ]
        data = raw.iloc[header_idx + 1:].copy()
        data.columns = header_cells
        data = data.loc[:, [col for col in data.columns if col]]
        data = data.fillna("")
        return data, profile

    def _find_header_row(
        self,
        raw: pd.DataFrame,
        scan_limit: int,
    ) -> tuple[int, CsvColumnProfile]:
        """Scan initial rows for a header matching a known column profile."""
        max_row = min(scan_limit, len(raw))
        for idx in range(max_row):
            cells = [
                str(value).strip()
                for value in raw.iloc[idx].tolist()
                if pd.notna(value) and str(value).strip()
            ]
            if not cells:
                continue
            profile = self._match_profile(cells)
            if profile is not None:
                return idx, profile

        raise DomainValidationError(
            "Unsupported Excel format. Expected columns like Date, Description, "
            "Debit/Credit."
        )

    def _match_profile(self, header_cells: list[str]) -> CsvColumnProfile | None:
        """Return the first profile matching the given header cells."""
        try:
            return self._tabular.detect_profile_from_headers(header_cells)
        except DomainValidationError:
            return None
