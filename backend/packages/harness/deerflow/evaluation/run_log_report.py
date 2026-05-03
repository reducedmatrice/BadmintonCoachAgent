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
            "fallback_rate": 0.0,
            "overall": {},
            "by_route": {},
        }

    overall = _summarize_group(records)
    by_route: dict[str, dict[str, Any]] = {}
    grouped: dict[str, list[dict[str, Any]]] = {}
    for record in records:
        route = record.get("route", {})
        route_name = _resolve_route_name(route)
        grouped.setdefault(route_name, []).append(record)
    for route_name, items in grouped.items():
        by_route[route_name] = _summarize_group(items)

    return {
        "total_requests": len(records),
        "error_rate": overall["error_rate"],
        "fallback_rate": overall["fallback_rate"],
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
        f"- Fallback rate: {summary.get('fallback_rate', 0):.2%}",
        "",
        "## Key Findings",
        "",
    ]
    findings = build_key_findings(summary)
    if findings:
        for finding in findings:
            lines.append(f"- {finding}")
    else:
        lines.append("- None")

    lines.extend(
        [
            "",
            "## Overall",
            "",
        ]
    )
    overall = summary.get("overall", {})
    if overall:
        lines.extend(
            [
                f"- avg latency: {overall.get('avg_latency_ms', 0):.2f} ms",
                f"- p50 latency: {overall.get('p50_latency_ms', 0):.2f} ms",
                f"- p95 latency: {overall.get('p95_latency_ms', 0):.2f} ms",
                f"- avg total tokens: {overall.get('avg_total_tokens', 0):.2f}",
                f"- fallback rate: {overall.get('fallback_rate', 0):.2%}",
                f"- avg router tokens: {overall.get('avg_router_tokens', 0):.2f}",
                f"- avg memory-context tokens: {overall.get('avg_memory_context_tokens', 0):.2f}",
                f"- avg generation tokens: {overall.get('avg_generation_tokens', 0):.2f}",
            ]
        )
        fallback_reasons = overall.get("fallback_reason_breakdown", [])
        if fallback_reasons:
            lines.append(f"- fallback reasons: {_format_reason_breakdown(fallback_reasons)}")

    lines.extend(["", "## By Route", ""])
    if not summary.get("by_route"):
        lines.append("- None")
    else:
        for route_name, route_summary in summary["by_route"].items():
            lines.append(
                f"- {route_name}: requests={route_summary['requests']}, "
                f"avg_latency={route_summary['avg_latency_ms']:.2f} ms, "
                f"p50={route_summary['p50_latency_ms']:.2f} ms, "
                f"p95={route_summary['p95_latency_ms']:.2f} ms, "
                f"avg_total_tokens={route_summary['avg_total_tokens']:.2f}, "
                f"fallback_rate={route_summary['fallback_rate']:.2%}, "
                f"error_rate={route_summary['error_rate']:.2%}"
            )

    return "\n".join(lines) + "\n"


def build_key_findings(summary: dict[str, Any]) -> list[str]:
    by_route = summary.get("by_route", {})
    if not isinstance(by_route, dict) or not by_route:
        return []

    slowest_route = max(
        by_route.items(),
        key=lambda item: (float(item[1].get("p95_latency_ms", 0.0)), item[0]),
    )
    most_expensive_route = max(
        by_route.items(),
        key=lambda item: (float(item[1].get("avg_total_tokens", 0.0)), item[0]),
    )
    highest_fallback_route = max(
        by_route.items(),
        key=lambda item: (float(item[1].get("fallback_rate", 0.0)), item[0]),
    )
    overall = summary.get("overall", {})
    findings = [
        f"Slowest route by P95 latency: `{slowest_route[0]}` at {slowest_route[1].get('p95_latency_ms', 0):.2f} ms.",
        f"Most expensive route by avg total tokens: `{most_expensive_route[0]}` at {most_expensive_route[1].get('avg_total_tokens', 0):.2f}.",
    ]
    if float(highest_fallback_route[1].get("fallback_rate", 0.0)) > 0:
        findings.append(
            f"Fallback is most concentrated on `{highest_fallback_route[0]}` at {highest_fallback_route[1].get('fallback_rate', 0):.2%}."
        )
    else:
        findings.append("No fallback observed in the current sample.")

    stage_name, stage_value = max(
        (
            ("router", float(overall.get("avg_router_tokens", 0.0))),
            ("memory-context", float(overall.get("avg_memory_context_tokens", 0.0))),
            ("final generation", float(overall.get("avg_generation_tokens", 0.0))),
        ),
        key=lambda item: item[1],
    )
    if stage_value > 0:
        findings.append(f"Token cost is currently dominated by `{stage_name}` at {stage_value:.2f} avg tokens.")
    else:
        findings.append("Stage-level token breakdown is missing or incomplete in the current sample.")
    return findings


