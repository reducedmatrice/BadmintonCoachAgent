"""End-to-end analytics validation from log import to API queries."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

import deerflow.config.paths as path_config
from app.gateway.routers.analytics import router
from deerflow.evaluation.run_log_report import extract_manager_structured_records, summarize_run_logs


def test_analytics_import_and_summary_match_file_based_report(tmp_path, monkeypatch):
    monkeypatch.setattr(path_config, "_paths", path_config.Paths(tmp_path))
    log_path = tmp_path / "gateway.log"
    log_text = "\n".join(
        [
            '2026-04-05T10:00:00Z INFO [ManagerStructured] {"event":"channel_run_completed","channel":"feishu","route":{"assistant_id":"lead_agent","agent_name":"badminton-coach","coach_primary_route":"fallback"},"latency_ms":100.0,"error":false,"token_usage":{"input_tokens":40,"output_tokens":20,"total_tokens":60},"fallback":{"triggered":true,"reason":"underspecified_request","source":"clarification_request"}}',
            '2026-04-05T10:10:00Z INFO [ManagerStructured] {"event":"channel_run_completed","channel":"feishu","route":{"assistant_id":"lead_agent","agent_name":"badminton-coach","coach_primary_route":"prematch"},"latency_ms":3000.0,"error":true,"error_type":"timeout","token_usage":{"input_tokens":120,"output_tokens":80,"total_tokens":200}}',
            '2026-04-05T11:00:00Z INFO [ManagerStructured] {"event":"channel_run_completed","channel":"slack","route":{"assistant_id":"coach_agent","agent_name":"recovery-coach","coach_primary_route":"health"},"latency_ms":800.0,"error":false,"token_usage":{"input_tokens":50,"output_tokens":10,"total_tokens":60}}',
            'INFO [ManagerStructured] {"event":"channel_run_completed",invalid}',
        ]
    )
    log_path.write_text(log_text, encoding="utf-8")

    app = FastAPI()
    app.include_router(router)

    with TestClient(app) as client:
        import_response = client.post("/api/analytics/import", json={"log_file": str(log_path)})
        second_import_response = client.post("/api/analytics/import", json={"log_file": str(log_path)})
        summary_response = client.get("/api/analytics/summary")
        by_route_response = client.get("/api/analytics/by-route")
        jobs_response = client.get("/api/analytics/import-jobs")

    file_summary = summarize_run_logs(extract_manager_structured_records(log_text))

    assert import_response.status_code == 200
    assert import_response.json()["records_inserted"] == 3
    assert import_response.json()["records_failed"] == 1

    assert second_import_response.status_code == 200
    assert second_import_response.json()["records_inserted"] == 0
    assert second_import_response.json()["records_skipped"] == 3

    summary_data = summary_response.json()
    assert summary_response.status_code == 200
    assert summary_data["total_requests"] == file_summary["total_requests"]
    assert summary_data["error_rate"] == file_summary["error_rate"]
    assert summary_data["p50_latency_ms"] == file_summary["overall"]["p50_latency_ms"]
    assert summary_data["p95_latency_ms"] == file_summary["overall"]["p95_latency_ms"]
    assert summary_data["avg_total_tokens"] == file_summary["overall"]["avg_total_tokens"]

    by_route_data = by_route_response.json()
    assert by_route_response.status_code == 200
    assert {item["route"] for item in by_route_data["routes"]} == {"fallback", "prematch", "health"}
    prematch_route = next(item for item in by_route_data["routes"] if item["route"] == "prematch")
    assert prematch_route["total_requests"] == 1
    assert prematch_route["error_rate"] == 1.0

    jobs_data = jobs_response.json()
    assert jobs_response.status_code == 200
    assert [job["status"] for job in jobs_data["jobs"][:2]] == ["success", "success"]
