"""SQLite storage helpers for structured log analytics."""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from deerflow.config.paths import get_paths

ANALYTICS_DB_RELATIVE_PATH = Path("analytics") / "structured_logs.db"

ANALYTICS_SCHEMA: dict[str, Any] = {
    "db_path": str(Path("backend") / ".deer-flow" / ANALYTICS_DB_RELATIVE_PATH),
    "raw_payload_retention": "Preserve the full normalized structured log payload in structured_log_runs.raw_json for replay, backfill, and future field expansion.",
    "idempotent_import": {
        "dedupe_key": "dedupe_hash = sha256(canonical JSON payload)",
        "source_fingerprint": "source_line_hash = sha256(source_file + line_number + dedupe_hash)",
        "unique_constraints": ["structured_log_runs.source_line_hash"],
        "duplicate_behavior": "Duplicate source_line_hash values are skipped with INSERT OR IGNORE and do not fail the whole import job.",
        "counting_rules": {
            "records_inserted": "Rows newly written into structured_log_runs.",
            "records_skipped": "Rows ignored because source_line_hash already exists.",
            "records_failed": "Rows rejected by parsing or non-duplicate database errors.",
        },
    },
    "tables": {
        "structured_log_runs": {
            "columns": [
                "id",
                "source_file",
                "source_line_hash",
                "dedupe_hash",
                "created_at",
                "channel",
                "thread_id",
                "assistant_id",
                "agent_name",
                "latency_ms",
                "response_length",
                "artifact_count",
                "error",
                "error_type",
                "input_tokens",
                "output_tokens",
                "total_tokens",
                "memory_hits_json",
                "route_json",
                "raw_json",
            ],
            "unique_constraints": [
                "structured_log_runs.source_line_hash",
            ],
            "indexes": [
                "structured_log_runs_created_at_idx",
                "structured_log_runs_agent_name_idx",
                "structured_log_runs_assistant_id_idx",
                "structured_log_runs_channel_idx",
                "structured_log_runs_error_idx",
                "structured_log_runs_dedupe_hash_idx",
            ],
        },
        "structured_log_import_jobs": {
            "columns": [
                "id",
                "started_at",
                "finished_at",
                "status",
                "source_file",
                "records_scanned",
                "records_inserted",
                "records_skipped",
                "error_message",
            ],
            "indexes": [
                "structured_log_import_jobs_started_at_idx",
                "structured_log_import_jobs_status_idx",
            ],
        },
        "structured_log_alerts": {
            "columns": [
                "id",
                "created_at",
                "alert_type",
                "severity",
                "window_start",
                "window_end",
                "threshold_value",
                "observed_value",
                "status",
                "payload_json",
            ],
            "indexes": [
                "structured_log_alerts_created_at_idx",
                "structured_log_alerts_status_idx",
                "structured_log_alerts_alert_type_idx",
            ],
        },
    },
}

_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS structured_log_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_file TEXT NOT NULL,
    source_line_hash TEXT NOT NULL,
    dedupe_hash TEXT NOT NULL,
    created_at TEXT NOT NULL,
    channel TEXT NOT NULL DEFAULT '',
    thread_id TEXT NOT NULL DEFAULT '',
    assistant_id TEXT NOT NULL DEFAULT '',
    agent_name TEXT NOT NULL DEFAULT '',
    latency_ms REAL,
    response_length INTEGER NOT NULL DEFAULT 0,
    artifact_count INTEGER NOT NULL DEFAULT 0,
    error INTEGER NOT NULL DEFAULT 0 CHECK (error IN (0, 1)),
    error_type TEXT NOT NULL DEFAULT '',
    input_tokens INTEGER,
    output_tokens INTEGER,
    total_tokens INTEGER,
    memory_hits_json TEXT NOT NULL DEFAULT '{}',
    route_json TEXT NOT NULL DEFAULT '{}',
    raw_json TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS structured_log_import_jobs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    started_at TEXT NOT NULL,
    finished_at TEXT,
    status TEXT NOT NULL,
    source_file TEXT NOT NULL,
    records_scanned INTEGER NOT NULL DEFAULT 0,
    records_inserted INTEGER NOT NULL DEFAULT 0,
    records_skipped INTEGER NOT NULL DEFAULT 0,
    error_message TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS structured_log_alerts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at TEXT NOT NULL,
    alert_type TEXT NOT NULL,
    severity TEXT NOT NULL,
    window_start TEXT NOT NULL,
    window_end TEXT NOT NULL,
    threshold_value REAL,
    observed_value REAL,
    status TEXT NOT NULL,
    payload_json TEXT NOT NULL DEFAULT '{}'
);

CREATE INDEX IF NOT EXISTS structured_log_runs_created_at_idx
    ON structured_log_runs (created_at);
CREATE INDEX IF NOT EXISTS structured_log_runs_agent_name_idx
    ON structured_log_runs (agent_name);
CREATE INDEX IF NOT EXISTS structured_log_runs_assistant_id_idx
    ON structured_log_runs (assistant_id);
