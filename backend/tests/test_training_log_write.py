"""Tests for training log and body metric write functions."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

from deerflow.config.paths import Paths
from deerflow.domain.coach.profile_store import (
    append_body_metric,
    append_training_log,
)


def _make_paths(base_dir: Path) -> Paths:
    return Paths(base_dir=base_dir)


def _read_profile(base_dir: Path) -> dict:
    profile_path = base_dir / "agents" / "badminton-coach" / "coach_profile.json"
    return json.loads(profile_path.read_text(encoding="utf-8"))


def test_append_training_log_creates_new_entry(tmp_path: Path):
    entry = {
        "date": "2026-05-21",
        "session_type": "match",
        "match_format": "doubles",
        "summary": "双打3局，反手失误多",
        "focus_areas": ["反手"],
        "improvements": [],
        "issues": ["反手过渡出界"],
        "source": "postmatch",
    }
    with patch("deerflow.domain.coach.profile_store.get_paths", return_value=_make_paths(tmp_path)):
        result_path = append_training_log(entry)
    assert result_path.exists()
    profile = _read_profile(tmp_path)
    assert len(profile["training_log"]) == 1
    assert profile["training_log"][0]["summary"] == "双打3局，反手失误多"


def test_append_training_log_caps_at_200(tmp_path: Path):
    existing_log = [
        {"date": f"2026-{i:02d}-01", "session_type": "training", "summary": f"训练{i}"}
        for i in range(1, 201)
    ]
    agent_dir = tmp_path / "agents" / "badminton-coach"
    agent_dir.mkdir(parents=True, exist_ok=True)
    (agent_dir / "coach_profile.json").write_text(
        json.dumps({"training_log": existing_log}, ensure_ascii=False), encoding="utf-8"
    )
    new_entry = {"date": "2026-05-21", "session_type": "match", "summary": "新记录"}
    with patch("deerflow.domain.coach.profile_store.get_paths", return_value=_make_paths(tmp_path)):
        append_training_log(new_entry)
    profile = _read_profile(tmp_path)
    assert len(profile["training_log"]) == 200
    assert profile["training_log"][-1]["summary"] == "新记录"
    assert profile["training_log"][0]["summary"] == "训练2"


def test_append_body_metric_creates_new_entry(tmp_path: Path):
    entry = {
        "date": "2026-05-21",
        "fatigue_level": "medium",
        "avg_heart_rate": 145,
        "source": "exercise_screenshot",
    }
    with patch("deerflow.domain.coach.profile_store.get_paths", return_value=_make_paths(tmp_path)):
        result_path = append_body_metric(entry)
    assert result_path.exists()
    profile = _read_profile(tmp_path)
    assert len(profile["body_metrics"]) == 1
    assert profile["body_metrics"][0]["fatigue_level"] == "medium"


def test_append_body_metric_caps_at_200(tmp_path: Path):
    existing_metrics = [
        {"date": f"2026-{i:02d}-01", "fatigue_level": "low", "source": "manual"}
        for i in range(1, 201)
    ]
    agent_dir = tmp_path / "agents" / "badminton-coach"
    agent_dir.mkdir(parents=True, exist_ok=True)
    (agent_dir / "coach_profile.json").write_text(
        json.dumps({"body_metrics": existing_metrics}, ensure_ascii=False), encoding="utf-8"
    )
    new_entry = {"date": "2026-05-21", "fatigue_level": "high", "source": "health_report"}
    with patch("deerflow.domain.coach.profile_store.get_paths", return_value=_make_paths(tmp_path)):
        append_body_metric(new_entry)
    profile = _read_profile(tmp_path)
    assert len(profile["body_metrics"]) == 200
    assert profile["body_metrics"][-1]["fatigue_level"] == "high"
