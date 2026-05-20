"""Training data context reader for badminton coach domain."""

from __future__ import annotations

import logging
from collections import Counter
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any

from .profile_store import load_coach_profile

logger = logging.getLogger(__name__)


@dataclass
class TrainingLogContext:
    entries: list[dict[str, Any]] = field(default_factory=list)
    total_count: int = 0
    source: str = "coach_profile"
    degraded: bool = False
    degrade_reason: str = ""


@dataclass
class BodyMetricsContext:
    entries: list[dict[str, Any]] = field(default_factory=list)
    trend_summary: dict[str, Any] = field(default_factory=dict)
    source: str = "coach_profile"
    degraded: bool = False
    degrade_reason: str = ""


def get_recent_training_log(
    n: int = 5,
    *,
    session_type: str | None = None,
    agent_name: str = "badminton-coach",
) -> TrainingLogContext:
    """Return the most recent *n* training log entries, optionally filtered by session_type."""
    profile = load_coach_profile(agent_name)
    if not profile:
        ctx = TrainingLogContext(degraded=True, degrade_reason="profile_missing")
        logger.warning("training_log degrade: %s", ctx.degrade_reason)
        return ctx

    raw_log = profile.get("training_log")
    if not isinstance(raw_log, list) or len(raw_log) == 0:
        ctx = TrainingLogContext(degraded=True, degrade_reason="training_log_empty")
        logger.warning("training_log degrade: %s", ctx.degrade_reason)
        return ctx

    entries = [e for e in raw_log if isinstance(e, dict)]
    if session_type is not None:
        entries = [e for e in entries if e.get("session_type") == session_type]

    if not entries:
        ctx = TrainingLogContext(total_count=len(raw_log), degraded=True, degrade_reason="no_matching_entries")
        logger.warning("training_log degrade: %s", ctx.degrade_reason)
        return ctx

    sorted_entries = sorted(entries, key=lambda e: e.get("date", ""), reverse=True)
    selected = sorted_entries[:n]

    logger.info("training_log: returning %d entries (total=%d)", len(selected), len(raw_log))
    return TrainingLogContext(entries=selected, total_count=len(raw_log))


def get_body_metrics_trend(
    days: int = 30,
    *,
    agent_name: str = "badminton-coach",
) -> BodyMetricsContext:
    """Compute trend summary over body metrics from the last *days* days."""
    profile = load_coach_profile(agent_name)
    if not profile:
        ctx = BodyMetricsContext(degraded=True, degrade_reason="profile_missing")
        logger.warning("body_metrics degrade: %s", ctx.degrade_reason)
        return ctx

    raw_metrics = profile.get("body_metrics")
    if not isinstance(raw_metrics, list) or len(raw_metrics) < 2:
        ctx = BodyMetricsContext(degraded=True, degrade_reason="insufficient_total_data")
        logger.warning("body_metrics degrade: %s", ctx.degrade_reason)
        return ctx

    all_entries = [e for e in raw_metrics if isinstance(e, dict)]
    if len(all_entries) < 2:
        ctx = BodyMetricsContext(degraded=True, degrade_reason="insufficient_total_data")
        logger.warning("body_metrics degrade: %s", ctx.degrade_reason)
        return ctx

    now = datetime.now(UTC)
    cutoff = (now - timedelta(days=days)).date().isoformat()
    recent = [e for e in all_entries if e.get("date", "") >= cutoff]

    if len(recent) < 2:
        ctx = BodyMetricsContext(entries=recent, degraded=True, degrade_reason="insufficient_recent_data")
        logger.warning("body_metrics degrade: %s", ctx.degrade_reason)
        return ctx

    trend_summary = _compute_trend_summary(recent)
    logger.info("body_metrics: returning %d entries with trend summary", len(recent))
    return BodyMetricsContext(entries=recent, trend_summary=trend_summary)


def _compute_trend_summary(entries: list[dict[str, Any]]) -> dict[str, Any]:
    hr_values = [e["avg_heart_rate"] for e in entries if isinstance(e.get("avg_heart_rate"), (int, float))]
    tl_values = [e["training_load"] for e in entries if isinstance(e.get("training_load"), (int, float))]
    fatigue_levels = [e.get("fatigue_level", "") for e in entries if e.get("fatigue_level")]

    summary: dict[str, Any] = {}

    if hr_values:
        mid = len(hr_values) // 2
        first_half = hr_values[:mid] if mid > 0 else hr_values
        second_half = hr_values[mid:] if mid > 0 else hr_values
        first_mean = sum(first_half) / len(first_half)
        second_mean = sum(second_half) / len(second_half)
        summary["avg_heart_rate_trend"] = "rising" if second_mean > first_mean else "falling" if second_mean < first_mean else "stable"
        summary["avg_heart_rate_mean"] = sum(hr_values) / len(hr_values)

    if tl_values:
        mid = len(tl_values) // 2
        first_half = tl_values[:mid] if mid > 0 else tl_values
        second_half = tl_values[mid:] if mid > 0 else tl_values
        first_mean = sum(first_half) / len(first_half)
        second_mean = sum(second_half) / len(second_half)
        summary["training_load_trend"] = "rising" if second_mean > first_mean else "falling" if second_mean < first_mean else "stable"
        summary["training_load_mean"] = sum(tl_values) / len(tl_values)

    if fatigue_levels:
        counter = Counter(fatigue_levels)
        summary["fatigue_high_ratio"] = counter.get("high", 0) / len(fatigue_levels)
        summary["dominant_fatigue"] = counter.most_common(1)[0][0]

    return summary
