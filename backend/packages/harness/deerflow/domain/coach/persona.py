"""Coach persona schema and merge helpers."""

from __future__ import annotations

from typing import Any, Literal, Mapping

from pydantic import BaseModel, ConfigDict, Field

CoachTone = Literal["supportive", "neutral", "strict"]
CoachStrictness = Literal["low", "medium", "high"]
CoachVerbosity = Literal["concise", "balanced", "detailed"]
CoachQuestioningStyle = Literal["direct", "guided", "socratic"]
CoachEncouragementStyle = Literal["calm", "motivating", "tough_love"]

_PROTECTED_OVERRIDE_FIELDS = {
    "risk_level",
    "safety_gate",
    "route",
    "primary_intent",
    "secondary_intents",
}


class CoachPersonaConfig(BaseModel):
    """Structured coach persona configuration.

    This schema is intentionally scoped to response style only.
    It must not control routing or safety decisions.
    """

    tone: CoachTone = Field(default="supportive")
    strictness: CoachStrictness = Field(default="medium")
    verbosity: CoachVerbosity = Field(default="concise")
    questioning_style: CoachQuestioningStyle = Field(default="guided")
    encouragement_style: CoachEncouragementStyle = Field(default="calm")

    model_config = ConfigDict(extra="forbid")


class CoachPersonaOverride(BaseModel):
    """Optional persona override fields for task/session scope."""

    tone: CoachTone | None = None
    strictness: CoachStrictness | None = None
    verbosity: CoachVerbosity | None = None
    questioning_style: CoachQuestioningStyle | None = None
    encouragement_style: CoachEncouragementStyle | None = None

    model_config = ConfigDict(extra="allow")


def default_coach_persona() -> CoachPersonaConfig:
    """Return the default coach persona."""
    return CoachPersonaConfig()


def _normalize_personality_id(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    normalized = value.strip()
    return normalized or None


def merge_coach_persona(
    base: CoachPersonaConfig,
    override: Mapping[str, Any] | None,
) -> tuple[CoachPersonaConfig, list[str]]:
    """Merge persona override while protecting routing/safety boundaries.

    Returns:
        A tuple of (merged_persona, ignored_keys).
    """
    if not override:
        return base, []

    ignored_keys: list[str] = []
    filtered: dict[str, Any] = {}
    allowed_fields = set(CoachPersonaOverride.model_fields.keys())
    for key, value in override.items():
        if key in _PROTECTED_OVERRIDE_FIELDS:
            ignored_keys.append(key)
            continue
        if key not in allowed_fields:
            ignored_keys.append(key)
            continue
        filtered[key] = value

    persona_override = CoachPersonaOverride.model_validate(filtered)
    merged = base.model_copy(update=persona_override.model_dump(exclude_none=True))
    return merged, ignored_keys


def build_agent_coach_persona(
    agent_name: str = "badminton-coach",
    *,
    personality_id: str | None = None,
) -> tuple[CoachPersonaConfig, list[str]]:
    """Resolve base persona for an agent from its selected personality style."""
    from deerflow.config.agents_config import load_agent_personality_style

    style = load_agent_personality_style(agent_name, personality_id=personality_id)
    return merge_coach_persona(default_coach_persona(), style)


def resolve_coach_persona_overrides(context: Mapping[str, Any] | None) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    """Resolve session/task persona override layers from runtime context."""
    if not context:
        return None, None

    session_override: dict[str, Any] | None = None
    task_override: dict[str, Any] | None = None

    raw_overrides = context.get("persona_overrides")
    if isinstance(raw_overrides, Mapping):
        raw_session = raw_overrides.get("session")
        raw_task = raw_overrides.get("task")
        if isinstance(raw_session, Mapping):
            session_override = dict(raw_session)
        if isinstance(raw_task, Mapping):
            task_override = dict(raw_task)

    if session_override is None and isinstance(context.get("session_persona"), Mapping):
        session_override = dict(context["session_persona"])
    if task_override is None and isinstance(context.get("task_persona"), Mapping):
        task_override = dict(context["task_persona"])

    return session_override, task_override


def resolve_coach_personality_id(context: Mapping[str, Any] | None) -> str | None:
    """Resolve selected personality id from runtime context."""
    if not context:
        return None

    persona_overrides = context.get("persona_overrides")
    if isinstance(persona_overrides, Mapping):
        personality_id = _normalize_personality_id(persona_overrides.get("personality_id"))
        if personality_id:
            return personality_id

    return _normalize_personality_id(context.get("personality_id"))


def resolve_coach_persona(
    base: CoachPersonaConfig,
    context: Mapping[str, Any] | None,
) -> tuple[CoachPersonaConfig, dict[str, list[str]]]:
    """Apply session/task persona overrides with task taking precedence."""
    session_override, task_override = resolve_coach_persona_overrides(context)

    resolved = base
    ignored: dict[str, list[str]] = {"session": [], "task": []}
    resolved, ignored["session"] = merge_coach_persona(resolved, session_override)
    resolved, ignored["task"] = merge_coach_persona(resolved, task_override)
    return resolved, ignored


def resolve_runtime_coach_persona(
    context: Mapping[str, Any] | None,
    *,
    agent_name: str = "badminton-coach",
) -> tuple[CoachPersonaConfig, dict[str, list[str]]]:
    """Resolve the full runtime persona: agent personality defaults + overrides."""
    personality_id = resolve_coach_personality_id(context)
    base, personality_ignored = build_agent_coach_persona(agent_name, personality_id=personality_id)
    resolved, ignored = resolve_coach_persona(base, context)
    ignored["personality"] = personality_ignored
    return resolved, ignored
