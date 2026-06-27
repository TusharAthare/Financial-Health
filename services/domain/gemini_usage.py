"""Serialize Gemini SDK objects for persistence."""

from typing import Any


def serialize_sdk_object(value: object | None) -> dict[str, Any]:
    """Convert a Gemini SDK model (or dict) into a JSON-safe dict."""
    if value is None:
        return {}
    if isinstance(value, dict):
        return value
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json", exclude_none=True)
    return {"value": str(value)}


def extract_usage_fields(usage_metadata: dict[str, Any]) -> dict[str, int | None]:
    """Pull normalized token integer fields from usage metadata."""
    return {
        "prompt_token_count": _int_or_none(usage_metadata.get("prompt_token_count")),
        "candidates_token_count": _int_or_none(
            usage_metadata.get("candidates_token_count"),
        ),
        "cached_content_token_count": _int_or_none(
            usage_metadata.get("cached_content_token_count"),
        ),
        "thoughts_token_count": _int_or_none(usage_metadata.get("thoughts_token_count")),
        "tool_use_prompt_token_count": _int_or_none(
            usage_metadata.get("tool_use_prompt_token_count"),
        ),
        "total_token_count": _int_or_none(usage_metadata.get("total_token_count")),
    }


def _int_or_none(value: object | None) -> int | None:
    """Return an int when value is numeric, else None."""
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None
