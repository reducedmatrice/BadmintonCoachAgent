"""Tests for analytics aggregation services and alert evaluation."""

from __future__ import annotations

import sqlite3

import deerflow.config.paths as path_config
from app.analytics.importer import import_manager_structured_log_text
from app.analytics.repository import AnalyticsFilters
from app.analytics.service import get_alerts, get_by_route, get_errors, get_import_jobs, get_summary, get_timeseries


def test_analytics_service_queries_support_filters_and_aggregations(tmp_path, monkeypatch):
    monkeypatch.setattr(path_config, "_paths", path_config.Paths(tmp_path))
    text = "\n".join(
        [
            '2026-04-05T10:00:00Z INFO [ManagerStructured] {"event":"channel_run_completed","channel":"feishu","route":{"assistant_id":"lead_agent","agent_name":"badminton-coach"},"latency_ms":100.0,"error":false,"token_usage":{"total_tokens":100},"clarification":{"requested":true,"reason":"underspecified_request","missing_slots":["session_goal"],"question":"先补一条信息"}}',
            '2026-04-05T10:15:00Z INFO [ManagerStructured] {"event":"channel_run_completed","channel":"feishu","route":{"assistant_id":"lead_agent","agent_name":"badminton-coach"},"latency_ms":3000.0,"error":true,"error_type":"timeout","token_usage":{"total_tokens":200},"clarification":{"requested":false,"reason":"","missing_slots":[],"question":""}}',
            '2026-04-05T11:00:00Z INFO [ManagerStructured] {"event":"channel_run_completed","channel":"slack","route":{"assistant_id":"coach_agent","agent_name":"recovery-coach"},"latency_ms":800.0,"error":false,"token_usage":{"total_tokens":120}}',
        ]
    )

    result = import_manager_structured_log_text(text, source_file="logs/gateway.log")

    assert result.alerts_generated == 2

    filters = AnalyticsFilters(channel="feishu", assistant_id="lead_agent")
    summary = get_summary(filters)
    by_route = get_by_route(filters)
    errors = get_errors(filters)
    timeseries = get_timeseries(AnalyticsFilters(), bucket="hour")
    jobs = get_import_jobs()
    alerts = get_alerts()

    assert summary["total_requests"] == 2
    assert summary["error_rate"] == 0.5
    assert summary["avg_total_tokens"] == 150.0
    assert summary["clarification_requested_count"] == 1
    assert summary["clarification_request_rate"] == 0.5
    assert summary["clarification_reasons"] == [{"reason": "underspecified_request", "count": 1}]
    assert by_route["routes"][0]["route"] == "badminton-coach"
    assert by_route["routes"][0]["total_requests"] == 2
    assert by_route["routes"][0]["clarification_requested_count"] == 1
    assert errors["total_errors"] == 1
    assert errors["error_types"][0] == {"error_type": "timeout", "count": 1}
    assert len(timeseries["points"]) == 2
    assert jobs["jobs"][0]["status"] == "success"
    alert_types = {item["alert_type"] for item in alerts["alerts"]}
    assert {"high_error_rate", "high_p95_latency"}.issubset(alert_types)


def test_import_failure_creates_alert(tmp_path, monkeypatch):
    monkeypatch.setattr(path_config, "_paths", path_config.Paths(tmp_path))
    from app.analytics import importer

    original_insert = importer.insert_structured_log_run

    def broken_insert(*args, **kwargs):
        raise RuntimeError("db write failed")

    monkeypatch.setattr(importer, "insert_structured_log_run", broken_insert)
    text = 'INFO [ManagerStructured] {"event":"channel_run_completed","route":{"assistant_id":"lead_agent"},"latency_ms":100.0}'

    result = import_manager_structured_log_text(text, source_file="logs/gateway.log")

    monkeypatch.setattr(importer, "insert_structured_log_run", original_insert)

    assert result.status == "failed"
    assert result.alerts_generated == 1

    with sqlite3.connect(tmp_path / "analytics" / "structured_logs.db") as connection:
        row = connection.execute(
            "SELECT alert_type, status FROM structured_log_alerts ORDER BY id DESC LIMIT 1"
        ).fetchone()

    assert row == ("import_failed", "open")
