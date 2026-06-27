"""Custom JWT authentication helpers."""

from django.contrib.auth import get_user_model
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework_simplejwt.views import TokenObtainPairView as BaseTokenObtainPairView

User = get_user_model()


class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    """Extend JWT payload with user id and email."""

    username_field = User.USERNAME_FIELD

    @classmethod
    def get_token(cls, user):
        """Add custom claims to the refresh token."""
        token = super().get_token(user)
        token["email"] = user.email
        return token


class TokenObtainPairView(BaseTokenObtainPairView):
    """Login view using the custom JWT serializer."""

    serializer_class = CustomTokenObtainPairSerializer
