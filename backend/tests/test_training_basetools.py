"""Tests for training data BaseTools."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

from deerflow.config.paths import Paths


def _make_paths(base_dir: Path) -> Paths:
    return Paths(base_dir=base_dir)


def _write_profile(base_dir: Path, profile: dict) -> None:
    agent_dir = base_dir / "agents" / "badminton-coach"
    agent_dir.mkdir(parents=True, exist_ok=True)
    (agent_dir / "coach_profile.json").write_text(
        json.dumps(profile, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def test_query_training_log_tool_exists():
    from deerflow.tools.builtins.training_tools import query_training_log
    assert query_training_log.name == "query_training_log"


def test_get_body_metrics_trend_tool_exists():
    from deerflow.tools.builtins.training_tools import get_body_metrics_trend_tool
    assert get_body_metrics_trend_tool.name == "get_body_metrics_trend"


def test_query_training_log_returns_summary(tmp_path: Path):
    profile = {
        "training_log": [
            {"date": "2026-05-19", "session_type": "match", "summary": "双打", "focus_areas": ["反手"], "issues": ["反手失误"], "improvements": []},
            {"date": "2026-05-21", "session_type": "training", "summary": "步法", "focus_areas": ["步法"], "issues": [], "improvements": ["步法有进步"]},
        ]
    }
    _write_profile(tmp_path, profile)

    from deerflow.tools.builtins.training_tools import query_training_log

    with patch("deerflow.domain.coach.profile_store.get_paths", return_value=_make_paths(tmp_path)):
        result = query_training_log.invoke({"query": "反手", "n": 5})

    assert "反手" in result
    assert "数据不足" not in result


def test_query_training_log_degrades(tmp_path: Path):
    _write_profile(tmp_path, {"training_log": []})

    from deerflow.tools.builtins.training_tools import query_training_log

    with patch("deerflow.domain.coach.profile_store.get_paths", return_value=_make_paths(tmp_path)):
        result = query_training_log.invoke({"query": "反手", "n": 5})

    assert "数据不足" in result


def test_get_body_metrics_trend_tool_returns_summary(tmp_path: Path):
    profile = {
        "body_metrics": [
            {"date": "2026-05-19", "avg_heart_rate": 140, "fatigue_level": "low"},
            {"date": "2026-05-21", "avg_heart_rate": 150, "fatigue_level": "medium"},
        ]
    }
    _write_profile(tmp_path, profile)

    from deerflow.tools.builtins.training_tools import get_body_metrics_trend_tool

    with patch("deerflow.domain.coach.profile_store.get_paths", return_value=_make_paths(tmp_path)):
        result = get_body_metrics_trend_tool.invoke({"days": 14})

    assert "心率" in result