CREATE INDEX IF NOT EXISTS structured_log_runs_channel_idx
    ON structured_log_runs (channel);
CREATE INDEX IF NOT EXISTS structured_log_runs_error_idx
    ON structured_log_runs (error);
CREATE INDEX IF NOT EXISTS structured_log_runs_dedupe_hash_idx
    ON structured_log_runs (dedupe_hash);
CREATE UNIQUE INDEX IF NOT EXISTS structured_log_runs_source_line_hash_uidx
    ON structured_log_runs (source_line_hash);

CREATE INDEX IF NOT EXISTS structured_log_import_jobs_started_at_idx
    ON structured_log_import_jobs (started_at);
CREATE INDEX IF NOT EXISTS structured_log_import_jobs_status_idx
    ON structured_log_import_jobs (status);

CREATE INDEX IF NOT EXISTS structured_log_alerts_created_at_idx
    ON structured_log_alerts (created_at);
CREATE INDEX IF NOT EXISTS structured_log_alerts_status_idx
    ON structured_log_alerts (status);
CREATE INDEX IF NOT EXISTS structured_log_alerts_alert_type_idx
    ON structured_log_alerts (alert_type);
"""


def get_analytics_db_path(db_path: str | Path | None = None) -> Path:
    """Resolve the analytics SQLite database path."""
    if db_path is None:
        return (get_paths().base_dir / ANALYTICS_DB_RELATIVE_PATH).resolve()

    candidate = Path(db_path)
    if candidate.is_absolute():
        return candidate.resolve()
    return (get_paths().base_dir / candidate).resolve()


def initialize_analytics_schema(connection: sqlite3.Connection) -> None:
    """Create analytics tables and indexes when missing."""
    connection.executescript(_SCHEMA_SQL)
    connection.commit()


def ensure_analytics_db(db_path: str | Path | None = None) -> Path:
    """Ensure the analytics SQLite file and parent directory exist."""
    resolved_path = get_analytics_db_path(db_path)
    resolved_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(resolved_path) as connection:
        initialize_analytics_schema(connection)
    return resolved_path


def connect_analytics_db(db_path: str | Path | None = None) -> sqlite3.Connection:
    """Open a configured analytics SQLite connection."""
    resolved_path = ensure_analytics_db(db_path)
    connection = sqlite3.connect(resolved_path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def insert_structured_log_run(connection: sqlite3.Connection, record: dict[str, Any]) -> bool:
    """Insert one structured log run and skip duplicates idempotently."""
    cursor = connection.execute(
        """
        INSERT OR IGNORE INTO structured_log_runs (
            source_file,
            source_line_hash,
            dedupe_hash,
            created_at,
            channel,
            thread_id,
            assistant_id,
            agent_name,
            latency_ms,
            response_length,
            artifact_count,
            error,
            error_type,
            input_tokens,
            output_tokens,
            total_tokens,
            memory_hits_json,
            route_json,
            raw_json
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            record["source_file"],
            record["source_line_hash"],
            record["dedupe_hash"],
            record["created_at"],
            record.get("channel", ""),
            record.get("thread_id", ""),
            record.get("assistant_id", ""),
            record.get("agent_name", ""),
            record.get("latency_ms"),
            record.get("response_length", 0),
            record.get("artifact_count", 0),
            int(bool(record.get("error", False))),
            record.get("error_type", ""),
            record.get("input_tokens"),
            record.get("output_tokens"),
            record.get("total_tokens"),
            record.get("memory_hits_json", "{}"),
            record.get("route_json", "{}"),
            record["raw_json"],
        ),
    )
    return cursor.rowcount > 0


def create_import_job(connection: sqlite3.Connection, *, source_file: str, started_at: str | None = None) -> int:
    """Create an import job row in running status."""
    started_at_value = started_at or datetime.now(UTC).isoformat()
    cursor = connection.execute(
        """
        INSERT INTO structured_log_import_jobs (
            started_at,
            status,
            source_file,
            records_scanned,
            records_inserted,
            records_skipped,
            error_message
        ) VALUES (?, ?, ?, 0, 0, 0, '')
        """,
        (started_at_value, "running", source_file),
    )
    return int(cursor.lastrowid)


def finalize_import_job(
    connection: sqlite3.Connection,
    *,
    job_id: int,
    status: str,
    records_scanned: int,
    records_inserted: int,
    records_skipped: int,
    error_message: str = "",
    finished_at: str | None = None,
) -> None:
    """Finalize an import job with aggregate counters."""
    finished_at_value = finished_at or datetime.now(UTC).isoformat()
    connection.execute(
        """
        UPDATE structured_log_import_jobs
        SET
            finished_at = ?,
            status = ?,
            records_scanned = ?,
            records_inserted = ?,
            records_skipped = ?,
            error_message = ?
        WHERE id = ?
        """,
        (
            finished_at_value,
            status,
            records_scanned,
            records_inserted,
            records_skipped,
            error_message,
            job_id,
        ),
    )
