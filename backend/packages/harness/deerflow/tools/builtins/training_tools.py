"""LLM-callable BaseTools for training log and body metrics queries."""

from __future__ import annotations

import logging

from langchain.tools import tool

logger = logging.getLogger(__name__)


@tool("query_training_log", parse_docstring=True)
def query_training_log(query: str, n: int = 5, session_type: str | None = None) -> str:
    """Query the user's badminton training log with a free-form question.

    Use this when the user asks about their recent training history,
    performance patterns, or wants a summary of past sessions.

    Args:
        query: Free-form question about training (e.g. "最近反手表现怎么样").
        n: Number of recent entries to retrieve (default 5).
        session_type: Optional filter: "match", "training", or "drill".
    """
    logger.info('[coach] query_training_log tool invoked: query="%s" n=%d', query, n)

    from deerflow.domain.coach.training_data import get_recent_training_log

    ctx = get_recent_training_log(n, session_type=session_type)
    if ctx.degraded:
        return f"数据不足，无法回答：{ctx.degrade_reason}"

    lines = [f"最近 {len(ctx.entries)} 条训练记录："]
    for entry in ctx.entries:
        date = entry.get("date", "?")
        summary = entry.get("summary", "")
        focus = ", ".join(entry.get("focus_areas", []))
        issues = ", ".join(entry.get("issues", []))
        parts = [f"[{date}]"]
        if summary:
            parts.append(summary)
        if focus:
            parts.append(f"训练重点：{focus}")
        if issues:
            parts.append(f"问题：{issues}")
        lines.append(" | ".join(parts))

    return "\n".join(lines)


@tool("get_body_metrics_trend", parse_docstring=True)
def get_body_metrics_trend_tool(days: int = 14, metric: str | None = None) -> str:
    """Get the user's body metrics trend analysis (heart rate, fatigue, training load).

    Use this when the user asks about their physical condition trends,
    recovery patterns, or training intensity changes over time.

    Args:
        days: Number of days to analyze (default 14).
        metric: Optional focus: "heart_rate", "training_load", "recovery", or None for all.
    """
    logger.info("[coach] get_body_metrics_trend tool invoked: days=%d metric=%s", days, metric)

    from deerflow.domain.coach.training_data import get_body_metrics_trend

    ctx = get_body_metrics_trend(days)
    if ctx.degraded:
        return f"数据不足，无法进行趋势分析：{ctx.degrade_reason}"

    summary = ctx.trend_summary
    lines = [f"最近 {days} 天身体指标趋势："]

    if not metric or metric == "heart_rate":
        hr_trend = summary.get("avg_heart_rate_trend", "未知")
        hr_mean = summary.get("avg_heart_rate_mean", "?")
        if isinstance(hr_mean, (int, float)):
            hr_mean = round(hr_mean, 1)
        lines.append(f"- 平均心率趋势：{hr_trend}（均值 {hr_mean} bpm）")

    if not metric or metric == "training_load":
        load_trend = summary.get("training_load_trend", "未知")
        load_mean = summary.get("training_load_mean", "?")
        if isinstance(load_mean, (int, float)):
            load_mean = round(load_mean, 1)
        lines.append(f"- 训练负荷趋势：{load_trend}（均值 {load_mean}）")

    if not metric or metric == "recovery":
        fatigue_ratio = summary.get("fatigue_high_ratio", "?")
        dominant = summary.get("dominant_fatigue", "未知")
        lines.append(f"- 高疲劳占比：{fatigue_ratio}，主要疲劳等级：{dominant}")

    return "\n".join(lines)
