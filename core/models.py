"""Custom user model and shared core models."""

from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.db import models


class UserManager(BaseUserManager):
    """Manager for the custom email-based User model."""

    def create_user(self, email: str, password: str | None = None, **extra_fields) -> "User":
        """Create and save a regular user with the given email and password."""
        if not email:
            raise ValueError("Email is required.")
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email: str, password: str | None = None, **extra_fields) -> "User":
        """Create and save a superuser."""
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("is_active", True)

        if extra_fields.get("is_staff") is not True:
            raise ValueError("Superuser must have is_staff=True.")
        if extra_fields.get("is_superuser") is not True:
            raise ValueError("Superuser must have is_superuser=True.")

        return self.create_user(email, password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin):
    """Custom user identified by email."""

    email = models.EmailField(unique=True)
    first_name = models.CharField(max_length=150, blank=True)
    last_name = models.CharField(max_length=150, blank=True)
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = UserManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS: list[str] = []

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        """Return the user's email."""
        return self.email

    @property
    def full_name(self) -> str:
        """Return the user's full name or email."""
        name = f"{self.first_name} {self.last_name}".strip()
        return name or self.email


class AuditLog(models.Model):
    """Immutable audit trail for sensitive user actions."""

    class Action(models.TextChoices):
        UPLOAD = "upload", "Upload"
        DELETE_DATA = "delete_data", "Delete data"
        DELETE_ACCOUNT = "delete_account", "Delete account"
        EXPORT = "export", "Export"

    user = models.ForeignKey(
        "User",
        on_delete=models.CASCADE,
        related_name="audit_logs",
    )
    action = models.CharField(max_length=32, choices=Action.choices)
    target_type = models.CharField(max_length=64, blank=True)
    target_id = models.CharField(max_length=64, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "-created_at"]),
            models.Index(fields=["action", "-created_at"]),
        ]

    def __str__(self) -> str:
        """Return a readable audit entry label."""
        return f"{self.action} user={self.user_id} at {self.created_at}"


class GeminiUsageLog(models.Model):
    """Per-request Gemini API usage and estimated cost."""

    class Action(models.TextChoices):
        TRANSACTION_CATEGORIZE_PARSE = (
            "transaction_categorize_parse",
            "Categorize transactions (statement parse)",
        )
        TRANSACTION_CATEGORIZE_MANUAL = (
            "transaction_categorize_manual",
            "Categorize transactions (manual AI)",
        )

    class Status(models.TextChoices):
        SUCCESS = "success", "Success"
        ERROR = "error", "Error"
        RATE_LIMITED = "rate_limited", "Rate limited"

    user = models.ForeignKey(
        "User",
        on_delete=models.CASCADE,
        related_name="gemini_usage_logs",
    )
    action = models.CharField(max_length=64, choices=Action.choices)
    status = models.CharField(
        max_length=16,
        choices=Status.choices,
        default=Status.SUCCESS,
    )
    model = models.CharField(max_length=128)
    statement = models.ForeignKey(
        "statements.Statement",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="gemini_usage_logs",
    )
    merchants_in_batch = models.PositiveIntegerField(default=0)
    transactions_updated = models.PositiveIntegerField(default=0)
    prompt_token_count = models.PositiveIntegerField(null=True, blank=True)
    candidates_token_count = models.PositiveIntegerField(null=True, blank=True)
    cached_content_token_count = models.PositiveIntegerField(null=True, blank=True)
    thoughts_token_count = models.PositiveIntegerField(null=True, blank=True)
    tool_use_prompt_token_count = models.PositiveIntegerField(null=True, blank=True)
    total_token_count = models.PositiveIntegerField(null=True, blank=True)
    estimated_cost_usd = models.DecimalField(
        max_digits=12,
        decimal_places=8,
        null=True,
        blank=True,
    )
    latency_ms = models.PositiveIntegerField(null=True, blank=True)
    response_id = models.CharField(max_length=128, blank=True, default="")
    model_version = models.CharField(max_length=128, blank=True, default="")
    usage_metadata = models.JSONField(default=dict, blank=True)
    response_metadata = models.JSONField(default=dict, blank=True)
    context = models.JSONField(
        default=dict,
        blank=True,
        help_text="Caller context such as merchant keys and statement ids.",
    )
    error_code = models.CharField(max_length=64, blank=True, default="")
    error_message = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "-created_at"]),
            models.Index(fields=["action", "-created_at"]),
            models.Index(fields=["user", "action", "-created_at"]),
        ]

    def __str__(self) -> str:
        """Return a short label for admin lists."""
        return (
            f"{self.action} user={self.user_id} "
            f"tokens={self.total_token_count or 0} "
            f"${self.estimated_cost_usd or 0}"
        )
