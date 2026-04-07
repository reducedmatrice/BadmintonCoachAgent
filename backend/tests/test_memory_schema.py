"""Tests for phase 2.2 memory schema and trace metadata."""

import json
from datetime import UTC, datetime
from pathlib import Path

from langchain_core.messages import AIMessage, HumanMessage

from deerflow.agents.memory.schema import (
    MemoryGet,
    MemoryReadMode,
    MemorySet,
    build_memory_entry_path,
    generate_memory_entry_id,
)
from deerflow.agents.memory.updater import (
    MemoryUpdater,
    _append_memory_entry,
    _create_empty_memory,
    _normalize_memory_shape,
)


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

    updated = updater._apply_updates(
        current_memory,
        update_data,
        thread_id="thread_abc",
        entry_metadata={"entry_id": "mem_20260407T093000Z_deadbeef"},
    )

    assert updated["user"]["topOfMind"]["thread_ids"] == ["thread_abc"]
    assert updated["user"]["topOfMind"]["sources"] == ["mem_20260407T093000Z_deadbeef"]
    assert updated["facts"][0]["thread_ids"] == ["thread_abc"]
    assert updated["facts"][0]["source"] == "thread_abc"
    assert updated["facts"][0]["sources"] == ["mem_20260407T093000Z_deadbeef"]


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


def test_append_memory_entry_writes_daily_markdown(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr("deerflow.agents.memory.updater._get_memory_owner_root", lambda agent_name=None: tmp_path)

    entry = _append_memory_entry(
        [
            HumanMessage(content="今天打球后场步法还是慢。"),
            AIMessage(content="下次继续关注启动和步频。"),
        ],
        thread_id="thread_abc",
        agent_name="badminton-coach",
    )

    assert entry is not None
    entry_path = Path(entry["entry_path"])
    content = entry_path.read_text(encoding="utf-8")
    assert entry_path == tmp_path / "memory" / f"{datetime.now(UTC).strftime('%Y-%m-%d')}.md"
    assert entry["entry_id"] in content
    assert "thread_id: thread_abc" in content
    assert "今天打球后场步法还是慢。" in content


def test_update_memory_requires_thread_id_for_file_first_indexing(monkeypatch) -> None:
    updater = MemoryUpdater()
    monkeypatch.setattr("deerflow.agents.memory.updater.get_memory_data", lambda agent_name=None: _create_empty_memory())

    class _Model:
        def invoke(self, prompt: str):
            return type(
                "_Resp",
                (),
                {
                    "content": json.dumps(
                        {
                            "user": {},
                            "history": {},
                            "newFacts": [],
                            "factsToRemove": [],
                        }
                    )
                },
            )()

    monkeypatch.setattr(updater, "_get_model", lambda: _Model())

    assert updater.update_memory([HumanMessage(content="hello")], thread_id=None) is False
