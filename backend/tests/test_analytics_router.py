"""Tests for analytics API routes."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

import deerflow.config.paths as path_config
from app.analytics.importer import import_manager_structured_log_text
from app.gateway.routers.analytics import router


def test_analytics_router_exposes_summary_and_lists(tmp_path, monkeypatch):
    monkeypatch.setattr(path_config, "_paths", path_config.Paths(tmp_path))
    import_manager_structured_log_text(
        "\n".join(
            [
                '2026-04-05T10:00:00Z INFO [ManagerStructured] {"event":"channel_run_completed","channel":"feishu","route":{"assistant_id":"lead_agent","agent_name":"badminton-coach"},"latency_ms":100.0,"error":false,"token_usage":{"total_tokens":100}}',
                '2026-04-05T10:15:00Z INFO [ManagerStructured] {"event":"channel_run_completed","channel":"feishu","route":{"assistant_id":"lead_agent","agent_name":"badminton-coach"},"latency_ms":3000.0,"error":true,"error_type":"timeout","token_usage":{"total_tokens":200}}',
            ]
        ),
        source_file="logs/gateway.log",
    )
    app = FastAPI()
    app.include_router(router)

    with TestClient(app) as client:
        summary_response = client.get("/api/analytics/summary", params={"channel": "feishu"})
        by_route_response = client.get("/api/analytics/by-route")
        errors_response = client.get("/api/analytics/errors")
        jobs_response = client.get("/api/analytics/import-jobs")
        alerts_response = client.get("/api/analytics/alerts")

    assert summary_response.status_code == 200
    assert summary_response.json()["total_requests"] == 2
    assert summary_response.json()["error_rate"] == 0.5
    assert by_route_response.status_code == 200
    assert by_route_response.json()["routes"][0]["route"] == "badminton-coach"
    assert errors_response.status_code == 200
    assert errors_response.json()["error_types"][0]["error_type"] == "timeout"
    assert jobs_response.status_code == 200
    assert jobs_response.json()["jobs"][0]["status"] == "success"
    assert alerts_response.status_code == 200
    assert len(alerts_response.json()["alerts"]) >= 1


def test_analytics_import_endpoint_triggers_import(tmp_path, monkeypatch):
    monkeypatch.setattr(path_config, "_paths", path_config.Paths(tmp_path))
    log_path = tmp_path / "gateway.log"
    log_path.write_text(
        'INFO [ManagerStructured] {"event":"channel_run_completed","route":{"assistant_id":"lead_agent"},"latency_ms":100.0}\n',
        encoding="utf-8",
    )
    app = FastAPI()
    app.include_router(router)

    with TestClient(app) as client:
        response = client.post("/api/analytics/import", json={"log_file": str(log_path)})

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert data["records_inserted"] == 1


def test_analytics_import_endpoint_returns_404_for_missing_file():
    app = FastAPI()
    app.include_router(router)

    with TestClient(app) as client:
        response = client.post("/api/analytics/import", json={"log_file": "/tmp/not-found.log"})

    assert response.status_code == 404


def test_analytics_import_endpoint_resolves_repo_root_relative_log_path(tmp_path, monkeypatch):
    monkeypatch.setattr(path_config, "_paths", path_config.Paths(tmp_path / ".deer-flow"))
    backend_dir = tmp_path / "backend"
    logs_dir = tmp_path / "logs"
    backend_dir.mkdir()
    logs_dir.mkdir()
    log_path = logs_dir / "gateway.log"
    log_path.write_text(
        'INFO [ManagerStructured] {"event":"channel_run_completed","route":{"assistant_id":"lead_agent"},"latency_ms":100.0}\n',
        encoding="utf-8",
    )
    monkeypatch.chdir(backend_dir)
    app = FastAPI()
    app.include_router(router)

    with TestClient(app) as client:
        response = client.post("/api/analytics/import", json={"log_file": "logs/gateway.log"})

    assert response.status_code == 200
    assert response.json()["records_inserted"] == 1
