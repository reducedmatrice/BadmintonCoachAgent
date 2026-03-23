"""Weather context adapter for badminton coach planning."""

from __future__ import annotations

import inspect
from dataclasses import dataclass
from typing import Any


@dataclass
class WeatherContext:
    temperature_c: float | None = None
    humidity: float | None = None
    condition: str = ""
    location: str = ""
    source: str = "weather-mcp"
    degraded: bool = False
    degrade_reason: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "temperature_c": self.temperature_c,
            "humidity": self.humidity,
            "condition": self.condition,
            "location": self.location,
            "source": self.source,
            "degraded": self.degraded,
            "degrade_reason": self.degrade_reason,
        }


def degrade_weather_context(*, source: str = "weather-mcp", reason: str) -> dict[str, Any]:
    """Return a normalized degraded weather context."""
    return WeatherContext(source=source, degraded=True, degrade_reason=reason).to_dict()


async def fetch_weather_context(
    tool: Any,
    *,
    location: str,
    query: str | None = None,
    source: str | None = None,
    extra_args: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Fetch and normalize weather context from an MCP-like tool."""
    resolved_source = source or getattr(tool, "name", None) or "weather-mcp"
    if tool is None:
        return degrade_weather_context(source=resolved_source, reason="weather_tool_unavailable")

    payload = {"location": location}
    if query:
        payload["query"] = query
    if extra_args:
        payload.update(extra_args)

    try:
        raw_result = await _invoke_tool(tool, payload)
    except Exception:
        return degrade_weather_context(source=resolved_source, reason="weather_lookup_failed")

    normalized = normalize_weather_payload(raw_result, source=resolved_source)
    if normalized["degraded"]:
        return normalized
    if normalized["temperature_c"] is None and normalized["humidity"] is None and not normalized["condition"]:
        return degrade_weather_context(source=resolved_source, reason="weather_payload_missing_signal")
    return normalized


def normalize_weather_payload(payload: Any, *, source: str = "weather-mcp") -> dict[str, Any]:
    """Normalize common weather payload shapes into a stable coach context."""
    candidate = _unwrap_payload(payload)
    if not isinstance(candidate, dict):
        return degrade_weather_context(source=source, reason="weather_payload_invalid")

    temperature = _extract_number(candidate, ("temperature_c", "temp_c", "temperature", "temp"))
    humidity = _extract_number(candidate, ("humidity", "relative_humidity"))
    condition = _extract_condition(candidate)
    location = _extract_text(candidate, ("location", "city", "name"))

    return WeatherContext(
        temperature_c=temperature,
        humidity=humidity,
        condition=condition,
        location=location,
        source=source,
    ).to_dict()


async def _invoke_tool(tool: Any, payload: dict[str, Any]) -> Any:
    if hasattr(tool, "ainvoke"):
        return await tool.ainvoke(payload)
    if hasattr(tool, "invoke"):
        result = tool.invoke(payload)
        if inspect.isawaitable(result):
            return await result
        return result
    if callable(tool):
        result = tool(payload)
        if inspect.isawaitable(result):
            return await result
        return result
    raise TypeError("Weather tool must expose ainvoke/invoke or be callable")


def _unwrap_payload(payload: Any) -> Any:
    if isinstance(payload, dict):
        for key in ("current", "now", "weather", "data", "result"):
            nested = payload.get(key)
            if isinstance(nested, dict):
                return nested
    return payload


def _extract_number(payload: dict[str, Any], keys: tuple[str, ...]) -> float | None:
    for key in keys:
        value = payload.get(key)
        if isinstance(value, (int, float)):
            return float(value)
        if isinstance(value, str):
            stripped = value.strip().replace("°C", "").replace("%", "")
            try:
                return float(stripped)
            except ValueError:
                continue
    return None


def _extract_condition(payload: dict[str, Any]) -> str:
    for key in ("condition", "weather", "summary", "description", "text"):
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
        if isinstance(value, dict):
            text = value.get("text")
            if isinstance(text, str) and text.strip():
                return text.strip()
    return ""


def _extract_text(payload: dict[str, Any], keys: tuple[str, ...]) -> str:
    for key in keys:
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""
