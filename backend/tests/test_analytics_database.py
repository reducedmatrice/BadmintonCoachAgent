"""Tests for the analytics SQLite schema."""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime
from pathlib import Path

import deerflow.config.paths as path_config
from app.analytics.database import ANALYTICS_SCHEMA, ensure_analytics_db, get_analytics_db_path, insert_structured_log_run
from app.analytics.dedupe import build_structured_log_dedupe_keys, compute_dedupe_hash


def test_get_analytics_db_path_defaults_to_deer_flow_home(tmp_path, monkeypatch):
    monkeypatch.setattr(path_config, "_paths", path_config.Paths(tmp_path))

    resolved = get_analytics_db_path()

    assert resolved == (tmp_path / "analytics" / "structured_logs.db").resolve()


def test_ensure_analytics_db_creates_expected_tables_and_indexes(tmp_path):
    db_path = ensure_analytics_db(tmp_path / "analytics" / "structured_logs.db")

    assert db_path.exists()

    with sqlite3.connect(db_path) as connection:
        table_names = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%'"
            )
        }
        index_names = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'index' AND name NOT LIKE 'sqlite_%'"
            )
        }
        run_columns = {
            row[1]
            for row in connection.execute("PRAGMA table_info('structured_log_runs')")
        }

    assert table_names == {
        "structured_log_runs",
        "structured_log_import_jobs",
        "structured_log_alerts",
    }
    assert "raw_json" in run_columns
    assert ANALYTICS_SCHEMA["raw_payload_retention"].startswith("Preserve the full normalized")
    assert ANALYTICS_SCHEMA["idempotent_import"]["unique_constraints"] == [
        "structured_log_runs.source_line_hash"
    ]
    assert {
        "structured_log_runs_created_at_idx",
        "structured_log_runs_agent_name_idx",
        "structured_log_runs_assistant_id_idx",
        "structured_log_runs_channel_idx",
        "structured_log_runs_error_idx",
        "structured_log_runs_dedupe_hash_idx",
        "structured_log_runs_source_line_hash_uidx",
    }.issubset(index_names)


def test_get_analytics_db_path_supports_relative_and_absolute_paths(tmp_path, monkeypatch):
    monkeypatch.setattr(path_config, "_paths", path_config.Paths(tmp_path))

    relative_path = get_analytics_db_path(Path("custom") / "metrics.db")
    absolute_path = get_analytics_db_path(tmp_path / "external" / "metrics.db")

    assert relative_path == (tmp_path / "custom" / "metrics.db").resolve()
    assert absolute_path == (tmp_path / "external" / "metrics.db").resolve()


def test_compute_dedupe_hash_is_stable_for_equivalent_payloads():
    payload_a = {
        "event": "channel_run_completed",
        "route": {"assistant_id": "lead_agent", "agent_name": "badminton-coach"},
        "latency_ms": 120.0,
    }
    payload_b = {
        "latency_ms": 120.0,
        "route": {"agent_name": "badminton-coach", "assistant_id": "lead_agent"},
        "event": "channel_run_completed",
    }

    assert compute_dedupe_hash(payload_a) == compute_dedupe_hash(payload_b)


def test_insert_structured_log_run_skips_duplicate_source_line_hash(tmp_path):
    db_path = ensure_analytics_db(tmp_path / "analytics" / "structured_logs.db")
    payload = {
        "event": "channel_run_completed",
        "channel": "feishu",
        "thread_id": "thread-1",
        "route": {"assistant_id": "lead_agent", "agent_name": "badminton-coach"},
        "latency_ms": 120.0,
        "response_length": 8,
        "artifact_count": 0,
        "error": False,
        "error_type": "",
        "token_usage": {"input_tokens": 20, "output_tokens": 10, "total_tokens": 30},
        "memory_hits": {"status": "unknown"},
    }
    dedupe_keys = build_structured_log_dedupe_keys(
        payload,
        source_file="logs/gateway.log",
        line_number=17,
    )
    record = {
        "source_file": "logs/gateway.log",
        "source_line_hash": dedupe_keys.source_line_hash,
        "dedupe_hash": dedupe_keys.dedupe_hash,
        "created_at": datetime.now(UTC).isoformat(),
        "channel": "feishu",
        "thread_id": "thread-1",
        "assistant_id": "lead_agent",
        "agent_name": "badminton-coach",
        "latency_ms": 120.0,
        "response_length": 8,
        "artifact_count": 0,
        "error": False,
        "error_type": "",
        "input_tokens": 20,
        "output_tokens": 10,
        "total_tokens": 30,
        "memory_hits_json": '{"status":"unknown"}',
        "route_json": '{"assistant_id":"lead_agent","agent_name":"badminton-coach"}',
        "raw_json": '{"event":"channel_run_completed"}',
    }

    with sqlite3.connect(db_path) as connection:
        inserted_first = insert_structured_log_run(connection, record)
        inserted_second = insert_structured_log_run(connection, record)
        stored_rows = connection.execute("SELECT COUNT(*) FROM structured_log_runs").fetchone()[0]

    assert inserted_first is True
    assert inserted_second is False
    assert stored_rows == 1
