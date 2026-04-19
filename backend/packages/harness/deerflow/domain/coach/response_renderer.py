"""Persona-aware response rendering helpers for coach routes."""

from __future__ import annotations

from typing import Any, Mapping

from .persona import CoachPersonaConfig, default_coach_persona


def resolve_persona_config(persona: CoachPersonaConfig | Mapping[str, Any] | None) -> CoachPersonaConfig:
    """Normalize loose persona input into a validated config."""
    if isinstance(persona, CoachPersonaConfig):
        return persona
    if isinstance(persona, Mapping):
        return CoachPersonaConfig.model_validate(dict(persona))
    return default_coach_persona()


def render_coach_route_payload(
    route: str,
    payload: Mapping[str, Any],
    *,
    persona: CoachPersonaConfig | Mapping[str, Any] | None = None,
) -> str:
    """Render route payload into a compact persona-aware response."""
    resolved_persona = resolve_persona_config(persona)
    if route == "prematch":
        return _render_prematch(payload, resolved_persona)
    if route == "postmatch":
        return _render_postmatch(payload, resolved_persona)
    if route == "health":
        return _render_health(payload, resolved_persona)
    return _render_fallback(payload, resolved_persona)


def _render_prematch(payload: Mapping[str, Any], persona: CoachPersonaConfig) -> str:
    focus_points = _limit_items(payload.get("focus_points"), persona.verbosity)
    warmup = _limit_items(payload.get("warmup"), persona.verbosity)
    risk_reminders = _limit_items(payload.get("risk_reminders"), persona.verbosity)
    follow_up_questions = _limit_items(payload.get("follow_up_questions"), persona.verbosity)

    lines: list[str] = []
    recall_line = _render_recall_line(payload.get("recall_context"))
    if recall_line:
        lines.append(recall_line)

    opening = _render_prematch_opening(focus_points, risk_reminders, persona)
    if opening:
        lines.append(opening)
    if warmup:
        lines.append(_render_warmup_paragraph(warmup, persona))
    question = _render_questions(follow_up_questions, persona)
    if question:
        lines.append(question)
    return "\n".join(line for line in lines if line)


def _render_postmatch(payload: Mapping[str, Any], persona: CoachPersonaConfig) -> str:
    summary = str(payload.get("summary", "")).strip()
    next_focus = _limit_items(payload.get("next_focus"), persona.verbosity)

    lines: list[str] = []
    if summary:
        lines.append(summary)
    if next_focus:
        lines.append(_render_postmatch_follow_up(next_focus, persona))
    return "\n".join(line for line in lines if line)


def _render_health(payload: Mapping[str, Any], persona: CoachPersonaConfig) -> str:
    observations = _limit_items(payload.get("structured_observations"), persona.verbosity)
    actions = _limit_items(payload.get("recovery_actions"), persona.verbosity)
    intensity = str(payload.get("next_session_intensity", "")).strip()
    follow_up = str(payload.get("follow_up_question", "")).strip()

    lines: list[str] = []
    recall_line = _render_recall_line(payload.get("recall_context"))
    if recall_line:
        lines.append(recall_line)
    first_paragraph = _render_health_opening(observations, actions, persona)
    if first_paragraph:
        lines.append(first_paragraph)
    if intensity:
        lines.append(_render_intensity_paragraph(intensity, persona))
    question = _render_questions([follow_up] if follow_up else [], persona)
    if question:
        lines.append(question)
    return "\n".join(line for line in lines if line)


def _render_fallback(payload: Mapping[str, Any], persona: CoachPersonaConfig) -> str:
    guidance = str(payload.get("guidance", "")).strip()
    follow_up = str(payload.get("follow_up_question", "")).strip()
    lines: list[str] = []
    if guidance:
        lines.append(guidance)
    question = _render_questions([follow_up] if follow_up else [], persona)
    if question:
        lines.append(question)
    return "\n".join(line for line in lines if line)


