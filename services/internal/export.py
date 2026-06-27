"""Report export generation (CSV and PDF)."""

import csv
import io
import logging
import os
import uuid
from decimal import Decimal
from pathlib import Path

from django.conf import settings
from django.db import transaction

from analysis.models import ExportJob, Report
from services.domain.exceptions import DomainValidationError
from services.internal.audit import AuditService
from statements.models import Transaction

logger = logging.getLogger(__name__)


class ExportService:
    """Create and manage async report exports."""

    def __init__(self) -> None:
        """Initialize dependent services."""
        self._audit = AuditService()

    def get_job(self, user_id: int, job_id: int) -> ExportJob | None:
        """Return an export job owned by the user."""
        return (
            ExportJob.objects.filter(id=job_id, user_id=user_id)
            .select_related("report", "report__statement")
            .first()
        )

    @transaction.atomic
    def create_export_job(
        self,
        user_id: int,
        statement_id: int,
        export_format: str,
    ) -> ExportJob:
        """
        Create a pending export job for a parsed statement report.

        Raises DomainValidationError when the report is missing or format invalid.
        """
        if export_format not in (ExportJob.Format.CSV, ExportJob.Format.PDF):
            raise DomainValidationError("Export format must be 'csv' or 'pdf'.")

        report = (
            Report.objects.filter(user_id=user_id, statement_id=statement_id)
            .select_related("statement")
            .first()
        )
        if report is None:
            raise DomainValidationError("Report not found for statement.")

        job = ExportJob.objects.create(
            user_id=user_id,
            report=report,
            export_format=export_format,
            status=ExportJob.Status.PENDING,
        )
        logger.info(
            "Export job created id=%s user_id=%s statement_id=%s format=%s",
            job.id,
            user_id,
            statement_id,
            export_format,
        )
        return job

    @transaction.atomic
    def process_export(self, job_id: int) -> ExportJob:
        """Generate the export file and mark the job completed or failed."""
        job = ExportJob.objects.select_for_update().select_related(
            "report",
            "report__statement",
            "report__statement__account",
        ).get(id=job_id)

        job.status = ExportJob.Status.PROCESSING
        job.save(update_fields=["status", "updated_at"])

        try:
            if job.export_format == ExportJob.Format.CSV:
                relative_path = self._write_csv(job)
            else:
                relative_path = self._write_pdf(job)

            job.file_path = relative_path
            job.status = ExportJob.Status.COMPLETED
            job.error_message = ""
            job.save(update_fields=["file_path", "status", "error_message", "updated_at"])

            self._audit.log(
                job.user_id,
                "export",
                target_type="statement",
                target_id=str(job.report.statement_id),
                metadata={
                    "export_job_id": job.id,
                    "format": job.export_format,
                },
            )
            logger.info("Export completed job_id=%s path=%s", job.id, relative_path)
        except Exception as exc:
            job.status = ExportJob.Status.FAILED
            job.error_message = str(exc)[:2000]
            job.save(update_fields=["status", "error_message", "updated_at"])
            logger.exception("Export failed job_id=%s", job.id)
            raise exc

        return job

    def absolute_path(self, relative_path: str) -> Path:
        """Resolve an export file path under MEDIA_ROOT."""
        return settings.MEDIA_ROOT / relative_path

    def _export_dir(self, user_id: int) -> Path:
        """Ensure and return the user's export directory."""
        export_dir = settings.MEDIA_ROOT / "exports" / str(user_id)
        export_dir.mkdir(parents=True, exist_ok=True)
        if os.name != "nt":
            os.chmod(export_dir, 0o750)
        return export_dir

    def _write_csv(self, job: ExportJob) -> str:
        """Write a CSV export with summary and transaction rows."""
        report = job.report
        statement = report.statement
        aggregates = report.aggregates or {}

        buffer = io.StringIO()
        writer = csv.writer(buffer)

        writer.writerow(["Financial Health Report Export"])
        writer.writerow(["Period", report.period_start, report.period_end])
        writer.writerow(["Bank", statement.account.bank_name])
        writer.writerow(["Filename", statement.original_filename])
        writer.writerow([])
        writer.writerow(["Summary"])
        writer.writerow(["Income", aggregates.get("income", "0")])
        writer.writerow(["Expense", aggregates.get("expense", "0")])
        writer.writerow(["Net cash flow", aggregates.get("net_cash_flow", "0")])
        writer.writerow(["Savings rate %", aggregates.get("savings_rate", "")])
        writer.writerow(["EMI total", aggregates.get("emi_total", "0")])
        writer.writerow(
            ["Subscription total", aggregates.get("subscription_total", "0")],
        )
        writer.writerow([])
        writer.writerow(
            [
                "Date",
                "Amount",
                "Merchant",
                "Description",
                "Category",
                "Balance",
            ],
        )

        txns = Transaction.objects.filter(
            user_id=job.user_id,
            statement_id=statement.id,
        ).select_related("category").order_by("transaction_date", "id")

        for txn in txns:
            writer.writerow(
                [
                    txn.transaction_date.isoformat(),
                    str(txn.amount),
                    txn.normalized_merchant,
                    txn.raw_description,
                    txn.category.name if txn.category else "Uncategorized",
                    str(txn.balance) if txn.balance is not None else "",
                ],
            )

        filename = f"report_{statement.id}_{uuid.uuid4().hex[:8]}.csv"
        relative_path = str(Path("exports") / str(job.user_id) / filename)
        absolute_path = settings.MEDIA_ROOT / relative_path
        absolute_path.parent.mkdir(parents=True, exist_ok=True)
        absolute_path.write_text(buffer.getvalue(), encoding="utf-8")
        if os.name != "nt":
            os.chmod(absolute_path, 0o640)
        return relative_path

    def _write_pdf(self, job: ExportJob) -> str:
        """Write a simple PDF summary export using reportlab."""
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import getSampleStyleSheet
        from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

        report = job.report
        statement = report.statement
        aggregates = report.aggregates or {}

        filename = f"report_{statement.id}_{uuid.uuid4().hex[:8]}.pdf"
        relative_path = str(Path("exports") / str(job.user_id) / filename)
        absolute_path = settings.MEDIA_ROOT / relative_path
        absolute_path.parent.mkdir(parents=True, exist_ok=True)

        doc = SimpleDocTemplate(str(absolute_path), pagesize=A4)
        styles = getSampleStyleSheet()
        elements = [
            Paragraph("Financial Health Report", styles["Title"]),
            Spacer(1, 12),
            Paragraph(
                f"Period: {report.period_start} – {report.period_end}",
                styles["Normal"],
            ),
            Paragraph(f"Bank: {statement.account.bank_name}", styles["Normal"]),
            Paragraph(f"File: {statement.original_filename}", styles["Normal"]),
            Spacer(1, 16),
        ]

        summary_data = [
            ["Metric", "Value"],
            ["Income", self._format_inr(aggregates.get("income", "0"))],
            ["Expense", self._format_inr(aggregates.get("expense", "0"))],
            ["Net cash flow", self._format_inr(aggregates.get("net_cash_flow", "0"))],
            ["Savings rate", f"{aggregates.get('savings_rate', '—')}%"],
            ["EMI total", self._format_inr(aggregates.get("emi_total", "0"))],
            [
                "Subscriptions",
                self._format_inr(aggregates.get("subscription_total", "0")),
            ],
        ]
        summary_table = Table(summary_data, colWidths=[180, 200])
        summary_table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2563eb")),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ],
            ),
        )
        elements.append(summary_table)
        elements.append(Spacer(1, 16))

        category_totals = aggregates.get("category_totals", [])[:8]
        if category_totals:
            elements.append(Paragraph("Top categories", styles["Heading2"]))
            cat_data = [["Category", "Total"]]
            for item in category_totals:
                cat_data.append(
                    [
                        item.get("category_name", ""),
                        self._format_inr(item.get("total", "0")),
                    ],
                )
            cat_table = Table(cat_data, colWidths=[240, 140])
            cat_table.setStyle(
                TableStyle(
                    [
                        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e2e8f0")),
                        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                    ],
                ),
            )
            elements.append(cat_table)

        doc.build(elements)
        if os.name != "nt":
            os.chmod(absolute_path, 0o640)
        return relative_path

    def _format_inr(self, value: str | Decimal) -> str:
        """Format a decimal string as INR for PDF output."""
        amount = Decimal(str(value))
        return f"₹{amount:,.0f}"
