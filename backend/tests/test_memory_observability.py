"""Tests for structured memory writeback observability."""

from __future__ import annotations

import json
import logging

from langchain_core.messages import HumanMessage

from deerflow.agents.memory.observability import (
    MemoryUpdateResult,
    build_memory_update_event,
    format_memory_update_event,
    log_memory_update_event,
)
from deerflow.agents.memory.queue import ConversationContext, MemoryUpdateQueue
from deerflow.agents.memory.updater import MemoryUpdater


def test_format_memory_update_event_includes_structured_payload() -> None:
    result = MemoryUpdateResult(
        status="success",
        success=True,
        thread_id="thread_123",
        agent_name="badminton-coach",
        message_count=2,
        entry_id="mem_20260407T093000Z_deadbeef",
        entry_path="/tmp/agent/memory/2026-04-07.md",
        memory_file="/tmp/agent/memory.json",
        updated_sections=["user.topOfMind"],
        new_facts=["User wants concise coaching feedback"],
        facts_removed=["fact_old"],
        extracted_signals=["user.topOfMind", "fact:preference:User wants concise coaching feedback"],
        latency_ms=12.5,
    )

    formatted = format_memory_update_event(result)

    payload = json.loads(formatted)
    assert payload == build_memory_update_event(result)
    assert payload["event"] == "memory_update_completed"
    assert payload["status"] == "success"
    assert payload["entry"]["id"] == "mem_20260407T093000Z_deadbeef"
    assert payload["memory"]["updated_sections"] == ["user.topOfMind"]
    assert payload["memory"]["new_facts"] == ["User wants concise coaching feedback"]
    assert payload["memory"]["facts_removed"] == ["fact_old"]


def test_log_memory_update_event_emits_memory_structured_prefix(caplog) -> None:
    result = MemoryUpdateResult(
        status="skipped",
        success=False,
        thread_id="thread_skip",
        agent_name=None,
        message_count=0,
        latency_ms=1.0,
        reason="no_messages",
    )

    with caplog.at_level(logging.INFO):
        log_memory_update_event(result)

    messages = [record.message for record in caplog.records if "[MemoryStructured]" in record.message]
    assert len(messages) == 1
    payload = json.loads(messages[0].split("[MemoryStructured] ", 1)[1])
    assert payload["event"] == "memory_update_completed"
    assert payload["status"] == "skipped"
    assert payload["reason"] == "no_messages"


def test_update_memory_with_result_reports_skip_for_missing_thread_id(monkeypatch) -> None:
    updater = MemoryUpdater()
    monkeypatch.setattr("deerflow.agents.memory.updater.get_memory_data", lambda agent_name=None: {})

    result = updater.update_memory_with_result([HumanMessage(content="hello")], thread_id=None)

    assert result.success is False
    assert result.status == "skipped"
    assert result.reason == "missing_thread_id"
    assert result.thread_id is None
    assert result.message_count == 1


def test_update_memory_bool_api_uses_result_success(monkeypatch) -> None:
    updater = MemoryUpdater()

    monkeypatch.setattr(
        updater,
        "update_memory_with_result",
        lambda messages, thread_id=None, agent_name=None: MemoryUpdateResult(
            status="success",
            success=True,
            thread_id=thread_id,
            agent_name=agent_name,
            message_count=len(messages),
            latency_ms=0.0,
        ),
    )

    assert updater.update_memory([HumanMessage(content="hello")], thread_id="thread_abc") is True


def test_memory_update_event_redacts_secret_like_string_values() -> None:
    event = build_memory_update_event(
        MemoryUpdateResult(
            status="success",
            success=True,
            new_facts=[
                {
                    "category": "debug",
                    "content": "Authorization: Bearer abc.def api_key=sk-test password=hunter2 data:image/png;base64,AAAA",
                }
            ],
            extracted_signals=["fact:debug:Authorization: Bearer abc.def"],
        )
    )

    text = json.dumps(event, ensure_ascii=False)
    assert "Bearer abc.def" not in text
    assert "sk-test" not in text
    assert "hunter2" not in text
    assert "base64,AAAA" not in text
    assert "[REDACTED]" in text


def test_memory_queue_logs_structured_event_when_updater_raises(monkeypatch, caplog) -> None:
    queue = MemoryUpdateQueue()

    class _BoomUpdater:
        def update_memory_with_result(self, **kwargs):
            raise RuntimeError("writeback exploded")

    monkeypatch.setattr("deerflow.agents.memory.updater.MemoryUpdater", _BoomUpdater)
    queue._queue = [ConversationContext(thread_id="thread-err", messages=[HumanMessage(content="hello")], agent_name="badminton-coach")]

    with caplog.at_level(logging.INFO):
        queue._process_queue()

    messages = [record.message for record in caplog.records if "[MemoryStructured]" in record.message]
    assert messages
    payload = json.loads(messages[-1].split("[MemoryStructured] ", 1)[1])
    assert payload["status"] == "error"
    assert payload["success"] is False
    assert payload["thread_id"] == "thread-err"
    assert payload["agent_name"] == "badminton-coach"
    assert payload["error_type"] == "RuntimeError"
