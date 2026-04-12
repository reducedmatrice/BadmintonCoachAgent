from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import patch

from deerflow.domain.coach.recall import build_recall_context


def test_build_recall_context_health_route_mentions_latest_metric():
    profile = {
        "health_profile": {
            "recent_metrics": [
                {
                    "recorded_at": "2026-04-10",
                    "source": "exercise_screenshot",
                    "duration_min": 90.0,
                    "avg_heart_rate": 152.0,
                    "training_load": 160.0,
                    "recovery_hours": 24.0,
                    "fatigue_level": "high",
                }
            ]
        }
    }
    with patch("deerflow.domain.coach.recall.load_coach_profile", return_value=profile):
        ctx = build_recall_context(
            latest_user_input="今天恢复建议",
            primary_intent="health",
            now=datetime(2026, 4, 12, tzinfo=UTC),
        )
    assert ctx is not None
    assert ctx["should_mention"] is True
    assert ctx["mention_reason"] == "health_route_default_recall"


def test_build_recall_context_prematch_mentions_high_risk_state():
    profile = {
        "health_profile": {
            "recent_metrics": [
                {
                    "recorded_at": "2026-04-11",
                    "source": "exercise_screenshot",
                    "training_load": 170.0,
                    "fatigue_level": "high",
                    "raw_summary": "高负荷训练",
                }
            ]
        }
    }
    with patch("deerflow.domain.coach.recall.load_coach_profile", return_value=profile):
        ctx = build_recall_context(
            latest_user_input="今晚赛前怎么打",
            primary_intent="prematch",
            now=datetime(2026, 4, 12, tzinfo=UTC),
        )
    assert ctx is not None
    assert ctx["mention_reason"] == "prematch_high_fatigue"

