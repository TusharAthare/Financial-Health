"""Account API views."""

from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from api.permissions import IsOwner
from services.internal.account import AccountService
from statements.serializers.accounts import AccountCreateSerializer, AccountSerializer


class AccountListCreateView(APIView):
    """List and create tenant-scoped bank accounts."""

    permission_classes = [IsAuthenticated]

    def get(self, request) -> Response:
        """Return accounts belonging to the authenticated user."""
        accounts = AccountService().list_accounts(user_id=request.user.id)
        return Response(AccountSerializer(accounts, many=True).data)

    def post(self, request) -> Response:
        """Create a new account for the authenticated user."""
        serializer = AccountCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        account = AccountService().create_account(
            user_id=request.user.id,
            **serializer.validated_data,
        )
        return Response(AccountSerializer(account).data, status=status.HTTP_201_CREATED)


class AccountDetailView(APIView):
    """Retrieve or delete a single tenant-scoped account."""

    permission_classes = [IsAuthenticated, IsOwner]

    def get(self, request, pk: int) -> Response:
        """Return a single account if owned by the user."""
        account = AccountService().get_account(user_id=request.user.id, account_id=pk)
        if account is None:
            return Response(
                {"error": {"code": "not_found", "message": "Account not found."}},
                status=status.HTTP_404_NOT_FOUND,
            )
        self.check_object_permissions(request, account)
        return Response(AccountSerializer(account).data)

    def delete(self, request, pk: int) -> Response:
        """Delete an account owned by the user."""
        account = AccountService().get_account(user_id=request.user.id, account_id=pk)
        if account is None:
            return Response(
                {"error": {"code": "not_found", "message": "Account not found."}},
                status=status.HTTP_404_NOT_FOUND,
            )
        self.check_object_permissions(request, account)
        AccountService().delete_account(user_id=request.user.id, account_id=pk)
        return Response(status=status.HTTP_204_NO_CONTENT)
