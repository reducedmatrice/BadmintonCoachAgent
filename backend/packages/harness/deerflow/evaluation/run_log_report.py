"""Summaries for structured manager run logs."""

from __future__ import annotations

import json
from statistics import mean
from typing import Any


def extract_manager_structured_records(text: str) -> list[dict[str, Any]]:
    """Extract manager structured log records from plain log text."""
    records: list[dict[str, Any]] = []
    marker = "[ManagerStructured] "
    for line in text.splitlines():
        if marker not in line:
            continue
        payload = line.split(marker, 1)[1].strip()
        try:
            decoded = json.loads(payload)
        except json.JSONDecodeError:
            continue
        if isinstance(decoded, dict):
            records.append(decoded)
    return records


def summarize_run_logs(records: list[dict[str, Any]]) -> dict[str, Any]:
    """Aggregate latency, token, and error stats from structured run logs."""
    if not records:
        return {
            "total_requests": 0,
            "error_rate": 0.0,
            "overall": {},
            "by_route": {},
        }

    overall = _summarize_group(records)
    by_route: dict[str, dict[str, Any]] = {}
    grouped: dict[str, list[dict[str, Any]]] = {}
    for record in records:
        route = record.get("route", {})
        route_name = str(route.get("agent_name") or route.get("assistant_id") or "unknown")
        grouped.setdefault(route_name, []).append(record)
    for route_name, items in grouped.items():
        by_route[route_name] = _summarize_group(items)

    return {
        "total_requests": len(records),
        "error_rate": overall["error_rate"],
        "overall": overall,
        "by_route": by_route,
    }


def format_run_log_markdown(summary: dict[str, Any]) -> str:
    """Render a markdown report from summarized structured logs."""
    lines = [
        "# Structured Run Log Summary",
        "",
        f"- Total requests: {summary['total_requests']}",
        f"- Error rate: {summary['error_rate']:.2%}",
        "",
        "## Overall",
        "",
    ]
    overall = summary.get("overall", {})
    if overall:
        lines.extend(
            [
                f"- p50 latency: {overall.get('p50_latency_ms', 0):.2f} ms",
                f"- p95 latency: {overall.get('p95_latency_ms', 0):.2f} ms",
                f"- avg total tokens: {overall.get('avg_total_tokens', 0):.2f}",
            ]
        )

    lines.extend(["", "## By Route", ""])
    if not summary.get("by_route"):
        lines.append("- None")
    else:
        for route_name, route_summary in summary["by_route"].items():
            lines.append(
                f"- {route_name}: requests={route_summary['requests']}, "
                f"p50={route_summary['p50_latency_ms']:.2f} ms, "
                f"p95={route_summary['p95_latency_ms']:.2f} ms, "
                f"avg_total_tokens={route_summary['avg_total_tokens']:.2f}, "
                f"error_rate={route_summary['error_rate']:.2%}"
            )

    return "\n".join(lines) + "\n"


def _summarize_group(records: list[dict[str, Any]]) -> dict[str, Any]:
    latencies = [float(record.get("latency_ms", 0.0)) for record in records]
    input_tokens = _collect_token_values(records, "input_tokens")
    output_tokens = _collect_token_values(records, "output_tokens")
    total_tokens = _collect_token_values(records, "total_tokens")
    errors = sum(1 for record in records if bool(record.get("error")))

    return {
        "requests": len(records),
        "p50_latency_ms": _percentile(latencies, 50),
        "p95_latency_ms": _percentile(latencies, 95),
        "avg_input_tokens": round(mean(input_tokens), 2) if input_tokens else 0.0,
        "avg_output_tokens": round(mean(output_tokens), 2) if output_tokens else 0.0,
        "avg_total_tokens": round(mean(total_tokens), 2) if total_tokens else 0.0,
        "error_rate": round(errors / len(records), 4) if records else 0.0,
    }


def _collect_token_values(records: list[dict[str, Any]], key: str) -> list[float]:
    values: list[float] = []
    for record in records:
        token_usage = record.get("token_usage", {})
        if not isinstance(token_usage, dict):
            continue
        value = token_usage.get(key)
        if isinstance(value, (int, float)):
            values.append(float(value))
    return values


def _percentile(values: list[float], percentile: int) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    rank = (percentile / 100) * (len(ordered) - 1)
    lower = int(rank)
    upper = min(lower + 1, len(ordered) - 1)
    weight = rank - lower
    return round(ordered[lower] * (1 - weight) + ordered[upper] * weight, 2)
