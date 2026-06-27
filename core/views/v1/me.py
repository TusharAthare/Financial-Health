"""Current-user API views."""

from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from core.serializers.auth import UserSerializer


class MeView(APIView):
    """Return the authenticated user's profile."""

    permission_classes = [IsAuthenticated]

    def get(self, request) -> Response:
        """Serialize and return the current user."""
        return Response(UserSerializer(request.user).data)
