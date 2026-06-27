"""Authentication serializers."""

from django.contrib.auth import get_user_model
from rest_framework import serializers

from core.models import AuditLog

User = get_user_model()

DELETE_CONFIRMATION_PHRASE = "DELETE_MY_DATA"


class RegisterSerializer(serializers.Serializer):
    """Validate registration input."""

    email = serializers.EmailField()
    password = serializers.CharField(min_length=8, write_only=True)
    first_name = serializers.CharField(required=False, allow_blank=True, max_length=150)
    last_name = serializers.CharField(required=False, allow_blank=True, max_length=150)

    def validate_email(self, value: str) -> str:
        """Normalize email to lowercase."""
        return value.strip().lower()


class UserSerializer(serializers.ModelSerializer):
    """Serialize user profile fields."""

    full_name = serializers.CharField(read_only=True)

    class Meta:
        model = User
        fields = ("id", "email", "first_name", "last_name", "full_name", "created_at")
        read_only_fields = fields


class DeleteDataSerializer(serializers.Serializer):
    """Validate delete-my-data confirmation."""

    confirmation = serializers.CharField()

    def validate_confirmation(self, value: str) -> str:
        """Require the exact confirmation phrase."""
        if value != DELETE_CONFIRMATION_PHRASE:
            raise serializers.ValidationError(
                f"Type '{DELETE_CONFIRMATION_PHRASE}' to confirm deletion.",
            )
        return value


class AuditLogSerializer(serializers.ModelSerializer):
    """Serialize audit log entries."""

    class Meta:
        model = AuditLog
        fields = (
            "id",
            "action",
            "target_type",
            "target_id",
            "metadata",
            "created_at",
        )
        read_only_fields = fields
