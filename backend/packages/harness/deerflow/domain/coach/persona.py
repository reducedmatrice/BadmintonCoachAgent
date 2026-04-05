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
