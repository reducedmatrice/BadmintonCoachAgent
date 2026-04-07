"""Tests for phase 2.2 memory schema and trace metadata."""

from datetime import UTC, datetime
from pathlib import Path

from deerflow.agents.memory.schema import (
    MemoryGet,
    MemoryReadMode,
    MemorySet,
    build_memory_entry_path,
    generate_memory_entry_id,
)
from deerflow.agents.memory.updater import MemoryUpdater, _create_empty_memory, _normalize_memory_shape


def test_create_empty_memory_includes_traceability_fields() -> None:
    memory = _create_empty_memory()

    assert memory["user"]["workContext"]["sources"] == []
    assert memory["user"]["workContext"]["thread_ids"] == []
    assert memory["history"]["recentMonths"]["sources"] == []
    assert memory["history"]["recentMonths"]["thread_ids"] == []


def test_normalize_memory_shape_backfills_legacy_traceability_fields() -> None:
    legacy = {
        "version": "1.0",
        "lastUpdated": "2026-04-07T00:00:00Z",
        "user": {
            "workContext": {
                "summary": "Working on note-agent",
                "updatedAt": "2026-04-07T00:00:00Z",
            }
        },
        "facts": [
            {
                "id": "fact_1",
                "content": "User prefers concise replies",
                "category": "preference",
                "confidence": 0.9,
                "createdAt": "2026-04-07T00:00:00Z",
                "source": "thread_123",
            }
        ],
    }

    normalized = _normalize_memory_shape(legacy)

    assert normalized["user"]["workContext"]["sources"] == []
    assert normalized["user"]["workContext"]["thread_ids"] == []
    assert normalized["facts"][0]["sources"] == []
    assert normalized["facts"][0]["thread_ids"] == ["thread_123"]


def test_apply_updates_sets_thread_trace_metadata() -> None:
    updater = MemoryUpdater()
    current_memory = _create_empty_memory()
    update_data = {
        "user": {
            "topOfMind": {
                "shouldUpdate": True,
                "summary": "Preparing badminton interview notes",
            }
        },
        "newFacts": [
            {
                "content": "User is preparing interview material",
                "category": "goal",
                "confidence": 0.95,
            }
        ],
    }

    updated = updater._apply_updates(current_memory, update_data, thread_id="thread_abc")

    assert updated["user"]["topOfMind"]["thread_ids"] == ["thread_abc"]
    assert updated["user"]["topOfMind"]["sources"] == []
    assert updated["facts"][0]["thread_ids"] == ["thread_abc"]
    assert updated["facts"][0]["source"] == "thread_abc"


def test_memory_entry_helpers_follow_file_first_contract() -> None:
    ts = datetime(2026, 4, 7, 9, 30, 0, tzinfo=UTC)
    entry_id = generate_memory_entry_id(ts)
    entry_path = build_memory_entry_path(Path("/tmp/agent"), ts)

    assert entry_id.startswith("mem_20260407T093000Z_")
    assert entry_path == Path("/tmp/agent/memory/2026-04-07.md")


def test_memory_get_and_set_defaults_capture_phase_22_semantics() -> None:
    get_request = MemoryGet()
    set_request = MemorySet(thread_id="thread_abc")

    assert get_request.read_mode == MemoryReadMode.INDEX_ONLY
    assert get_request.prefer_coach_profile is True
    assert set_request.write_markdown_first is True
    assert set_request.require_source_for_index is True
