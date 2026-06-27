"""Statement, transaction, and account models."""

from django.conf import settings
from django.db import models


class Account(models.Model):
    """User-owned bank account (tenant-scoped)."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="accounts",
    )
    bank_name = models.CharField(max_length=255)
    masked_number = models.CharField(max_length=32)
    currency = models.CharField(max_length=3, default="INR")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "-created_at"]),
        ]

    def __str__(self) -> str:
        """Return a readable account label."""
        return f"{self.bank_name} ({self.masked_number})"


class Category(models.Model):
    """System default or user-defined transaction category."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="categories",
        null=True,
        blank=True,
    )
    name = models.CharField(max_length=128)
    slug = models.SlugField(max_length=128)
    parent = models.ForeignKey(
        "self",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="children",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(
                fields=["slug"],
                condition=models.Q(user__isnull=True),
                name="unique_system_category_slug",
            ),
            models.UniqueConstraint(
                fields=["user", "slug"],
                condition=models.Q(user__isnull=False),
                name="unique_user_category_slug",
            ),
        ]
        verbose_name_plural = "categories"

    def __str__(self) -> str:
        """Return category name."""
        return self.name


class Statement(models.Model):
    """Uploaded bank statement with parse lifecycle."""

    class Status(models.TextChoices):
        UPLOADED = "uploaded", "Uploaded"
        PARSING = "parsing", "Parsing"
        PARSED = "parsed", "Parsed"
        FAILED = "failed", "Failed"

    class FileFormat(models.TextChoices):
        CSV = "csv", "CSV"
        PDF = "pdf", "PDF"
        XLS = "xls", "XLS"
        XLSX = "xlsx", "XLSX"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="statements",
    )
    account = models.ForeignKey(
        Account,
        on_delete=models.CASCADE,
        related_name="statements",
    )
    period_start = models.DateField(null=True, blank=True)
    period_end = models.DateField(null=True, blank=True)
    source_file = models.CharField(max_length=512)
    original_filename = models.CharField(max_length=255)
    file_format = models.CharField(max_length=8, choices=FileFormat.choices)
    status = models.CharField(
        max_length=16,
        choices=Status.choices,
        default=Status.UPLOADED,
    )
    checksum = models.CharField(max_length=64, db_index=True)
    error_message = models.TextField(blank=True, default="")
    transaction_count = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "-created_at"]),
            models.Index(fields=["user", "status"]),
        ]

    def __str__(self) -> str:
        """Return a readable statement label."""
        return f"{self.original_filename} ({self.status})"


class CategoryRule(models.Model):
    """Pattern-based categorization rule (system or user-scoped)."""

    class RuleType(models.TextChoices):
        MERCHANT_CONTAINS = "merchant_contains", "Merchant contains"
        KEYWORD = "keyword", "Keyword in description"
        REGEX = "regex", "Regular expression"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="category_rules",
        null=True,
        blank=True,
    )
    category = models.ForeignKey(
        Category,
        on_delete=models.CASCADE,
        related_name="rules",
    )
    pattern = models.CharField(max_length=512)
    rule_type = models.CharField(
        max_length=32,
        choices=RuleType.choices,
        default=RuleType.MERCHANT_CONTAINS,
    )
    priority = models.PositiveIntegerField(
        default=100,
        help_text="Lower number = higher priority when matching.",
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["priority", "id"]
        indexes = [
            models.Index(fields=["user", "is_active", "priority"]),
        ]

    def __str__(self) -> str:
        """Return a readable rule label."""
        scope = "user" if self.user_id else "system"
        return f"[{scope}] {self.pattern} → {self.category.name}"


class Transaction(models.Model):
    """Normalized bank transaction (tenant-scoped, dedupe-enforced)."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="transactions",
    )
    account = models.ForeignKey(
        Account,
        on_delete=models.CASCADE,
        related_name="transactions",
    )
    statement = models.ForeignKey(
        Statement,
        on_delete=models.CASCADE,
        related_name="transactions",
    )
    category = models.ForeignKey(
        Category,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="transactions",
    )
    matched_rule = models.ForeignKey(
        CategoryRule,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="matched_transactions",
    )
    categorization_evidence = models.JSONField(default=dict, blank=True)
    transaction_date = models.DateField()
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    raw_description = models.TextField()
    normalized_merchant = models.CharField(max_length=512, blank=True, default="")
    balance = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    is_recurring = models.BooleanField(default=False)
    recurring_pattern = models.ForeignKey(
        "analysis.RecurringPattern",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="transactions",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-transaction_date", "-id"]
        indexes = [
            models.Index(fields=["user", "-transaction_date"]),
            models.Index(fields=["user", "statement"]),
            models.Index(fields=["user", "category"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=[
                    "user",
                    "account",
                    "transaction_date",
                    "amount",
                    "raw_description",
                ],
                name="unique_transaction_dedupe",
            ),
        ]

    def __str__(self) -> str:
        """Return a short transaction label."""
        return f"{self.transaction_date} {self.amount} {self.normalized_merchant[:40]}"
