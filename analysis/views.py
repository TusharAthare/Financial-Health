"""Analysis API views."""

from django.http import FileResponse
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from analysis.models import ExportJob
from analysis.serializers import (
    ExportJobSerializer,
    ExportRequestSerializer,
    InsightSerializer,
    ReportSerializer,
    ReportSummaryItemSerializer,
    RecurringPatternSerializer,
)
from analysis.tasks import export_report_task
from services.domain.exceptions import DomainValidationError
from services.domain.progress import compute_category_drift, compute_emi_burden_pct
from services.internal.export import ExportService
from services.internal.monthly_report import MonthlyReportService
from services.internal.recurring import RecurringDetectionService
from services.internal.report import ReportService


class RecurringPatternListView(APIView):
    """List detected recurring patterns (subscriptions, autopay, EMIs)."""

    permission_classes = [IsAuthenticated]

    def get(self, request) -> Response:
        """Return recurring patterns for the authenticated user."""
        patterns = RecurringDetectionService().list_patterns(user_id=request.user.id)
        serializer = RecurringPatternSerializer(patterns, many=True)
        return Response(serializer.data)


class ReportDetailView(APIView):
    """Return the report snapshot for a parsed statement."""

    permission_classes = [IsAuthenticated]

    def get(self, request, statement_id: int) -> Response:
        """Return report aggregates for the given statement."""
        service = ReportService()
        report = service.get_report(
            user_id=request.user.id,
            statement_id=statement_id,
        )
        if report is None:
            try:
                report = service.build_for_statement(
                    user_id=request.user.id,
                    statement_id=statement_id,
                )
            except DomainValidationError:
                return Response(
                    {"error": {"code": "not_found", "message": "Report not found."}},
                    status=status.HTTP_404_NOT_FOUND,
                )
        return Response(ReportSerializer(report).data)


class ReportSummaryView(APIView):
    """Return cross-statement progress data for trend charts."""

    permission_classes = [IsAuthenticated]

    def get(self, request) -> Response:
        """Return ordered period summaries for the authenticated user."""
        reports = ReportService().list_summary(user_id=request.user.id)
        items = []
        prior_aggregates = None
        for report in reports:
            aggregates = report.aggregates or {}
            category_drift = compute_category_drift(
                aggregates.get("category_totals", []),
                prior_aggregates,
            )
            items.append(
                {
                    "statement_id": report.statement_id,
                    "period_start": report.period_start,
                    "period_end": report.period_end,
                    "original_filename": report.statement.original_filename,
                    "income": aggregates.get("income", "0"),
                    "expense": aggregates.get("expense", "0"),
                    "net_cash_flow": aggregates.get("net_cash_flow", "0"),
                    "savings_rate": aggregates.get("savings_rate"),
                    "emi_total": aggregates.get("emi_total", "0"),
                    "subscription_total": aggregates.get("subscription_total", "0"),
                    "emi_burden_pct": compute_emi_burden_pct(
                        aggregates.get("income", "0"),
                        aggregates.get("emi_total", "0"),
                    ),
                    "category_drift": category_drift,
                }
            )
            prior_aggregates = aggregates.get("category_totals", [])
        serializer = ReportSummaryItemSerializer(items, many=True)
        return Response(serializer.data)


class MonthlyMonthsListView(APIView):
    """List calendar months that have transactions."""

    permission_classes = [IsAuthenticated]

    def get(self, request) -> Response:
        """Return available year/month buckets for the user."""
        months = MonthlyReportService().list_available_months(
            user_id=request.user.id,
        )
        return Response(months)


class MonthlySummaryView(APIView):
    """Return aggregates and insights for a calendar month."""

    permission_classes = [IsAuthenticated]

    def get(self, request) -> Response:
        """Return monthly summary for year/month query params."""
        year_param = request.query_params.get("year")
        month_param = request.query_params.get("month")
        if not year_param or not month_param:
            return Response(
                {
                    "error": {
                        "code": "validation_error",
                        "message": "year and month query params are required.",
                    },
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            year = int(year_param)
            month = int(month_param)
            if month < 1 or month > 12:
                raise ValueError
        except ValueError:
            return Response(
                {
                    "error": {
                        "code": "validation_error",
                        "message": "Invalid year or month.",
                    },
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        summary = MonthlyReportService().get_summary(
            request.user.id,
            year=year,
            month=month,
        )
        return Response(summary)


class InsightListView(APIView):
    """List prioritized explainable insights."""

    permission_classes = [IsAuthenticated]

    def get(self, request) -> Response:
        """Return insights, optionally filtered by statement query param."""
        statement_param = request.query_params.get("statement")
        statement_id = int(statement_param) if statement_param else None
        insights = ReportService().list_insights(
            user_id=request.user.id,
            statement_id=statement_id,
        )
        serializer = InsightSerializer(insights, many=True)
        return Response(serializer.data)


class ReportExportView(APIView):
    """Enqueue a CSV or PDF export for a statement report."""

    permission_classes = [IsAuthenticated]

    def post(self, request, statement_id: int) -> Response:
        """Create an export job and enqueue Celery processing."""
        serializer = ExportRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            job = ExportService().create_export_job(
                user_id=request.user.id,
                statement_id=statement_id,
                export_format=serializer.validated_data["format"],
            )
        except DomainValidationError as exc:
            return Response(
                {"error": {"code": "validation_error", "message": str(exc)}},
                status=status.HTTP_400_BAD_REQUEST,
            )

        export_report_task.delay(job.id)
        return Response(
            ExportJobSerializer(job).data,
            status=status.HTTP_202_ACCEPTED,
        )


class ExportJobDetailView(APIView):
    """Poll export job status."""

    permission_classes = [IsAuthenticated]

    def get(self, request, job_id: int) -> Response:
        """Return export job status for the authenticated user."""
        job = ExportService().get_job(user_id=request.user.id, job_id=job_id)
        if job is None:
            return Response(
                {"error": {"code": "not_found", "message": "Export job not found."}},
                status=status.HTTP_404_NOT_FOUND,
            )
        return Response(ExportJobSerializer(job).data)


class ExportJobDownloadView(APIView):
    """Download a completed export file."""

    permission_classes = [IsAuthenticated]

    def get(self, request, job_id: int) -> FileResponse:
        """Stream the export file when the job is completed."""
        job = ExportService().get_job(user_id=request.user.id, job_id=job_id)
        if job is None:
            return Response(
                {"error": {"code": "not_found", "message": "Export job not found."}},
                status=status.HTTP_404_NOT_FOUND,
            )

        if job.status != ExportJob.Status.COMPLETED or not job.file_path:
            return Response(
                {
                    "error": {
                        "code": "not_ready",
                        "message": "Export is not ready for download.",
                    },
                },
                status=status.HTTP_409_CONFLICT,
            )

        export_service = ExportService()
        file_path = export_service.absolute_path(job.file_path)
        content_type = (
            "text/csv"
            if job.export_format == ExportJob.Format.CSV
            else "application/pdf"
        )
        extension = job.export_format
        filename = f"financial-health-report-{job.report.statement_id}.{extension}"
        return FileResponse(
            open(file_path, "rb"),
            content_type=content_type,
            as_attachment=True,
            filename=filename,
        )
