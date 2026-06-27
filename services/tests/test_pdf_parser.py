"""PDF parser golden-file and edge-case tests."""

import json
import os
from decimal import Decimal
from pathlib import Path

from django.test import SimpleTestCase, override_settings

from services.domain.exceptions import DomainValidationError
from services.domain.pdf_validation import validate_parsed_transactions
from services.internal.pdf_parser import PdfParserService
from tests.fixtures.pdf.generate import build_hdfc_pdf, build_icici_pdf, build_password_pdf, build_scanned_pdf

FIXTURES_DIR = (
    Path(__file__).resolve().parent.parent.parent / "tests" / "fixtures" / "pdf"
)
EXPECTED_DIR = FIXTURES_DIR / "expected"


@override_settings(
    PDF_MIN_TEXT_CHARS_PER_PAGE=5,
    PDF_MIN_TOTAL_TEXT_CHARS=10,
)
class PdfParserGoldenFileTests(SimpleTestCase):
    """Golden-file tests for HDFC and ICICI PDF adapters."""

    def setUp(self) -> None:
        """Build fresh PDF fixtures before each test."""
        os.environ.setdefault("DJANGO_SETTINGS_MODULE", "api.settings")
        self.parser = PdfParserService()
        self.hdfc_pdf = FIXTURES_DIR / "hdfc_sample.pdf"
        self.icici_pdf = FIXTURES_DIR / "icici_sample.pdf"
        build_hdfc_pdf(self.hdfc_pdf)
        build_icici_pdf(self.icici_pdf)

    def _load_expected(self, name: str) -> list[dict]:
        """Load expected transaction JSON for a fixture."""
        with open(EXPECTED_DIR / name, encoding="utf-8") as handle:
            return json.load(handle)

    def _assert_matches_golden(self, result_rows, golden_name: str) -> None:
        """Compare parsed rows against golden JSON expectations."""
        expected = self._load_expected(golden_name)
        self.assertEqual(len(result_rows), len(expected))

        for parsed, exp in zip(result_rows, expected, strict=True):
            self.assertEqual(
                parsed.transaction_date.isoformat(),
                exp["transaction_date"],
            )
            self.assertEqual(str(parsed.amount), exp["amount"])
            self.assertEqual(parsed.raw_description, exp["raw_description"])
            if exp["balance"] is None:
                self.assertIsNone(parsed.balance)
            else:
                self.assertEqual(str(parsed.balance), exp["balance"])

    def test_hdfc_pdf_matches_golden_file(self) -> None:
        """HDFC adapter extracts expected transactions from sample PDF."""
        result = self.parser.parse_file(self.hdfc_pdf)
        self.assertEqual(result.bank_profile, "hdfc")
        self._assert_matches_golden(result.rows, "hdfc_sample.json")

    def test_icici_pdf_matches_golden_file(self) -> None:
        """ICICI adapter extracts expected transactions from sample PDF."""
        result = self.parser.parse_file(self.icici_pdf)
        self.assertEqual(result.bank_profile, "icici")
        self._assert_matches_golden(result.rows, "icici_sample.json")

    def test_hdfc_validation_passes_balance_continuity(self) -> None:
        """HDFC golden rows satisfy balance continuity checks."""
        result = self.parser.parse_file(self.hdfc_pdf)
        validation = validate_parsed_transactions(result.rows)
        self.assertTrue(validation.balance_continuity_ok)
        self.assertTrue(validation.dates_monotonic)


