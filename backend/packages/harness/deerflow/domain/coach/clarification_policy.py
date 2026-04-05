"""Clarification policy helpers for coach intake."""

from __future__ import annotations

from typing import Any, Mapping

from .intent import CoachIntent
from .persona import CoachPersonaConfig, default_coach_persona


def build_clarification_request(
    intent: CoachIntent,
    *,
    persona: CoachPersonaConfig | Mapping[str, Any] | None = None,
) -> dict[str, Any] | None:
    """Build a structured clarification request from intent and persona."""
    if not intent.needs_clarification:
        return None

    resolved_persona = _resolve_persona(persona)
    question, options = _question_for_intent(intent, resolved_persona)
    if not question:
        return None

    return {
        "question": question,
        "clarification_type": "missing_info",
        "reason": intent.clarification_reason,
        "missing_slots": list(intent.missing_slots),
        "options": options,
    }


def _resolve_persona(persona: CoachPersonaConfig | Mapping[str, Any] | None) -> CoachPersonaConfig:
    if isinstance(persona, CoachPersonaConfig):
        return persona
    if isinstance(persona, Mapping):
        return CoachPersonaConfig.model_validate(dict(persona))
    return default_coach_persona()


def _question_for_intent(intent: CoachIntent, persona: CoachPersonaConfig) -> tuple[str, list[str]]:
    prefix = _question_prefix(persona)

    if intent.primary_intent == "prematch":
        missing = set(intent.missing_slots)
        if "session_goal" in missing:
            return (
                f"{prefix}你这次更偏向哪种场景？",
                ["双打赛前提醒", "单打赛前提醒", "通用热身和注意事项"],
            )
        return (
            f"{prefix}你更想先解决赛前准备里的哪一块？",
            ["热身安排", "战术提醒", "强度控制"],
        )

    if intent.primary_intent == "postmatch":
        return (
            f"{prefix}这次你更想先复盘哪部分？",
            ["技术问题", "体能和节奏", "下次重点"],
        )

    if intent.primary_intent == "health":
        return (
            f"{prefix}你现在更接近哪种情况？",
            ["单纯疲劳", "局部酸痛", "明显疼痛或受伤风险"],
        )

    return (
        f"{prefix}你现在希望我先帮你做哪类判断？",
        ["赛前准备", "赛后复盘", "恢复建议"],
    )


def _question_prefix(persona: CoachPersonaConfig) -> str:
    if persona.questioning_style == "direct":
        return "直接说，"
    if persona.questioning_style == "socratic":
        return "你先判断一下，"
    return "先补一条信息，"
