"""PDF bank-statement parser with per-bank template adapters."""

import logging
from dataclasses import dataclass, field
from pathlib import Path

import pdfplumber
from django.conf import settings
from pypdf import PdfReader
from pypdf.errors import PdfReadError

from services.domain.exceptions import DomainValidationError
from services.domain.pdf_validation import ParseValidationResult, validate_parsed_transactions
from services.domain.transaction_row import ParsedTransactionRow
from services.internal.pdf_adapters import PDF_ADAPTERS, BankPdfAdapter

logger = logging.getLogger(__name__)


@dataclass
class PdfParseResult:
    """Parsed PDF output including validation metadata."""

    rows: list[ParsedTransactionRow]
    bank_profile: str
    validation: ParseValidationResult = field(default_factory=ParseValidationResult)


class PdfParserService:
    """Parse bank statement PDFs using per-bank template adapters."""

    def parse_file(
        self,
        file_path: Path,
        password: str | None = None,
    ) -> PdfParseResult:
        """
        Parse a PDF statement file into normalized transaction rows.

        Raises DomainValidationError for unsupported, scanned, or password-protected PDFs.
        """
        self._check_encryption(file_path, password)
        document_text, tables = self._extract_content(file_path, password)
        self._reject_scanned(document_text)
        adapter = self._detect_adapter(document_text)
        rows = adapter.parse(document_text, tables)
        validation = validate_parsed_transactions(rows)

        if validation.row_count == 0:
            raise DomainValidationError("No valid transactions found in PDF.")

        for warning in validation.warnings:
            logger.info(
                "PDF parse warning bank=%s code=%s message=%s",
                adapter.name,
                warning.code,
                warning.message,
            )

        return PdfParseResult(
            rows=rows,
            bank_profile=adapter.name,
            validation=validation,
        )

    def _check_encryption(self, file_path: Path, password: str | None) -> None:
        """Reject encrypted PDFs when no password is supplied."""
        try:
            reader = PdfReader(str(file_path))
        except PdfReadError as exc:
            raise DomainValidationError(f"Could not read PDF file: {exc}") from exc

        if not reader.is_encrypted:
            return

        if not password:
            raise DomainValidationError(
                "This PDF is password-protected. Provide the PDF password to parse it."
            )

        try:
            decrypt_result = reader.decrypt(password)
        except PdfReadError as exc:
            raise DomainValidationError(
                "Could not decrypt PDF. Check the password and try again."
            ) from exc

        if decrypt_result == 0:
            raise DomainValidationError(
                "Incorrect PDF password. Please verify and try again."
            )

    def _extract_content(
        self,
        file_path: Path,
        password: str | None,
    ) -> tuple[str, list[list[list]]]:
        """Extract plain text and tables from all PDF pages."""
        text_parts: list[str] = []
        tables: list[list[list]] = []
        min_chars = settings.PDF_MIN_TEXT_CHARS_PER_PAGE

        try:
            with pdfplumber.open(str(file_path), password=password) as pdf:
                for page in pdf.pages:
                    page_text = page.extract_text() or ""
                    text_parts.append(page_text)
                    page_tables = page.extract_tables() or []
                    tables.extend(page_tables)
        except PdfReadError as exc:
            raise DomainValidationError(
                "Could not open PDF. It may be password-protected or corrupted."
            ) from exc
        except Exception as exc:
            if "password" in str(exc).lower():
                raise DomainValidationError(
                    "This PDF is password-protected. Provide the PDF password to parse it."
                ) from exc
            raise DomainValidationError(f"Could not read PDF: {exc}") from exc

        combined_text = "\n".join(text_parts)
        if min_chars > 0 and text_parts:
            avg_chars = sum(len(part.strip()) for part in text_parts) / len(text_parts)
            if avg_chars < min_chars and not tables:
                raise DomainValidationError(
                    "This PDF appears to be scanned or image-only. "
                    "Text-based PDF statements are supported; OCR is not available yet."
                )

        return combined_text, tables

    def _reject_scanned(self, document_text: str) -> None:
        """Reject PDFs with insufficient extractable text."""
        min_total = settings.PDF_MIN_TOTAL_TEXT_CHARS
        stripped = document_text.strip()
        if len(stripped) < min_total:
            raise DomainValidationError(
                "This PDF appears to be scanned or image-only. "
                "Upload a text-based statement export from your bank."
            )

    def _detect_adapter(self, document_text: str) -> BankPdfAdapter:
        """Select the first adapter whose bank markers appear in the document."""
        for adapter in PDF_ADAPTERS:
            if adapter.matches(document_text):
                return adapter

        raise DomainValidationError(
            "Unsupported PDF bank format. Supported banks: HDFC, ICICI."
        )
