"""Celery tasks for async statement parsing."""

import logging

from celery import shared_task

from services.domain.exceptions import DomainValidationError
from services.internal.statement import StatementService

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=0)
def parse_statement_task(
    self,
    statement_id: int,
    pdf_password: str | None = None,
) -> dict:
    """
    Parse an uploaded statement asynchronously.

    Returns a summary dict with statement id and status.
    """
    service = StatementService()
    try:
        service.mark_parsing(statement_id)
        statement = service.parse_statement(
            statement_id,
            pdf_password=pdf_password,
        )
        return {
            "statement_id": statement.id,
            "status": statement.status,
            "transaction_count": statement.transaction_count,
        }
    except DomainValidationError as exc:
        service.mark_failed(statement_id, str(exc))
        logger.warning("Parse validation error statement_id=%s: %s", statement_id, exc)
        raise
    except Exception as exc:
        service.mark_failed(statement_id, "An unexpected error occurred during parsing.")
        logger.exception("Parse failed statement_id=%s", statement_id)
        raise exc
