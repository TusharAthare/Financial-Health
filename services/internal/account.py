"""Account management services with tenant scoping."""

from django.contrib.auth import get_user_model
from django.db import transaction

from services.domain.exceptions import DomainPermissionDenied, DomainValidationError
from services.internal.audit import AuditService
from statements.models import Account

User = get_user_model()


class AccountService:
    """CRUD operations for user-scoped bank accounts."""

    def list_accounts(self, user_id: int) -> list[Account]:
        """Return all accounts belonging to the given user."""
        return list(Account.objects.filter(user_id=user_id).order_by("-created_at"))

    def get_account(self, user_id: int, account_id: int) -> Account | None:
        """Return an account if it belongs to the user, else None."""
        return Account.objects.filter(id=account_id, user_id=user_id).first()

    @transaction.atomic
    def create_account(
        self,
        user_id: int,
        bank_name: str,
        masked_number: str,
        currency: str = "INR",
    ) -> Account:
        """
        Create a bank account for the user.

        Raises DomainValidationError when required fields are missing.
        """
        if not bank_name.strip():
            raise DomainValidationError("Bank name is required.")
        if not masked_number.strip():
            raise DomainValidationError("Masked account number is required.")

        user = User.objects.filter(id=user_id).first()
        if user is None:
            raise DomainValidationError("User not found.")

        return Account.objects.create(
            user=user,
            bank_name=bank_name.strip(),
            masked_number=masked_number.strip(),
            currency=currency.strip().upper() or "INR",
        )

    @transaction.atomic
    def delete_account(self, user_id: int, account_id: int) -> None:
        """
        Delete an account owned by the user.

        Raises DomainPermissionDenied when the account does not belong to the user.
        """
        account = self.get_account(user_id, account_id)
        if account is None:
            raise DomainPermissionDenied("Account not found or access denied.")
        AuditService().log(
            user_id,
            "delete_account",
            target_type="account",
            target_id=str(account_id),
            metadata={"bank_name": account.bank_name},
        )
        account.delete()
