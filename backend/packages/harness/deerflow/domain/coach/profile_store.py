"""Persistence helpers for the badminton coach profile and review logs."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from deerflow.config.paths import get_paths

from .health_image import HealthImageObservation, HealthRecoveryAdvice
from .multimodal_schema import ExerciseScreenshotRecord
from .postmatch import PostmatchReview, extract_postmatch_review


@dataclass
class PrematchPersistenceResult:
    extracted: dict[str, list[str]]
    profile: dict[str, Any]
    profile_path: Path
    persisted: bool


@dataclass
class PostmatchPersistenceResult:
    review: PostmatchReview
    profile: dict[str, Any]
    review_log_path: Path


@dataclass
class HealthPersistenceResult:
    observation: HealthImageObservation
    advice: HealthRecoveryAdvice
    profile: dict[str, Any]
    profile_path: Path


@dataclass
class ExercisePersistenceResult:
    record: ExerciseScreenshotRecord
    profile: dict[str, Any]
    review_log_path: Path | None
    profile_path: Path | None
    wrote_event_evidence: bool
    updated_profile: bool


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
            "training_preferences": [],
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


def append_exercise_review_log(
    record: ExerciseScreenshotRecord,
    *,
    agent_name: str = "badminton-coach",
    occurred_at: datetime | None = None,
    thread_id: str | None = None,
    source_message_id: str | None = None,
) -> Path:
    timestamp = occurred_at or datetime.now(UTC)
    reviews_dir = get_paths().agent_dir(agent_name) / "memory" / "reviews"
    reviews_dir.mkdir(parents=True, exist_ok=True)
    log_path = reviews_dir / f"{timestamp.date().isoformat()}.md"

    missing = ", ".join(record.missing_fields) if record.missing_fields else ""

    def _fmt(value: float | None, suffix: str) -> str:
        if value is None:
            return "（缺失）"
        if value.is_integer():
            return f"{int(value)}{suffix}"
        return f"{value:.1f}{suffix}"

    entry_lines = [
        f"## {timestamp.astimezone(UTC).strftime('%H:%M')} UTC",
        f"- 记录类型：{record.record_type}",
        f"- 运动类型：{record.sport_type or 'unknown'}",
        f"- 截图类型：{record.screenshot_type or 'unknown'}",
        f"- 时长：{_fmt(record.duration_min, 'min')}",
        f"- 平均心率：{_fmt(record.avg_heart_rate, 'bpm')}",
        f"- 最高心率：{_fmt(record.max_heart_rate, 'bpm')}",
        f"- 训练负荷：{_fmt(record.training_load, '')}",
        f"- 有氧压力：{_fmt(record.aerobic_stress, '')}",
        f"- 热量：{_fmt(record.calories_kcal, 'kcal')}",
        f"- 恢复时间：{_fmt(record.recovery_hours, 'h')}",
        f"- 置信度：{record.confidence:.2f}",
        f"- 缺失字段：{missing or '（无）'}",
    ]
    if record.raw_summary:
        entry_lines.append(f"- 抽取摘要：{record.raw_summary}")
    if thread_id:
        entry_lines.append(f"- thread_id：{thread_id}")
    if source_message_id:
        entry_lines.append(f"- source_message_id：{source_message_id}")
    entry_lines.append("")

    with log_path.open("a", encoding="utf-8") as handle:
        handle.write("\n".join(entry_lines))

    return log_path


def _infer_exercise_fatigue_level(record: ExerciseScreenshotRecord) -> str:
    # Conservative heuristic: prefer medium/high when load or recovery hints are large.
    if (record.training_load or 0) >= 160 or (record.recovery_hours or 0) >= 24:
        return "high"
    if (record.avg_heart_rate or 0) >= 160 and (record.duration_min or 0) >= 75:
        return "high"
    if (record.duration_min or 0) >= 110:
        return "high"

    if (record.training_load or 0) >= 110 or (record.recovery_hours or 0) >= 16:
        return "medium"
    if (record.avg_heart_rate or 0) >= 145 or (record.duration_min or 0) >= 60:
        return "medium"

    return "low"


def update_profile_from_exercise_record(
    record: ExerciseScreenshotRecord,
    *,
    agent_name: str = "badminton-coach",
    occurred_at: datetime | None = None,
) -> dict[str, Any]:
    timestamp = occurred_at or datetime.now(UTC)
    profile = load_coach_profile(agent_name)
    health_profile = profile.setdefault("health_profile", {})

    fatigue_level = _infer_exercise_fatigue_level(record)
    health_profile["fatigue_level"] = fatigue_level

    risk_flags = [str(item) for item in health_profile.get("risk_flags", []) if isinstance(item, str)]
    risk_flags.append(f"exercise:{fatigue_level}")
    health_profile["risk_flags"] = _unique_keep_order(risk_flags)[-12:]

    recent_metrics = list(health_profile.get("recent_metrics", []))
    recent_metrics.append(
        {
            "source": "exercise_screenshot",
            "recorded_at": timestamp.date().isoformat(),
            "sport_type": record.sport_type or "unknown",
            "duration_min": record.duration_min,
            "avg_heart_rate": record.avg_heart_rate,
            "max_heart_rate": record.max_heart_rate,
            "training_load": record.training_load,
            "aerobic_stress": record.aerobic_stress,
            "calories_kcal": record.calories_kcal,
            "recovery_hours": record.recovery_hours,
            "confidence": record.confidence,
            "missing_fields": record.missing_fields,
            "raw_summary": record.raw_summary,
            "fatigue_level": fatigue_level,
        }
    )
    health_profile["recent_metrics"] = recent_metrics[-10:]
    profile["health_profile"] = health_profile
    profile["last_updated_at"] = timestamp.isoformat().replace("+00:00", "Z")
    save_coach_profile(profile, agent_name)
    return profile


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


def persist_health_observation(
    observation: HealthImageObservation,
    advice: HealthRecoveryAdvice,
    *,
    agent_name: str = "badminton-coach",
    occurred_at: datetime | None = None,
) -> HealthPersistenceResult:
    timestamp = occurred_at or datetime.now(UTC)
    profile = load_coach_profile(agent_name)
    health_profile = profile.setdefault("health_profile", {})

    existing_flags = [str(item) for item in health_profile.get("risk_flags", []) if isinstance(item, str)]
    if advice.risk_level in {"medium", "high"}:
        existing_flags.append(f"health:{observation.screenshot_type}:{advice.risk_level}")

    recent_metrics = list(health_profile.get("recent_metrics", []))
    recent_metrics.append(
        {
            "date": timestamp.date().isoformat(),
            "source": observation.screenshot_type,
            "risk_level": advice.risk_level,
            "observed_metrics": observation.observed_metrics,
            "observations": observation.observations,
            "next_session_intensity": advice.next_session_intensity,
        }
    )

    health_profile["fatigue_level"] = _risk_to_fatigue_level(advice.risk_level)
    health_profile["risk_flags"] = _unique_keep_order(existing_flags)[-5:]
    health_profile["recent_metrics"] = recent_metrics[-5:]
    profile["health_profile"] = health_profile
    profile["last_updated_at"] = timestamp.isoformat().replace("+00:00", "Z")
    profile_path = save_coach_profile(profile, agent_name)
    return HealthPersistenceResult(observation=observation, advice=advice, profile=profile, profile_path=profile_path)


def persist_exercise_record(
    record: ExerciseScreenshotRecord,
    *,
    agent_name: str = "badminton-coach",
    occurred_at: datetime | None = None,
    thread_id: str | None = None,
    source_message_id: str | None = None,
    event_min_confidence: float = 0.5,
    profile_min_confidence: float = 0.75,
    allow_event_only: bool = True,
) -> ExercisePersistenceResult:
    """Persist a single extracted exercise record.

    Writeback policy (Spec 3.0):
    - VLM/Schema failure => handled upstream, this function assumes a validated record
    - Low confidence: allow writing event evidence, but skip profile merge
    - Very low confidence: skip all writeback
    """
    timestamp = occurred_at or datetime.now(UTC)
    profile = load_coach_profile(agent_name)
    profile_path = get_paths().agent_dir(agent_name) / "coach_profile.json"

    wrote_event_evidence = False
    updated_profile = False
    review_log_path: Path | None = None
    saved_profile_path: Path | None = None

    if not allow_event_only and record.confidence < profile_min_confidence:
        return ExercisePersistenceResult(
            record=record,
            profile=profile,
            review_log_path=None,
            profile_path=profile_path if profile_path.exists() else None,
            wrote_event_evidence=False,
            updated_profile=False,
        )

    if record.confidence >= event_min_confidence:
        review_log_path = append_exercise_review_log(
            record,
            agent_name=agent_name,
            occurred_at=timestamp,
            thread_id=thread_id,
            source_message_id=source_message_id,
        )
        wrote_event_evidence = True

    if record.confidence >= profile_min_confidence:
        profile = update_profile_from_exercise_record(record, agent_name=agent_name, occurred_at=timestamp)
        saved_profile_path = get_paths().agent_dir(agent_name) / "coach_profile.json"
        updated_profile = True

    return ExercisePersistenceResult(
        record=record,
        profile=profile,
        review_log_path=review_log_path,
        profile_path=saved_profile_path,
        wrote_event_evidence=wrote_event_evidence,
        updated_profile=updated_profile,
    )


def persist_prematch_signal(
    message: str,
    *,
    agent_name: str = "badminton-coach",
    occurred_at: datetime | None = None,
) -> PrematchPersistenceResult:
    timestamp = occurred_at or datetime.now(UTC)
    extracted = _extract_prematch_writeback_signal(message)
    if not any(extracted.values()):
        profile = load_coach_profile(agent_name)
        profile_path = get_paths().agent_dir(agent_name) / "coach_profile.json"
        return PrematchPersistenceResult(extracted=extracted, profile=profile, profile_path=profile_path, persisted=False)

    profile = load_coach_profile(agent_name)

    athlete_profile = profile.setdefault("athlete_profile", {})
    constraints = [str(item) for item in athlete_profile.get("constraints", []) if isinstance(item, str)]
    constraints.extend(extracted["constraints"])
    athlete_profile["constraints"] = _unique_keep_order(constraints)[:8]
    profile["athlete_profile"] = athlete_profile

    preferences = profile.setdefault("preferences", {})
    training_preferences = [str(item) for item in preferences.get("training_preferences", []) if isinstance(item, str)]
    training_preferences.extend(extracted["training_preferences"])
    preferences["training_preferences"] = _unique_keep_order(training_preferences)[:8]
    profile["preferences"] = preferences

    tech_profile = profile.setdefault("tech_profile", {})
    recent_goals = list(tech_profile.get("recent_goals", []))
    for goal in extracted["recent_goals"]:
        recent_goals.append(
            {
                "goal": goal,
                "source": "prematch",
                "recorded_at": timestamp.date().isoformat(),
            }
        )
    deduped_goals: list[dict[str, Any]] = []
    seen_goals: set[str] = set()
    for item in reversed(recent_goals):
        if not isinstance(item, dict):
            continue
        goal = item.get("goal")
        if not isinstance(goal, str) or not goal.strip():
            continue
        normalized_goal = goal.strip()
        if normalized_goal in seen_goals:
            continue
        seen_goals.add(normalized_goal)
        deduped_goals.append(item)
    prioritized_goals = list(reversed(deduped_goals))
    prioritized_goals.sort(key=lambda item: (_prematch_goal_priority(item.get("goal")), item.get("recorded_at", "")), reverse=True)
    tech_profile["recent_goals"] = prioritized_goals[:5]
    profile["tech_profile"] = tech_profile

    profile["last_updated_at"] = timestamp.isoformat().replace("+00:00", "Z")
    profile_path = save_coach_profile(profile, agent_name)
    return PrematchPersistenceResult(extracted=extracted, profile=profile, profile_path=profile_path, persisted=True)


def process_postmatch_message(
    message: str,
    *,
    agent_name: str = "badminton-coach",
    occurred_at: datetime | None = None,
) -> PostmatchPersistenceResult:
    review = extract_postmatch_review(message)
    return persist_postmatch_review(review, agent_name=agent_name, occurred_at=occurred_at)


def _extract_prematch_writeback_signal(message: str) -> dict[str, list[str]]:
    text = " ".join(message.split())
    constraints: list[str] = []
    training_preferences: list[str] = []
    recent_goals: list[str] = []
    preference_triggers = (
        "更想练",
        "想练",
        "优先练",
        "主要练",
        "重点练",
        "多练",
        "加强",
        "补一补",
        "巩固",
        "准备",
        "侧重",
        "偏向",
        "针对",
        "着重",
    )
    goal_triggers = (
        "最近",
        "这周",
        "这两周",
        "近期",
        "月底",
        "下周",
        "这个月",
        "本月",
        "接下来",
        "这阶段",
        "阶段性",
    )
    topic_aliases = {
        "后场步法": ("后场步法", "后撤步法", "后场启动", "后退步法"),
        "步法": ("步法", "脚步", "移动", "启动", "回位", "启动步", "启动速度", "回位节奏"),
        "反手": ("反手", "反手过渡", "反手发力", "反手稳定性", "反手准备"),
        "杀球": ("杀球", "进攻", "重杀", "点杀", "突击"),
        "网前": ("网前", "搓球", "勾对角", "扑球", "放网", "封网", "推扑"),
        "发接发": ("发接发", "发球", "接发", "接发表现", "发接发轮"),
        "高远球": ("高远球", "高远", "拉吊", "拉开"),
        "吊球": ("吊球", "劈吊", "轻吊"),
        "平抽挡": ("平抽挡", "抽挡", "平抽", "快挡"),
        "防守": ("防守", "接杀", "防反", "被动球"),
        "体能": ("体能", "耐力", "爆发", "速度", "多拍", "连续性"),
        "核心稳定": ("核心", "核心稳定", "躯干稳定"),
        "肩部发力": ("肩部发力", "肩发力", "挥拍发力", "发力链"),
    }

    if "久坐" in text:
        constraints.append("久坐后启动偏紧")
    if any(keyword in text for keyword in ("旧伤", "老伤", "恢复期")) and "肩" in text:
        constraints.append("肩部旧伤/恢复期")
    if any(keyword in text for keyword in ("旧伤", "老伤", "恢复期")) and "膝" in text:
        constraints.append("膝部旧伤/恢复期")
    if any(keyword in text for keyword in ("旧伤", "老伤", "恢复期")) and "腰" in text:
        constraints.append("腰部旧伤/恢复期")
    if any(keyword in text for keyword in ("旧伤", "老伤", "恢复期")) and "踝" in text:
        constraints.append("踝部旧伤/恢复期")
    if any(keyword in text for keyword in ("不能连续", "别连续", "不适合连续")) and "高强度" in text:
        constraints.append("不适合连续高强度")
    if any(keyword in text for keyword in ("怕疼", "容易酸", "容易紧", "容易累")) and "肩" in text:
        constraints.append("肩部负荷耐受有限")
    if any(keyword in text for keyword in ("怕疼", "容易酸", "容易紧", "容易累")) and "膝" in text:
        constraints.append("膝部负荷耐受有限")

    if "双打" in text and any(keyword in text for keyword in preference_triggers):
        training_preferences.append("偏双打训练")
    if "单打" in text and any(keyword in text for keyword in preference_triggers):
        training_preferences.append("偏单打训练")
    if "女双" in text:
        training_preferences.append("偏女双训练")
    if "男双" in text:
        training_preferences.append("偏男双训练")
    if "混双" in text:
        training_preferences.append("偏混双训练")
    if any(keyword in text for keyword in preference_triggers):
        for canonical_topic, aliases in topic_aliases.items():
            if any(alias in text for alias in aliases):
                training_preferences.append(f"优先训练{canonical_topic}")

    if any(keyword in text for keyword in goal_triggers):
        if "比赛" in text:
            recent_goals.append("近期以比赛准备为主")
        if any(keyword in text for keyword in ("稳定", "稳定性", "失误少一点", "减少失误", "别那么乱")):
            recent_goals.append("近期目标：提升稳定性")
        if any(keyword in text for keyword in ("节奏", "连贯", "衔接")):
            recent_goals.append("近期目标：提升回合衔接")
        for canonical_topic, aliases in topic_aliases.items():
            if any(alias in text for alias in aliases):
                recent_goals.append(f"近期目标：提升{canonical_topic}")

    return {
        "constraints": _unique_keep_order(constraints),
        "training_preferences": _unique_keep_order(training_preferences),
        "recent_goals": _unique_keep_order(recent_goals),
    }


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


def _risk_to_fatigue_level(risk_level: str) -> str:
    if risk_level == "high":
        return "high"
    if risk_level == "medium":
        return "medium"
    return "low"


def _prematch_goal_priority(goal: Any) -> int:
    if not isinstance(goal, str):
        return 0
    if "比赛准备" in goal:
        return 3
    if "稳定性" in goal or "回合衔接" in goal:
        return 2
    return 1
