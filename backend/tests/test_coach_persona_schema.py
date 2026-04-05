"""Tests for coach persona schema and merge boundaries."""

from __future__ import annotations

import pytest

from deerflow.domain.coach.persona import CoachPersonaConfig, default_coach_persona, merge_coach_persona


def test_default_coach_persona_has_expected_values():
    persona = default_coach_persona()

    assert persona.tone == "supportive"
    assert persona.strictness == "medium"
    assert persona.verbosity == "concise"
    assert persona.questioning_style == "guided"
    assert persona.encouragement_style == "calm"


def test_persona_schema_rejects_invalid_field_values():
    with pytest.raises(ValueError):
        CoachPersonaConfig(tone="invalid")  # type: ignore[arg-type]

    with pytest.raises(ValueError):
        CoachPersonaConfig(strictness="extreme")  # type: ignore[arg-type]


def test_merge_coach_persona_applies_allowed_overrides_only():
    base = default_coach_persona()
    merged, ignored = merge_coach_persona(
        base,
        {
            "tone": "strict",
            "verbosity": "detailed",
            "risk_level": "high",
            "route": "health",
            "unknown_key": "value",
        },
    )

    assert merged.tone == "strict"
    assert merged.verbosity == "detailed"
    assert merged.strictness == "medium"
    assert "risk_level" in ignored
    assert "route" in ignored
    assert "unknown_key" in ignored


def test_merge_coach_persona_keeps_boundaries_when_override_empty():
    base = default_coach_persona()
    merged, ignored = merge_coach_persona(base, None)

    assert merged == base
    assert ignored == []
