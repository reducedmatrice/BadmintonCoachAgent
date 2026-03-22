"""Rule-based prematch planner for the badminton coach agent."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from deerflow.agents.memory.updater import get_memory_data
from deerflow.config.paths import get_paths


@dataclass
class PrematchAdvice:
    focus_points: list[str]
    warmup: list[str]
    risk_reminders: list[str]
    cited_context: list[str]
    follow_up_questions: list[str]


def load_coach_profile(agent_name: str = "badminton-coach") -> dict[str, Any] | None:
    """Load the structured coach profile if it exists."""
    profile_path = get_paths().agent_dir(agent_name) / "coach_profile.json"
    if not profile_path.exists():
        return None

    try:
        return json.loads(profile_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


def load_recent_review_logs(agent_name: str = "badminton-coach", limit: int = 3) -> list[tuple[Path, str]]:
    """Load the newest review log markdown files for the agent."""
    reviews_dir = get_paths().agent_dir(agent_name) / "memory" / "reviews"
    if not reviews_dir.exists():
        return []

    review_files = sorted((path for path in reviews_dir.glob("*.md") if path.is_file()), reverse=True)
    loaded: list[tuple[Path, str]] = []
    for review_path in review_files[:limit]:
        try:
            loaded.append((review_path, review_path.read_text(encoding="utf-8")))
        except OSError:
            continue
    return loaded


def build_prematch_advice(
    message: str,
    *,
    agent_name: str = "badminton-coach",
    memory_data: dict[str, Any] | None = None,
    coach_profile: dict[str, Any] | None = None,
    review_logs: list[tuple[Path, str]] | None = None,
    weather: dict[str, Any] | None = None,
) -> PrematchAdvice:
    """Generate a prematch plan using available history and current context."""
    normalized_message = message.strip()
    memory = memory_data if memory_data is not None else get_memory_data(agent_name)
    profile = coach_profile if coach_profile is not None else load_coach_profile(agent_name)
    reviews = review_logs if review_logs is not None else load_recent_review_logs(agent_name)

    focus_points: list[str] = []
    warmup: list[str] = ["先做 8-10 分钟慢跑或跳绳，把心率和脚下节奏带起来。"]
    risk_reminders: list[str] = []
    cited_context: list[str] = []

    primary_focus = _infer_primary_focus(normalized_message)
    if primary_focus:
        focus_points.append(primary_focus)

    profile_signal = _extract_profile_signal(profile)
    if profile_signal is not None:
        signal, citation = profile_signal
        focus_points.append(f"延续处理历史弱项：{signal}。")
        cited_context.append(citation)

    review_signal = _extract_review_signal(reviews)
    if review_signal is not None:
        signal, citation = review_signal
        focus_points.append(f"结合最近训练记录，今天继续盯住：{signal}。")
        cited_context.append(citation)

    memory_signal = _extract_memory_signal(memory)
    if memory_signal is not None and not cited_context:
        focus_points.append(f"从长期记忆看，今天别忽略：{memory_signal}。")
        cited_context.append(f"memory:{memory_signal}")

    if len(focus_points) == 1 and cited_context:
        focus_points.append("前 15 分钟先把节奏打顺，再逐步抬强度，不要一上来就拼速度。")

    if not cited_context and len(focus_points) == 1:
        focus_points.append("没有可靠历史记录时，先用通用方案：启动、回位和出手前准备做到稳定。")

    combined_focus = " ".join(focus_points)
    if any(keyword in combined_focus for keyword in ("步法", "回位", "后场", "启动")):
        warmup.append("补 2 组启动步法、后撤回位和跨步蹬转，先把脚下节奏打开。")
    if any(keyword in combined_focus for keyword in ("反手", "杀球", "发力", "肩")):
        warmup.append("补 2 组肩袖、前臂和手腕激活，再做空挥拍进入击球状态。")
    if len(warmup) == 1:
        warmup.append("做 1 组空挥拍和小步启动，让击球准备和落点意识先回来。")

    _extend_risk_reminders(risk_reminders, profile, weather)

    if not risk_reminders:
        risk_reminders.append("前 15 分钟先把强度压住，优先找节奏和落点，不要直接顶满。")

    return PrematchAdvice(
        focus_points=_unique_keep_order(focus_points)[:3],
        warmup=_unique_keep_order(warmup)[:3],
        risk_reminders=_unique_keep_order(risk_reminders)[:3],
        cited_context=_unique_keep_order(cited_context),
        follow_up_questions=_build_follow_up_questions(normalized_message),
    )


def _infer_primary_focus(message: str) -> str:
    if "双打" in message:
        return "今天先把双打前后轮转、封网启动和第二拍衔接做稳。"
    if "单打" in message:
        return "今天先把单打启动、后撤和回位节奏做稳。"
    if "后场" in message or "步法" in message:
        return "今天优先盯后场启动、后撤和回位，不要只顾出手。"
    if "反手" in message:
        return "今天先把反手准备提前，保证来球一到就能完成站位和出手。"
    if "杀球" in message:
        return "今天先把杀球发力和落点衔接做稳，别只追求一拍发狠。"
    return "今天先把启动步法、击球准备和回位节奏做稳。"


def _extract_profile_signal(profile: dict[str, Any] | None) -> tuple[str, str] | None:
    if not isinstance(profile, dict):
        return None

    tech_profile = profile.get("tech_profile")
    if not isinstance(tech_profile, dict):
        return None

    weaknesses = tech_profile.get("weaknesses")
    if not isinstance(weaknesses, list):
        return None

    ranked: list[tuple[float, str]] = []
    for item in weaknesses:
        if not isinstance(item, dict):
            continue
        name = item.get("name")
        if not isinstance(name, str) or not name.strip():
            continue
        severity = item.get("severity", 0.0)
        try:
            ranked.append((float(severity), name.strip()))
        except (TypeError, ValueError):
            ranked.append((0.0, name.strip()))

    if not ranked:
        return None

    ranked.sort(reverse=True)
    top_name = ranked[0][1]
    return top_name, f"coach_profile:{top_name}"


def _extract_review_signal(review_logs: list[tuple[Path, str]]) -> tuple[str, str] | None:
    keywords = ("下次重点", "问题", "弱项", "后场", "反手", "步法", "回位", "杀球")
    for review_path, content in review_logs:
        for raw_line in content.splitlines():
            line = raw_line.strip().lstrip("-*# ").strip()
            if not line:
                continue
            if any(keyword in line for keyword in keywords):
                return line, f"review_log:{review_path.name}"
    return None


def _extract_memory_signal(memory_data: dict[str, Any]) -> str | None:
    facts = memory_data.get("facts", [])
    if not isinstance(facts, list):
        return None
    for fact in facts:
        if not isinstance(fact, dict):
            continue
        content = fact.get("content")
        if isinstance(content, str) and content.strip():
            return content.strip()
    return None


def _extend_risk_reminders(
    reminders: list[str],
    profile: dict[str, Any] | None,
    weather: dict[str, Any] | None,
) -> None:
    if not isinstance(profile, dict):
        profile = {}

    athlete_profile = profile.get("athlete_profile")
    if isinstance(athlete_profile, dict):
        constraints = athlete_profile.get("constraints", [])
        if isinstance(constraints, list) and any(isinstance(item, str) and "久坐" in item for item in constraints):
            reminders.append("久坐后别直接抢速度，先把髋部、胸椎和肩背打开。")

    health_profile = profile.get("health_profile")
    if isinstance(health_profile, dict):
        fatigue_level = str(health_profile.get("fatigue_level", "")).lower()
        if fatigue_level in {"medium", "high"}:
            reminders.append("最近疲劳不低，今天前半段先把强度控制在七成左右。")

    if isinstance(weather, dict):
        temperature = weather.get("temperature_c")
        humidity = weather.get("humidity")
        condition = str(weather.get("condition", ""))
        if isinstance(temperature, (int, float)) and temperature >= 28:
            reminders.append("天气偏热，训练前中后都要补水，第一局别把强度一下顶满。")
        if isinstance(humidity, (int, float)) and humidity >= 80:
            reminders.append("湿度偏高，脚下会更沉，前半段先把节奏放稳。")
        if "雨" in condition:
            reminders.append("天气条件一般时更要重视启动和止滑，别急着上强对抗。")


def _build_follow_up_questions(message: str) -> list[str]:
    questions: list[str] = []
    if "单打" not in message and "双打" not in message:
        questions.append("今天是单打还是双打？")
    if not any(keyword in message for keyword in ("后场", "反手", "杀球", "步法", "体能")):
        questions.append("今晚你最想优先练哪一项？")
    return questions[:2]


def _unique_keep_order(items: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        if item not in seen:
            seen.add(item)
            result.append(item)
    return result
