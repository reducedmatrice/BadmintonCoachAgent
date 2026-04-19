"""Integration tests for coach text loop pieces."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import patch

import pytest

from deerflow.config.paths import Paths
from deerflow.domain.coach.prematch import build_prematch_advice
from deerflow.domain.coach.weather import fetch_weather_context
from deerflow.domain.coach.profile_store import persist_exercise_record, process_postmatch_message
from deerflow.domain.coach.multimodal_schema import ExerciseScreenshotRecord
from deerflow.domain.coach.recall import build_recall_context
from deerflow.domain.coach.router import route_single_intent


def _make_paths(base_dir: Path) -> Paths:
    return Paths(base_dir=base_dir)


def test_postmatch_persistence_feeds_next_prematch(tmp_path: Path):
    with patch("deerflow.domain.coach.profile_store.get_paths", return_value=_make_paths(tmp_path)):
        persisted = process_postmatch_message(
            "今天后场步法还是慢，回位总跟不上。反手更敢发力了。下次重点继续盯后场启动和反手稳定性。",
            occurred_at=datetime(2026, 3, 23, 19, 0, tzinfo=UTC),
        )

    assert persisted.review_log_path.exists()

    with patch("deerflow.domain.coach.prematch.get_paths", return_value=_make_paths(tmp_path)):
        advice = build_prematch_advice("今晚打球注意什么", memory_data={"facts": []})

    assert any("后场步法" in item for item in advice.focus_points)
    assert any(context.startswith("coach_profile:") or context.startswith("review_log:") for context in advice.cited_context)


@pytest.mark.anyio
async def test_weather_context_changes_prematch_output():
    class FakeWeatherTool:
        name = "weather.current"

        async def ainvoke(self, payload: dict[str, str]) -> dict[str, object]:
            assert payload["location"] == "Shanghai"
            return {"current": {"temp_c": 32, "humidity": 78, "condition": {"text": "晴"}}}

    hot_weather = await fetch_weather_context(FakeWeatherTool(), location="Shanghai")
    hot_advice = build_prematch_advice("今晚打球注意什么", memory_data={"facts": []}, weather=hot_weather)
    normal_advice = build_prematch_advice(
        "今晚打球注意什么",
        memory_data={"facts": []},
        weather={"temperature_c": 24, "humidity": 55, "condition": "多云", "source": "weather.current"},
    )

    assert any("60-75 分钟" in item for item in hot_advice.risk_reminders)
    assert any("75-90 分钟" in item for item in normal_advice.risk_reminders)
    assert hot_advice.risk_reminders != normal_advice.risk_reminders


def test_exercise_writeback_feeds_next_prematch_recall(tmp_path: Path):
    record = ExerciseScreenshotRecord(
        sport_type="badminton",
        screenshot_type="training_load",
        duration_min=92.0,
        avg_heart_rate=154.0,
        max_heart_rate=183.0,
        training_load=166.0,
        aerobic_stress=None,
        calories_kcal=760.0,
        recovery_hours=26.0,
        confidence=0.92,
        missing_fields=[],
        raw_summary="高负荷训练，恢复时间偏长",
    )

    with patch("deerflow.domain.coach.profile_store.get_paths", return_value=_make_paths(tmp_path)):
        persisted = persist_exercise_record(
            record,
            occurred_at=datetime(2026, 4, 10, 18, 0, tzinfo=UTC),
            thread_id="thread-mm",
            source_message_id="om-image-1",
        )
    assert persisted.wrote_event_evidence is True
    assert persisted.updated_profile is True

    with patch("deerflow.domain.coach.recall.load_coach_profile", return_value=persisted.profile):
        recall_context = build_recall_context(
            latest_user_input="今晚打球前注意什么",
            primary_intent="prematch",
            now=datetime(2026, 4, 11, 9, 0, tzinfo=UTC),
        )
    assert recall_context is not None
    assert recall_context["should_mention"] is True

    with patch("deerflow.domain.coach.prematch.get_paths", return_value=_make_paths(tmp_path)):
        result = route_single_intent(
            "今晚打球前注意什么",
            memory_data={"facts": []},
            recall_context=recall_context,
        )

    assert result.route == "prematch"
    assert "我翻了下你最近一次相关记录" in result.payload["response_text"]
