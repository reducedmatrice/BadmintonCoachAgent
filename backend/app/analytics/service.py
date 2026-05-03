"""Analytics aggregation services built on repository queries."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime
from statistics import mean
from typing import Any

from app.analytics.repository import AnalyticsFilters, list_alerts, list_filtered_runs, list_import_jobs


@dataclass(frozen=True, slots=True)
class AnalyticsSummary:
    total_requests: int
    error_rate: float
    avg_latency_ms: float
    p50_latency_ms: float
    p95_latency_ms: float
    avg_total_tokens: float
    fallback_count: int
    fallback_rate: float
    fallback_reason_breakdown: list[dict[str, Any]]
    avg_router_tokens: float
    avg_memory_context_tokens: float
    avg_generation_tokens: float
    clarification_requested_count: int
    clarification_request_rate: float
    clarification_reasons: list[dict[str, Any]]

    def model_dump(self) -> dict[str, Any]:
        return asdict(self)


def get_summary(filters: AnalyticsFilters | None = None, *, db_path: str | None = None) -> dict[str, Any]:
    runs = list_filtered_runs(filters, db_path=db_path)
    summary = _summarize_runs(runs)
    return {
        **summary.model_dump(),
        "filters": (filters or AnalyticsFilters()).model_dump(),
    }


def get_timeseries(
    filters: AnalyticsFilters | None = None,
    *,
    bucket: str = "hour",
    db_path: str | None = None,
) -> dict[str, Any]:
    runs = list_filtered_runs(filters, db_path=db_path)
    grouped: dict[str, list[dict[str, Any]]] = {}
    for run in runs:
        bucket_key = _bucket_created_at(run.get("created_at", ""), bucket)
        grouped.setdefault(bucket_key, []).append(run)

    points = []
    for bucket_start in sorted(grouped):
        summary = _summarize_runs(grouped[bucket_start])
        points.append(
            {
                "bucket_start": bucket_start,
                **summary.model_dump(),
            }
        )

    return {
        "bucket": bucket,
        "points": points,
        "filters": (filters or AnalyticsFilters()).model_dump(),
    }


def get_by_route(filters: AnalyticsFilters | None = None, *, db_path: str | None = None) -> dict[str, Any]:
    runs = list_filtered_runs(filters, db_path=db_path)
    grouped: dict[str, list[dict[str, Any]]] = {}
    for run in runs:
        route_name = _resolve_route_name(run)
        grouped.setdefault(route_name, []).append(run)

    routes = []
    for route_name, route_runs in grouped.items():
        summary = _summarize_runs(route_runs)
        assistant_ids = sorted({run.get("assistant_id", "") for run in route_runs if run.get("assistant_id", "")})
        channels = sorted({run.get("channel", "") for run in route_runs if run.get("channel", "")})
        routes.append(
            {
                "route": route_name,
                "assistant_ids": assistant_ids,
                "channels": channels,
                **summary.model_dump(),
            }
        )

    routes.sort(key=lambda item: (-item["total_requests"], item["route"]))
    return {
        "routes": routes,
        "filters": (filters or AnalyticsFilters()).model_dump(),
    }


def get_errors(filters: AnalyticsFilters | None = None, *, db_path: str | None = None) -> dict[str, Any]:
    runs = list_filtered_runs(filters, db_path=db_path)
    error_runs = [run for run in runs if run.get("error")]
    by_type: dict[str, int] = {}
    recent_errors = []
    for run in error_runs:
        error_type = run.get("error_type") or "unknown"
        by_type[error_type] = by_type.get(error_type, 0) + 1

    for run in sorted(error_runs, key=lambda item: item.get("created_at", ""), reverse=True)[:20]:
        recent_errors.append(
            {
                "created_at": run.get("created_at", ""),
                "channel": run.get("channel", ""),
                "assistant_id": run.get("assistant_id", ""),
                "route": _resolve_route_name(run),
                "error_type": run.get("error_type") or "unknown",
            }
        )

    return {
        "total_errors": len(error_runs),
        "error_rate": round(len(error_runs) / len(runs), 4) if runs else 0.0,
        "error_types": [
            {"error_type": error_type, "count": count}
            for error_type, count in sorted(by_type.items(), key=lambda item: (-item[1], item[0]))
        ],
        "recent_errors": recent_errors,
        "filters": (filters or AnalyticsFilters()).model_dump(),
    }


def get_import_jobs(*, limit: int = 20, db_path: str | None = None) -> dict[str, Any]:
    return {
        "jobs": list_import_jobs(limit=limit, db_path=db_path),
    }


def get_alerts(*, limit: int = 20, db_path: str | None = None) -> dict[str, Any]:
    return {
        "alerts": list_alerts(limit=limit, db_path=db_path),
    }


def _summarize_runs(runs: list[dict[str, Any]]) -> AnalyticsSummary:
    if not runs:
        return AnalyticsSummary(
            total_requests=0,
            error_rate=0.0,
            avg_latency_ms=0.0,
            p50_latency_ms=0.0,
            p95_latency_ms=0.0,
            avg_total_tokens=0.0,
            fallback_count=0,
            fallback_rate=0.0,
            fallback_reason_breakdown=[],
            avg_router_tokens=0.0,
            avg_memory_context_tokens=0.0,
            avg_generation_tokens=0.0,
            clarification_requested_count=0,
            clarification_request_rate=0.0,
            clarification_reasons=[],
        )

    latencies = [float(run["latency_ms"]) for run in runs if run.get("latency_ms") is not None]
    total_tokens = [float(run["total_tokens"]) for run in runs if run.get("total_tokens") is not None]
    router_tokens = [float(run["router_tokens"]) for run in runs if run.get("router_tokens") is not None]
    memory_context_tokens = [
        float(run["memory_context_tokens"]) for run in runs if run.get("memory_context_tokens") is not None
    ]
    generation_tokens = [float(run["generation_tokens"]) for run in runs if run.get("generation_tokens") is not None]
    errors = sum(1 for run in runs if run.get("error"))
    fallback_count = 0
    fallback_reason_counts: dict[str, int] = {}
    clarification_requested_count = 0
    clarification_reason_counts: dict[str, int] = {}
    for run in runs:
        if run.get("fallback_triggered"):
            fallback_count += 1
            reason = run.get("fallback_reason")
            if isinstance(reason, str) and reason:
                fallback_reason_counts[reason] = fallback_reason_counts.get(reason, 0) + 1
        clarification = run.get("raw", {}).get("clarification", {})
        if not isinstance(clarification, dict):
            continue
        if clarification.get("requested"):
            clarification_requested_count += 1
            reason = clarification.get("reason")
            if isinstance(reason, str) and reason:
                clarification_reason_counts[reason] = clarification_reason_counts.get(reason, 0) + 1

    return AnalyticsSummary(
        total_requests=len(runs),
        error_rate=round(errors / len(runs), 4),
        avg_latency_ms=round(mean(latencies), 2) if latencies else 0.0,
        p50_latency_ms=_percentile(latencies, 50),
        p95_latency_ms=_percentile(latencies, 95),
        avg_total_tokens=round(mean(total_tokens), 2) if total_tokens else 0.0,
        fallback_count=fallback_count,
        fallback_rate=round(fallback_count / len(runs), 4),
        fallback_reason_breakdown=[
            {"reason": reason, "count": count}
            for reason, count in sorted(fallback_reason_counts.items(), key=lambda item: (-item[1], item[0]))
        ],
        avg_router_tokens=round(mean(router_tokens), 2) if router_tokens else 0.0,
        avg_memory_context_tokens=round(mean(memory_context_tokens), 2) if memory_context_tokens else 0.0,
        avg_generation_tokens=round(mean(generation_tokens), 2) if generation_tokens else 0.0,
        clarification_requested_count=clarification_requested_count,
        clarification_request_rate=round(clarification_requested_count / len(runs), 4),
        clarification_reasons=[
            {"reason": reason, "count": count}
            for reason, count in sorted(clarification_reason_counts.items(), key=lambda item: (-item[1], item[0]))
        ],
    )


def _resolve_route_name(run: dict[str, Any]) -> str:
    route = run.get("route", {})
    if isinstance(route, dict):
        coach_primary_route = route.get("coach_primary_route")
        if isinstance(coach_primary_route, str) and coach_primary_route and coach_primary_route != "unknown":
            return coach_primary_route
    return run.get("agent_name") or run.get("assistant_id") or "unknown"


def _bucket_created_at(created_at: str, bucket: str) -> str:
    parsed = _parse_datetime(created_at)
    if parsed is None:
        return ""

    if bucket == "day":
        return parsed.strftime("%Y-%m-%d")
    if bucket == "minute":
        return parsed.strftime("%Y-%m-%dT%H:%M")
    return parsed.strftime("%Y-%m-%dT%H:00")


def _parse_datetime(value: str) -> datetime | None:
    if not value:
        return None
    normalized = value.replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(normalized)
    except ValueError:
        return None


def _percentile(values: list[float], percentile: int) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    if len(ordered) == 1:
        return round(ordered[0], 2)
    rank = (percentile / 100) * (len(ordered) - 1)
    lower = int(rank)
    upper = min(lower + 1, len(ordered) - 1)
    weight = rank - lower
    return round(ordered[lower] * (1 - weight) + ordered[upper] * weight, 2)
