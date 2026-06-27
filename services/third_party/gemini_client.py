"""Thin Gemini API client for JSON categorization responses."""

import logging
import time
from dataclasses import dataclass, field
from typing import Any

from django.conf import settings

logger = logging.getLogger(__name__)


class GeminiClientError(Exception):
    """Raised when the Gemini API call fails."""

    def __init__(self, message: str, *, code: str = "api_error") -> None:
        """Initialize with a user-safe message and machine-readable code."""
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class GeminiGenerateResult:
    """Text response plus Gemini usage and response metadata."""

    text: str
    model: str
    latency_ms: int
    usage_metadata: dict[str, Any] = field(default_factory=dict)
    response_metadata: dict[str, Any] = field(default_factory=dict)
    response_id: str | None = None
    model_version: str | None = None


class GeminiClient:
    """Minimal Gemini client — one generate call per batch."""

    def __init__(self, api_key: str | None = None, model: str | None = None) -> None:
        """Initialize with optional overrides (defaults from settings)."""
        self._api_key = (api_key or settings.GEMINI_API_KEY).strip()
        self._model = model or settings.GEMINI_MODEL

    @property
    def is_configured(self) -> bool:
        """Return True when an API key is present."""
        return bool(self._api_key)

    @property
    def model_name(self) -> str:
        """Return the configured model identifier."""
        return self._model

    def generate_text(self, prompt: str) -> str:
        """
        Send a prompt and return the model text response.

        Retries on rate limits with exponential backoff.
        """
        return self.generate(prompt).text

    def generate(self, prompt: str) -> GeminiGenerateResult:
        """
        Send a prompt and return text with usage metadata.

        Raises GeminiClientError when the API is unavailable or misconfigured.
        """
        if not self.is_configured:
            raise GeminiClientError(
                "GEMINI_API_KEY is not configured.",
                code="not_configured",
            )

        try:
            from google import genai
            from google.genai import types
        except ImportError as exc:
            raise GeminiClientError(
                "google-genai package is not installed.",
                code="not_installed",
            ) from exc

        from services.internal.gemini_usage import GeminiUsageService

        client = genai.Client(api_key=self._api_key)
        max_retries = settings.GEMINI_MAX_RETRIES
        delay = settings.GEMINI_RETRY_DELAY_SECONDS
        started = time.perf_counter()

        for attempt in range(max_retries):
            try:
                response = client.models.generate_content(
                    model=self._model,
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        temperature=settings.GEMINI_TEMPERATURE,
                        response_mime_type="application/json",
                    ),
                )
                text = getattr(response, "text", None) or ""
                if not text.strip():
                    raise GeminiClientError(
                        "Gemini returned an empty response.",
                        code="empty_response",
                    )
                usage_metadata, response_metadata = (
                    GeminiUsageService.serialize_response(response)
                )
                latency_ms = int((time.perf_counter() - started) * 1000)
                return GeminiGenerateResult(
                    text=text.strip(),
                    model=self._model,
                    latency_ms=latency_ms,
                    usage_metadata=usage_metadata,
                    response_metadata=response_metadata,
                    response_id=response_metadata.get("response_id"),
                    model_version=response_metadata.get("model_version"),
                )
            except GeminiClientError:
                raise
            except Exception as exc:
                if self._is_rate_limited(exc) and attempt < max_retries - 1:
                    wait = delay * (2 ** attempt)
                    logger.warning(
                        "Gemini rate limited; retrying in %ss (attempt %s/%s)",
                        wait,
                        attempt + 1,
                        max_retries,
                    )
                    time.sleep(wait)
                    continue

                if self._is_rate_limited(exc):
                    raise GeminiClientError(
                        "Gemini rate limit exceeded. Wait a minute and try again.",
                        code="rate_limited",
                    ) from exc

                logger.error("Gemini API call failed: %s", type(exc).__name__)
                raise GeminiClientError(
                    "Gemini API request failed. Check your API key and quota.",
                    code="api_error",
                ) from exc

        raise GeminiClientError(
            "Gemini API request failed after retries.",
            code="api_error",
        )

    def _is_rate_limited(self, exc: Exception) -> bool:
        """Return True when the exception indicates HTTP 429 / quota exhaustion."""
        status = getattr(exc, "status_code", None) or getattr(exc, "code", None)
        if status == 429:
            return True
        message = str(exc).lower()
        return "429" in message or "rate" in message or "quota" in message
