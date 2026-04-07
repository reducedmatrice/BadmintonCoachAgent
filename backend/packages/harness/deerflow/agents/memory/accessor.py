"""File-first memory access helpers with optional source drill-down."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from deerflow.agents.memory.schema import MemoryGet, MemoryReadMode, empty_context_section, isoformat_z
from deerflow.agents.memory.updater import get_memory_data
from deerflow.config.paths import get_paths

_SOURCE_REQUEST_HINTS = ("来源", "根据", "为什么", "上次", "最近", "history", "source")


@dataclass(slots=True)
class MemoryEntry:
    entry_id: str
    thread_id: str
    ts: str
    user_summary: str
    assistant_summary: str
    extracted_signals: list[str]
    raw_text: str


@dataclass(slots=True)
class MemoryAccessResult:
    memory_index: dict[str, Any]
    entries: list[MemoryEntry]
    drilled_down: bool
    reason: str = ""


def _get_memory_owner_root(agent_name: str | None = None) -> Path:
    if agent_name is not None:
        return get_paths().agent_dir(agent_name)
    return get_paths().base_dir


def _collect_source_ids(memory_data: dict[str, Any]) -> list[str]:
    source_ids: list[str] = []

    for section_name in ("user", "history"):
        section = memory_data.get(section_name, {})
        if not isinstance(section, dict):
            continue
        for item in section.values():
            if not isinstance(item, dict):
                continue
            for source in item.get("sources", []):
                if isinstance(source, str) and source and source not in source_ids:
                    source_ids.append(source)

    for fact in memory_data.get("facts", []):
        if not isinstance(fact, dict):
            continue
        for source in fact.get("sources", []):
            if isinstance(source, str) and source and source not in source_ids:
                source_ids.append(source)

    return source_ids


def _parse_memory_entry(raw_text: str, entry_id: str) -> MemoryEntry | None:
    thread_match = re.search(r"- thread_id:\s*(.+)", raw_text)
    ts_match = re.search(r"- ts:\s*(.+)", raw_text)
    user_match = re.search(r"### User Summary\n\n(.*?)\n\n### Assistant Summary", raw_text, re.DOTALL)
    assistant_match = re.search(r"### Assistant Summary\n\n(.*?)\n\n### Extracted Signals", raw_text, re.DOTALL)
    signals_match = re.search(r"### Extracted Signals\n\n(.*?)(?:\n## |\Z)", raw_text, re.DOTALL)

    if thread_match is None or ts_match is None:
        return None

    extracted_signals: list[str] = []
    if signals_match is not None:
        for line in signals_match.group(1).splitlines():
            line = line.strip()
            if line.startswith("- "):
                extracted_signals.append(line[2:].strip())

    return MemoryEntry(
        entry_id=entry_id,
        thread_id=thread_match.group(1).strip(),
        ts=ts_match.group(1).strip(),
        user_summary=(user_match.group(1).strip() if user_match else ""),
        assistant_summary=(assistant_match.group(1).strip() if assistant_match else ""),
        extracted_signals=extracted_signals,
        raw_text=raw_text.strip(),
    )


def load_memory_entry(entry_id: str, agent_name: str | None = None) -> MemoryEntry | None:
    """Load a single memory markdown entry by id."""
    memory_dir = _get_memory_owner_root(agent_name) / "memory"
    if not memory_dir.exists():
        return None

    marker = f"## {entry_id}"
    for entry_path in sorted(path for path in memory_dir.glob("*.md") if path.is_file()):
        try:
            content = entry_path.read_text(encoding="utf-8")
        except OSError:
            continue

        start = content.find(marker)
        if start < 0:
            continue

        next_start = content.find("\n## ", start + len(marker))
        raw_entry = content[start:] if next_start < 0 else content[start:next_start]
        return _parse_memory_entry(raw_entry, entry_id)

    return None


def iter_memory_entries(agent_name: str | None = None) -> list[MemoryEntry]:
    """Load all markdown memory entries ordered from newest to oldest."""
    memory_dir = _get_memory_owner_root(agent_name) / "memory"
    if not memory_dir.exists():
        return []

    entries: list[MemoryEntry] = []
    for entry_path in sorted((path for path in memory_dir.glob("*.md") if path.is_file()), reverse=True):
        try:
            content = entry_path.read_text(encoding="utf-8")
        except OSError:
            continue

        matches = list(re.finditer(r"^## (mem_[^\n]+)$", content, re.MULTILINE))
        for idx, match in enumerate(matches):
            start = match.start()
            end = matches[idx + 1].start() if idx + 1 < len(matches) else len(content)
            parsed = _parse_memory_entry(content[start:end], match.group(1))
            if parsed is not None:
                entries.append(parsed)

    entries.sort(key=lambda entry: entry.ts, reverse=True)
    return entries


def should_drill_down(message: str, request: MemoryGet, memory_data: dict[str, Any]) -> bool:
    """Decide whether the caller should read markdown entries."""
    if request.read_mode != MemoryReadMode.ALLOW_DRILL_DOWN:
        return False

    if request.require_source:
        return True

    if any(hint in message.lower() for hint in _SOURCE_REQUEST_HINTS):
        return True

    facts = memory_data.get("facts", [])
    if isinstance(facts, list):
        low_confidence_count = sum(
            1 for fact in facts if isinstance(fact, dict) and float(fact.get("confidence", 0) or 0) < 0.75
        )
        if low_confidence_count >= 2:
            return True

    return False


def get_memory_access_result(
    *,
    agent_name: str | None = None,
    request: MemoryGet | None = None,
    memory_data: dict[str, Any] | None = None,
    message: str = "",
    max_entries: int = 3,
) -> MemoryAccessResult:
    """Return memory index and optionally a small set of drilled-down entries."""
    resolved_request = request or MemoryGet()
    resolved_memory = memory_data if memory_data is not None else get_memory_data(agent_name)

    if not should_drill_down(message, resolved_request, resolved_memory):
        return MemoryAccessResult(memory_index=resolved_memory, entries=[], drilled_down=False, reason=resolved_request.reason)

    entries: list[MemoryEntry] = []
    for entry_id in _collect_source_ids(resolved_memory)[:max_entries]:
        entry = load_memory_entry(entry_id, agent_name=agent_name)
        if entry is not None:
            entries.append(entry)

    return MemoryAccessResult(
        memory_index=resolved_memory,
        entries=entries,
        drilled_down=bool(entries),
        reason=resolved_request.reason,
    )


def rebuild_memory_index_from_markdown(agent_name: str | None = None) -> dict[str, Any]:
    """Rebuild a minimal memory.json-style index from markdown entries."""
    entries = iter_memory_entries(agent_name)
    rebuilt = {
        "version": "1.0",
        "lastUpdated": isoformat_z(),
        "user": {
            "workContext": empty_context_section(),
            "personalContext": empty_context_section(),
            "topOfMind": empty_context_section(),
        },
        "history": {
            "recentMonths": empty_context_section(),
            "earlierContext": empty_context_section(),
            "longTermBackground": empty_context_section(),
        },
        "facts": [],
    }

    if not entries:
        return rebuilt

    latest = entries[0]
    rebuilt["user"]["topOfMind"] = {
        "summary": latest.user_summary,
        "updatedAt": latest.ts,
        "sources": [latest.entry_id],
        "thread_ids": [latest.thread_id],
    }

    recent_entries = entries[:3]
    rebuilt["history"]["recentMonths"] = {
        "summary": "\n\n".join(
            f"- {entry.ts}: {entry.user_summary.splitlines()[0].strip()}" for entry in recent_entries if entry.user_summary.strip()
        ),
        "updatedAt": recent_entries[0].ts,
        "sources": [entry.entry_id for entry in recent_entries],
        "thread_ids": _dedupe([entry.thread_id for entry in recent_entries]),
    }

    facts: list[dict[str, Any]] = []
    for index, entry in enumerate(entries, start=1):
        for signal in entry.extracted_signals:
            if not signal.startswith("fact:"):
                continue
            parts = signal.split(":", 2)
            if len(parts) != 3:
                continue
            _, category, content = parts
            facts.append(
                {
                    "id": f"fact_rebuilt_{index}_{len(facts) + 1}",
                    "content": content,
                    "category": category or "context",
                    "confidence": 0.8,
                    "createdAt": entry.ts,
                    "source": entry.thread_id,
                    "sources": [entry.entry_id],
                    "thread_ids": [entry.thread_id],
                }
            )

    rebuilt["facts"] = facts
    return rebuilt


def _dedupe(values: list[str]) -> list[str]:
    deduped: list[str] = []
    for value in values:
        if value and value not in deduped:
            deduped.append(value)
    return deduped
