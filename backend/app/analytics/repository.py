"""Repository helpers for analytics SQLite queries."""

from __future__ import annotations

import json
import sqlite3
from dataclasses import asdict, dataclass
from typing import Any

from app.analytics.database import connect_analytics_db


@dataclass(frozen=True, slots=True)
class AnalyticsFilters:
    start_time: str = ""
    end_time: str = ""
    route: str = ""
    channel: str = ""
    assistant_id: str = ""

    def model_dump(self) -> dict[str, Any]:
        return asdict(self)


def list_filtered_runs(
    filters: AnalyticsFilters | None = None,
    *,
    db_path: str | None = None,
) -> list[dict[str, Any]]:
    """Load structured log runs with shared analytics filters applied."""
    applied_filters = filters or AnalyticsFilters()
    connection = connect_analytics_db(db_path)
    try:
        query = """
        SELECT
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
        FROM structured_log_runs
        """
        where_clauses: list[str] = []
        params: list[Any] = []

        if applied_filters.start_time:
            where_clauses.append("created_at >= ?")
            params.append(applied_filters.start_time)
        if applied_filters.end_time:
            where_clauses.append("created_at <= ?")
            params.append(applied_filters.end_time)
        if applied_filters.channel:
            where_clauses.append("channel = ?")
            params.append(applied_filters.channel)
        if applied_filters.assistant_id:
            where_clauses.append("assistant_id = ?")
            params.append(applied_filters.assistant_id)
        if applied_filters.route:
            where_clauses.append("(agent_name = ? OR assistant_id = ?)")
            params.extend([applied_filters.route, applied_filters.route])

        if where_clauses:
            query += " WHERE " + " AND ".join(where_clauses)
        query += " ORDER BY created_at ASC, id ASC"

        rows = connection.execute(query, params).fetchall()
        return [_decode_run_row(row) for row in rows]
    finally:
        connection.close()


def list_import_jobs(*, limit: int = 20, db_path: str | None = None) -> list[dict[str, Any]]:
    """Return recent import jobs."""
    connection = connect_analytics_db(db_path)
    try:
        rows = connection.execute(
            """
            SELECT
                id,
                started_at,
                finished_at,
                status,
                source_file,
                records_scanned,
                records_inserted,
                records_skipped,
                error_message
            FROM structured_log_import_jobs
            ORDER BY id DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        connection.close()


def list_alerts(*, limit: int = 20, db_path: str | None = None) -> list[dict[str, Any]]:
    """Return recent alerts."""
    connection = connect_analytics_db(db_path)
    try:
        rows = connection.execute(
            """
            SELECT
                id,
                created_at,
                alert_type,
                severity,
                window_start,
                window_end,
                threshold_value,
                observed_value,
                status,
                payload_json
            FROM structured_log_alerts
            ORDER BY id DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
        return [_decode_alert_row(row) for row in rows]
    finally:
        connection.close()


def create_alert(
    *,
    alert_type: str,
    severity: str,
    window_start: str,
    window_end: str,
    threshold_value: float | None,
    observed_value: float | None,
    status: str,
    payload: dict[str, Any],
    db_path: str | None = None,
) -> int:
    """Insert an alert record and return its id."""
    connection = connect_analytics_db(db_path)
    try:
        cursor = connection.execute(
            """
            INSERT INTO structured_log_alerts (
                created_at,
                alert_type,
                severity,
                window_start,
                window_end,
                threshold_value,
                observed_value,
                status,
                payload_json
            ) VALUES (datetime('now'), ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                alert_type,
                severity,
                window_start,
                window_end,
                threshold_value,
                observed_value,
                status,
                json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")),
            ),
        )
        connection.commit()
        return int(cursor.lastrowid)
    finally:
        connection.close()


def _decode_run_row(row: sqlite3.Row) -> dict[str, Any]:
    decoded = dict(row)
    decoded["error"] = bool(decoded["error"])
    decoded["route"] = _loads_json(decoded.pop("route_json", "{}"), default={})
    decoded["memory_hits"] = _loads_json(decoded.pop("memory_hits_json", "{}"), default={})
    decoded["raw"] = _loads_json(decoded.pop("raw_json", "{}"), default={})
    return decoded


def _decode_alert_row(row: sqlite3.Row) -> dict[str, Any]:
    decoded = dict(row)
    decoded["payload"] = _loads_json(decoded.pop("payload_json", "{}"), default={})
    return decoded


def _loads_json(raw: str, *, default: dict[str, Any]) -> dict[str, Any]:
    try:
        value = json.loads(raw)
    except json.JSONDecodeError:
        return default
    return value if isinstance(value, dict) else default
