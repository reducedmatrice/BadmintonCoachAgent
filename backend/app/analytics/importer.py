"""Structured log import service for analytics SQLite."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from app.analytics.alerts import evaluate_alerts_for_import
from app.analytics.database import (
    connect_analytics_db,
    create_import_job,
    finalize_import_job,
    insert_structured_log_run,
)
from app.analytics.parser import parse_manager_structured_log_line

_MARKER = "[ManagerStructured] "


@dataclass(frozen=True, slots=True)
class StructuredLogImportResult:
    job_id: int
    source_file: str
    status: str
    records_scanned: int
    records_inserted: int
    records_skipped: int
    records_failed: int
    alerts_generated: int
    error_message: str

    def model_dump(self) -> dict[str, Any]:
        return asdict(self)


def import_manager_structured_log_file(
    log_file: str | Path,
    *,
    db_path: str | Path | None = None,
) -> StructuredLogImportResult:
    """Import one gateway log file into analytics SQLite."""
    source_path = Path(log_file)
    text = source_path.read_text(encoding="utf-8")
    return import_manager_structured_log_text(text, source_file=source_path, db_path=db_path)


def import_manager_structured_log_text(
    text: str,
    *,
    source_file: str | Path,
    db_path: str | Path | None = None,
) -> StructuredLogImportResult:
    """Import structured log text into analytics SQLite."""
    connection = connect_analytics_db(db_path)
    source_name = Path(source_file).as_posix()
    job_id = create_import_job(connection, source_file=source_name)
    connection.commit()

    records_scanned = 0
    records_inserted = 0
    records_skipped = 0
    records_failed = 0
    parsed_records: list[dict[str, Any]] = []

    try:
        for line_number, line in enumerate(text.splitlines(), start=1):
            if _MARKER not in line:
                continue

            records_scanned += 1
            parsed = parse_manager_structured_log_line(line, source_file=source_name, line_number=line_number)
            if parsed is None:
                records_failed += 1
                continue
            parsed_records.append(parsed)

            inserted = insert_structured_log_run(
                connection,
                {
                    "source_file": parsed["source_file"],
                    "source_line_hash": parsed["source_line_hash"],
                    "dedupe_hash": parsed["dedupe_hash"],
                    "created_at": parsed["created_at"],
                    "channel": parsed["channel"],
                    "thread_id": parsed["thread_id"],
                    "assistant_id": parsed["assistant_id"],
                    "agent_name": parsed["agent_name"],
                    "latency_ms": parsed["latency_ms"],
                    "response_length": parsed["response_length"],
                    "artifact_count": parsed["artifact_count"],
                    "error": parsed["error"],
                    "error_type": parsed["error_type"],
                    "input_tokens": parsed["input_tokens"],
                    "output_tokens": parsed["output_tokens"],
                    "total_tokens": parsed["total_tokens"],
                    "memory_hits_json": parsed["memory_hits_json"],
                    "route_json": parsed["route_json"],
                    "raw_json": parsed["raw_json"],
                },
            )
            if inserted:
                records_inserted += 1
            else:
                records_skipped += 1

        finalize_import_job(
            connection,
            job_id=job_id,
            status="success",
            records_scanned=records_scanned,
            records_inserted=records_inserted,
            records_skipped=records_skipped,
        )
        connection.commit()
        alerts = evaluate_alerts_for_import(
            import_result=StructuredLogImportResult(
                job_id=job_id,
                source_file=source_name,
                status="success",
                records_scanned=records_scanned,
                records_inserted=records_inserted,
                records_skipped=records_skipped,
                records_failed=records_failed,
                alerts_generated=0,
                error_message="",
            ),
            parsed_records=parsed_records,
            db_path=db_path if isinstance(db_path, str) or db_path is None else str(db_path),
        )
        return StructuredLogImportResult(
            job_id=job_id,
            source_file=source_name,
            status="success",
            records_scanned=records_scanned,
            records_inserted=records_inserted,
            records_skipped=records_skipped,
            records_failed=records_failed,
            alerts_generated=len(alerts),
            error_message="",
        )
    except Exception as exc:
        error_message = str(exc)
        finalize_import_job(
            connection,
            job_id=job_id,
            status="failed",
            records_scanned=records_scanned,
            records_inserted=records_inserted,
            records_skipped=records_skipped,
            error_message=error_message,
        )
        connection.commit()
        alerts = evaluate_alerts_for_import(
            import_result=StructuredLogImportResult(
                job_id=job_id,
                source_file=source_name,
                status="failed",
                records_scanned=records_scanned,
                records_inserted=records_inserted,
                records_skipped=records_skipped,
                records_failed=records_failed + 1,
                alerts_generated=0,
                error_message=error_message,
            ),
            parsed_records=parsed_records,
            db_path=db_path if isinstance(db_path, str) or db_path is None else str(db_path),
        )
        return StructuredLogImportResult(
            job_id=job_id,
            source_file=source_name,
            status="failed",
            records_scanned=records_scanned,
            records_inserted=records_inserted,
            records_skipped=records_skipped,
            records_failed=records_failed + 1,
            alerts_generated=len(alerts),
            error_message=error_message,
        )
    finally:
        connection.close()
