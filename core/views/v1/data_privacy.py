"""Delete-my-data and audit log API views."""

from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from core.serializers.auth import AuditLogSerializer, DeleteDataSerializer
from services.internal.audit import AuditService
from services.internal.user_data import UserDataService


class DeleteMyDataView(APIView):
    """Hard-delete all financial data for the authenticated user."""

    permission_classes = [IsAuthenticated]

    def delete(self, request) -> Response:
        """Delete all tenant data after confirmation."""
        serializer = DeleteDataSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        counts = UserDataService().delete_all_data(user_id=request.user.id)
        return Response(
            {
                "message": "All financial data has been permanently deleted.",
                "deleted": counts,
            },
            status=status.HTTP_200_OK,
        )


class AuditLogListView(APIView):
    """List recent audit log entries for the authenticated user."""

    permission_classes = [IsAuthenticated]

    def get(self, request) -> Response:
        """Return the user's recent audit events."""
        limit = min(int(request.query_params.get("limit", 50)), 100)
        entries = AuditService().list_for_user(user_id=request.user.id, limit=limit)
        serializer = AuditLogSerializer(entries, many=True)
        return Response(serializer.data)