@override_settings(
    PDF_MIN_TEXT_CHARS_PER_PAGE=5,
    PDF_MIN_TOTAL_TEXT_CHARS=10,
)
class PdfParserEdgeCaseTests(SimpleTestCase):
    """Edge-case handling for scanned and password-protected PDFs."""

    def setUp(self) -> None:
        """Initialize parser and edge-case fixture paths."""
        os.environ.setdefault("DJANGO_SETTINGS_MODULE", "api.settings")
        self.parser = PdfParserService()
        self.scanned_pdf = FIXTURES_DIR / "scanned_empty.pdf"
        self.password_pdf = FIXTURES_DIR / "password_protected.pdf"
        build_scanned_pdf(self.scanned_pdf)
        build_password_pdf(self.password_pdf, password="secret123")

    def test_scanned_pdf_rejected_with_clear_message(self) -> None:
        """Image-only PDFs are rejected with a helpful error."""
        with self.assertRaises(DomainValidationError) as ctx:
            self.parser.parse_file(self.scanned_pdf)

        message = str(ctx.exception).lower()
        self.assertIn("scanned", message)

    def test_password_pdf_rejected_without_password(self) -> None:
        """Encrypted PDFs require a password."""
        with self.assertRaises(DomainValidationError) as ctx:
            self.parser.parse_file(self.password_pdf)

        message = str(ctx.exception).lower()
        self.assertIn("password", message)

    def test_password_pdf_parses_with_correct_password(self) -> None:
        """Encrypted PDFs parse when the correct password is supplied."""
        result = self.parser.parse_file(self.password_pdf, password="secret123")
        self.assertEqual(result.bank_profile, "hdfc")
        self.assertGreater(len(result.rows), 0)

    def test_password_pdf_rejects_wrong_password(self) -> None:
        """Wrong password yields a clear validation error."""
        with self.assertRaises(DomainValidationError) as ctx:
            self.parser.parse_file(self.password_pdf, password="wrong")

        message = str(ctx.exception).lower()
        self.assertIn("password", message)

    def test_unsupported_pdf_format_rejected(self) -> None:
        """Unknown bank PDFs are rejected with supported-bank hint."""
        unknown_pdf = FIXTURES_DIR / "unknown_bank.pdf"
        from reportlab.lib.styles import getSampleStyleSheet
        from reportlab.platypus import Paragraph, SimpleDocTemplate

        styles = getSampleStyleSheet()
        doc = SimpleDocTemplate(str(unknown_pdf))
        doc.build([Paragraph("Some Other Bank Statement", styles["Title"])])

        with self.assertRaises(DomainValidationError) as ctx:
            self.parser.parse_file(unknown_pdf)

        message = str(ctx.exception).lower()
        self.assertIn("unsupported", message)


REAL_HDFC_PDF = (
    Path(__file__).resolve().parent.parent.parent
    / "docs"
    / "Acct Statement_8145_13062026_13.30.33_unlocked.pdf"
)


@override_settings(
    PDF_MIN_TEXT_CHARS_PER_PAGE=5,
    PDF_MIN_TOTAL_TEXT_CHARS=10,
)
class RealHdfcStatementPdfTests(SimpleTestCase):
    """Integration test against the real HDFC statement in docs/."""

    def setUp(self) -> None:
        """Initialize parser."""
        os.environ.setdefault("DJANGO_SETTINGS_MODULE", "api.settings")
        self.parser = PdfParserService()

    def test_real_hdfc_unlocked_statement_parses(self) -> None:
        """Real HDFC salary-account PDF extracts text-line transactions."""
        if not REAL_HDFC_PDF.is_file():
            self.skipTest("Real HDFC sample PDF not present in docs/.")

        result = self.parser.parse_file(REAL_HDFC_PDF)
        self.assertEqual(result.bank_profile, "hdfc")
        self.assertGreaterEqual(len(result.rows), 1200)
        self.assertEqual(result.rows[0].raw_description[:4], "UPI-")
        self.assertTrue(result.validation.dates_monotonic)


class PdfValidationTests(SimpleTestCase):
    """Unit tests for post-parse validation helpers."""

    def test_balance_discontinuity_warning(self) -> None:
        """Validation flags rows where balance math does not add up."""
        from datetime import date

        from services.domain.transaction_row import ParsedTransactionRow

        rows = [
            ParsedTransactionRow(
                transaction_date=date(2025, 6, 1),
                amount=Decimal("-100.00"),
                raw_description="DEBIT A",
                normalized_merchant="DEBIT A",
                balance=Decimal("900.00"),
            ),
            ParsedTransactionRow(
                transaction_date=date(2025, 6, 2),
                amount=Decimal("-50.00"),
                raw_description="DEBIT B",
                normalized_merchant="DEBIT B",
                balance=Decimal("800.00"),
            ),
        ]
        result = validate_parsed_transactions(rows)
        self.assertFalse(result.balance_continuity_ok)
        codes = [w.code for w in result.warnings]
        self.assertIn("balance_discontinuity", codes)
