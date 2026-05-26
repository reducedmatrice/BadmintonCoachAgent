"""Small request-trace helpers for coach runtime observability."""

from __future__ import annotations

import uuid
import time
from collections.abc import Mapping
from typing import Any

from deerflow.observability_sanitizer import DEFAULT_TEXT_LIMIT, is_sensitive_key, sanitize_observability_value, summarize_text


def new_trace_id() -> str:
    """Return a compact trace id for one user request."""
    return f"rt_{uuid.uuid4().hex[:12]}"


def make_request_trace(trace_id: str | None = None) -> dict[str, Any]:
    """Create a serializable request trace payload."""
    return {"trace_id": trace_id or new_trace_id(), "steps": []}


def append_trace_step(
    trace: Mapping[str, Any] | None,
    *,
    name: str,
    layer: str,
    status: str = "ok",
    summary: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Return a new trace with one sanitized step appended."""
    base = normalize_request_trace(trace)
    steps = list(base.get("steps") or [])
    steps.append(
        {
            "name": str(name),
            "layer": str(layer),
            "status": str(status),
            "timestamp_ms": int(time.time() * 1000),
            "summary": sanitize_summary(dict(summary or {})),
        }
    )
    return {"trace_id": base["trace_id"], "steps": steps}


def merge_request_traces(existing: Any, new: Any) -> dict[str, Any]:
    """Merge two trace payloads while preserving step order."""
    left = normalize_request_trace(existing) if isinstance(existing, Mapping) else {"trace_id": None, "steps": []}
    right = (
        normalize_request_trace(
            new,
            fallback_trace_id=left.get("trace_id") if isinstance(left.get("trace_id"), str) else None,
        )
        if isinstance(new, Mapping)
        else {"trace_id": None, "steps": []}
    )

    left_trace_id = left.get("trace_id") if isinstance(left.get("trace_id"), str) else None
    right_trace_id = right.get("trace_id") if isinstance(right.get("trace_id"), str) else None
    if right_trace_id and left_trace_id and right_trace_id != left_trace_id:
        left = {"trace_id": right_trace_id, "steps": []}

    trace_id = right_trace_id or left_trace_id or new_trace_id()

    steps: list[dict[str, Any]] = []
    seen: set[tuple[Any, ...]] = set()
    for candidate in [*(left.get("steps") or []), *(right.get("steps") or [])]:
        if isinstance(candidate, Mapping):
            normalized = _normalize_step(candidate)
            fingerprint = _step_fingerprint(normalized)
            if fingerprint in seen:
                continue
            seen.add(fingerprint)
            steps.append(normalized)
    return {"trace_id": trace_id, "steps": steps}


def normalize_request_trace(value: Any, *, fallback_trace_id: str | None = None) -> dict[str, Any]:
    """Coerce an arbitrary value into the request trace schema."""
    if not isinstance(value, Mapping):
        return make_request_trace(fallback_trace_id)
    trace_id = value.get("trace_id")
    if not isinstance(trace_id, str) or not trace_id.strip():
        trace_id = fallback_trace_id or new_trace_id()
    raw_steps = value.get("steps")
    steps = [_normalize_step(step) for step in raw_steps if isinstance(step, Mapping)] if isinstance(raw_steps, list) else []
    return {"trace_id": trace_id, "steps": steps}


def filter_trace_steps_by_trace_id(trace: Any, trace_id: str) -> dict[str, Any]:
    """Return only the trace payload for the current request id."""
    normalized = normalize_request_trace(trace, fallback_trace_id=trace_id)
    if normalized["trace_id"] != trace_id:
        return make_request_trace(trace_id)
    return normalized


def sanitize_summary(value: Any, *, text_limit: int = DEFAULT_TEXT_LIMIT) -> Any:
    """Sanitize a trace summary so logs stay compact and safe."""
    return sanitize_observability_value(value, text_limit=text_limit)


def _normalize_step(step: Mapping[str, Any]) -> dict[str, Any]:
    name = step.get("name")
    layer = step.get("layer")
    status = step.get("status")
    timestamp_ms = step.get("timestamp_ms")
    summary = step.get("summary")
    return {
        "name": str(name or "unknown"),
        "layer": str(layer or "unknown"),
        "status": str(status or "ok"),
        "timestamp_ms": int(timestamp_ms)
        if isinstance(timestamp_ms, (int, float)) and not isinstance(timestamp_ms, bool)
        else int(time.time() * 1000),
        "summary": sanitize_summary(summary if isinstance(summary, Mapping) else {}),
    }


def _step_fingerprint(step: Mapping[str, Any]) -> tuple[Any, ...]:
    return (
        step.get("name"),
        step.get("layer"),
        step.get("status"),
        step.get("timestamp_ms"),
        _freeze_summary(step.get("summary")),
    )


def _freeze_summary(value: Any) -> Any:
    if isinstance(value, Mapping):
        return tuple((str(key), _freeze_summary(item)) for key, item in sorted(value.items(), key=lambda item: str(item[0])))
    if isinstance(value, list):
        return tuple(_freeze_summary(item) for item in value)
    return value


def _is_sensitive_key(key: str) -> bool:
    return is_sensitive_key(key)
