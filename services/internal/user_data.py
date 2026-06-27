"""Hard delete of all financial data for a user."""

import logging
import shutil

from django.conf import settings
from django.db import transaction

from analysis.models import ExportJob, RecurringPattern
from services.internal.audit import AuditService
from services.internal.upload import UploadService
from statements.models import Account, Category, CategoryRule, Statement

logger = logging.getLogger(__name__)


class UserDataService:
    """Remove all tenant-scoped financial data while keeping the user account."""

    def __init__(self) -> None:
        """Initialize dependent services."""
        self._audit = AuditService()
        self._upload = UploadService()

    @transaction.atomic
    def delete_all_data(self, user_id: int) -> dict[str, int]:
        """
        Hard-delete statements, transactions, reports, and related derived data.

        Returns counts of deleted entity types for the response payload.
        """
        statement_count = Statement.objects.filter(user_id=user_id).count()
        account_count = Account.objects.filter(user_id=user_id).count()
        recurring_count = RecurringPattern.objects.filter(user_id=user_id).count()
        rule_count = CategoryRule.objects.filter(user_id=user_id).count()
        category_count = Category.objects.filter(user_id=user_id).count()
        export_count = ExportJob.objects.filter(user_id=user_id).count()

        self._audit.log(
            user_id,
            "delete_data",
            target_type="user",
            target_id=str(user_id),
            metadata={
                "statements": statement_count,
                "accounts": account_count,
            },
        )

        self._purge_export_files(user_id)
        ExportJob.objects.filter(user_id=user_id).delete()

        for statement in Statement.objects.filter(user_id=user_id).only("source_file"):
            if statement.source_file:
                self._upload.delete_file(statement.source_file)

        Account.objects.filter(user_id=user_id).delete()
        RecurringPattern.objects.filter(user_id=user_id).delete()
        CategoryRule.objects.filter(user_id=user_id).delete()
        Category.objects.filter(user_id=user_id).delete()

        self._purge_user_media_dirs(user_id)

        logger.info(
            "User data deleted user_id=%s statements=%s accounts=%s",
            user_id,
            statement_count,
            account_count,
        )
        return {
            "statements_deleted": statement_count,
            "accounts_deleted": account_count,
            "recurring_patterns_deleted": recurring_count,
            "category_rules_deleted": rule_count,
            "custom_categories_deleted": category_count,
            "export_jobs_deleted": export_count,
        }

    def _purge_export_files(self, user_id: int) -> None:
        """Remove generated export files for the user."""
        export_dir = settings.MEDIA_ROOT / "exports" / str(user_id)
        if export_dir.is_dir():
            shutil.rmtree(export_dir, ignore_errors=True)

    def _purge_user_media_dirs(self, user_id: int) -> None:
        """Remove remaining user upload directories under MEDIA_ROOT."""
        for subdir in ("statements", "exports"):
            path = settings.MEDIA_ROOT / subdir / str(user_id)
            if path.is_dir():
                shutil.rmtree(path, ignore_errors=True)
