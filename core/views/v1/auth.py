"""Authentication API views."""

from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken

from api.auth import TokenObtainPairView
from core.serializers.auth import RegisterSerializer, UserSerializer
from services.internal.auth import AuthService


class RegisterView(APIView):
    """Register a new user account."""

    permission_classes = [AllowAny]

    def post(self, request) -> Response:
        """Validate input, create user, and return JWT tokens."""
        serializer = RegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user = AuthService().register_user(
            email=serializer.validated_data["email"],
            password=serializer.validated_data["password"],
            first_name=serializer.validated_data.get("first_name", ""),
            last_name=serializer.validated_data.get("last_name", ""),
        )

        refresh = RefreshToken.for_user(user)
        return Response(
            {
                "user": UserSerializer(user).data,
                "access": str(refresh.access_token),
                "refresh": str(refresh),
            },
            status=status.HTTP_201_CREATED,
        )


class LogoutView(APIView):
    """Blacklist the refresh token on logout."""

    permission_classes = [IsAuthenticated]

    def post(self, request) -> Response:
        """Blacklist the provided refresh token."""
        refresh_token = request.data.get("refresh")
        if not refresh_token:
            return Response(
                {"error": {"code": "validation_error", "message": "Refresh token is required."}},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            token = RefreshToken(refresh_token)
            token.blacklist()
        except Exception:
            return Response(
                {"error": {"code": "validation_error", "message": "Invalid refresh token."}},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response(status=status.HTTP_204_NO_CONTENT)


__all__ = ["RegisterView", "LogoutView", "TokenObtainPairView"]
