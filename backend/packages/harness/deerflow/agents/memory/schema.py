"""Memory schema helpers for file-first traceable memory."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from pathlib import Path
from uuid import uuid4

SUMMARY_SECTIONS = (
    ("user", "workContext"),
    ("user", "personalContext"),
    ("user", "topOfMind"),
    ("history", "recentMonths"),
    ("history", "earlierContext"),
    ("history", "longTermBackground"),
)


def utc_now() -> datetime:
    """Return timezone-aware UTC now for stable timestamp generation."""
    return datetime.now(UTC)


def isoformat_z(dt: datetime | None = None) -> str:
    """Format timestamps in the repo's canonical UTC-with-Z style."""
    value = dt or utc_now()
    return value.astimezone(UTC).replace(tzinfo=None).isoformat() + "Z"


def generate_memory_entry_id(ts: datetime | None = None) -> str:
    """Generate a unique memory entry id with a readable UTC prefix."""
    value = ts or utc_now()
    return f"mem_{value.strftime('%Y%m%dT%H%M%SZ')}_{uuid4().hex[:8]}"


def build_memory_entry_path(agent_root: Path, ts: datetime | None = None) -> Path:
    """Return the markdown entry path for a given UTC date."""
    value = ts or utc_now()
    return agent_root / "memory" / f"{value.strftime('%Y-%m-%d')}.md"


def render_memory_entry_markdown(
    *,
    entry_id: str,
    thread_id: str,
    ts: str,
    user_summary: str,
    assistant_summary: str,
    extracted_signals: list[str] | None = None,
) -> str:
    """Render a markdown memory entry in a stable, append-friendly format."""
    signals = extracted_signals or []
    signal_block = "\n".join(f"- {signal}" for signal in signals) if signals else "- none"

    return (
        f"## {entry_id}\n\n"
        f"- thread_id: {thread_id}\n"
        f"- ts: {ts}\n\n"
        "### User Summary\n\n"
        f"{user_summary or 'No user summary.'}\n\n"
        "### Assistant Summary\n\n"
        f"{assistant_summary or 'No assistant summary.'}\n\n"
        "### Extracted Signals\n\n"
        f"{signal_block}\n"
    )


def empty_context_section() -> dict[str, object]:
    """Create a traceable summary section."""
    return {
        "summary": "",
        "updatedAt": "",
        "sources": [],
        "thread_ids": [],
    }


def normalize_sources(value: object) -> list[str]:
    """Normalize source-like values into a de-duplicated string list."""
    if not isinstance(value, list):
        return []

    normalized: list[str] = []
    for item in value:
        if isinstance(item, str) and item and item not in normalized:
            normalized.append(item)
    return normalized


def normalize_thread_ids(value: object, legacy_source: object | None = None) -> list[str]:
    """Normalize thread ids, falling back to the legacy single-source field."""
    thread_ids = normalize_sources(value)
    if thread_ids:
        return thread_ids

    if isinstance(legacy_source, str) and legacy_source and legacy_source != "unknown":
        return [legacy_source]
    return []


def build_trace_metadata(
    *,
    sources: list[str] | None = None,
    thread_id: str | None = None,
    thread_ids: list[str] | None = None,
) -> tuple[list[str], list[str]]:
    """Build normalized source and thread-id lists for summary/fact metadata."""
    normalized_sources = normalize_sources(sources or [])

    merged_thread_ids: list[str] = []
    for value in (thread_ids or []) + ([thread_id] if thread_id else []):
        if isinstance(value, str) and value and value not in merged_thread_ids:
            merged_thread_ids.append(value)

    return normalized_sources, merged_thread_ids


class MemoryReadMode(str, Enum):
    """How MemoryGet should retrieve context."""

    INDEX_ONLY = "index_only"
    ALLOW_DRILL_DOWN = "allow_drill_down"


@dataclass(slots=True)
class MemoryGet:
    """Logical read contract for phase 2.2 memory access."""

    read_mode: MemoryReadMode = MemoryReadMode.INDEX_ONLY
    require_source: bool = False
    prefer_coach_profile: bool = True
    reason: str = ""


@dataclass(slots=True)
class MemorySet:
    """Logical write contract for phase 2.2 memory persistence."""

    thread_id: str | None = None
    entry_id: str | None = None
    write_markdown_first: bool = True
    require_source_for_index: bool = True
    sources: list[str] = field(default_factory=list)
