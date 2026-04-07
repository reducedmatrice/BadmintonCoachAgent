"""Tests for file-first memory accessor drill-down behavior."""

from pathlib import Path

from deerflow.agents.memory.accessor import (
    get_memory_access_result,
    load_memory_entry,
    rebuild_memory_index_from_markdown,
)
from deerflow.agents.memory.schema import MemoryGet, MemoryReadMode


def test_load_memory_entry_parses_markdown_entry(tmp_path: Path, monkeypatch) -> None:
    memory_dir = tmp_path / "memory"
    memory_dir.mkdir(parents=True)
    entry_path = memory_dir / "2026-04-07.md"
    entry_path.write_text(
        "## mem_20260407T093000Z_deadbeef\n\n"
        "- thread_id: thread_abc\n"
        "- ts: 2026-04-07T09:30:00Z\n\n"
        "### User Summary\n\n"
        "用户说昨天后场步法还是慢。\n\n"
        "### Assistant Summary\n\n"
        "建议继续盯启动和回位。\n\n"
        "### Extracted Signals\n\n"
        "- user.topOfMind\n"
        "- fact:goal:继续盯后场步法\n",
        encoding="utf-8",
    )
    monkeypatch.setattr("deerflow.agents.memory.accessor._get_memory_owner_root", lambda agent_name=None: tmp_path)

    entry = load_memory_entry("mem_20260407T093000Z_deadbeef", agent_name="badminton-coach")

    assert entry is not None
    assert entry.thread_id == "thread_abc"
    assert entry.user_summary == "用户说昨天后场步法还是慢。"
    assert entry.extracted_signals == ["user.topOfMind", "fact:goal:继续盯后场步法"]


def test_get_memory_access_result_drills_down_when_sources_requested(tmp_path: Path, monkeypatch) -> None:
    memory_dir = tmp_path / "memory"
    memory_dir.mkdir(parents=True)
    (memory_dir / "2026-04-07.md").write_text(
        "## mem_20260407T093000Z_deadbeef\n\n"
        "- thread_id: thread_abc\n"
        "- ts: 2026-04-07T09:30:00Z\n\n"
        "### User Summary\n\n"
        "用户说昨天后场步法还是慢。\n\n"
        "### Assistant Summary\n\n"
        "建议继续盯启动和回位。\n\n"
        "### Extracted Signals\n\n"
        "- fact:goal:继续盯后场步法\n",
        encoding="utf-8",
    )
    monkeypatch.setattr("deerflow.agents.memory.accessor._get_memory_owner_root", lambda agent_name=None: tmp_path)

    result = get_memory_access_result(
        agent_name="badminton-coach",
        request=MemoryGet(read_mode=MemoryReadMode.ALLOW_DRILL_DOWN, require_source=True),
        memory_data={
            "user": {},
            "history": {},
            "facts": [
                {
                    "content": "长期记忆提到后场步法问题",
                    "sources": ["mem_20260407T093000Z_deadbeef"],
                    "thread_ids": ["thread_abc"],
                    "confidence": 0.9,
                }
            ],
        },
        message="这个结论根据什么来的？",
    )

    assert result.drilled_down is True
    assert len(result.entries) == 1
    assert result.entries[0].entry_id == "mem_20260407T093000Z_deadbeef"


def test_rebuild_memory_index_from_markdown_restores_summary_and_facts(tmp_path: Path, monkeypatch) -> None:
    memory_dir = tmp_path / "memory"
    memory_dir.mkdir(parents=True)
    (memory_dir / "2026-04-07.md").write_text(
        "## mem_20260407T093000Z_deadbeef\n\n"
        "- thread_id: thread_abc\n"
        "- ts: 2026-04-07T09:30:00Z\n\n"
        "### User Summary\n\n"
        "昨天复盘里提到后场步法还是慢。\n\n"
        "### Assistant Summary\n\n"
        "建议继续盯启动和回位。\n\n"
        "### Extracted Signals\n\n"
        "- fact:goal:继续盯后场步法\n",
        encoding="utf-8",
    )
    monkeypatch.setattr("deerflow.agents.memory.accessor._get_memory_owner_root", lambda agent_name=None: tmp_path)

    rebuilt = rebuild_memory_index_from_markdown(agent_name="badminton-coach")

    assert rebuilt["user"]["topOfMind"]["sources"] == ["mem_20260407T093000Z_deadbeef"]
    assert rebuilt["user"]["topOfMind"]["thread_ids"] == ["thread_abc"]
    assert rebuilt["facts"][0]["content"] == "继续盯后场步法"
    assert rebuilt["facts"][0]["sources"] == ["mem_20260407T093000Z_deadbeef"]
    assert rebuilt["facts"][0]["thread_ids"] == ["thread_abc"]
