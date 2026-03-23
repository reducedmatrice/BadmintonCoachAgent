"""Structured logging helpers for channel request runs."""

from __future__ import annotations

import json
from typing import Any


def build_run_log_record(
    *,
    channel_name: str,
    thread_id: str,
    assistant_id: str,
    run_context: dict[str, Any],
    result: dict[str, Any] | list[Any] | None,
    latency_ms: float,
    response_text: str,
    artifacts: list[str],
    streaming: bool,
) -> dict[str, Any]:
    """Build a stable structured log payload for one request."""
    return {
        "event": "channel_run_completed",
        "channel": channel_name,
        "thread_id": thread_id,
        "route": {
            "assistant_id": assistant_id,
            "agent_name": run_context.get("agent_name", ""),
            "thinking_enabled": bool(run_context.get("thinking_enabled", False)),
            "is_plan_mode": bool(run_context.get("is_plan_mode", False)),
            "streaming": streaming,
        },
        "latency_ms": round(latency_ms, 2),
        "response_length": len(response_text),
        "artifact_count": len(artifacts),
        "token_usage": extract_token_usage(result),
        "memory_hits": extract_memory_hits(result),
    }


def format_run_log(record: dict[str, Any]) -> str:
    """Serialize a structured run log as compact JSON."""
    return json.dumps(record, ensure_ascii=False, sort_keys=True)


def extract_token_usage(result: dict[str, Any] | list[Any] | None) -> dict[str, int | None]:
    """Best-effort extraction of request token usage."""
    candidates: list[Any] = []
    if isinstance(result, dict):
        candidates.extend(
            [
                result.get("usage"),
                result.get("token_usage"),
                result.get("usage_metadata"),
                result.get("response_metadata"),
            ]
        )
        messages = result.get("messages", [])
    elif isinstance(result, list):
        messages = result
    else:
        messages = []

    if isinstance(messages, list):
        for message in reversed(messages):
            if not isinstance(message, dict):
                continue
            candidates.extend(
                [
                    message.get("usage"),
                    message.get("token_usage"),
                    message.get("usage_metadata"),
                    message.get("response_metadata"),
                ]
            )

    for candidate in candidates:
        usage = _normalize_token_usage(candidate)
        if usage["total_tokens"] is not None:
            return usage

    return {"input_tokens": None, "output_tokens": None, "total_tokens": None}


def extract_memory_hits(result: dict[str, Any] | list[Any] | None) -> dict[str, Any]:
    """Extract memory-hit signals from explicit fields or cited context."""
    contexts: list[str] = []

    if isinstance(result, dict):
        explicit = result.get("memory_hits")
        if isinstance(explicit, dict):
            return explicit
        contexts.extend(_coerce_context_list(result.get("cited_context")))
        contexts.extend(_coerce_context_list(result.get("context_hits")))
        messages = result.get("messages", [])
    elif isinstance(result, list):
        messages = result
    else:
        messages = []

    if isinstance(messages, list):
        for message in reversed(messages):
            if not isinstance(message, dict):
                continue
            contexts.extend(_coerce_context_list(message.get("cited_context")))
            contexts.extend(_coerce_context_list(message.get("context_hits")))

    hits = {
        "coach_profile": any(item.startswith("coach_profile:") for item in contexts),
        "review_log": any(item.startswith("review_log:") for item in contexts),
        "memory_json": any(item.startswith("memory:") for item in contexts),
        "weather": any(item.startswith("weather:") or item.startswith("weather.current:") for item in contexts),
    }
    hits["status"] = "hit" if any(hits.values()) else "unknown"
    return hits


def _coerce_context_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, str)]


def _normalize_token_usage(candidate: Any) -> dict[str, int | None]:
    if not isinstance(candidate, dict):
        return {"input_tokens": None, "output_tokens": None, "total_tokens": None}

    input_tokens = _read_first_int(candidate, "input_tokens", "prompt_tokens")
    output_tokens = _read_first_int(candidate, "output_tokens", "completion_tokens")
    total_tokens = _read_first_int(candidate, "total_tokens", "total")

    if total_tokens is None and input_tokens is not None and output_tokens is not None:
        total_tokens = input_tokens + output_tokens

    return {
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "total_tokens": total_tokens,
    }


def _read_first_int(candidate: dict[str, Any], *keys: str) -> int | None:
    for key in keys:
        value = candidate.get(key)
        if isinstance(value, bool):
            continue
        if isinstance(value, int):
            return value
        if isinstance(value, float):
            return int(value)
    return None
