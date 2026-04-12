"""Recall context policy for coach runtime (Spec 3.0 phase C)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime
from typing import Any

from .profile_store import load_coach_profile

_PREMATCH_RECALL_HINTS = ("今天", "今晚", "昨晚", "恢复", "疲劳", "状态", "还能练", "强度")


@dataclass
class CoachRecallContext:
    source: str
    recorded_at: str
    summary: str
    risk_level: str
    should_mention: bool
    mention_reason: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "source": self.source,
            "recorded_at": self.recorded_at,
            "summary": self.summary,
            "risk_level": self.risk_level,
            "should_mention": self.should_mention,
            "mention_reason": self.mention_reason,
        }


def _to_date(value: Any) -> date | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        return date.fromisoformat(value[:10])
    except ValueError:
        return None


def _build_metric_summary(metric: dict[str, Any]) -> str:
    parts: list[str] = []
    duration = metric.get("duration_min")
    avg_hr = metric.get("avg_heart_rate")
    load = metric.get("training_load")
    recovery = metric.get("recovery_hours")

    if isinstance(duration, (int, float)):
        parts.append(f"时长约 {duration:g} 分钟")
    if isinstance(avg_hr, (int, float)):
        parts.append(f"平均心率约 {avg_hr:g}")
    if isinstance(load, (int, float)):
        parts.append(f"训练负荷约 {load:g}")
    if isinstance(recovery, (int, float)):
        parts.append(f"建议恢复 {recovery:g} 小时")

    if not parts:
        raw = metric.get("raw_summary")
        if isinstance(raw, str) and raw.strip():
            return raw.strip()
        return "最近有一条运动/恢复记录"

    return "，".join(parts)


def _metric_risk_level(metric: dict[str, Any]) -> str:
    level = metric.get("fatigue_level")
    if isinstance(level, str) and level.strip():
        return level.strip().lower()
    # Fallback heuristic when metric entry has no explicit fatigue_level.
    load = metric.get("training_load")
    recovery = metric.get("recovery_hours")
    if isinstance(load, (int, float)) and load >= 160:
        return "high"
    if isinstance(recovery, (int, float)) and recovery >= 24:
        return "high"
    if isinstance(load, (int, float)) and load >= 110:
        return "medium"
    if isinstance(recovery, (int, float)) and recovery >= 16:
        return "medium"
    return "low"


def build_recall_context(
    *,
    latest_user_input: str,
    primary_intent: str,
    agent_name: str = "badminton-coach",
    now: datetime | None = None,
) -> dict[str, Any] | None:
    """Build recall context from recent health profile for health/prematch routes."""
    profile = load_coach_profile(agent_name)
    health_profile = profile.get("health_profile")
    if not isinstance(health_profile, dict):
        return None

    recent_metrics = health_profile.get("recent_metrics")
    if not isinstance(recent_metrics, list) or not recent_metrics:
        return None

    latest_metric = next((item for item in reversed(recent_metrics) if isinstance(item, dict)), None)
    if latest_metric is None:
        return None

    recorded_at = str(latest_metric.get("recorded_at") or latest_metric.get("date") or "")
    risk_level = _metric_risk_level(latest_metric)
    summary = _build_metric_summary(latest_metric)

    now_dt = now or datetime.now(UTC)
    recorded_date = _to_date(recorded_at)
    age_days = (now_dt.date() - recorded_date).days if recorded_date else None
    is_recent_48h = age_days is not None and age_days <= 2

    normalized_intent = (primary_intent or "").lower()
    text = (latest_user_input or "").strip()
    mention_reason = "none"
    should_mention = False

    if normalized_intent == "health":
        should_mention = True
        mention_reason = "health_route_default_recall"
    elif normalized_intent == "prematch":
        if risk_level in {"medium", "high"}:
            should_mention = True
            mention_reason = f"prematch_{risk_level}_fatigue"
        elif is_recent_48h and (
            (isinstance(latest_metric.get("training_load"), (int, float)) and latest_metric.get("training_load", 0) >= 140)
            or (isinstance(latest_metric.get("recovery_hours"), (int, float)) and latest_metric.get("recovery_hours", 0) >= 20)
        ):
            should_mention = True
            mention_reason = "prematch_recent_high_load"
        elif any(hint in text for hint in _PREMATCH_RECALL_HINTS):
            should_mention = True
            mention_reason = "prematch_user_recovery_hint"

    if not should_mention:
        return None

    source = str(latest_metric.get("source") or "health_profile")
    return CoachRecallContext(
        source=source,
        recorded_at=recorded_at,
        summary=summary,
        risk_level=risk_level,
        should_mention=True,
        mention_reason=mention_reason,
    ).as_dict()

