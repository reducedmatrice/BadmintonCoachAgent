"""Tests for structured run logging."""

from __future__ import annotations

import json
import logging

from app.channels.structured_logging import build_run_log_record, format_run_log


def test_build_run_log_record_extracts_route_tokens_and_memory_hits():
    result = {
        "cost_breakdown": {
            "router_tokens": 18,
            "memory_context_tokens": 42,
            "generation_tokens": 48,
        },
        "coach_intake": {
            "intent": {
                "primary_intent": "prematch",
                "secondary_intents": ["health"],
                "missing_slots": [],
                "clarification_reason": None,
            },
            "multimodal": {
                "status": "success",
                "model_name": "gpt-4o",
                "extraction_latency_ms": 321.2,
            },
            "clarification_request": None,
        },
        "messages": [
            {"type": "human", "content": "今晚打球注意什么"},
            {
                "type": "ai",
                "content": "先盯后场回位。",
                "usage_metadata": {"input_tokens": 120, "output_tokens": 48, "total_tokens": 168},
                "cited_context": [
                    "coach_profile:后场步法回位慢",
                    "review_log:2026-03-22.md",
                    "weather:30C/阵雨",
                ],
            },
        ]
    }

    record = build_run_log_record(
        channel_name="feishu",
        thread_id="thread-1",
        assistant_id="lead_agent",
        run_context={"agent_name": "badminton-coach", "thinking_enabled": False, "is_plan_mode": False},
        result=result,
        latency_ms=842.7,
        response_text="先盯后场回位。",
        artifacts=[],
        streaming=True,
    )

    assert record["route"]["assistant_id"] == "lead_agent"
    assert record["route"]["agent_name"] == "badminton-coach"
    assert record["route"]["streaming"] is True
    assert record["route"]["coach_primary_route"] == "prematch"
    assert record["route"]["coach_secondary_routes"] == ["health"]
    assert record["latency_ms"] == 842.7
    assert record["error"] is False
    assert record["token_usage"] == {"input_tokens": 120, "output_tokens": 48, "total_tokens": 168}
    assert record["cost_breakdown"]["router_tokens"] == 18
    assert record["cost_breakdown"]["memory_context_tokens"] == 42
    assert record["cost_breakdown"]["generation_tokens"] == 48
    assert record["cost_breakdown"]["unaccounted_tokens"] == 60
    assert record["memory_hits"]["coach_profile"] is True
    assert record["memory_hits"]["review_log"] is True
    assert record["memory_hits"]["weather"] is True
    assert record["memory_hits"]["status"] == "hit"
    assert record["clarification"]["requested"] is False
    assert record["fallback"]["triggered"] is False
    assert record["multimodal"]["status"] == "success"
    assert record["multimodal"]["model_name"] == "gpt-4o"


def test_build_run_log_record_includes_clarification_decision():
    record = build_run_log_record(
        channel_name="feishu",
        thread_id="thread-clarify",
        assistant_id="lead_agent",
        run_context={"agent_name": "badminton-coach"},
        result={
            "coach_intake": {
                "intent": {
                    "missing_slots": ["session_goal"],
                    "clarification_reason": "underspecified_request",
                },
                "clarification_request": {
                    "question": "先补一条信息，你这次更偏向哪种场景？",
                },
            }
        },
        latency_ms=95.0,
        response_text="先补一条信息，你这次更偏向哪种场景？",
        artifacts=[],
        streaming=False,
    )

    assert record["clarification"] == {
        "requested": True,
        "reason": "underspecified_request",
        "missing_slots": ["session_goal"],
        "question": "先补一条信息，你这次更偏向哪种场景？",
    }
    assert record["route"]["coach_primary_route"] == "fallback"
    assert record["fallback"] == {
        "triggered": True,
        "reason": "underspecified_request",
        "source": "clarification_request",
    }


def test_format_run_log_outputs_json_string(caplog):
    record = build_run_log_record(
        channel_name="feishu",
        thread_id="thread-2",
        assistant_id="lead_agent",
        run_context={"agent_name": "badminton-coach"},
        result={"memory_hits": {"coach_profile": False, "review_log": False, "memory_json": False, "weather": False, "status": "unknown"}},
        latency_ms=120.4,
        response_text="ok",
        artifacts=["/mnt/user-data/outputs/report.md"],
        streaming=False,
        error=False,
    )

    with caplog.at_level(logging.INFO):
        logging.getLogger("app.channels.manager").info("[ManagerStructured] %s", format_run_log(record))

    payload = caplog.records[-1].message.split("[ManagerStructured] ", 1)[1]
    decoded = json.loads(payload)
    assert decoded["artifact_count"] == 1
    assert decoded["route"]["streaming"] is False
    assert decoded["multimodal"]["status"] == "unknown"


def test_build_run_log_record_includes_multimodal_failure_type():
    record = build_run_log_record(
        channel_name="feishu",
        thread_id="thread-mm-fail",
        assistant_id="lead_agent",
        run_context={"agent_name": "badminton-coach"},
        result={
            "coach_intake": {
                "multimodal": {
                    "status": "extract_failed",
                    "error_type": "ValueError",
                    "model_name": "gpt-4o",
                    "extraction_latency_ms": 912.4,
                }
            }
        },
        latency_ms=1000.0,
        response_text="截图识别失败，先补充文字。",
        artifacts=[],
        streaming=False,
    )

    assert record["multimodal"]["status"] == "extract_failed"
    assert record["multimodal"]["error_type"] == "ValueError"


def test_build_run_log_record_uses_output_tokens_as_generation_fallback():
    record = build_run_log_record(
        channel_name="feishu",
        thread_id="thread-cost-fallback",
        assistant_id="lead_agent",
        run_context={"agent_name": "badminton-coach"},
        result={
            "coach_intake": {
                "intent": {
                    "primary_intent": "health",
                    "secondary_intents": [],
                }
            },
            "usage": {"input_tokens": 70, "output_tokens": 21, "total_tokens": 91},
        },
        latency_ms=120.0,
        response_text="先暂停高强度，观察恢复。",
        artifacts=[],
        streaming=False,
    )

    assert record["cost_breakdown"] == {
        "router_tokens": None,
        "memory_context_tokens": None,
        "generation_tokens": 21,
        "input_tokens": 70,
        "output_tokens": 21,
        "total_tokens": 91,
        "unaccounted_tokens": 70,
        "status": "partial",
    }
