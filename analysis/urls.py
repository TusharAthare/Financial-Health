"""Analysis API URL routes."""

from django.urls import path

from analysis.views import (
    ExportJobDetailView,
    ExportJobDownloadView,
    InsightListView,
    MonthlyMonthsListView,
    MonthlySummaryView,
    RecurringPatternListView,
    ReportDetailView,
    ReportExportView,
    ReportSummaryView,
)

urlpatterns = [
    path("recurring/", RecurringPatternListView.as_view(), name="recurring-list"),
    path(
        "reports/months/",
        MonthlyMonthsListView.as_view(),
        name="monthly-months",
    ),
    path(
        "reports/monthly/",
        MonthlySummaryView.as_view(),
        name="monthly-summary",
    ),
    path(
        "reports/summary/",
        ReportSummaryView.as_view(),
        name="report-summary",
    ),
    path(
        "reports/<int:statement_id>/",
        ReportDetailView.as_view(),
        name="report-detail",
    ),
    path(
        "reports/<int:statement_id>/export/",
        ReportExportView.as_view(),
        name="report-export",
    ),
    path(
        "exports/<int:job_id>/",
        ExportJobDetailView.as_view(),
        name="export-job-detail",
    ),
    path(
        "exports/<int:job_id>/download/",
        ExportJobDownloadView.as_view(),
        name="export-job-download",
    ),
    path("insights/", InsightListView.as_view(), name="insight-list"),
]
