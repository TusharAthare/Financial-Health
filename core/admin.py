"""Admin registration for core models."""

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.utils.html import format_html

from core.models import AuditLog, GeminiUsageLog, User


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    """Admin interface for the custom email-based User model."""

    ordering = ("email",)
    list_display = (
        "email",
        "full_name_display",
        "is_staff",
        "is_superuser",
        "is_active",
        "created_at",
    )
    list_filter = ("is_staff", "is_superuser", "is_active", "created_at")
    search_fields = ("email", "first_name", "last_name")
    date_hierarchy = "created_at"
    readonly_fields = ("created_at", "updated_at", "last_login")

    fieldsets = (
        (None, {"fields": ("email", "password")}),
        ("Personal info", {"fields": ("first_name", "last_name")}),
        (
            "Permissions",
            {"fields": ("is_active", "is_staff", "is_superuser", "groups", "user_permissions")},
        ),
        ("Important dates", {"fields": ("last_login", "created_at", "updated_at")}),
    )

    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": ("email", "password1", "password2", "is_staff", "is_superuser"),
            },
        ),
    )

    @admin.display(description="Name")
    def full_name_display(self, obj: User) -> str:
        """Return the user's display name."""
        return obj.full_name


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    """Read-only audit trail for sensitive actions."""

    list_display = ("created_at", "action", "user", "target_type", "target_id")
    list_filter = ("action", "created_at")
    search_fields = ("user__email", "target_type", "target_id")
    readonly_fields = (
        "user",
        "action",
        "target_type",
        "target_id",
        "metadata",
        "created_at",
    )
    raw_id_fields = ("user",)
    date_hierarchy = "created_at"
    ordering = ("-created_at",)

    def has_add_permission(self, request) -> bool:
        """Audit logs are created by the application only."""
        return False

    def has_change_permission(self, request, obj=None) -> bool:
        """Audit logs are immutable."""
        return False

    def has_delete_permission(self, request, obj=None) -> bool:
        """Allow superusers to purge old audit rows if needed."""
        return request.user.is_superuser


@admin.register(GeminiUsageLog)
class GeminiUsageLogAdmin(admin.ModelAdmin):
    """Read-focused admin for Gemini API usage and cost tracking."""

    list_display = (
        "created_at",
        "user",
        "action",
        "status",
        "model",
        "total_token_count",
        "estimated_cost_display",
        "merchants_in_batch",
        "transactions_updated",
        "latency_ms",
    )
    list_filter = ("action", "status", "model", "created_at")
    search_fields = ("user__email", "response_id", "error_message", "model_version")
    raw_id_fields = ("user", "statement")
    readonly_fields = (
        "user",
        "action",
        "status",
        "model",
        "statement",
        "merchants_in_batch",
        "transactions_updated",
        "prompt_token_count",
        "candidates_token_count",
        "cached_content_token_count",
        "thoughts_token_count",
        "tool_use_prompt_token_count",
        "total_token_count",
        "estimated_cost_usd",
        "latency_ms",
        "response_id",
        "model_version",
        "usage_metadata",
        "response_metadata",
        "context",
        "error_code",
        "error_message",
        "created_at",
    )
    date_hierarchy = "created_at"
    ordering = ("-created_at",)

    def has_add_permission(self, request) -> bool:
        """Usage rows are created by the application."""
        return False

    def has_change_permission(self, request, obj=None) -> bool:
        """Usage logs are immutable."""
        return False

    @admin.display(description="Est. cost (USD)", ordering="estimated_cost_usd")
    def estimated_cost_display(self, obj: GeminiUsageLog) -> str:
        """Format estimated cost for the list view."""
        if obj.estimated_cost_usd is None:
            return "—"
        return f"${obj.estimated_cost_usd:.6f}"


admin.site.site_header = "Financial Health Administration"
admin.site.site_title = "Financial Health"
admin.site.index_title = "Manage users, statements, and analysis data"
