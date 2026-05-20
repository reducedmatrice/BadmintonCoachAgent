"""Tests for training_data context read functions."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from deerflow.config.paths import Paths
from deerflow.domain.coach.training_data import (
    get_body_metrics_trend,
    get_recent_training_log,
)


def _make_paths(base_dir: Path) -> Paths:
    return Paths(base_dir=base_dir)


def _write_profile(tmp_path: Path, profile: dict) -> None:
    agent_dir = tmp_path / "agents" / "badminton-coach"
    agent_dir.mkdir(parents=True, exist_ok=True)
    (agent_dir / "coach_profile.json").write_text(json.dumps(profile), encoding="utf-8")


def _sample_profile_with_training_log() -> dict:
    return {
        "training_log": [
            {
                "date": "2026-05-01",
                "session_type": "match",
                "summary": "双打比赛，反手表现不错",
                "duration_min": 60,
            },
            {
                "date": "2026-05-05",
                "session_type": "drill",
                "summary": "多球训练，网前手感好",
                "duration_min": 90,
            },
            {
                "date": "2026-05-10",
                "session_type": "match",
                "summary": "单打比赛，后场步法需要加强",
                "duration_min": 75,
            },
        ]
    }


def _sample_profile_with_body_metrics() -> dict:
    return {
        "body_metrics": [
            {
                "date": "2026-05-01",
                "avg_heart_rate": 140,
                "training_load": 100,
                "fatigue_level": "low",
            },
            {
                "date": "2026-05-05",
                "avg_heart_rate": 148,
                "training_load": 120,
                "fatigue_level": "medium",
            },
            {
                "date": "2026-05-10",
                "avg_heart_rate": 155,
                "training_load": 135,
                "fatigue_level": "high",
            },
            {
                "date": "2026-05-15",
                "avg_heart_rate": 160,
                "training_load": 145,
                "fatigue_level": "high",
            },
        ]
    }


# ── get_recent_training_log tests ─────────────────────────────────────


def test_get_recent_training_log_returns_entries(tmp_path: Path):
    profile = _sample_profile_with_training_log()
    _write_profile(tmp_path, profile)

    with patch("deerflow.domain.coach.profile_store.get_paths", return_value=_make_paths(tmp_path)):
        result = get_recent_training_log(n=2, agent_name="badminton-coach")

    assert result.degraded is False
    assert result.total_count == 3
    assert len(result.entries) == 2
    # Most recent first
    assert result.entries[0]["date"] == "2026-05-10"
    assert result.entries[1]["date"] == "2026-05-05"
    assert result.source == "coach_profile"


def test_get_recent_training_log_filters_by_session_type(tmp_path: Path):
    profile = _sample_profile_with_training_log()
    _write_profile(tmp_path, profile)

    with patch("deerflow.domain.coach.profile_store.get_paths", return_value=_make_paths(tmp_path)):
        result = get_recent_training_log(n=10, session_type="match", agent_name="badminton-coach")

    assert result.degraded is False
    assert len(result.entries) == 2
    assert all(e["session_type"] == "match" for e in result.entries)
    assert result.entries[0]["date"] == "2026-05-10"
    assert result.entries[1]["date"] == "2026-05-01"


def test_get_recent_training_log_degrades_on_empty(tmp_path: Path):
    profile = {"training_log": []}
    _write_profile(tmp_path, profile)

    with patch("deerflow.domain.coach.profile_store.get_paths", return_value=_make_paths(tmp_path)):
        result = get_recent_training_log(n=5, agent_name="badminton-coach")

    assert result.degraded is True
    assert result.degrade_reason != ""
    assert result.entries == []


def test_get_recent_training_log_degrades_on_missing_profile(tmp_path: Path):
    # No profile file written at all
    with patch("deerflow.domain.coach.profile_store.get_paths", return_value=_make_paths(tmp_path)):
        result = get_recent_training_log(n=5, agent_name="badminton-coach")

    assert result.degraded is True
    assert result.degrade_reason != ""
    assert result.entries == []


# ── get_body_metrics_trend tests ──────────────────────────────────────


def test_get_body_metrics_trend_returns_summary(tmp_path: Path):
    profile = _sample_profile_with_body_metrics()
    _write_profile(tmp_path, profile)

    with patch("deerflow.domain.coach.profile_store.get_paths", return_value=_make_paths(tmp_path)):
        result = get_body_metrics_trend(days=30, agent_name="badminton-coach")

    assert result.degraded is False
    assert len(result.entries) == 4
    assert result.source == "coach_profile"

    summary = result.trend_summary
    # avg_heart_rate: first half mean = (140+148)/2 = 144, second half = (155+160)/2 = 157.5 -> rising
    assert summary["avg_heart_rate_trend"] == "rising"
    assert summary["avg_heart_rate_mean"] == pytest.approx(150.75)

    # training_load: first half = (100+120)/2 = 110, second half = (135+145)/2 = 140 -> rising
    assert summary["training_load_trend"] == "rising"
    assert summary["training_load_mean"] == pytest.approx(125.0)

    # fatigue: 2 high out of 4
    assert summary["fatigue_high_ratio"] == pytest.approx(0.5)
    assert summary["dominant_fatigue"] == "high"


def test_get_body_metrics_trend_degrades_on_insufficient_data(tmp_path: Path):
    profile = {"body_metrics": [{"date": "2026-05-01", "avg_heart_rate": 140, "training_load": 100, "fatigue_level": "low"}]}
    _write_profile(tmp_path, profile)

    with patch("deerflow.domain.coach.profile_store.get_paths", return_value=_make_paths(tmp_path)):
        result = get_body_metrics_trend(days=30, agent_name="badminton-coach")

    assert result.degraded is True
    assert result.degrade_reason != ""
    assert result.entries == []


def test_get_body_metrics_trend_degrades_on_missing_profile(tmp_path: Path):
    # No profile file written
    with patch("deerflow.domain.coach.profile_store.get_paths", return_value=_make_paths(tmp_path)):
        result = get_body_metrics_trend(days=30, agent_name="badminton-coach")

    assert result.degraded is True
    assert result.degrade_reason != ""
    assert result.entries == []
