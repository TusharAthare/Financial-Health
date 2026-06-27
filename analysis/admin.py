"""Admin registration for analysis models."""

from django.contrib import admin

from analysis.models import ExportJob, Insight, RecurringPattern, Report


class InsightInline(admin.TabularInline):
    """Insights attached to a report snapshot."""

    model = Insight
    extra = 0
    fields = ("priority", "insight_type", "title", "message")
    ordering = ("priority", "id")
    show_change_link = True


class ExportJobInline(admin.TabularInline):
    """Export jobs for a report."""

    model = ExportJob
    extra = 0
    fields = ("export_format", "status", "file_path", "created_at")
    readonly_fields = ("created_at",)
    show_change_link = True
    can_delete = False


@admin.register(Report)
class ReportAdmin(admin.ModelAdmin):
    """Admin interface for statement report snapshots."""

    list_display = (
        "id",
        "statement",
        "user",
        "period_start",
        "period_end",
        "income_display",
        "expense_display",
        "created_at",
    )
    list_filter = ("created_at", "period_start", "period_end")
    search_fields = (
        "user__email",
        "statement__original_filename",
    )
    raw_id_fields = ("user", "statement")
    readonly_fields = ("aggregates", "created_at", "updated_at")
    inlines = (InsightInline, ExportJobInline)
    date_hierarchy = "period_end"
    ordering = ("-period_end", "-id")

    @admin.display(description="Income")
    def income_display(self, obj: Report) -> str:
        """Show income from stored aggregates."""
        return obj.aggregates.get("income", "—") if obj.aggregates else "—"

    @admin.display(description="Expense")
    def expense_display(self, obj: Report) -> str:
        """Show expense from stored aggregates."""
        return obj.aggregates.get("expense", "—") if obj.aggregates else "—"


@admin.register(Insight)
class InsightAdmin(admin.ModelAdmin):
    """Admin interface for explainable insights."""

    list_display = (
        "title",
        "insight_type",
        "priority",
        "user",
        "statement",
        "period_start",
        "period_end",
        "created_at",
    )
    list_filter = ("insight_type", "priority", "created_at")
    search_fields = ("title", "message", "user__email", "statement__original_filename")
    raw_id_fields = ("user", "report", "statement")
    readonly_fields = ("created_at",)
    ordering = ("priority", "id")


@admin.register(RecurringPattern)
class RecurringPatternAdmin(admin.ModelAdmin):
    """Admin interface for detected recurring debits."""

    list_display = (
        "normalized_merchant",
        "pattern_type",
        "cadence",
        "expected_amount",
        "user",
        "is_active",
        "next_expected_date",
        "updated_at",
    )
    list_filter = ("pattern_type", "cadence", "is_active", "created_at")
    search_fields = ("normalized_merchant", "user__email")
    raw_id_fields = ("user",)
    readonly_fields = ("created_at", "updated_at")
    ordering = ("normalized_merchant",)


@admin.register(ExportJob)
class ExportJobAdmin(admin.ModelAdmin):
    """Admin interface for async report exports."""

    list_display = (
        "id",
        "user",
        "report",
        "export_format",
        "status",
        "file_path",
        "created_at",
        "updated_at",
    )
    list_filter = ("status", "export_format", "created_at")
    search_fields = ("user__email", "file_path", "error_message")
    raw_id_fields = ("user", "report")
    readonly_fields = ("created_at", "updated_at")
    ordering = ("-created_at",)
