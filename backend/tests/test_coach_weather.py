"""Tests for badminton coach weather context adapter."""

from __future__ import annotations

import pytest

from deerflow.domain.coach.weather import fetch_weather_context, normalize_weather_payload


class FakeWeatherTool:
    name = "weather.current"

    async def ainvoke(self, payload: dict[str, str]) -> dict[str, object]:
        assert payload["location"] == "Shanghai"
        return {
            "current": {
                "temp_c": 31,
                "humidity": 84,
                "condition": {"text": "阵雨"},
                "city": "Shanghai",
            }
        }


@pytest.mark.anyio
async def test_fetch_weather_context_normalizes_nested_mcp_payload():
    context = await fetch_weather_context(FakeWeatherTool(), location="Shanghai")

    assert context["temperature_c"] == 31
    assert context["humidity"] == 84
    assert context["condition"] == "阵雨"
    assert context["location"] == "Shanghai"
    assert context["source"] == "weather.current"
    assert context["degraded"] is False


@pytest.mark.anyio
async def test_fetch_weather_context_degrades_on_tool_failure():
    async def failing_tool(_: dict[str, str]) -> dict[str, object]:
        raise RuntimeError("mcp unavailable")

    context = await fetch_weather_context(failing_tool, location="Shanghai", source="weather.current")

    assert context["degraded"] is True
    assert context["degrade_reason"] == "weather_lookup_failed"
    assert context["source"] == "weather.current"


def test_normalize_weather_payload_accepts_flat_shape():
    context = normalize_weather_payload(
        {"temperature": "26", "relative_humidity": "68%", "summary": "多云"},
        source="manual-weather",
    )

    assert context["temperature_c"] == 26
    assert context["humidity"] == 68
    assert context["condition"] == "多云"
    assert context["source"] == "manual-weather"
    assert context["degraded"] is False
