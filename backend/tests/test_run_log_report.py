"""Tests for structured run log summarization."""

from deerflow.evaluation.run_log_report import (
    build_key_findings,
    extract_manager_structured_records,
    format_run_log_markdown,
    summarize_run_logs,
)


def test_extract_and_summarize_manager_structured_logs():
    text = "\n".join(
        [
            'INFO [ManagerStructured] {"event":"channel_run_completed","latency_ms":120.0,"error":false,"route":{"assistant_id":"lead_agent","agent_name":"badminton-coach","coach_primary_route":"fallback"},"token_usage":{"input_tokens":100,"output_tokens":50,"total_tokens":150},"cost_breakdown":{"router_tokens":12,"memory_context_tokens":30,"generation_tokens":50},"fallback":{"triggered":true,"reason":"underspecified_request","source":"clarification_request"}}',
            'INFO [ManagerStructured] {"event":"channel_run_completed","latency_ms":260.0,"error":true,"route":{"assistant_id":"lead_agent","agent_name":"badminton-coach","coach_primary_route":"prematch"},"token_usage":{"input_tokens":80,"output_tokens":20,"total_tokens":100},"cost_breakdown":{"router_tokens":8,"memory_context_tokens":20}}',
        ]
    )

    records = extract_manager_structured_records(text)
    summary = summarize_run_logs(records)

    assert len(records) == 2
    assert summary["total_requests"] == 2
    assert summary["error_rate"] == 0.5
    assert summary["fallback_rate"] == 0.5
    assert summary["overall"]["p50_latency_ms"] == 190.0
    assert summary["overall"]["avg_router_tokens"] == 10.0
    assert summary["overall"]["avg_generation_tokens"] == 35.0
    assert summary["by_route"]["fallback"]["avg_total_tokens"] == 150.0
    findings = build_key_findings(summary)
    assert any("Slowest route" in item for item in findings)
    assert any("Token cost is currently dominated" in item for item in findings)

    rendered = format_run_log_markdown(summary)
    assert "Structured Run Log Summary" in rendered
    assert "Key Findings" in rendered
    assert "fallback reasons" in rendered
    assert "fallback" in rendered
