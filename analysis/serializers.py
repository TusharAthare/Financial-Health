"""Analysis API serializers."""

from rest_framework import serializers

from analysis.models import ExportJob, Insight, RecurringPattern, Report


class RecurringPatternSerializer(serializers.ModelSerializer):
    """Serialize recurring pattern with evidence."""

    class Meta:
        model = RecurringPattern
        fields = (
            "id",
            "normalized_merchant",
            "pattern_type",
            "cadence",
            "expected_amount",
            "amount_variance_pct",
            "next_expected_date",
            "evidence",
            "is_active",
            "created_at",
            "updated_at",
        )
        read_only_fields = fields


class ReportSerializer(serializers.ModelSerializer):
    """Serialize a statement report snapshot."""

    statement_id = serializers.IntegerField(source="statement.id", read_only=True)
    account_bank_name = serializers.CharField(
        source="statement.account.bank_name",
        read_only=True,
    )
    original_filename = serializers.CharField(
        source="statement.original_filename",
        read_only=True,
    )

    class Meta:
        model = Report
        fields = (
            "id",
            "statement_id",
            "account_bank_name",
            "original_filename",
            "period_start",
            "period_end",
            "aggregates",
            "created_at",
            "updated_at",
        )
        read_only_fields = fields


class ReportSummaryItemSerializer(serializers.Serializer):
    """One period entry for cross-statement progress charts."""

    statement_id = serializers.IntegerField()
    period_start = serializers.DateField(allow_null=True)
    period_end = serializers.DateField(allow_null=True)
    original_filename = serializers.CharField()
    income = serializers.CharField()
    expense = serializers.CharField()
    net_cash_flow = serializers.CharField()
    savings_rate = serializers.FloatField(allow_null=True)
    emi_total = serializers.CharField()
    subscription_total = serializers.CharField()
    emi_burden_pct = serializers.FloatField(allow_null=True)
    category_drift = serializers.ListField(child=serializers.DictField())


class ExportRequestSerializer(serializers.Serializer):
    """Validate report export request."""

    format = serializers.ChoiceField(choices=["csv", "pdf"])


class ExportJobSerializer(serializers.ModelSerializer):
    """Serialize export job status."""

    statement_id = serializers.IntegerField(
        source="report.statement_id",
        read_only=True,
    )

    class Meta:
        model = ExportJob
        fields = (
            "id",
            "statement_id",
            "export_format",
            "status",
            "error_message",
            "created_at",
            "updated_at",
        )
        read_only_fields = fields


class InsightSerializer(serializers.ModelSerializer):
    """Serialize an explainable insight with evidence."""

    statement_id = serializers.IntegerField(source="statement.id", read_only=True)

    class Meta:
        model = Insight
        fields = (
            "id",
            "statement_id",
            "insight_type",
            "priority",
            "title",
            "message",
            "evidence",
            "period_start",
            "period_end",
            "created_at",
        )
        read_only_fields = fields
