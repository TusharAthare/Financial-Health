"""Account serializers."""

from rest_framework import serializers

from statements.models import Account


class AccountSerializer(serializers.ModelSerializer):
    """Serialize account fields for API responses."""

    class Meta:
        model = Account
        fields = ("id", "bank_name", "masked_number", "currency", "created_at", "updated_at")
        read_only_fields = fields


class AccountCreateSerializer(serializers.Serializer):
    """Validate account creation input."""

    bank_name = serializers.CharField(max_length=255)
    masked_number = serializers.CharField(max_length=32)
    currency = serializers.CharField(max_length=3, required=False, default="INR")
