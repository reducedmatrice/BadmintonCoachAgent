"""Tests for analytics structured log importing."""

from __future__ import annotations

import sqlite3

from app.analytics.importer import import_manager_structured_log_file, import_manager_structured_log_text


def test_import_manager_structured_log_text_records_job_and_run_stats(tmp_path):
    db_path = tmp_path / "analytics" / "structured_logs.db"
    text = "\n".join(
        [
            'INFO [ManagerStructured] {"event":"channel_run_completed","channel":"feishu","route":{"assistant_id":"lead_agent","agent_name":"badminton-coach"},"latency_ms":120.0,"error":false,"token_usage":{"input_tokens":100,"output_tokens":50,"total_tokens":150}}',
            'INFO [ManagerStructured] {"event":"channel_run_completed","channel":"feishu","route":{"assistant_id":"lead_agent","agent_name":"badminton-coach"},"latency_ms":260.0,"error":true,"token_usage":{"input_tokens":80,"output_tokens":20,"total_tokens":100}}',
            'INFO [ManagerStructured] {"event":"channel_run_completed",invalid}',
        ]
    )

    result = import_manager_structured_log_text(
        text,
        source_file="logs/gateway.log",
        db_path=db_path,
    )

    assert result.status == "success"
    assert result.records_scanned == 3
    assert result.records_inserted == 2
    assert result.records_skipped == 0
    assert result.records_failed == 1

    with sqlite3.connect(db_path) as connection:
        run_count = connection.execute("SELECT COUNT(*) FROM structured_log_runs").fetchone()[0]
        job_row = connection.execute(
            """
            SELECT status, source_file, records_scanned, records_inserted, records_skipped, error_message
            FROM structured_log_import_jobs
            WHERE id = ?
            """,
            (result.job_id,),
        ).fetchone()

    assert run_count == 2
    assert job_row == ("success", "logs/gateway.log", 3, 2, 0, "")


def test_import_manager_structured_log_file_is_idempotent_for_repeated_imports(tmp_path):
    db_path = tmp_path / "analytics" / "structured_logs.db"
    log_path = tmp_path / "gateway.log"
    log_path.write_text(
        "\n".join(
            [
                'INFO [ManagerStructured] {"event":"channel_run_completed","route":{"assistant_id":"lead_agent"},"latency_ms":100.0}',
                'INFO [ManagerStructured] {"event":"channel_run_completed","route":{"assistant_id":"lead_agent"},"latency_ms":100.0}',
            ]
        ),
        encoding="utf-8",
    )

    first = import_manager_structured_log_file(log_path, db_path=db_path)
    second = import_manager_structured_log_file(log_path, db_path=db_path)

    assert first.records_inserted == 2
    assert first.records_skipped == 0
    assert second.records_inserted == 0
    assert second.records_skipped == 2

    with sqlite3.connect(db_path) as connection:
        run_count = connection.execute("SELECT COUNT(*) FROM structured_log_runs").fetchone()[0]
        job_count = connection.execute("SELECT COUNT(*) FROM structured_log_import_jobs").fetchone()[0]

    assert run_count == 2
    assert job_count == 2
