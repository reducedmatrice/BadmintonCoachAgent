"""Tests for coach request trace helpers."""

from __future__ import annotations

from deerflow.domain.coach.request_trace import (
    append_trace_step,
    make_request_trace,
    merge_request_traces,
    new_trace_id,
    sanitize_summary,
)


def test_new_trace_id_has_stable_prefix():
    trace_id = new_trace_id()

    assert trace_id.startswith("rt_")
    assert len(trace_id) >= 10


def test_append_trace_step_preserves_order_and_sanitizes_summary():
    trace = make_request_trace("rt_test")

    trace = append_trace_step(
        trace,
        name="channel.inbound",
        layer="channel",
        summary={
            "text": "x" * 300,
            "api_key": "secret-value",
            "file_count": 2,
        },
    )
    trace = append_trace_step(
        trace,
        name="manager.run_context",
        layer="manager",
        status="ok",
        summary={"agent_name": "badminton-coach"},
    )

    assert trace["trace_id"] == "rt_test"
    assert [step["name"] for step in trace["steps"]] == [
        "channel.inbound",
        "manager.run_context",
    ]
    assert trace["steps"][0]["summary"]["text"]["length"] == 300
    assert len(trace["steps"][0]["summary"]["text"]["preview"]) <= 120
    assert "api_key" not in trace["steps"][0]["summary"]
    assert trace["steps"][0]["summary"]["file_count"] == 2


def test_merge_request_traces_appends_steps_without_losing_trace_id():
    existing = append_trace_step(make_request_trace("rt_parent"), name="channel.inbound", layer="channel")
    new = append_trace_step(make_request_trace("rt_parent"), name="middleware.coach_intake", layer="middleware")

    merged = merge_request_traces(existing, new)

    assert merged["trace_id"] == "rt_parent"
    assert [step["name"] for step in merged["steps"]] == [
        "channel.inbound",
        "middleware.coach_intake",
    ]


def test_merge_request_traces_deduplicates_cumulative_state_updates():
    existing = append_trace_step(make_request_trace("rt_parent"), name="channel.inbound", layer="channel")
    cumulative = append_trace_step(existing, name="middleware.coach_intake", layer="middleware")

    merged = merge_request_traces(existing, cumulative)

    assert [step["name"] for step in merged["steps"]] == [
        "channel.inbound",
        "middleware.coach_intake",
    ]


def test_merge_request_traces_preserves_new_trace_id_when_existing_is_empty():
    new = append_trace_step(make_request_trace("rt_child"), name="middleware.coach_intake", layer="middleware")

    merged = merge_request_traces(None, new)

    assert merged["trace_id"] == "rt_child"
    assert [step["name"] for step in merged["steps"]] == ["middleware.coach_intake"]


def test_sanitize_summary_handles_nested_sensitive_values():
    summary = sanitize_summary(
        {
            "headers": {"Authorization": "Bearer secret", "safe": "ok"},
            "items": ["a" * 200, {"password": "secret", "count": 1}],
        }
    )

    assert "Authorization" not in summary["headers"]
    assert summary["headers"]["safe"] == "ok"
    assert summary["items"][0]["length"] == 200
    assert "password" not in summary["items"][1]
