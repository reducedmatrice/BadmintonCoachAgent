"""Persistence helpers for the badminton coach profile and review logs."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from deerflow.config.paths import get_paths

from .postmatch import PostmatchReview, extract_postmatch_review


@dataclass
class PostmatchPersistenceResult:
    review: PostmatchReview
    profile: dict[str, Any]
    review_log_path: Path


def create_default_coach_profile() -> dict[str, Any]:
    return {
        "athlete_profile": {
            "dominant_hand": "right",
            "experience_level": "intermediate",
            "constraints": [],
            "injury_history": [],
        },
        "tech_profile": {
            "focus_topics": [],
            "weaknesses": [],
            "strengths": [],
            "recent_reviews": [],
        },
        "health_profile": {
            "fatigue_level": "",
            "risk_flags": [],
            "recent_metrics": [],
        },
        "preferences": {
            "reply_style": "concise",
            "preferred_language": "zh-CN",
            "wants_proactive_reminder": False,
        },
        "last_updated_at": "",
    }


def load_coach_profile(agent_name: str = "badminton-coach") -> dict[str, Any]:
    profile_path = get_paths().agent_dir(agent_name) / "coach_profile.json"
    if not profile_path.exists():
        return create_default_coach_profile()

    try:
        data = json.loads(profile_path.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            return data
    except (json.JSONDecodeError, OSError):
        pass
    return create_default_coach_profile()


def save_coach_profile(profile: dict[str, Any], agent_name: str = "badminton-coach") -> Path:
    profile_path = get_paths().agent_dir(agent_name) / "coach_profile.json"
    profile_path.parent.mkdir(parents=True, exist_ok=True)
    profile_path.write_text(json.dumps(profile, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return profile_path


def append_review_log(
    review: PostmatchReview,
    *,
    agent_name: str = "badminton-coach",
    occurred_at: datetime | None = None,
) -> Path:
    timestamp = occurred_at or datetime.now(UTC)
    reviews_dir = get_paths().agent_dir(agent_name) / "memory" / "reviews"
    reviews_dir.mkdir(parents=True, exist_ok=True)
    log_path = reviews_dir / f"{timestamp.date().isoformat()}.md"

    entry_lines = [
        f"## {timestamp.astimezone(UTC).strftime('%H:%M')} UTC",
        f"- 技术问题：{_join_observations(review)}",
        f"- 进步点：{_join_improvements(review)}",
        f"- 下次重点：{_join_focus(review.next_focus)}",
        f"- 总结：{review.summary}",
        "",
    ]

    with log_path.open("a", encoding="utf-8") as handle:
        handle.write("\n".join(entry_lines))

    return log_path


def update_profile_from_postmatch(
    review: PostmatchReview,
    *,
    agent_name: str = "badminton-coach",
    occurred_at: datetime | None = None,
) -> dict[str, Any]:
    timestamp = occurred_at or datetime.now(UTC)
    profile = load_coach_profile(agent_name)
    tech_profile = profile.setdefault("tech_profile", {})

    weaknesses = list(tech_profile.get("weaknesses", []))
    for observation in review.technical_observations:
        weakness_name = _format_observation_name(observation.topic, observation.finding)
        existing = next((item for item in weaknesses if isinstance(item, dict) and item.get("name") == weakness_name), None)
        if existing is None:
            weaknesses.append(
                {
                    "name": weakness_name,
                    "severity": observation.severity,
                    "trend": "stable",
                    "last_seen_at": timestamp.date().isoformat(),
                    "evidence": observation.evidence,
                }
            )
        else:
            existing["severity"] = max(float(existing.get("severity", 0.0)), observation.severity)
            existing["last_seen_at"] = timestamp.date().isoformat()
            existing["evidence"] = observation.evidence
            existing["trend"] = "stable"

    strengths = list(tech_profile.get("strengths", []))
    for improvement in review.improvements:
        if any(isinstance(item, dict) and item.get("name") == improvement.topic for item in strengths):
            continue
        strengths.append({"name": improvement.topic, "evidence": improvement.evidence, "last_seen_at": timestamp.date().isoformat()})

    focus_topics = list(tech_profile.get("focus_topics", []))
    focus_topics.extend(review.next_focus)

    recent_reviews = list(tech_profile.get("recent_reviews", []))
    recent_reviews.append(
        {
            "date": timestamp.date().isoformat(),
            "summary": review.summary,
            "next_focus": review.next_focus,
        }
    )

    tech_profile["weaknesses"] = weaknesses
    tech_profile["strengths"] = strengths
    tech_profile["focus_topics"] = _unique_keep_order(focus_topics)[:5]
    tech_profile["recent_reviews"] = recent_reviews[-5:]
    profile["tech_profile"] = tech_profile
    profile["last_updated_at"] = timestamp.isoformat().replace("+00:00", "Z")
    save_coach_profile(profile, agent_name)
    return profile


def persist_postmatch_review(
    review: PostmatchReview,
    *,
    agent_name: str = "badminton-coach",
    occurred_at: datetime | None = None,
) -> PostmatchPersistenceResult:
    profile = update_profile_from_postmatch(review, agent_name=agent_name, occurred_at=occurred_at)
    log_path = append_review_log(review, agent_name=agent_name, occurred_at=occurred_at)
    return PostmatchPersistenceResult(review=review, profile=profile, review_log_path=log_path)


def process_postmatch_message(
    message: str,
    *,
    agent_name: str = "badminton-coach",
    occurred_at: datetime | None = None,
) -> PostmatchPersistenceResult:
    review = extract_postmatch_review(message)
    return persist_postmatch_review(review, agent_name=agent_name, occurred_at=occurred_at)


def _format_observation_name(topic: str, finding: str) -> str:
    if topic in finding:
        return finding
    return f"{topic}{finding}"


def _join_observations(review: PostmatchReview) -> str:
    if not review.technical_observations:
        return "无明确技术问题"
    return "；".join(f"{item.topic} {item.finding}" for item in review.technical_observations)


def _join_improvements(review: PostmatchReview) -> str:
    if not review.improvements:
        return "无明确进步点"
    return "；".join(f"{item.topic} {item.evidence}" for item in review.improvements)


def _join_focus(items: list[str]) -> str:
    return "、".join(items) if items else "待补充"


def _unique_keep_order(items: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        if item not in seen:
            seen.add(item)
            result.append(item)
    return result
