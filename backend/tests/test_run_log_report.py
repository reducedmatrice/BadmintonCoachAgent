"""Tests for structured run log summarization."""

from deerflow.evaluation.run_log_report import (
    extract_manager_structured_records,
    format_run_log_markdown,
    summarize_run_logs,
)


def test_extract_and_summarize_manager_structured_logs():
    text = "\n".join(
        [
            'INFO [ManagerStructured] {"event":"channel_run_completed","latency_ms":120.0,"error":false,"route":{"assistant_id":"lead_agent","agent_name":"badminton-coach"},"token_usage":{"input_tokens":100,"output_tokens":50,"total_tokens":150}}',
            'INFO [ManagerStructured] {"event":"channel_run_completed","latency_ms":260.0,"error":true,"route":{"assistant_id":"lead_agent","agent_name":"badminton-coach"},"token_usage":{"input_tokens":80,"output_tokens":20,"total_tokens":100}}',
        ]
    )

    records = extract_manager_structured_records(text)
    summary = summarize_run_logs(records)

    assert len(records) == 2
    assert summary["total_requests"] == 2
    assert summary["error_rate"] == 0.5
    assert summary["overall"]["p50_latency_ms"] == 190.0
    assert summary["by_route"]["badminton-coach"]["avg_total_tokens"] == 125.0

    rendered = format_run_log_markdown(summary)
    assert "Structured Run Log Summary" in rendered
    assert "badminton-coach" in rendered
