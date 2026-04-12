"""Schema for multimodal exercise screenshot extraction (Spec 3.0)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class ExerciseScreenshotRecord(BaseModel):
    """Strong schema for a single exercise record extracted from a screenshot.

    Design principles:
    - Prefer missing over hallucinated values (宁缺勿滥)
    - Keep confidence + missing_fields explicit for safe writeback decisions
    """

    record_type: Literal["exercise_screenshot"] = "exercise_screenshot"
    sport_type: str | None = None
    screenshot_type: str | None = None

    duration_min: float | None = Field(default=None, ge=0)
    avg_heart_rate: float | None = Field(default=None, ge=0)
    max_heart_rate: float | None = Field(default=None, ge=0)

    training_load: float | None = Field(default=None, ge=0)
    aerobic_stress: float | None = Field(default=None, ge=0)
    calories_kcal: float | None = Field(default=None, ge=0)
    recovery_hours: float | None = Field(default=None, ge=0)

    confidence: float = Field(ge=0, le=1)
    missing_fields: list[str] = Field(default_factory=list)
    raw_summary: str = ""

