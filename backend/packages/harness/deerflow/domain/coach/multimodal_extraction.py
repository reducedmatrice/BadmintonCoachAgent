"""Multimodal extraction for exercise screenshots (Spec 3.0).

This module intentionally performs a dedicated VLM call to "down-project" the
image into a strong JSON schema before the coach reasoning step.
"""

from __future__ import annotations

import base64
import json
import mimetypes
from pathlib import Path

from langchain_core.messages import HumanMessage, SystemMessage

from deerflow.models import create_chat_model

from .multimodal_schema import ExerciseScreenshotRecord


def _extract_json_object(text: str) -> str:
    """Best-effort extraction of the first JSON object from a model response."""
    stripped = text.strip()
    if stripped.startswith("{") and stripped.endswith("}"):
        return stripped
    start = stripped.find("{")
    end = stripped.rfind("}")
    if start >= 0 and end > start:
        return stripped[start : end + 1]
    raise ValueError("No JSON object found in model output")


def extract_exercise_screenshot_record(
    *,
    image_path: Path,
    user_text: str | None,
    model_name: str,
) -> ExerciseScreenshotRecord:
    """Call a vision model to extract a structured exercise record from an image."""
    if not image_path.is_file():
        raise FileNotFoundError(f"Image not found: {image_path}")

    data = image_path.read_bytes()
    image_base64 = base64.b64encode(data).decode("utf-8")
    mime_type, _ = mimetypes.guess_type(str(image_path))
    mime_type = mime_type or "image/png"

    system = SystemMessage(
        content=(
            "You are a strict information extraction system.\n"
            "Given a workout/exercise screenshot, extract metrics into the provided JSON schema.\n"
            "Rules:\n"
            "- Output JSON only (no markdown, no code fences).\n"
            "- If a value is not clearly visible, set it to null and add its field name to missing_fields.\n"
            "- confidence must be a number between 0 and 1 representing how reliable the extraction is.\n"
        )
    )

    schema = ExerciseScreenshotRecord.model_json_schema()
    hint = (user_text or "").strip()
    user_block = (
        "Optional user context:\n"
        + (hint if hint else "(none)")
        + "\n\n"
        + "Return JSON matching this schema:\n"
        + json.dumps(schema, ensure_ascii=False)
    )

    human = HumanMessage(
        content=[
            {"type": "text", "text": user_block},
            {"type": "image_url", "image_url": {"url": f"data:{mime_type};base64,{image_base64}"}},
        ]
    )

    model = create_chat_model(name=model_name, thinking_enabled=False)
    response = model.invoke([system, human])
    content = getattr(response, "content", "")
    if not isinstance(content, str) or not content.strip():
        raise ValueError("Empty model output")

    json_text = _extract_json_object(content)
    # Ensure it's JSON and validate with pydantic.
    json.loads(json_text)
    return ExerciseScreenshotRecord.model_validate_json(json_text)
