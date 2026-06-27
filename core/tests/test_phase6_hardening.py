"""Phase 6 hardening tests: delete-my-data, audit, export, quotas."""

import io
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase, override_settings
from rest_framework_simplejwt.tokens import RefreshToken

from analysis.models import ExportJob, Insight, RecurringPattern, Report
from core.models import AuditLog
from statements.models import Account, Category, CategoryRule, Statement, Transaction

User = get_user_model()


class Phase6HardeningTests(APITestCase):
    """Verify delete-my-data, audit log, export, and quota enforcement."""

    def setUp(self) -> None:
        """Create a user with sample financial data."""
        self.user = User.objects.create_user(
            email="phase6@example.com",
            password="securepass123",
            first_name="Phase",
        )
        self.other = User.objects.create_user(
            email="other@example.com",
            password="securepass123",
        )
        self.token = str(RefreshToken.for_user(self.user).access_token)
        self.other_token = str(RefreshToken.for_user(self.other).access_token)

        self.account = Account.objects.create(
            user=self.user,
            bank_name="HDFC Bank",
            masked_number="XXXX9999",
        )
        self.statement = Statement.objects.create(
            user=self.user,
            account=self.account,
            source_file="",
            original_filename="sample.csv",
            file_format=Statement.FileFormat.CSV,
            status=Statement.Status.PARSED,
            checksum="abc123",
            transaction_count=1,
        )
        category = Category.objects.filter(user__isnull=True, slug="uncategorized").first()
        Transaction.objects.create(
            user=self.user,
            account=self.account,
            statement=self.statement,
            category=category,
            transaction_date="2025-01-15",
            amount=Decimal("-500.00"),
            raw_description="Test txn",
            normalized_merchant="Test Merchant",
        )
        self.report = Report.objects.create(
            user=self.user,
            statement=self.statement,
            period_start="2025-01-01",
            period_end="2025-01-31",
            aggregates={
                "income": "50000",
                "expense": "30000",
                "net_cash_flow": "20000",
                "savings_rate": 40.0,
                "transaction_count": 1,
                "category_totals": [],
                "emi_total": "5000",
                "subscription_total": "500",
                "recurring_debit_total": "5500",
            },
        )
        Insight.objects.create(
            user=self.user,
            report=self.report,
            statement=self.statement,
            insight_type=Insight.InsightType.SAVING,
            priority=10,
            title="Good savings",
            message="Savings rate is healthy.",
            evidence={},
        )
        RecurringPattern.objects.create(
            user=self.user,
            normalized_merchant="Netflix",
            pattern_type=RecurringPattern.PatternType.SUBSCRIPTION,
            cadence=RecurringPattern.Cadence.MONTHLY,
            expected_amount=Decimal("499.00"),
        )
        CategoryRule.objects.create(
            user=self.user,
            category=category,
            pattern="netflix",
            rule_type=CategoryRule.RuleType.MERCHANT_CONTAINS,
            priority=10,
        )

    def _auth(self, token: str | None = None) -> dict[str, str]:
        """Return Authorization header."""
        return {"HTTP_AUTHORIZATION": f"Bearer {token or self.token}"}

    def test_delete_my_data_clears_financial_records(self) -> None:
        """Delete-my-data removes statements, reports, and related entities."""
        url = reverse("delete-my-data")
        response = self.client.delete(
            url,
            {"confirmation": "DELETE_MY_DATA"},
            format="json",
            **self._auth(),
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(Statement.objects.filter(user=self.user).count(), 0)
        self.assertEqual(Account.objects.filter(user=self.user).count(), 0)
        self.assertEqual(Report.objects.filter(user=self.user).count(), 0)
        self.assertEqual(RecurringPattern.objects.filter(user=self.user).count(), 0)
        self.assertTrue(User.objects.filter(id=self.user.id).exists())
        self.assertTrue(
            AuditLog.objects.filter(user=self.user, action="delete_data").exists(),
        )

    def test_delete_my_data_requires_confirmation(self) -> None:
        """Delete-my-data rejects missing or wrong confirmation phrase."""
        url = reverse("delete-my-data")
        response = self.client.delete(
            url,
            {"confirmation": "WRONG"},
            format="json",
            **self._auth(),
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(Statement.objects.filter(user=self.user).count(), 1)

    def test_audit_log_lists_user_events(self) -> None:
        """Audit log endpoint returns entries scoped to the authenticated user."""
        AuditLog.objects.create(
            user=self.user,
            action=AuditLog.Action.UPLOAD,
            target_type="statement",
            target_id=str(self.statement.id),
        )
        AuditLog.objects.create(
            user=self.other,
            action=AuditLog.Action.UPLOAD,
            target_type="statement",
            target_id="999",
        )
        url = reverse("audit-log")
        response = self.client.get(url, **self._auth())
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]["action"], "upload")

    @override_settings(MAX_STATEMENTS_PER_USER=1)
    def test_upload_quota_returns_429(self) -> None:
        """Upload quota enforcement returns 429 when limit exceeded."""
        account = self.account
        url = reverse("statement-list-create")
        csv_content = b"date,description,amount\n2025-01-01,Test,-100\n"
        upload = io.BytesIO(csv_content)
        upload.name = "second.csv"
        response = self.client.post(
            url,
            {"account_id": account.id, "file": upload},
            format="multipart",
            **self._auth(),
        )
        self.assertEqual(response.status_code, status.HTTP_429_TOO_MANY_REQUESTS)

    def test_report_summary_includes_progress_fields(self) -> None:
        """Progress summary includes EMI burden and category drift fields."""
        url = reverse("report-summary")
        response = self.client.get(url, **self._auth())
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        item = response.data[0]
        self.assertIn("emi_total", item)
        self.assertIn("emi_burden_pct", item)
        self.assertIn("category_drift", item)

    def test_csv_export_produces_downloadable_file(self) -> None:
        """CSV export job completes and returns a downloadable file."""
        export_url = reverse("report-export", kwargs={"statement_id": self.statement.id})
        create_response = self.client.post(
            export_url,
            {"format": "csv"},
            format="json",
            **self._auth(),
        )
        self.assertEqual(create_response.status_code, status.HTTP_202_ACCEPTED)
        job_id = create_response.data["id"]

        job = ExportJob.objects.get(id=job_id)
        self.assertEqual(job.status, ExportJob.Status.COMPLETED)

        download_url = reverse("export-job-download", kwargs={"job_id": job_id})
        download_response = self.client.get(download_url, **self._auth())
        self.assertEqual(download_response.status_code, status.HTTP_200_OK)
        self.assertIn("text/csv", download_response["Content-Type"])
        self.assertTrue(
            AuditLog.objects.filter(user=self.user, action="export").exists(),
        )

    def test_user_cannot_access_other_users_export_job(self) -> None:
        """Export job detail returns 404 for another user's job."""
        job = ExportJob.objects.create(
            user=self.user,
            report=self.report,
            export_format=ExportJob.Format.CSV,
            status=ExportJob.Status.COMPLETED,
            file_path="exports/1/test.csv",
        )
        url = reverse("export-job-detail", kwargs={"job_id": job.id})
        response = self.client.get(url, **self._auth(self.other_token))
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
