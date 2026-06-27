"""Analysis models for recurring detection, reports, and insights."""

from django.conf import settings
from django.db import models


class Report(models.Model):
    """Financial report snapshot for a parsed statement period."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="reports",
    )
    statement = models.OneToOneField(
        "statements.Statement",
        on_delete=models.CASCADE,
        related_name="report",
    )
    period_start = models.DateField(null=True, blank=True)
    period_end = models.DateField(null=True, blank=True)
    aggregates = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-period_end", "-id"]
        indexes = [
            models.Index(fields=["user", "-period_end"]),
        ]

    def __str__(self) -> str:
        """Return a readable report label."""
        return f"Report statement={self.statement_id}"


class Insight(models.Model):
    """Explainable leak, saving, or suggestion insight."""

    class InsightType(models.TextChoices):
        LEAK = "leak", "Leak"
        SAVING = "saving", "Saving"
        SUGGESTION = "suggestion", "Suggestion"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="insights",
    )
    report = models.ForeignKey(
        Report,
        on_delete=models.CASCADE,
        related_name="insights",
    )
    statement = models.ForeignKey(
        "statements.Statement",
        on_delete=models.CASCADE,
        related_name="insights",
    )
    insight_type = models.CharField(max_length=16, choices=InsightType.choices)
    priority = models.PositiveIntegerField(
        default=100,
        help_text="Lower number = higher priority.",
    )
    title = models.CharField(max_length=255)
    message = models.TextField()
    evidence = models.JSONField(default=dict, blank=True)
    period_start = models.DateField(null=True, blank=True)
    period_end = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["priority", "id"]
        indexes = [
            models.Index(fields=["user", "priority"]),
            models.Index(fields=["user", "statement"]),
        ]

    def __str__(self) -> str:
        """Return insight title."""
        return self.title


class RecurringPattern(models.Model):
    """Detected recurring debit pattern (subscription, autopay, EMI)."""

    class PatternType(models.TextChoices):
        SUBSCRIPTION = "subscription", "Subscription"
        AUTOPAY = "autopay", "Autopay"
        EMI = "emi", "EMI"
        LOAN = "loan", "Loan"

    class Cadence(models.TextChoices):
        WEEKLY = "weekly", "Weekly"
        BIWEEKLY = "biweekly", "Bi-weekly"
        MONTHLY = "monthly", "Monthly"
        QUARTERLY = "quarterly", "Quarterly"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="recurring_patterns",
    )
    normalized_merchant = models.CharField(max_length=512)
    pattern_type = models.CharField(max_length=16, choices=PatternType.choices)
    cadence = models.CharField(max_length=16, choices=Cadence.choices)
    expected_amount = models.DecimalField(max_digits=14, decimal_places=2)
    amount_variance_pct = models.FloatField(
        default=0.0,
        help_text="Percent deviation of amounts from the mean.",
    )
    next_expected_date = models.DateField(null=True, blank=True)
    evidence = models.JSONField(default=dict, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["normalized_merchant"]
        indexes = [
            models.Index(fields=["user", "is_active"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["user", "normalized_merchant", "pattern_type"],
                name="unique_user_merchant_pattern_type",
            ),
        ]

    def __str__(self) -> str:
        """Return a readable pattern label."""
        return f"{self.normalized_merchant} ({self.pattern_type}, {self.cadence})"


class ExportJob(models.Model):
    """Async report export job (CSV or PDF)."""

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        PROCESSING = "processing", "Processing"
        COMPLETED = "completed", "Completed"
        FAILED = "failed", "Failed"

    class Format(models.TextChoices):
        CSV = "csv", "CSV"
        PDF = "pdf", "PDF"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="export_jobs",
    )
    report = models.ForeignKey(
        Report,
        on_delete=models.CASCADE,
        related_name="export_jobs",
    )
    export_format = models.CharField(max_length=8, choices=Format.choices)
    status = models.CharField(
        max_length=16,
        choices=Status.choices,
        default=Status.PENDING,
    )
    file_path = models.CharField(max_length=512, blank=True)
    error_message = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "-created_at"]),
            models.Index(fields=["user", "status"]),
        ]

    def __str__(self) -> str:
        """Return a readable export job label."""
        return f"ExportJob {self.id} ({self.export_format}, {self.status})"
