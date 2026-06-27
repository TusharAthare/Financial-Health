"""Excel (XLS/XLSX) bank-statement parser tests."""

import os
from pathlib import Path

import pandas as pd
from django.test import SimpleTestCase, override_settings

from services.internal.csv_parser import CsvParserService
from services.internal.xlsx_parser import XlsxParserService

FIXTURES_DIR = Path(__file__).resolve().parent.parent.parent / "docs"
SAMPLE_CSV = FIXTURES_DIR / "sample_statement.csv"


@override_settings(XLSX_HEADER_SCAN_ROWS=30)
class XlsxParserTests(SimpleTestCase):
    """Parse Excel exports using the generic INR column profile."""

    def setUp(self) -> None:
        """Build XLS and XLSX fixtures from the sample CSV."""
        os.environ.setdefault("DJANGO_SETTINGS_MODULE", "api.settings")
        self.parser = XlsxParserService()
        self.xlsx_path = FIXTURES_DIR / "sample_statement.xlsx"
        self.xls_path = FIXTURES_DIR / "sample_statement.xls"
        dataframe = pd.read_csv(SAMPLE_CSV, dtype=str, keep_default_na=False)
        dataframe.to_excel(self.xlsx_path, index=False, engine="openpyxl")
        self._write_xls_fixture(dataframe, self.xls_path)

    def _write_xls_fixture(self, dataframe: pd.DataFrame, output_path: Path) -> None:
        """Write a legacy .xls workbook using xlwt."""
        import xlwt

        workbook = xlwt.Workbook()
        sheet = workbook.add_sheet("Sheet1")
        for col_idx, column in enumerate(dataframe.columns):
            sheet.write(0, col_idx, column)
        for row_idx, row in enumerate(dataframe.itertuples(index=False), start=1):
            for col_idx, value in enumerate(row):
                sheet.write(row_idx, col_idx, value)
        workbook.save(str(output_path))

    def tearDown(self) -> None:
        """Remove generated Excel fixtures."""
        self.xlsx_path.unlink(missing_ok=True)
        self.xls_path.unlink(missing_ok=True)

    def test_xlsx_parses_sample_statement(self) -> None:
        """XLSX parser reads standard Date/Description/Debit/Credit columns."""
        csv_rows = CsvParserService().parse_file(SAMPLE_CSV)
        rows = self.parser.parse_file(self.xlsx_path)
        self.assertEqual(len(rows), len(csv_rows))
        self.assertEqual(rows[0].raw_description, "UPI-SWIGGY BANGALORE")

    def test_xls_parses_sample_statement(self) -> None:
        """Legacy XLS parser reads standard Date/Description/Debit/Credit columns."""
        csv_rows = CsvParserService().parse_file(SAMPLE_CSV)
        rows = self.parser.parse_file(self.xls_path)
        self.assertEqual(len(rows), len(csv_rows))
        self.assertEqual(rows[0].raw_description, "UPI-SWIGGY BANGALORE")


REAL_HDFC_XLS = (
    Path(__file__).resolve().parent.parent.parent
    / "docs"
    / "Acct Statement_8145_27062026_13.37.40.xls"
)


@override_settings(XLSX_HEADER_SCAN_ROWS=50)
class RealHdfcStatementXlsTests(SimpleTestCase):
    """Integration test against the real HDFC XLS export in docs/."""

    def setUp(self) -> None:
        """Initialize parser."""
        os.environ.setdefault("DJANGO_SETTINGS_MODULE", "api.settings")
        self.parser = XlsxParserService()

    def test_real_hdfc_xls_statement_parses(self) -> None:
        """Real HDFC XLS export parses Withdrawal/Deposit column layout."""
        if not REAL_HDFC_XLS.is_file():
            self.skipTest("Real HDFC sample XLS not present in docs/.")

        rows = self.parser.parse_file(REAL_HDFC_XLS)
        self.assertGreaterEqual(len(rows), 1200)
        self.assertEqual(rows[0].raw_description[:4], "UPI-")
