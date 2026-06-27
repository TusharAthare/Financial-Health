"""Celery tasks for report export and retention cleanup."""

import logging

from celery import shared_task
from django.conf import settings
from django.utils import timezone

from services.internal.export import ExportService
from services.internal.upload import UploadService
from statements.models import Statement

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=1)
def export_report_task(self, job_id: int) -> dict:
    """
    Generate a report export file asynchronously.

    Returns job id and final status.
    """
    service = ExportService()
    try:
        job = service.process_export(job_id)
        return {"job_id": job.id, "status": job.status}
    except Exception:
        logger.exception("Export task failed job_id=%s", job_id)
        raise


@shared_task
def cleanup_stale_raw_files_task() -> dict:
    """
    Delete raw statement files past the configured retention window.

    Applies when STATEMENT_RAW_RETENTION_SECONDS > 0.
    """
    retention_seconds = settings.STATEMENT_RAW_RETENTION_SECONDS
    if retention_seconds <= 0:
        return {"deleted": 0, "skipped": True}

    cutoff = timezone.now() - timezone.timedelta(seconds=retention_seconds)
    upload = UploadService()
    deleted = 0

    stale = Statement.objects.filter(
        created_at__lt=cutoff,
        source_file__gt="",
    ).exclude(source_file="")

    for statement in stale.only("id", "source_file"):
        upload.delete_file(statement.source_file)
        Statement.objects.filter(id=statement.id).update(source_file="")
        deleted += 1

    if deleted:
        logger.info("Retention cleanup deleted %s stale raw files", deleted)
    return {"deleted": deleted, "skipped": False}
