"""Statement and transaction serializers."""

from rest_framework import serializers

from statements.models import Category, CategoryRule, Statement, Transaction


class CategorySerializer(serializers.ModelSerializer):
    """Serialize category fields."""

    class Meta:
        model = Category
        fields = ("id", "name", "slug")
        read_only_fields = fields


class CategoryRuleSummarySerializer(serializers.ModelSerializer):
    """Minimal rule info for transaction categorization evidence."""

    class Meta:
        model = CategoryRule
        fields = ("id", "pattern", "rule_type", "priority")
        read_only_fields = fields


class StatementSerializer(serializers.ModelSerializer):
    """Serialize statement fields for API responses."""

    account_id = serializers.IntegerField(source="account.id", read_only=True)
    account_bank_name = serializers.CharField(source="account.bank_name", read_only=True)

    class Meta:
        model = Statement
        fields = (
            "id",
            "account_id",
            "account_bank_name",
            "period_start",
            "period_end",
            "original_filename",
            "file_format",
            "status",
            "checksum",
            "error_message",
            "transaction_count",
            "created_at",
            "updated_at",
        )
        read_only_fields = fields


class StatementUploadSerializer(serializers.Serializer):
    """Validate multipart statement upload input."""

    account_id = serializers.IntegerField()
    file = serializers.FileField()
    pdf_password = serializers.CharField(
        required=False,
        allow_blank=True,
        max_length=128,
        write_only=True,
    )


class TransactionSerializer(serializers.ModelSerializer):
    """Serialize transaction fields with nested category and evidence."""

    category = CategorySerializer(read_only=True)
    matched_rule = CategoryRuleSummarySerializer(read_only=True)
    account_id = serializers.IntegerField(source="account.id", read_only=True)
    statement_id = serializers.IntegerField(source="statement.id", read_only=True)

    class Meta:
        model = Transaction
        fields = (
            "id",
            "account_id",
            "statement_id",
            "transaction_date",
            "amount",
            "raw_description",
            "normalized_merchant",
            "balance",
            "category",
            "matched_rule",
            "categorization_evidence",
            "is_recurring",
            "created_at",
        )
        read_only_fields = fields


class TransactionCategoryUpdateSerializer(serializers.Serializer):
    """Validate manual category override input."""

    category_id = serializers.IntegerField()
