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

    lines = [_opening_line("prematch", persona)]
    recall_line = _render_recall_line(payload.get("recall_context"))
    if recall_line:
        lines.append(recall_line)
    if focus_points:
        lines.append(_format_section("今天重点", focus_points))
    if warmup:
        lines.append(_format_section("热身安排", warmup))
    if risk_reminders:
        lines.append(_format_section("风险提醒", risk_reminders))
    question = _render_questions(follow_up_questions, persona)
    if question:
        lines.append(question)
    lines.append(_closing_line(persona))
    return "\n".join(line for line in lines if line)


def _render_postmatch(payload: Mapping[str, Any], persona: CoachPersonaConfig) -> str:
    summary = str(payload.get("summary", "")).strip()
    next_focus = _limit_items(payload.get("next_focus"), persona.verbosity)

    lines = [_opening_line("postmatch", persona)]
    if summary:
        lines.append(summary)
    if next_focus:
        lines.append(_format_section("下次重点", next_focus))
    lines.append(_closing_line(persona))
    return "\n".join(line for line in lines if line)


def _render_health(payload: Mapping[str, Any], persona: CoachPersonaConfig) -> str:
    observations = _limit_items(payload.get("structured_observations"), persona.verbosity)
    actions = _limit_items(payload.get("recovery_actions"), persona.verbosity)
    intensity = str(payload.get("next_session_intensity", "")).strip()
    follow_up = str(payload.get("follow_up_question", "")).strip()

    lines = [_opening_line("health", persona)]
    recall_line = _render_recall_line(payload.get("recall_context"))
    if recall_line:
        lines.append(recall_line)
    if observations:
        lines.append(_format_section("恢复判断", observations))
    if actions:
        lines.append(_format_section("现在怎么做", actions))
    if intensity:
        lines.append(f"下一次强度：{intensity}")
    question = _render_questions([follow_up] if follow_up else [], persona)
    if question:
        lines.append(question)
    lines.append(_closing_line(persona))
    return "\n".join(line for line in lines if line)


def _render_fallback(payload: Mapping[str, Any], persona: CoachPersonaConfig) -> str:
    guidance = str(payload.get("guidance", "")).strip()
    follow_up = str(payload.get("follow_up_question", "")).strip()
    lines = [_opening_line("fallback", persona)]
    if guidance:
        lines.append(guidance)
    question = _render_questions([follow_up] if follow_up else [], persona)
    if question:
        lines.append(question)
    return "\n".join(line for line in lines if line)


def _opening_line(route: str, persona: CoachPersonaConfig) -> str:
    if persona.tone == "strict":
        if route == "health":
            return "先别硬顶强度，先按恢复处理。"
        return "先按计划执行，不要临场乱加内容。"
    if persona.tone == "neutral":
        return "先按这个顺序处理。"
    if route == "health":
        return "先别着急，先把恢复判断做稳。"
    return "先别着急，今天按这个节奏来。"


def _closing_line(persona: CoachPersonaConfig) -> str:
    if persona.encouragement_style == "tough_love":
        return "别偷量，也别逞强，按节奏做完。"
    if persona.encouragement_style == "motivating":
        return "把这几步做好，状态会比你想的更稳。"
    return "先把基础做好，再看身体反馈。"


def _render_questions(questions: list[str], persona: CoachPersonaConfig) -> str:
    cleaned = [item.strip() for item in questions if isinstance(item, str) and item.strip()]
    if not cleaned:
        return ""

    if persona.questioning_style == "direct":
        return f"直接回答我：{cleaned[0]}"
    if persona.questioning_style == "socratic":
        return f"你先自己判断一下：{cleaned[0]}"
    return f"如果你愿意，我们再补一句：{cleaned[0]}"


def _format_section(title: str, items: list[str]) -> str:
    body = " ".join(f"{index}. {item}" for index, item in enumerate(items, start=1))
    return f"{title}：{body}"


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
    return "我回忆到你最近一次相关记录：" + "；".join(tokens) + "。"


def _limit_items(value: Any, verbosity: str) -> list[str]:
    if not isinstance(value, list):
        return []
    items = [str(item).strip() for item in value if str(item).strip()]
    limit = 2 if verbosity == "concise" else 3 if verbosity == "balanced" else 5
    return items[:limit]
