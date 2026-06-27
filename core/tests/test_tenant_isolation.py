"""Tenant isolation tests for user-scoped resources."""

from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

from statements.models import Account

User = get_user_model()


class TenantIsolationTests(APITestCase):
    """Verify users can only access their own tenant-scoped data."""

    def setUp(self) -> None:
        """Create two users with separate accounts and auth tokens."""
        self.user_a = User.objects.create_user(
            email="alice@example.com",
            password="securepass123",
            first_name="Alice",
        )
        self.user_b = User.objects.create_user(
            email="bob@example.com",
            password="securepass123",
            first_name="Bob",
        )
        self.account_a = Account.objects.create(
            user=self.user_a,
            bank_name="HDFC Bank",
            masked_number="XXXX1234",
        )
        self.account_b = Account.objects.create(
            user=self.user_b,
            bank_name="ICICI Bank",
            masked_number="XXXX5678",
        )
        self.token_a = str(RefreshToken.for_user(self.user_a).access_token)
        self.token_b = str(RefreshToken.for_user(self.user_b).access_token)

    def _auth(self, token: str) -> dict[str, str]:
        """Return Authorization header for the given JWT."""
        return {"HTTP_AUTHORIZATION": f"Bearer {token}"}

    def test_user_sees_only_own_accounts_in_list(self) -> None:
        """List endpoint returns only the authenticated user's accounts."""
        url = reverse("account-list-create")
        response = self.client.get(url, **self._auth(self.token_a))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        ids = {item["id"] for item in response.data}
        self.assertEqual(ids, {self.account_a.id})
        self.assertNotIn(self.account_b.id, ids)

    def test_user_cannot_access_other_users_account_detail(self) -> None:
        """Detail endpoint returns 404 for another user's account."""
        url = reverse("account-detail", kwargs={"pk": self.account_b.id})
        response = self.client.get(url, **self._auth(self.token_a))
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_user_cannot_delete_other_users_account(self) -> None:
        """Delete endpoint returns 404 for another user's account."""
        url = reverse("account-detail", kwargs={"pk": self.account_b.id})
        response = self.client.delete(url, **self._auth(self.token_a))
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertTrue(Account.objects.filter(id=self.account_b.id).exists())

    def test_unauthenticated_request_is_rejected(self) -> None:
        """Protected endpoints require authentication."""
        url = reverse("account-list-create")
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_me_endpoint_returns_current_user_only(self) -> None:
        """The /me endpoint returns the authenticated user's profile."""
        url = reverse("me")
        response = self.client.get(url, **self._auth(self.token_b))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["email"], self.user_b.email)
        self.assertNotEqual(response.data["email"], self.user_a.email)

    def test_register_and_login_flow(self) -> None:
        """Registration creates a user and login returns JWT tokens."""
        register_url = reverse("auth-register")
        register_response = self.client.post(
            register_url,
            {
                "email": "carol@example.com",
                "password": "securepass123",
                "first_name": "Carol",
            },
            format="json",
        )
        self.assertEqual(register_response.status_code, status.HTTP_201_CREATED)
        self.assertIn("access", register_response.data)
        self.assertIn("refresh", register_response.data)

        login_url = reverse("auth-login")
        login_response = self.client.post(
            login_url,
            {"email": "carol@example.com", "password": "securepass123"},
            format="json",
        )
        self.assertEqual(login_response.status_code, status.HTTP_200_OK)
        self.assertIn("access", login_response.data)
