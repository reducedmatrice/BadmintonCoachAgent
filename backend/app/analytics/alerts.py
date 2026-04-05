"""Alert evaluation for analytics imports."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from typing import Any

from app.analytics.repository import create_alert
from app.analytics.service import _percentile

DEFAULT_ALERT_THRESHOLDS = {
    "error_rate": 0.2,
    "p95_latency_ms": 2000.0,
}


@dataclass(frozen=True, slots=True)
class AnalyticsAlert:
    alert_type: str
    severity: str
    window_start: str
    window_end: str
    threshold_value: float | None
    observed_value: float | None
    status: str
    payload: dict[str, Any]

    def model_dump(self) -> dict[str, Any]:
        return asdict(self)


def evaluate_alerts_for_import(
    *,
    import_result: Any,
    parsed_records: list[dict[str, Any]],
    db_path: str | None = None,
) -> list[dict[str, Any]]:
    """Evaluate import-result and run-level thresholds, then persist alerts."""
    alerts: list[AnalyticsAlert] = []
    window_start, window_end = _resolve_window(parsed_records)

    if getattr(import_result, "status", "") == "failed":
        alerts.append(
            AnalyticsAlert(
                alert_type="import_failed",
                severity="critical",
                window_start=window_start,
                window_end=window_end,
                threshold_value=None,
                observed_value=None,
                status="open",
                payload={
                    "source_file": getattr(import_result, "source_file", ""),
                    "error_message": getattr(import_result, "error_message", ""),
                },
            )
        )

    if parsed_records:
        error_count = sum(1 for record in parsed_records if record.get("error"))
        error_rate = error_count / len(parsed_records)
        if error_rate >= DEFAULT_ALERT_THRESHOLDS["error_rate"]:
            alerts.append(
                AnalyticsAlert(
                    alert_type="high_error_rate",
                    severity="warning" if error_rate < 0.5 else "critical",
                    window_start=window_start,
                    window_end=window_end,
                    threshold_value=DEFAULT_ALERT_THRESHOLDS["error_rate"],
                    observed_value=round(error_rate, 4),
                    status="open",
                    payload={
                        "records_scanned": len(parsed_records),
                        "error_count": error_count,
                    },
                )
            )

        latencies = [float(record["latency_ms"]) for record in parsed_records if record.get("latency_ms") is not None]
        p95_latency_ms = _percentile(latencies, 95)
        if p95_latency_ms >= DEFAULT_ALERT_THRESHOLDS["p95_latency_ms"]:
            alerts.append(
                AnalyticsAlert(
                    alert_type="high_p95_latency",
                    severity="warning" if p95_latency_ms < 4000 else "critical",
                    window_start=window_start,
                    window_end=window_end,
                    threshold_value=DEFAULT_ALERT_THRESHOLDS["p95_latency_ms"],
                    observed_value=p95_latency_ms,
                    status="open",
                    payload={
                        "records_scanned": len(parsed_records),
                    },
                )
            )

    stored_alerts = []
    for alert in alerts:
        alert_id = create_alert(
            alert_type=alert.alert_type,
            severity=alert.severity,
            window_start=alert.window_start,
            window_end=alert.window_end,
            threshold_value=alert.threshold_value,
            observed_value=alert.observed_value,
            status=alert.status,
            payload=alert.payload,
            db_path=db_path,
        )
        stored_alerts.append(
            {
                "id": alert_id,
                **alert.model_dump(),
            }
        )
    return stored_alerts


def _resolve_window(parsed_records: list[dict[str, Any]]) -> tuple[str, str]:
    timestamps = [record.get("created_at", "") for record in parsed_records if record.get("created_at", "")]
    if timestamps:
        ordered = sorted(timestamps)
        return ordered[0], ordered[-1]

    now = datetime.now(UTC).isoformat()
    return now, now
