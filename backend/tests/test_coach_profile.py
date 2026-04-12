"""Tests for coach profile persistence."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import patch

from deerflow.config.paths import Paths
from deerflow.domain.coach.health_image import HealthImageObservation, HealthRecoveryAdvice
from deerflow.domain.coach.postmatch import Improvement, PostmatchReview, TechnicalObservation
from deerflow.domain.coach.profile_store import (
    append_review_log,
    persist_exercise_record,
    persist_health_observation,
    persist_prematch_signal,
    update_profile_from_postmatch,
)
from deerflow.domain.coach.multimodal_schema import ExerciseScreenshotRecord


def _make_paths(base_dir: Path) -> Paths:
    return Paths(base_dir=base_dir)


def test_update_profile_merges_weakness_and_recent_review(tmp_path: Path):
    agent_dir = tmp_path / "agents" / "badminton-coach"
    agent_dir.mkdir(parents=True)
    existing_profile = {
        "tech_profile": {
            "focus_topics": ["后场步法"],
            "weaknesses": [
                {
                    "name": "后场步法回位慢",
                    "severity": 0.6,
                    "trend": "stable",
                    "last_seen_at": "2026-03-20",
                    "evidence": "旧记录",
                }
            ],
            "strengths": [],
            "recent_reviews": [],
        }
    }
    (agent_dir / "coach_profile.json").write_text(json.dumps(existing_profile), encoding="utf-8")

    review = PostmatchReview(
        technical_observations=[TechnicalObservation(topic="后场步法", finding="回位慢", severity=0.8, evidence="后场球后续衔接不上")],
        improvements=[Improvement(topic="反手稳定性", evidence="今天反手更敢发力了")],
        next_focus=["后场步法", "反手稳定性"],
        emotional_notes=[],
        summary="识别到 1 条技术问题；1 条进步点",
    )

    with patch("deerflow.domain.coach.profile_store.get_paths", return_value=_make_paths(tmp_path)):
        updated = update_profile_from_postmatch(review, occurred_at=datetime(2026, 3, 23, 12, 0, tzinfo=UTC))

    weakness = updated["tech_profile"]["weaknesses"][0]
    assert weakness["severity"] == 0.8
    assert weakness["last_seen_at"] == "2026-03-23"
    assert "反手稳定性" in updated["tech_profile"]["focus_topics"]
    assert updated["tech_profile"]["recent_reviews"][-1]["next_focus"] == ["后场步法", "反手稳定性"]


def test_append_review_log_writes_expected_sections(tmp_path: Path):
    review = PostmatchReview(
        technical_observations=[TechnicalObservation(topic="后场步法", finding="回位慢", severity=0.7, evidence="回位总跟不上")],
        improvements=[Improvement(topic="反手稳定性", evidence="反手更稳了")],
        next_focus=["后场步法"],
        emotional_notes=[],
        summary="识别到 1 条技术问题；1 条进步点",
    )

    with patch("deerflow.domain.coach.profile_store.get_paths", return_value=_make_paths(tmp_path)):
        log_path = append_review_log(review, occurred_at=datetime(2026, 3, 23, 12, 30, tzinfo=UTC))

    content = log_path.read_text(encoding="utf-8")
    assert "技术问题" in content
    assert "进步点" in content
    assert "下次重点" in content
    assert "后场步法" in content


def test_persist_health_observation_updates_health_profile(tmp_path: Path):
    observation = HealthImageObservation(
        screenshot_type="sleep_recovery",
        observed_metrics={"sleep_min": 318.0, "hrv": 28.0},
        observations=["睡眠时长不足 6 小时，恢复质量偏弱。"],
        risk_level="high",
        missing_data=[],
    )
    advice = HealthRecoveryAdvice(
        risk_level="high",
        structured_observations=observation.observations,
        recovery_actions=["今晚以恢复为主。"],
        next_session_intensity="下一次先按恢复或低强度处理。",
        follow_up_question="你现在是单纯累还是有明显疼痛点？",
    )

    with patch("deerflow.domain.coach.profile_store.get_paths", return_value=_make_paths(tmp_path)):
        persisted = persist_health_observation(observation, advice, occurred_at=datetime(2026, 3, 23, 12, 45, tzinfo=UTC))

    health_profile = persisted.profile["health_profile"]
    assert persisted.profile_path.exists()
    assert health_profile["fatigue_level"] == "high"
    assert "health:sleep_recovery:high" in health_profile["risk_flags"]
    assert health_profile["recent_metrics"][-1]["source"] == "sleep_recovery"
    assert health_profile["recent_metrics"][-1]["risk_level"] == "high"


def test_persist_prematch_signal_writes_only_high_value_fields(tmp_path: Path):
    with patch("deerflow.domain.coach.profile_store.get_paths", return_value=_make_paths(tmp_path)):
        persisted = persist_prematch_signal(
            "我平时久坐，肩部旧伤恢复期，这两周准备比赛，优先练后场步法和反手，今晚先按双打准备。",
            occurred_at=datetime(2026, 3, 23, 13, 0, tzinfo=UTC),
        )

    assert persisted.persisted is True
    assert persisted.profile_path.exists()
    assert "久坐后启动偏紧" in persisted.profile["athlete_profile"]["constraints"]
    assert "肩部旧伤/恢复期" in persisted.profile["athlete_profile"]["constraints"]


def test_persist_exercise_record_writes_event_and_updates_profile(tmp_path: Path):
    record = ExerciseScreenshotRecord(
        sport_type="badminton",
        screenshot_type="training_load",
        duration_min=92.0,
        avg_heart_rate=152.0,
        max_heart_rate=182.0,
        training_load=165.0,
        aerobic_stress=None,
        calories_kcal=780.0,
        recovery_hours=26.0,
        confidence=0.91,
        missing_fields=[],
        raw_summary="高负荷训练 + 建议恢复时间较长",
    )

    with patch("deerflow.domain.coach.profile_store.get_paths", return_value=_make_paths(tmp_path)):
        persisted = persist_exercise_record(
            record,
            occurred_at=datetime(2026, 3, 23, 14, 0, tzinfo=UTC),
            thread_id="thread-123",
            source_message_id="om-image-1",
        )

    assert persisted.wrote_event_evidence is True
    assert persisted.updated_profile is True
    assert persisted.review_log_path is not None
    assert persisted.review_log_path.exists()
    assert persisted.profile_path is not None
    assert persisted.profile_path.exists()

    log_text = persisted.review_log_path.read_text(encoding="utf-8")
    assert "训练负荷" in log_text
    assert "恢复时间" in log_text
    assert "thread-123" in log_text

    health_profile = persisted.profile["health_profile"]
    assert health_profile["fatigue_level"] in {"medium", "high"}
    assert "exercise:" in "".join(health_profile.get("risk_flags", []))
    assert health_profile["recent_metrics"][-1]["source"] == "exercise_screenshot"


def test_persist_exercise_record_low_confidence_writes_event_only(tmp_path: Path):
    record = ExerciseScreenshotRecord(
        sport_type="badminton",
        screenshot_type="heart_rate",
        duration_min=60.0,
        avg_heart_rate=140.0,
        max_heart_rate=168.0,
        training_load=None,
        aerobic_stress=None,
        calories_kcal=None,
        recovery_hours=None,
        confidence=0.62,
        missing_fields=["training_load", "recovery_hours"],
        raw_summary="心率信息较清晰，但负荷/恢复缺失",
    )

    with patch("deerflow.domain.coach.profile_store.get_paths", return_value=_make_paths(tmp_path)):
        persisted = persist_exercise_record(
            record,
            occurred_at=datetime(2026, 3, 23, 14, 10, tzinfo=UTC),
            event_min_confidence=0.5,
            profile_min_confidence=0.75,
            allow_event_only=True,
        )

    assert persisted.wrote_event_evidence is True
    assert persisted.updated_profile is False
    assert persisted.review_log_path is not None and persisted.review_log_path.exists()
    assert persisted.profile_path is None


def test_persist_exercise_record_very_low_confidence_skips_all(tmp_path: Path):
    record = ExerciseScreenshotRecord(
        sport_type=None,
        screenshot_type=None,
        duration_min=None,
        avg_heart_rate=None,
        max_heart_rate=None,
        training_load=None,
        aerobic_stress=None,
        calories_kcal=None,
        recovery_hours=None,
        confidence=0.2,
        missing_fields=["duration_min", "avg_heart_rate"],
        raw_summary="无法可靠识别截图指标",
    )

    with patch("deerflow.domain.coach.profile_store.get_paths", return_value=_make_paths(tmp_path)):
        persisted = persist_exercise_record(
            record,
            occurred_at=datetime(2026, 3, 23, 14, 20, tzinfo=UTC),
            event_min_confidence=0.5,
        )

    assert persisted.wrote_event_evidence is False
    assert persisted.updated_profile is False
    assert persisted.review_log_path is None


def test_persist_prematch_signal_skips_when_no_stable_signal(tmp_path: Path):
    with patch("deerflow.domain.coach.profile_store.get_paths", return_value=_make_paths(tmp_path)):
        persisted = persist_prematch_signal("今晚打球前怎么热身？", occurred_at=datetime(2026, 3, 23, 13, 5, tzinfo=UTC))

    assert persisted.persisted is False
    assert persisted.extracted == {
        "constraints": [],
        "training_preferences": [],
        "recent_goals": [],
    }


def test_persist_prematch_signal_covers_more_badminton_topics(tmp_path: Path):
    with patch("deerflow.domain.coach.profile_store.get_paths", return_value=_make_paths(tmp_path)):
        persisted = persist_prematch_signal(
            "这阶段主要练混双，想加强发接发、平抽挡、网前封网和接杀防守，月底比赛前希望稳定性和回合衔接更好。",
            occurred_at=datetime(2026, 3, 23, 13, 10, tzinfo=UTC),
        )

    assert persisted.persisted is True
    prefs = persisted.profile["preferences"]["training_preferences"]
    goals = [item["goal"] for item in persisted.profile["tech_profile"]["recent_goals"]]
    assert "偏混双训练" in prefs
    assert "优先训练发接发" in prefs
    assert "优先训练平抽挡" in prefs
    assert "优先训练网前" in prefs
    assert "优先训练防守" in prefs
    assert "近期以比赛准备为主" in goals
    assert "近期目标：提升稳定性" in goals
    assert "近期目标：提升回合衔接" in goals
