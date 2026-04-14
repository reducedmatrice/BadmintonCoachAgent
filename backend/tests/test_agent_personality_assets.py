"""Tests for switchable coach personality assets."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import yaml


def _write_agent_with_personality(
    base_dir: Path,
    *,
    agent_name: str = "badminton-coach",
    default_personality: str = "guodegang",
) -> None:
    agent_dir = base_dir / "agents" / agent_name
    personality_dir = agent_dir / "personalities" / "guodegang"
    personality_dir.mkdir(parents=True, exist_ok=True)

    (agent_dir / "config.yaml").write_text(
        yaml.safe_dump(
            {
                "name": agent_name,
                "default_personality": default_personality,
            }
        ),
        encoding="utf-8",
    )
    (agent_dir / "SOUL.md").write_text("Base soul", encoding="utf-8")
    (personality_dir / "persona.md").write_text("郭德纲式教练人格", encoding="utf-8")
    (personality_dir / "meta.json").write_text(
        json.dumps(
            {
                "id": "guodegang",
                "style": {
                    "tone": "strict",
                    "verbosity": "balanced",
                    "questioning_style": "direct",
                    "encouragement_style": "tough_love",
                },
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )


def test_load_agent_personality_uses_default_from_config(tmp_path):
    from deerflow.config.agents_config import load_agent_personality
    from deerflow.config.paths import Paths

    _write_agent_with_personality(tmp_path)

    with patch("deerflow.config.agents_config.get_paths", return_value=Paths(base_dir=tmp_path)):
        asset = load_agent_personality("badminton-coach")

    assert asset is not None
    assert asset.id == "guodegang"
    assert asset.persona == "郭德纲式教练人格"
    assert asset.style == {
        "tone": "strict",
        "verbosity": "balanced",
        "questioning_style": "direct",
        "encouragement_style": "tough_love",
    }


def test_load_agent_personality_returns_none_for_missing_or_invalid_selection(tmp_path):
    from deerflow.config.agents_config import load_agent_personality
    from deerflow.config.paths import Paths

    _write_agent_with_personality(tmp_path)

    with patch("deerflow.config.agents_config.get_paths", return_value=Paths(base_dir=tmp_path)):
        assert load_agent_personality("badminton-coach", personality_id="missing") is None
        assert load_agent_personality("badminton-coach", personality_id="../bad") is None


def test_apply_prompt_template_injects_selected_persona(tmp_path, monkeypatch):
    from deerflow.agents.lead_agent import prompt as prompt_module
    from deerflow.config.paths import Paths

    _write_agent_with_personality(tmp_path)

    monkeypatch.setattr(prompt_module, "_get_memory_context", lambda agent_name=None: "<memory />")
    monkeypatch.setattr(prompt_module, "get_skills_prompt_section", lambda available_skills=None: "")
    monkeypatch.setattr(prompt_module, "get_deferred_tools_prompt_section", lambda: "")

    with patch("deerflow.config.agents_config.get_paths", return_value=Paths(base_dir=tmp_path)):
        rendered = prompt_module.apply_prompt_template(
            agent_name="badminton-coach",
            personality_id="guodegang",
        )

    assert "<soul>" in rendered
    assert '<persona id="guodegang">' in rendered
    assert "郭德纲式教练人格" in rendered
    assert rendered.index("<soul>") < rendered.index('<persona id="guodegang">')
    assert rendered.index('<persona id="guodegang">') < rendered.index("<memory />")


def test_apply_prompt_template_falls_back_to_soul_when_personality_missing(tmp_path, monkeypatch):
    from deerflow.agents.lead_agent import prompt as prompt_module
    from deerflow.config.paths import Paths

    _write_agent_with_personality(tmp_path)

    monkeypatch.setattr(prompt_module, "_get_memory_context", lambda agent_name=None: "<memory />")
    monkeypatch.setattr(prompt_module, "get_skills_prompt_section", lambda available_skills=None: "")
    monkeypatch.setattr(prompt_module, "get_deferred_tools_prompt_section", lambda: "")

    with patch("deerflow.config.agents_config.get_paths", return_value=Paths(base_dir=tmp_path)):
        rendered = prompt_module.apply_prompt_template(
            agent_name="badminton-coach",
            personality_id="missing",
        )

    assert "<soul>" in rendered
    assert "<persona " not in rendered
