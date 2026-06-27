"""Statement upload and parse lifecycle services."""

import logging
from datetime import date
from pathlib import Path

from django.conf import settings
from django.core.files.uploadedfile import UploadedFile
from django.db import transaction

from services.domain.exceptions import DomainPermissionDenied, DomainValidationError
from services.internal.audit import AuditService
from services.internal.quota import QuotaService
from services.domain.transaction_row import ParsedTransactionRow
from services.internal.csv_parser import CsvParserService
from services.internal.pdf_parser import PdfParserService
from services.internal.upload import UploadService
from services.internal.xlsx_parser import XlsxParserService
from statements.models import Account, Statement, Transaction

logger = logging.getLogger(__name__)


class StatementService:
    """Manage statement uploads, parsing, and tenant-scoped queries."""

    def __init__(self) -> None:
        """Initialize dependent services."""
        self._upload = UploadService()
        self._csv_parser = CsvParserService()
        self._pdf_parser = PdfParserService()
        self._xlsx_parser = XlsxParserService()
        self._audit = AuditService()
        self._quota = QuotaService()

    def list_statements(self, user_id: int) -> list[Statement]:
        """Return all statements belonging to the user."""
        return list(
            Statement.objects.filter(user_id=user_id)
            .select_related("account")
            .order_by("-created_at")
        )

    def get_statement(self, user_id: int, statement_id: int) -> Statement | None:
        """Return a statement if owned by the user."""
        return (
            Statement.objects.filter(id=statement_id, user_id=user_id)
            .select_related("account")
            .first()
        )

    @transaction.atomic
    def upload_statement(
        self,
        user_id: int,
        account_id: int,
        uploaded_file: UploadedFile,
    ) -> Statement:
        """
        Store an upload and create a Statement record.

        Raises DomainValidationError, DomainPermissionDenied, InvalidStateError.
        """
        account = Account.objects.filter(id=account_id, user_id=user_id).first()
        if account is None:
            raise DomainPermissionDenied("Account not found or access denied.")

        self._quota.check_upload_allowed(user_id)

        relative_path, checksum = self._upload.save_upload(user_id, uploaded_file)

        existing = Statement.objects.filter(
            user_id=user_id,
            checksum=checksum,
            status=Statement.Status.PARSED,
        ).first()
        if existing is not None:
            self._upload.delete_file(relative_path)
            logger.info(
                "Duplicate statement upload user_id=%s checksum=%s existing_id=%s",
                user_id,
                checksum,
                existing.id,
            )
            return existing

        ext = uploaded_file.name.rsplit(".", 1)[-1].lower()
        format_map = {
            "csv": Statement.FileFormat.CSV,
            "pdf": Statement.FileFormat.PDF,
            "xls": Statement.FileFormat.XLS,
            "xlsx": Statement.FileFormat.XLSX,
        }
        file_format = format_map.get(ext)
        if file_format is None:
            self._upload.delete_file(relative_path)
            raise DomainValidationError(
                f"Unsupported file extension '.{ext}'. Allowed: csv, pdf, xls, xlsx."
            )

        statement = Statement.objects.create(
            user_id=user_id,
            account=account,
            source_file=relative_path,
            original_filename=uploaded_file.name,
            file_format=file_format,
            status=Statement.Status.UPLOADED,
            checksum=checksum,
        )
        logger.info(
            "Statement uploaded id=%s user_id=%s account_id=%s format=%s",
            statement.id,
            user_id,
            account_id,
            file_format,
        )
        self._audit.log(
            user_id,
            "upload",
            target_type="statement",
            target_id=str(statement.id),
            metadata={
                "filename": uploaded_file.name,
                "format": file_format,
                "checksum": checksum,
            },
        )
        return statement

    @transaction.atomic
    def mark_parsing(self, statement_id: int) -> Statement:
        """Transition statement to parsing status."""
        statement = Statement.objects.select_for_update().get(id=statement_id)
        statement.status = Statement.Status.PARSING
        statement.error_message = ""
        statement.save(update_fields=["status", "error_message", "updated_at"])
        return statement

    @transaction.atomic
    def parse_statement(
        self,
        statement_id: int,
        pdf_password: str | None = None,
    ) -> Statement:
        """
        Parse a statement (CSV, PDF, XLS, or XLSX), persist transactions, and update status.

        Called from the Celery worker. Raises on unrecoverable errors.
        """
        statement = Statement.objects.select_for_update().select_related(
            "account",
        ).get(id=statement_id)

        file_path = self._upload.absolute_path(statement.source_file)

        if statement.file_format == Statement.FileFormat.CSV:
            parsed_rows = self._csv_parser.parse_file(file_path)
        elif statement.file_format == Statement.FileFormat.PDF:
            result = self._pdf_parser.parse_file(file_path, password=pdf_password)
            parsed_rows = result.rows
            logger.info(
                "PDF parsed statement_id=%s bank=%s warnings=%s",
                statement_id,
                result.bank_profile,
                len(result.validation.warnings),
            )
        elif self._is_excel_statement(statement):
            parsed_rows = self._xlsx_parser.parse_file(file_path)
        else:
            raise DomainValidationError(
                f"Unsupported file format: {statement.file_format}"
            )

        return self._persist_parsed_rows(statement, parsed_rows)

    @transaction.atomic
    def parse_csv_statement(self, statement_id: int) -> Statement:
        """Parse a CSV statement (backward-compatible entry point)."""
        return self.parse_statement(statement_id)

    @transaction.atomic
    def mark_failed(self, statement_id: int, error_message: str) -> Statement:
        """Mark a statement as failed with an error message."""
        statement = Statement.objects.select_for_update().get(id=statement_id)
        statement.status = Statement.Status.FAILED
        statement.error_message = error_message[:2000]
        statement.save(update_fields=["status", "error_message", "updated_at"])
        logger.error("Statement parse failed id=%s error=%s", statement_id, error_message)
        return statement

    def _persist_parsed_rows(
        self,
        statement: Statement,
        parsed_rows: list[ParsedTransactionRow],
    ) -> Statement:
        """Bulk-insert transactions and mark the statement parsed."""
        period_start, period_end = self._derive_period(parsed_rows)
        uncategorized = self._get_uncategorized_category()

        txn_objects = [
            Transaction(
                user_id=statement.user_id,
                account_id=statement.account_id,
                statement=statement,
                category=uncategorized,
                transaction_date=row.transaction_date,
                amount=row.amount,
                raw_description=row.raw_description,
                normalized_merchant=row.normalized_merchant,
                balance=row.balance,
            )
            for row in parsed_rows
        ]

        Transaction.objects.bulk_create(
            txn_objects,
            ignore_conflicts=True,
        )
        inserted_count = Transaction.objects.filter(statement=statement).count()

        statement.period_start = period_start
        statement.period_end = period_end
        statement.transaction_count = inserted_count
        statement.status = Statement.Status.PARSED
        statement.error_message = ""
        statement.save(
            update_fields=[
                "period_start",
                "period_end",
                "transaction_count",
                "status",
                "error_message",
                "updated_at",
            ],
        )

        if settings.STATEMENT_DELETE_RAW_AFTER_PARSE:
            self._upload.delete_file(statement.source_file)

        from services.internal.categorization import CategorizationService
        from services.internal.recurring import RecurringDetectionService

        CategorizationService().categorize_for_statement(
            user_id=statement.user_id,
            statement_id=statement.id,
        )
        RecurringDetectionService().detect_for_user(
            user_id=statement.user_id,
            statement_id=statement.id,
        )

        from services.internal.report import ReportService

        ReportService().build_for_statement(
            user_id=statement.user_id,
            statement_id=statement.id,
        )

        logger.info(
            "Statement parsed id=%s transactions=%s",
            statement.id,
            inserted_count,
        )
        return statement

    def _is_excel_statement(self, statement: Statement) -> bool:
        """Return True for XLS/XLSX statements, including extension fallback."""
        if statement.file_format in (
            Statement.FileFormat.XLS,
            Statement.FileFormat.XLSX,
        ):
            return True

        ext = Path(statement.original_filename).suffix.lower().lstrip(".")
        return ext in ("xls", "xlsx")

    def _derive_period(
        self,
        rows: list[ParsedTransactionRow],
    ) -> tuple[date | None, date | None]:
        """Return min/max transaction dates from parsed rows."""
        if not rows:
            return None, None
        dates = [row.transaction_date for row in rows]
        return min(dates), max(dates)

    def _get_uncategorized_category(self):
        """Return the system Uncategorized category."""
        from statements.models import Category

        category = Category.objects.filter(
            user__isnull=True,
            slug="uncategorized",
        ).first()
        if category is None:
            raise DomainValidationError(
                "System category 'uncategorized' is missing. Run migrations."
            )
        return category
