"""Coach multimodal intake middleware (Spec 3.0).

Stage A goal: turn an uploaded exercise screenshot into a strong JSON record
via a dedicated VLM call, then inject the record into the current turn context.
"""

from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Any, Mapping, NotRequired, override

from langchain.agents import AgentState
from langchain.agents.middleware import AgentMiddleware
from langchain_core.messages import HumanMessage
from langgraph.runtime import Runtime

from deerflow.config.app_config import get_app_config
from deerflow.config.paths import get_paths
from deerflow.domain.coach.multimodal_extraction import extract_exercise_screenshot_record
from deerflow.domain.coach.profile_store import persist_exercise_record

logger = logging.getLogger(__name__)

_IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp"}


class CoachMultimodalIntakeMiddlewareState(AgentState):
    thread_data: NotRequired[dict[str, Any] | None]
    uploaded_files: NotRequired[list[dict] | None]
    coach_multimodal: NotRequired[dict[str, Any] | None]


def _extract_text_content(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for block in content:
            if isinstance(block, dict) and block.get("type") == "text":
                parts.append(str(block.get("text") or ""))
            elif isinstance(block, str):
                parts.append(block)
        return "\n".join([p for p in parts if p])
    return str(content or "")


def _resolve_vlm_model_name(runtime: Runtime) -> str | None:
    ctx = runtime.context or {}
    candidate = ctx.get("coach_multimodal_model_name")
    if isinstance(candidate, str) and candidate.strip():
        return candidate.strip()

    # Fallback: choose the first vision-capable model from config.
    cfg = get_app_config()
    for m in cfg.models:
        if m.supports_vision:
            return m.name
    return None


def _as_float(value: Any, default: float) -> float:
    try:
        f = float(value)
        return f
    except (TypeError, ValueError):
        return default


def _as_bool(value: Any, default: bool) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"1", "true", "yes", "y", "on"}:
            return True
        if lowered in {"0", "false", "no", "n", "off"}:
            return False
    return default


class CoachMultimodalIntakeMiddleware(AgentMiddleware[CoachMultimodalIntakeMiddlewareState]):
    """Extract an exercise record from a newly-uploaded image and inject it into the prompt."""

    state_schema = CoachMultimodalIntakeMiddlewareState

    @override
    def before_agent(self, state: CoachMultimodalIntakeMiddlewareState, runtime: Runtime) -> dict | None:
        uploaded_files = state.get("uploaded_files") or []
        if not uploaded_files:
            return None

        ctx = runtime.context or {}
        if not _as_bool(ctx.get("coach_multimodal_enabled"), True):
            return {"coach_multimodal": {"status": "disabled", "reason": "feature_flag_off"}}

        thread_id = runtime.context.get("thread_id")
        if not isinstance(thread_id, str) or not thread_id:
            return None

        image_file: dict[str, Any] | None = None
        for f in uploaded_files:
            if not isinstance(f, Mapping):
                continue
            ext = str(f.get("extension") or "").lower()
            if ext in _IMAGE_EXTS:
                image_file = dict(f)
                break
        if not image_file:
            return None

        messages = list(state.get("messages", []))
        if not messages:
            return None

        last_idx = len(messages) - 1
        last = messages[last_idx]
        if not isinstance(last, HumanMessage):
            return None

        original_text = _extract_text_content(last.content)
        if "<exercise_screenshot_record>" in original_text:
            return None

        model_name = _resolve_vlm_model_name(runtime)
        if model_name is None:
            logger.info("[CoachMultimodal] no vision-capable model configured; skipping extraction")
            return {"coach_multimodal": {"status": "model_unavailable"}}

        virtual_path = str(image_file.get("path") or "")
        if not virtual_path.startswith("/mnt/user-data/"):
            return {
                "coach_multimodal": {
                    "status": "skipped",
                    "reason": "non_sandbox_upload_path",
                }
            }

        started = time.monotonic()
        try:
            actual_path = get_paths().resolve_virtual_path(thread_id, virtual_path)
            record = extract_exercise_screenshot_record(
                image_path=Path(actual_path),
                user_text=original_text,
                model_name=model_name,
            )

            channel_metadata = last.additional_kwargs.get("channel_metadata", {}) if isinstance(last.additional_kwargs, Mapping) else {}
            source_message_id = None
            if isinstance(channel_metadata, Mapping):
                mid = channel_metadata.get("message_id")
                if isinstance(mid, str) and mid.strip():
                    source_message_id = mid.strip()

            event_min_confidence = _as_float(ctx.get("coach_multimodal_event_min_confidence"), 0.5)
            profile_min_confidence = _as_float(ctx.get("coach_multimodal_profile_min_confidence"), 0.75)
            allow_event_only = _as_bool(ctx.get("coach_multimodal_allow_event_only"), True)
            keep_uploads = _as_bool(ctx.get("coach_multimodal_keep_uploads"), False)

            persistence = persist_exercise_record(
                record,
                agent_name=str(ctx.get("agent_name") or "badminton-coach"),
                thread_id=thread_id,
                source_message_id=source_message_id,
                event_min_confidence=event_min_confidence,
                profile_min_confidence=profile_min_confidence,
                allow_event_only=allow_event_only,
            )

            writeback_lines = [
                "<exercise_writeback>",
                f"wrote_event_evidence={persistence.wrote_event_evidence}",
                f"updated_profile={persistence.updated_profile}",
                f"event_min_confidence={event_min_confidence}",
                f"profile_min_confidence={profile_min_confidence}",
                f"allow_event_only={allow_event_only}",
                "</exercise_writeback>",
            ]

            record_json = record.model_dump_json(indent=2, ensure_ascii=False)
            injected = (
                f"<exercise_screenshot_record>\n{record_json}\n</exercise_screenshot_record>\n"
                + "\n".join(writeback_lines)
                + "\n\n"
                + original_text
            )

            if (persistence.wrote_event_evidence or persistence.updated_profile) and not keep_uploads:
                try:
                    Path(actual_path).unlink(missing_ok=True)
                except OSError:
                    logger.info("[CoachMultimodal] failed to delete temp upload: %s", actual_path)
            coach_multimodal = {
                "status": "success",
                "model_name": model_name,
                "record_type": record.record_type,
                "confidence": record.confidence,
                "wrote_event_evidence": persistence.wrote_event_evidence,
                "updated_profile": persistence.updated_profile,
                "extraction_latency_ms": round((time.monotonic() - started) * 1000, 2),
            }
        except Exception as exc:
            logger.exception("[CoachMultimodal] extraction failed: thread_id=%s path=%s", thread_id, virtual_path)
            injected = (
                "<exercise_screenshot_error>\n"
                f"{type(exc).__name__}: {exc}\n"
                "</exercise_screenshot_error>\n\n"
                + original_text
            )
            coach_multimodal = {
                "status": "extract_failed",
                "error_type": type(exc).__name__,
                "model_name": model_name,
                "extraction_latency_ms": round((time.monotonic() - started) * 1000, 2),
            }

        messages[last_idx] = HumanMessage(
            content=injected,
            id=last.id,
            additional_kwargs=last.additional_kwargs,
        )
        return {"messages": messages, "coach_multimodal": coach_multimodal}
