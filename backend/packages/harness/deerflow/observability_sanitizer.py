"""Shared sanitizers for structured observability payloads."""

from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any

SENSITIVE_KEY_PARTS = ("api_key", "apikey", "token", "secret", "password", "authorization", "credential")
DEFAULT_TEXT_LIMIT = 500

_SECRET_VALUE_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"(?i)(authorization\s*[:=]\s*bearer\s+)[^\s,;]+"),
    re.compile(r"(?i)(api[_-]?key\s*[:=]\s*)[^\s,;]+"),
    re.compile(r"(?i)(password\s*[:=]\s*)[^\s,;]+"),
    re.compile(r"(?i)(token\s*[:=]\s*)[^\s,;]+"),
    re.compile(r"(?i)(secret\s*[:=]\s*)[^\s,;]+"),
    re.compile(r"(?i)(credential\s*[:=]\s*)[^\s,;]+"),
    re.compile(r"(?i)(data:[^,\s;]+;base64,)[A-Za-z0-9+/=_-]+"),
)


def sanitize_observability_value(value: Any, *, text_limit: int = DEFAULT_TEXT_LIMIT) -> Any:
    """Sanitize structured observability payloads while preserving useful previews."""
    if isinstance(value, Mapping):
        cleaned: dict[str, Any] = {}
        for key, item in value.items():
            key_text = str(key)
            if is_sensitive_key(key_text):
                continue
            cleaned[key_text] = sanitize_observability_value(item, text_limit=text_limit)
        return cleaned
    if isinstance(value, list):
        return [sanitize_observability_value(item, text_limit=text_limit) for item in value[:10]]
    if isinstance(value, tuple):
        return [sanitize_observability_value(item, text_limit=text_limit) for item in value[:10]]
    if isinstance(value, str):
        redacted = redact_sensitive_text(value)
        return summarize_text(redacted, limit=text_limit) if len(redacted) > text_limit else redacted
    if isinstance(value, (int, float, bool)) or value is None:
        return value
    return str(value)


def summarize_text(text: str, *, limit: int = DEFAULT_TEXT_LIMIT) -> dict[str, Any]:
    """Return length plus a short preview for long text."""
    return {"length": len(text), "preview": text[:limit]}


def redact_sensitive_text(text: str) -> str:
    """Redact secret-like values that appear inside otherwise safe text fields."""
    redacted = text
    for pattern in _SECRET_VALUE_PATTERNS:
        redacted = pattern.sub(lambda match: f"{match.group(1)}[REDACTED]", redacted)
    return redacted


def is_sensitive_key(key: str) -> bool:
    lowered = key.replace("-", "_").lower()
    return any(part in lowered for part in SENSITIVE_KEY_PARTS)