def _summarize_group(records: list[dict[str, Any]]) -> dict[str, Any]:
    latencies = [float(record.get("latency_ms", 0.0)) for record in records]
    input_tokens = _collect_token_values(records, "input_tokens")
    output_tokens = _collect_token_values(records, "output_tokens")
    total_tokens = _collect_token_values(records, "total_tokens")
    router_tokens = _collect_cost_values(records, "router_tokens")
    memory_context_tokens = _collect_cost_values(records, "memory_context_tokens")
    generation_tokens = _collect_cost_values(records, "generation_tokens")
    errors = sum(1 for record in records if bool(record.get("error")))
    fallback_count = 0
    fallback_reason_counts: dict[str, int] = {}
    for record in records:
        fallback = record.get("fallback", {})
        if not isinstance(fallback, dict) or not bool(fallback.get("triggered")):
            continue
        fallback_count += 1
        reason = fallback.get("reason")
        if isinstance(reason, str) and reason:
            fallback_reason_counts[reason] = fallback_reason_counts.get(reason, 0) + 1

    return {
        "requests": len(records),
        "avg_latency_ms": round(mean(latencies), 2) if latencies else 0.0,
        "p50_latency_ms": _percentile(latencies, 50),
        "p95_latency_ms": _percentile(latencies, 95),
        "avg_input_tokens": round(mean(input_tokens), 2) if input_tokens else 0.0,
        "avg_output_tokens": round(mean(output_tokens), 2) if output_tokens else 0.0,
        "avg_total_tokens": round(mean(total_tokens), 2) if total_tokens else 0.0,
        "avg_router_tokens": round(mean(router_tokens), 2) if router_tokens else 0.0,
        "avg_memory_context_tokens": round(mean(memory_context_tokens), 2) if memory_context_tokens else 0.0,
        "avg_generation_tokens": round(mean(generation_tokens), 2) if generation_tokens else 0.0,
        "fallback_count": fallback_count,
        "fallback_rate": round(fallback_count / len(records), 4) if records else 0.0,
        "fallback_reason_breakdown": [
            {"reason": reason, "count": count}
            for reason, count in sorted(fallback_reason_counts.items(), key=lambda item: (-item[1], item[0]))
        ],
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


def _collect_cost_values(records: list[dict[str, Any]], key: str) -> list[float]:
    values: list[float] = []
    for record in records:
        cost_breakdown = record.get("cost_breakdown", {})
        if not isinstance(cost_breakdown, dict):
            continue
        value = cost_breakdown.get(key)
        if value is None and key == "generation_tokens":
            token_usage = record.get("token_usage", {})
            if isinstance(token_usage, dict):
                value = token_usage.get("output_tokens")
        if isinstance(value, (int, float)):
            values.append(float(value))
    return values


def _resolve_route_name(route: Any) -> str:
    if not isinstance(route, dict):
        return "unknown"
    coach_primary_route = route.get("coach_primary_route")
    if isinstance(coach_primary_route, str) and coach_primary_route:
        return coach_primary_route
    return str(route.get("agent_name") or route.get("assistant_id") or "unknown")


def _format_reason_breakdown(items: list[dict[str, Any]]) -> str:
    parts: list[str] = []
    for item in items:
        reason = item.get("reason")
        count = item.get("count")
        if isinstance(reason, str) and isinstance(count, int):
            parts.append(f"{reason}={count}")
    return ", ".join(parts)


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
