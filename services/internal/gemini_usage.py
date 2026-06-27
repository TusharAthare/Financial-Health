"""Persist Gemini API usage and estimated costs."""

from decimal import Decimal

from django.conf import settings

from core.models import GeminiUsageLog
from services.domain.gemini_cost import estimate_gemini_cost_usd
from services.domain.gemini_usage import extract_usage_fields, serialize_sdk_object
from services.third_party.gemini_client import GeminiGenerateResult


class GeminiUsageService:
    """Record Gemini API calls with token and cost details."""

    def log_success(
        self,
        *,
        user_id: int,
        action: str,
        result: GeminiGenerateResult,
        statement_id: int | None = None,
        merchants_in_batch: int = 0,
        transactions_updated: int = 0,
        context: dict | None = None,
    ) -> GeminiUsageLog:
        """
        Persist a successful Gemini API call.

        Returns the created usage log row.
        """
        usage = extract_usage_fields(result.usage_metadata)
        cost = self._estimate_cost(
            prompt_tokens=usage["prompt_token_count"] or 0,
            candidates_tokens=usage["candidates_token_count"] or 0,
            thoughts_tokens=usage["thoughts_token_count"] or 0,
        )
        return GeminiUsageLog.objects.create(
            user_id=user_id,
            action=action,
            status=GeminiUsageLog.Status.SUCCESS,
            model=result.model,
            statement_id=statement_id,
            merchants_in_batch=merchants_in_batch,
            transactions_updated=transactions_updated,
            prompt_token_count=usage["prompt_token_count"],
            candidates_token_count=usage["candidates_token_count"],
            cached_content_token_count=usage["cached_content_token_count"],
            thoughts_token_count=usage["thoughts_token_count"],
            tool_use_prompt_token_count=usage["tool_use_prompt_token_count"],
            total_token_count=usage["total_token_count"],
            estimated_cost_usd=cost,
            latency_ms=result.latency_ms,
            response_id=result.response_id or "",
            model_version=result.model_version or "",
            usage_metadata=result.usage_metadata,
            response_metadata=result.response_metadata,
            context=context or {},
        )

    def log_failure(
        self,
        *,
        user_id: int,
        action: str,
        model: str,
        error_code: str,
        error_message: str,
        statement_id: int | None = None,
        merchants_in_batch: int = 0,
        latency_ms: int | None = None,
        context: dict | None = None,
    ) -> GeminiUsageLog:
        """Persist a failed Gemini API call."""
        status = (
            GeminiUsageLog.Status.RATE_LIMITED
            if error_code == "rate_limited"
            else GeminiUsageLog.Status.ERROR
        )
        return GeminiUsageLog.objects.create(
            user_id=user_id,
            action=action,
            status=status,
            model=model,
            statement_id=statement_id,
            merchants_in_batch=merchants_in_batch,
            latency_ms=latency_ms,
            error_code=error_code,
            error_message=error_message[:2000],
            context=context or {},
        )

    def _estimate_cost(
        self,
        *,
        prompt_tokens: int,
        candidates_tokens: int,
        thoughts_tokens: int,
    ) -> Decimal | None:
        """Return estimated USD cost when pricing is configured."""
        input_rate = Decimal(str(settings.GEMINI_COST_INPUT_PER_MILLION_USD))
        output_rate = Decimal(str(settings.GEMINI_COST_OUTPUT_PER_MILLION_USD))
        if input_rate <= 0 and output_rate <= 0:
            return None
        return estimate_gemini_cost_usd(
            prompt_tokens=prompt_tokens,
            candidates_tokens=candidates_tokens,
            thoughts_tokens=thoughts_tokens,
            input_cost_per_million=input_rate,
            output_cost_per_million=output_rate,
        )

    @staticmethod
    def serialize_response(response: object) -> tuple[dict, dict]:
        """
        Extract usage and response metadata dicts from a Gemini SDK response.

        Returns (usage_metadata, response_metadata).
        """
        usage_raw = getattr(response, "usage_metadata", None)
        usage_metadata = serialize_sdk_object(usage_raw)
        response_metadata = {
            key: value
            for key, value in {
                "response_id": getattr(response, "response_id", None),
                "model_version": getattr(response, "model_version", None),
                "create_time": _json_time(getattr(response, "create_time", None)),
            }.items()
            if value is not None
        }
        return usage_metadata, response_metadata


def _json_time(value: object | None) -> str | None:
    """Serialize datetime values for JSON storage."""
    if value is None:
        return None
    return value.isoformat() if hasattr(value, "isoformat") else str(value)
