"""Authentication and user registration services."""

from django.contrib.auth import get_user_model
from django.db import transaction

from services.domain.exceptions import DomainValidationError

User = get_user_model()


class AuthService:
    """Handle user registration and related auth flows."""

    @transaction.atomic
    def register_user(self, email: str, password: str, first_name: str = "", last_name: str = "") -> User:
        """
        Create a new user account.

        Raises DomainValidationError if the email is already registered.
        """
        normalized_email = email.strip().lower()
        if User.objects.filter(email=normalized_email).exists():
            raise DomainValidationError("A user with this email already exists.")

        user = User.objects.create_user(
            email=normalized_email,
            password=password,
            first_name=first_name.strip(),
            last_name=last_name.strip(),
        )
        return user
