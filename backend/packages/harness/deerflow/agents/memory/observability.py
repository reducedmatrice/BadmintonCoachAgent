"""Structured observability helpers for asynchronous memory writeback."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Any

from deerflow.observability_sanitizer import DEFAULT_TEXT_LIMIT, sanitize_observability_value

logger = logging.getLogger(__name__)

MEMORY_STRUCTURED_PREFIX = "[MemoryStructured] "


@dataclass
class MemoryUpdateResult:
    """Serializable result metadata for a memory writeback attempt."""

    status: str
    success: bool
    thread_id: str | None = None
    agent_name: str | None = None
    message_count: int = 0
    entry_id: str = ""
    entry_path: str = ""
    memory_file: str = ""
    updated_sections: list[str] = field(default_factory=list)
    new_facts: list[Any] = field(default_factory=list)
    facts_removed: list[str] = field(default_factory=list)
    extracted_signals: list[str] = field(default_factory=list)
    latency_ms: float | None = None
    reason: str = ""
    error_type: str = ""


def build_memory_update_event(result: MemoryUpdateResult) -> dict[str, Any]:
    """Build a compact structured event for memory writeback logs."""
    updates = {
        "updated_sections": result.updated_sections,
        "new_facts": result.new_facts,
        "facts_removed": result.facts_removed,
        "extracted_signals": result.extracted_signals,
    }
    return sanitize_summary(
        {
            "event": "memory_update_completed",
            "thread_id": result.thread_id or "",
            "agent_name": result.agent_name or "",
            "success": result.success,
            "status": result.status,
            "latency_ms": result.latency_ms,
            "message_count": result.message_count,
            "entry": {
                "id": result.entry_id,
                "path": result.entry_path,
                "entry_id": result.entry_id,
                "entry_path": result.entry_path,
            },
            "memory_file": result.memory_file,
            "memory": updates,
            "updates": updates,
            "reason": result.reason,
            "error_type": result.error_type,
        }
    )


def sanitize_summary(value: Any, *, text_limit: int = DEFAULT_TEXT_LIMIT) -> Any:
    """Sanitize structured memory logs without importing coach domain packages."""
    return sanitize_observability_value(value, text_limit=text_limit)


def format_memory_update_event(result: MemoryUpdateResult) -> str:
    """Format a memory update result as structured JSON."""
    return json.dumps(build_memory_update_event(result), ensure_ascii=False, sort_keys=True)


def log_memory_update_event(result: MemoryUpdateResult) -> None:
    """Emit a structured memory writeback log event."""
    logger.info("%s%s", MEMORY_STRUCTURED_PREFIX, format_memory_update_event(result))
