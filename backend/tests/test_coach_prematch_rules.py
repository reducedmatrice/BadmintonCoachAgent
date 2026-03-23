"""Tests for badminton coach prematch advice rules."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

from deerflow.config.paths import Paths
from deerflow.domain.coach.prematch import build_prematch_advice


def _make_paths(base_dir: Path) -> Paths:
    return Paths(base_dir=base_dir)


def test_prematch_uses_structured_profile_weakness(tmp_path: Path):
    agent_dir = tmp_path / "agents" / "badminton-coach"
    agent_dir.mkdir(parents=True)
    profile = {
        "tech_profile": {
            "weaknesses": [
                {"name": "后场步法回位慢", "severity": 0.9},
                {"name": "反手准备偏晚", "severity": 0.5},
            ]
        },
        "health_profile": {"fatigue_level": "medium"},
    }
    (agent_dir / "coach_profile.json").write_text(json.dumps(profile), encoding="utf-8")

    with patch("deerflow.domain.coach.prematch.get_paths", return_value=_make_paths(tmp_path)):
        advice = build_prematch_advice("今晚打双打注意什么", memory_data={"facts": []})

    assert any("后场步法回位慢" in item for item in advice.focus_points)
    assert "coach_profile:后场步法回位慢" in advice.cited_context
    assert any("七成" in item for item in advice.risk_reminders)


def test_prematch_uses_recent_review_logs_when_profile_missing(tmp_path: Path):
    review_dir = tmp_path / "agents" / "badminton-coach" / "memory" / "reviews"
    review_dir.mkdir(parents=True)
    (review_dir / "2026-03-22.md").write_text(
        "# 复盘\n- 下次重点：反手准备要更早，别等球到身前再处理。\n",
        encoding="utf-8",
    )

    with patch("deerflow.domain.coach.prematch.get_paths", return_value=_make_paths(tmp_path)):
        advice = build_prematch_advice("今晚打球注意什么", memory_data={"facts": []})

    assert any("反手" in item for item in advice.focus_points)
    assert "review_log:2026-03-22.md" in advice.cited_context


def test_prematch_falls_back_to_generic_guidance_without_history(tmp_path: Path):
    with patch("deerflow.domain.coach.prematch.get_paths", return_value=_make_paths(tmp_path)):
        advice = build_prematch_advice("今晚打球注意什么", memory_data={"facts": []})

    assert advice.cited_context == []
    assert any("启动步法" in item or "回位节奏" in item for item in advice.focus_points)
    assert any("前 15 分钟" in item for item in advice.risk_reminders)


def test_prematch_weather_and_constraints_influence_risk_reminders(tmp_path: Path):
    agent_dir = tmp_path / "agents" / "badminton-coach"
    agent_dir.mkdir(parents=True)
    profile = {
        "athlete_profile": {"constraints": ["久坐"]},
        "health_profile": {"fatigue_level": "high"},
        "tech_profile": {"weaknesses": []},
    }
    (agent_dir / "coach_profile.json").write_text(json.dumps(profile), encoding="utf-8")

    with patch("deerflow.domain.coach.prematch.get_paths", return_value=_make_paths(tmp_path)):
        advice = build_prematch_advice(
            "今晚练杀球",
            memory_data={"facts": []},
            weather={"temperature_c": 30, "humidity": 82, "condition": "阵雨"},
        )

    assert any("补水" in item and "60-75 分钟" in item for item in advice.risk_reminders)
    assert any("久坐" in item for item in advice.risk_reminders)
    assert any("七成" in item for item in advice.risk_reminders)
    assert any(context.startswith("weather:") for context in advice.cited_context)


def test_prematch_degrades_gracefully_when_weather_context_missing(tmp_path: Path):
    with patch("deerflow.domain.coach.prematch.get_paths", return_value=_make_paths(tmp_path)):
        advice = build_prematch_advice(
            "今晚打双打注意什么",
            memory_data={"facts": []},
            weather={"degraded": True, "degrade_reason": "weather_lookup_failed", "source": "weather.current"},
        )

    assert any("未获取到天气上下文" in item for item in advice.risk_reminders)
