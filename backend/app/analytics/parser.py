"""Structured log parsing and normalization for analytics imports."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from app.analytics.dedupe import build_structured_log_dedupe_keys, canonicalize_structured_log_payload

_MARKER = "[ManagerStructured] "
_TIMESTAMP_RE = re.compile(
    r"(?P<ts>\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}:\d{2}(?:[.,]\d{1,6})?(?:Z|[+-]\d{2}:\d{2})?)"
)


def parse_manager_structured_log_text(text: str, *, source_file: str | Path) -> list[dict[str, Any]]:
    """Parse all valid structured log lines from plain log text."""
    parsed_records: list[dict[str, Any]] = []
    for line_number, line in enumerate(text.splitlines(), start=1):
        parsed = parse_manager_structured_log_line(line, source_file=source_file, line_number=line_number)
        if parsed is not None:
            parsed_records.append(parsed)
    return parsed_records


def parse_manager_structured_log_file(file_path: str | Path) -> list[dict[str, Any]]:
    """Parse a gateway log file into normalized analytics records."""
    path = Path(file_path)
    return parse_manager_structured_log_text(path.read_text(encoding="utf-8"), source_file=path)


def parse_manager_structured_log_line(
    line: str,
    *,
    source_file: str | Path,
    line_number: int,
) -> dict[str, Any] | None:
    """Parse one structured log line into a normalized analytics record."""
    if _MARKER not in line:
        return None

    payload_raw = line.split(_MARKER, 1)[1].strip()
    try:
        payload = json.loads(payload_raw)
    except json.JSONDecodeError:
        return None
    if not isinstance(payload, dict):
        return None

    route = _normalize_route(payload.get("route"))
    token_usage = _normalize_token_usage(payload.get("token_usage"))
    memory_hits = _normalize_memory_hits(payload.get("memory_hits"))
    dedupe_keys = build_structured_log_dedupe_keys(payload, source_file=source_file, line_number=line_number)
    created_at = _normalize_created_at(payload, line)
    raw_json = canonicalize_structured_log_payload(payload)

    return {
        "source_file": Path(source_file).as_posix(),
        "source_line_number": line_number,
        "source_line_hash": dedupe_keys.source_line_hash,
        "dedupe_hash": dedupe_keys.dedupe_hash,
        "created_at": created_at,
        "channel": _normalize_string(payload.get("channel")),
        "thread_id": _normalize_string(payload.get("thread_id")),
        "assistant_id": _normalize_string(route.get("assistant_id")),
        "agent_name": _normalize_string(route.get("agent_name")),
        "latency_ms": _normalize_float(payload.get("latency_ms")),
        "response_length": _normalize_int(payload.get("response_length"), default=0),
        "artifact_count": _normalize_int(payload.get("artifact_count"), default=0),
        "error": _normalize_bool(payload.get("error")),
        "error_type": _normalize_string(payload.get("error_type")),
        "input_tokens": token_usage["input_tokens"],
        "output_tokens": token_usage["output_tokens"],
        "total_tokens": token_usage["total_tokens"],
        "memory_hits_json": json.dumps(memory_hits, ensure_ascii=False, sort_keys=True, separators=(",", ":")),
        "route_json": json.dumps(route, ensure_ascii=False, sort_keys=True, separators=(",", ":")),
        "raw_json": raw_json,
        "payload": payload,
    }


def _normalize_created_at(payload: dict[str, Any], line: str) -> str:
    for key in ("created_at", "timestamp", "ts"):
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()

    match = _TIMESTAMP_RE.search(line)
    if not match:
        return ""

    timestamp = match.group("ts").replace(" ", "T")
    if "," in timestamp:
        timestamp = timestamp.replace(",", ".", 1)
    return timestamp


def _normalize_route(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {
            "assistant_id": "",
            "agent_name": "",
            "thinking_enabled": False,
            "is_plan_mode": False,
            "streaming": False,
        }

    return {
        "assistant_id": _normalize_string(value.get("assistant_id")),
        "agent_name": _normalize_string(value.get("agent_name")),
        "thinking_enabled": _normalize_bool(value.get("thinking_enabled")),
        "is_plan_mode": _normalize_bool(value.get("is_plan_mode")),
        "streaming": _normalize_bool(value.get("streaming")),
    }


def _normalize_memory_hits(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {
            "coach_profile": False,
            "review_log": False,
            "memory_json": False,
            "weather": False,
            "status": "unknown",
        }

    normalized = {
        "coach_profile": _normalize_bool(value.get("coach_profile")),
        "review_log": _normalize_bool(value.get("review_log")),
        "memory_json": _normalize_bool(value.get("memory_json")),
        "weather": _normalize_bool(value.get("weather")),
    }
    status = value.get("status")
    normalized["status"] = status if isinstance(status, str) and status.strip() else ("hit" if any(normalized.values()) else "unknown")
    return normalized


def _normalize_token_usage(value: Any) -> dict[str, int | None]:
    if not isinstance(value, dict):
        return {"input_tokens": None, "output_tokens": None, "total_tokens": None}

    input_tokens = _read_first_int(value, "input_tokens", "prompt_tokens")
    output_tokens = _read_first_int(value, "output_tokens", "completion_tokens")
    total_tokens = _read_first_int(value, "total_tokens", "total")
    if total_tokens is None and input_tokens is not None and output_tokens is not None:
        total_tokens = input_tokens + output_tokens

    return {
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "total_tokens": total_tokens,
    }


def _read_first_int(value: dict[str, Any], *keys: str) -> int | None:
    for key in keys:
        candidate = value.get(key)
        if isinstance(candidate, bool):
            continue
        if isinstance(candidate, int):
            return candidate
        if isinstance(candidate, float):
            return int(candidate)
    return None


def _normalize_string(value: Any) -> str:
    return value.strip() if isinstance(value, str) else ""


def _normalize_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return bool(value)
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"1", "true", "yes", "on"}:
            return True
        if lowered in {"0", "false", "no", "off", ""}:
            return False
    return False


def _normalize_int(value: Any, *, default: int) -> int:
    if isinstance(value, bool):
        return default
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    return default


def _normalize_float(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    return None