def _render_questions(questions: list[str], persona: CoachPersonaConfig) -> str:
    cleaned = [item.strip() for item in questions if isinstance(item, str) and item.strip()]
    if not cleaned:
        return ""

    if persona.questioning_style == "direct":
        return f"你先直接回我一句：{cleaned[0]}"
    if persona.questioning_style == "socratic":
        return f"你也先自己判断一下：{cleaned[0]}"
    return f"你再补我一句：{cleaned[0]}"


def _render_prematch_opening(
    focus_points: list[str],
    risk_reminders: list[str],
    persona: CoachPersonaConfig,
) -> str:
    sentences: list[str] = []
    if focus_points:
        lead = "你今天上来先别铺太开" if persona.tone != "strict" else "你今天别一上来就乱加内容"
        sentences.append(f"{lead}，先把{_join_items(focus_points)}抓住。")
    if risk_reminders:
        risk_prefix = "另外你自己收着点" if persona.tone != "strict" else "还有一条你必须记住"
        sentences.append(f"{risk_prefix}，{_join_items(risk_reminders)}。")
    return "".join(sentences)


def _render_warmup_paragraph(items: list[str], persona: CoachPersonaConfig) -> str:
    if not items:
        return ""
    prefix = "热身这块你按这个顺序走就行" if persona.tone != "strict" else "热身别省，按这个顺序做"
    return f"{prefix}：\n{_render_bullets(items)}"


def _render_postmatch_follow_up(items: list[str], persona: CoachPersonaConfig) -> str:
    if not items:
        return ""
    prefix = "下次你就继续盯" if persona.tone != "strict" else "下次继续把这件事盯住"
    return f"{prefix}{_join_items(items)}。"


def _render_health_opening(
    observations: list[str],
    actions: list[str],
    persona: CoachPersonaConfig,
) -> str:
    sentences: list[str] = []
    if observations:
        lead = "按你现在这个情况看" if persona.tone != "strict" else "按现在这些信号看"
        sentences.append(f"{lead}，更像是{_join_items(observations)}。")
    if actions:
        action_prefix = "你先别急着上量，先做" if persona.tone != "strict" else "先别往上顶，先做"
        sentences.append(f"{action_prefix}{_join_items(actions)}。")
    return "".join(sentences)


def _render_intensity_paragraph(intensity: str, persona: CoachPersonaConfig) -> str:
    prefix = "下一次强度先放在" if persona.tone != "strict" else "下一次强度先压在"
    return f"{prefix}{intensity}。"


def _join_items(items: list[str]) -> str:
    if not items:
        return ""
    if len(items) == 1:
        return items[0]
    if len(items) == 2:
        return f"{items[0]}，再把{items[1]}"
    head = "，".join(items[:-1])
    return f"{head}，最后把{items[-1]}"


def _render_bullets(items: list[str]) -> str:
    return "\n".join(f"- {item}" for item in items)


def _render_recall_line(recall_context: Any) -> str:
    if not isinstance(recall_context, Mapping):
        return ""
    if recall_context.get("should_mention") is not True:
        return ""

    summary = str(recall_context.get("summary") or "").strip()
    recorded_at = str(recall_context.get("recorded_at") or "").strip()
    risk_level = str(recall_context.get("risk_level") or "").strip()
    mention_reason = str(recall_context.get("mention_reason") or "").strip()

    tokens: list[str] = []
    if recorded_at:
        tokens.append(f"记录时间 {recorded_at}")
    if summary:
        tokens.append(summary)
    if risk_level:
        tokens.append(f"风险等级 {risk_level}")
    if mention_reason:
        tokens.append(f"触发原因 {mention_reason}")

    if not tokens:
        return ""
    return "我翻了下你最近一次相关记录：" + "；".join(tokens) + "。"


def _limit_items(value: Any, verbosity: str) -> list[str]:
    if not isinstance(value, list):
        return []
    items = [str(item).strip() for item in value if str(item).strip()]
    limit = 2 if verbosity == "concise" else 3 if verbosity == "balanced" else 5
    return items[:limit]
