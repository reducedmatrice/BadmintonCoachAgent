"""Integration tests for coach text loop pieces."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import patch

import pytest

from deerflow.config.paths import Paths
from deerflow.domain.coach.prematch import build_prematch_advice
from deerflow.domain.coach.weather import fetch_weather_context
from deerflow.domain.coach.profile_store import process_postmatch_message


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
