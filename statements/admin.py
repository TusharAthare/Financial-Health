"""Admin registration for statement models."""

from django.contrib import admin
from django.utils.html import format_html

from statements.models import Account, Category, CategoryRule, Statement, Transaction


class TransactionInline(admin.TabularInline):
    """Compact transaction list on a statement detail page."""

    model = Transaction
    extra = 0
    can_delete = False
    show_change_link = True
    fields = (
        "transaction_date",
        "amount",
        "normalized_merchant",
        "category",
        "is_recurring",
    )
    readonly_fields = fields
    raw_id_fields = ("category",)
    ordering = ("-transaction_date",)
    max_num = 25

    def has_add_permission(self, request, obj=None) -> bool:
        """Transactions are created by the parse pipeline."""
        return False


@admin.register(Account)
class AccountAdmin(admin.ModelAdmin):
    """Admin interface for bank accounts."""

    list_display = (
        "bank_name",
        "masked_number",
        "user",
        "currency",
        "statement_count",
        "created_at",
    )
    list_filter = ("currency", "created_at")
    search_fields = ("bank_name", "masked_number", "user__email")
    raw_id_fields = ("user",)
    readonly_fields = ("created_at", "updated_at")
    ordering = ("-created_at",)

    @admin.display(description="Statements")
    def statement_count(self, obj: Account) -> int:
        """Return the number of statements for this account."""
        return obj.statements.count()


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    """Admin interface for transaction categories."""

    list_display = ("name", "slug", "scope_display", "user", "parent", "created_at")
    list_filter = ("parent", "created_at")
    search_fields = ("name", "slug", "user__email")
    raw_id_fields = ("user", "parent")
    readonly_fields = ("created_at",)
    ordering = ("name",)

    @admin.display(description="Scope", ordering="user")
    def scope_display(self, obj: Category) -> str:
        """Return whether the category is system-wide or user-owned."""
        return "System" if obj.user_id is None else "User"


@admin.register(Statement)
class StatementAdmin(admin.ModelAdmin):
    """Admin interface for uploaded statements."""

    list_display = (
        "original_filename",
        "user",
        "account",
        "status_badge",
        "file_format",
        "period_start",
        "period_end",
        "transaction_count",
        "created_at",
    )
    list_filter = ("status", "file_format", "created_at")
    search_fields = (
        "original_filename",
        "checksum",
        "user__email",
        "account__bank_name",
        "error_message",
    )
    raw_id_fields = ("user", "account")
    readonly_fields = (
        "checksum",
        "transaction_count",
        "source_file",
        "created_at",
        "updated_at",
    )
    date_hierarchy = "created_at"
    inlines = (TransactionInline,)
    ordering = ("-created_at",)

    @admin.display(description="Status", ordering="status")
    def status_badge(self, obj: Statement) -> str:
        """Render statement status with a simple color cue."""
        colors = {
            Statement.Status.PARSED: "#166534",
            Statement.Status.FAILED: "#b91c1c",
            Statement.Status.PARSING: "#b45309",
            Statement.Status.UPLOADED: "#475569",
        }
        color = colors.get(obj.status, "#475569")
        return format_html(
            '<span style="color:{}; font-weight:600;">{}</span>',
            color,
            obj.get_status_display(),
        )


@admin.register(CategoryRule)
class CategoryRuleAdmin(admin.ModelAdmin):
    """Admin interface for categorization rules."""

    list_display = (
        "pattern",
        "category",
        "rule_type",
        "priority",
        "is_active",
        "scope_display",
        "user",
        "updated_at",
    )
    list_filter = ("rule_type", "is_active", "category", "created_at")
    search_fields = ("pattern", "category__name", "category__slug", "user__email")
    raw_id_fields = ("user", "category")
    readonly_fields = ("created_at", "updated_at")
    ordering = ("priority", "id")

    @admin.display(description="Scope", ordering="user")
    def scope_display(self, obj: CategoryRule) -> str:
        """Return whether the rule is system-wide or user-learned."""
        return "System" if obj.user_id is None else "User"


@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    """Admin interface for normalized transactions."""

    list_display = (
        "transaction_date",
        "amount_display",
        "normalized_merchant",
        "category",
        "user",
        "statement",
        "is_recurring",
    )
    list_filter = (
        "category",
        "is_recurring",
        ("transaction_date", admin.DateFieldListFilter),
        "created_at",
    )
    search_fields = (
        "raw_description",
        "normalized_merchant",
        "user__email",
        "statement__original_filename",
    )
    raw_id_fields = (
        "user",
        "account",
        "statement",
        "category",
        "matched_rule",
        "recurring_pattern",
    )
    readonly_fields = ("created_at",)
    date_hierarchy = "transaction_date"
    list_select_related = ("category", "user", "statement", "account")
    ordering = ("-transaction_date", "-id")
    list_per_page = 50

    fieldsets = (
        (
            "Transaction",
            {
                "fields": (
                    "user",
                    "account",
                    "statement",
                    "transaction_date",
                    "amount",
                    "balance",
                ),
            },
        ),
        (
            "Description",
            {
                "fields": ("raw_description", "normalized_merchant"),
            },
        ),
        (
            "Categorization",
            {
                "fields": (
                    "category",
                    "matched_rule",
                    "categorization_evidence",
                    "is_recurring",
                    "recurring_pattern",
                ),
            },
        ),
        ("Meta", {"fields": ("created_at",)}),
    )

    @admin.display(description="Amount", ordering="amount")
    def amount_display(self, obj: Transaction) -> str:
        """Color debit amounts red and credits green."""
        if obj.amount < 0:
            return format_html('<span style="color:#b91c1c;">{}</span>', obj.amount)
        return format_html('<span style="color:#166534;">{}</span>', obj.amount)
