"""Structured logging helpers for channel request runs."""

from __future__ import annotations

import json
from typing import Any


def build_run_log_record(
    *,
    channel_name: str,
    thread_id: str,
    assistant_id: str,
    run_context: dict[str, Any],
    result: dict[str, Any] | list[Any] | None,
    latency_ms: float,
    response_text: str,
    artifacts: list[str],
    streaming: bool,
    error: bool = False,
    error_type: str = "",
) -> dict[str, Any]:
    """Build a stable structured log payload for one request."""
    return {
        "event": "channel_run_completed",
        "channel": channel_name,
        "thread_id": thread_id,
        "route": extract_route_metadata(
            assistant_id=assistant_id,
            run_context=run_context,
            result=result,
            streaming=streaming,
        ),
        "latency_ms": round(latency_ms, 2),
        "response_length": len(response_text),
        "artifact_count": len(artifacts),
        "error": error,
        "error_type": error_type,
        "token_usage": extract_token_usage(result),
        "cost_breakdown": extract_cost_breakdown(result),
        "memory_hits": extract_memory_hits(result),
        "clarification": extract_clarification(result),
        "fallback": extract_fallback(result),
        "multimodal": extract_multimodal(result),
    }


def format_run_log(record: dict[str, Any]) -> str:
    """Serialize a structured run log as compact JSON."""
    return json.dumps(record, ensure_ascii=False, sort_keys=True)


def extract_token_usage(result: dict[str, Any] | list[Any] | None) -> dict[str, int | None]:
    """Best-effort extraction of request token usage."""
    candidates: list[Any] = []
    if isinstance(result, dict):
        candidates.extend(
            [
                result.get("usage"),
                result.get("token_usage"),
                result.get("usage_metadata"),
                result.get("response_metadata"),
            ]
        )
        messages = result.get("messages", [])
    elif isinstance(result, list):
        messages = result
    else:
        messages = []

    if isinstance(messages, list):
        for message in reversed(messages):
            if not isinstance(message, dict):
                continue
            candidates.extend(
                [
                    message.get("usage"),
                    message.get("token_usage"),
                    message.get("usage_metadata"),
                    message.get("response_metadata"),
                ]
            )

    for candidate in candidates:
        usage = _normalize_token_usage(candidate)
        if usage["total_tokens"] is not None:
            return usage

    return {"input_tokens": None, "output_tokens": None, "total_tokens": None}


def extract_route_metadata(
    *,
    assistant_id: str,
    run_context: dict[str, Any],
    result: dict[str, Any] | list[Any] | None,
    streaming: bool,
) -> dict[str, Any]:
    route = {
        "assistant_id": assistant_id,
        "agent_name": run_context.get("agent_name", ""),
        "thinking_enabled": bool(run_context.get("thinking_enabled", False)),
        "is_plan_mode": bool(run_context.get("is_plan_mode", False)),
        "streaming": streaming,
        "coach_primary_route": "unknown",
        "coach_secondary_routes": [],
        "coach_route_source": "unknown",
    }
    if not isinstance(result, dict):
        return route

    coach_intake = result.get("coach_intake")
    if not isinstance(coach_intake, dict):
        return route

    intent = coach_intake.get("intent")
    if not isinstance(intent, dict):
        return route

    primary_intent = intent.get("primary_intent")
    if isinstance(primary_intent, str) and primary_intent:
        route["coach_primary_route"] = primary_intent
        route["coach_route_source"] = "coach_intake.intent"

    secondary_intents = intent.get("secondary_intents")
    if isinstance(secondary_intents, list):
        route["coach_secondary_routes"] = [item for item in secondary_intents if isinstance(item, str) and item]

    if route["coach_primary_route"] == "unknown":
        clarification = coach_intake.get("clarification_request")
        if isinstance(clarification, dict) and clarification.get("question"):
            route["coach_primary_route"] = "fallback"
            route["coach_route_source"] = "clarification_request"

    return route


def extract_cost_breakdown(result: dict[str, Any] | list[Any] | None) -> dict[str, Any]:
    token_usage = extract_token_usage(result)
    input_tokens = token_usage["input_tokens"]
    output_tokens = token_usage["output_tokens"]
    explicit = _find_explicit_cost_breakdown(result)

    router_tokens = explicit.get("router_tokens")
    memory_context_tokens = explicit.get("memory_context_tokens")
    generation_tokens = explicit.get("generation_tokens")
    status = "explicit"

    if generation_tokens is None and output_tokens is not None:
        generation_tokens = output_tokens
        status = "partial"

    if router_tokens is None or memory_context_tokens is None:
        status = "unknown" if status == "explicit" and generation_tokens is None else "partial"

    accounted_tokens = sum(
        value for value in (router_tokens, memory_context_tokens, generation_tokens) if isinstance(value, int)
    )
    unaccounted_tokens = None
    if token_usage["total_tokens"] is not None:
        unaccounted_tokens = max(token_usage["total_tokens"] - accounted_tokens, 0)

    return {
        "router_tokens": router_tokens,
        "memory_context_tokens": memory_context_tokens,
        "generation_tokens": generation_tokens,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "total_tokens": token_usage["total_tokens"],
        "unaccounted_tokens": unaccounted_tokens,
        "status": status,
    }


def extract_memory_hits(result: dict[str, Any] | list[Any] | None) -> dict[str, Any]:
    """Extract memory-hit signals from explicit fields or cited context."""
    contexts: list[str] = []

    if isinstance(result, dict):
        explicit = result.get("memory_hits")
        if isinstance(explicit, dict):
            return explicit
        contexts.extend(_coerce_context_list(result.get("cited_context")))
        contexts.extend(_coerce_context_list(result.get("context_hits")))
        messages = result.get("messages", [])
    elif isinstance(result, list):
        messages = result
    else:
        messages = []

    if isinstance(messages, list):
        for message in reversed(messages):
            if not isinstance(message, dict):
                continue
            contexts.extend(_coerce_context_list(message.get("cited_context")))
            contexts.extend(_coerce_context_list(message.get("context_hits")))

    hits = {
        "coach_profile": any(item.startswith("coach_profile:") for item in contexts),
        "review_log": any(item.startswith("review_log:") for item in contexts),
        "memory_json": any(item.startswith("memory:") for item in contexts),
        "weather": any(item.startswith("weather:") or item.startswith("weather.current:") for item in contexts),
    }
    hits["status"] = "hit" if any(hits.values()) else "unknown"
    return hits


def extract_clarification(result: dict[str, Any] | list[Any] | None) -> dict[str, Any]:
    """Extract clarification decision signals from coach intake state."""
    if not isinstance(result, dict):
        return {
            "requested": False,
            "reason": "",
            "missing_slots": [],
            "question": "",
        }

    coach_intake = result.get("coach_intake")
    if not isinstance(coach_intake, dict):
        return {
            "requested": False,
            "reason": "",
            "missing_slots": [],
            "question": "",
        }

    intent = coach_intake.get("intent")
    clarification_request = coach_intake.get("clarification_request")

    reason = ""
    missing_slots: list[str] = []
    if isinstance(intent, dict):
        raw_reason = intent.get("clarification_reason")
        if isinstance(raw_reason, str):
            reason = raw_reason
        raw_missing_slots = intent.get("missing_slots")
        if isinstance(raw_missing_slots, list):
            missing_slots = [item for item in raw_missing_slots if isinstance(item, str) and item]

    question = ""
    requested = False
    if isinstance(clarification_request, dict):
        raw_question = clarification_request.get("question")
        if isinstance(raw_question, str):
            question = raw_question
        requested = bool(question)

    return {
        "requested": requested,
        "reason": reason,
        "missing_slots": missing_slots,
        "question": question,
    }


def extract_fallback(result: dict[str, Any] | list[Any] | None) -> dict[str, Any]:
    if not isinstance(result, dict):
        return {"triggered": False, "reason": "", "source": "unknown"}

    coach_intake = result.get("coach_intake")
    if not isinstance(coach_intake, dict):
        return {"triggered": False, "reason": "", "source": "unknown"}

    intent = coach_intake.get("intent")
    clarification_request = coach_intake.get("clarification_request")

    if isinstance(intent, dict):
        primary_intent = intent.get("primary_intent")
        if primary_intent == "fallback":
            reason = intent.get("clarification_reason")
            if not isinstance(reason, str) or not reason:
                source = intent.get("source")
                reason = source if isinstance(source, str) else ""
            return {"triggered": True, "reason": reason, "source": "intent"}

    if isinstance(clarification_request, dict):
        question = clarification_request.get("question")
        if isinstance(question, str) and question:
            reason = clarification_request.get("reason")
            if not isinstance(reason, str) or not reason:
                if isinstance(intent, dict):
                    raw_reason = intent.get("clarification_reason")
                    reason = raw_reason if isinstance(raw_reason, str) else ""
            return {"triggered": True, "reason": reason, "source": "clarification_request"}

    return {"triggered": False, "reason": "", "source": "coach_route"}


def extract_multimodal(result: dict[str, Any] | list[Any] | None) -> dict[str, Any]:
    """Extract multimodal intake/extraction status from coach intake."""
    if not isinstance(result, dict):
        return {"status": "unknown"}
    coach_intake = result.get("coach_intake")
    if not isinstance(coach_intake, dict):
        return {"status": "unknown"}
    multimodal = coach_intake.get("multimodal")
    if not isinstance(multimodal, dict):
        return {"status": "unknown"}

    status = multimodal.get("status")
    if isinstance(status, str) and status:
        return dict(multimodal)
    return {"status": "unknown"}


def _coerce_context_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, str)]


def _find_explicit_cost_breakdown(result: dict[str, Any] | list[Any] | None) -> dict[str, int | None]:
    if not isinstance(result, dict):
        return {
            "router_tokens": None,
            "memory_context_tokens": None,
            "generation_tokens": None,
        }

    candidates: list[Any] = [
        result.get("cost_breakdown"),
        result.get("token_breakdown"),
        result.get("usage_breakdown"),
    ]
    coach_intake = result.get("coach_intake")
    if isinstance(coach_intake, dict):
        candidates.extend(
            [
                coach_intake.get("cost_breakdown"),
                coach_intake.get("token_breakdown"),
            ]
        )

    for candidate in candidates:
        if not isinstance(candidate, dict):
            continue
        breakdown = {
            "router_tokens": _read_first_int(candidate, "router_tokens"),
            "memory_context_tokens": _read_first_int(candidate, "memory_context_tokens", "memory_tokens"),
            "generation_tokens": _read_first_int(candidate, "generation_tokens", "final_generation_tokens"),
        }
        if any(value is not None for value in breakdown.values()):
            return breakdown

    return {
        "router_tokens": None,
        "memory_context_tokens": None,
        "generation_tokens": None,
    }


def _normalize_token_usage(candidate: Any) -> dict[str, int | None]:
    if not isinstance(candidate, dict):
        return {"input_tokens": None, "output_tokens": None, "total_tokens": None}

    input_tokens = _read_first_int(candidate, "input_tokens", "prompt_tokens")
    output_tokens = _read_first_int(candidate, "output_tokens", "completion_tokens")
    total_tokens = _read_first_int(candidate, "total_tokens", "total")

    if total_tokens is None and input_tokens is not None and output_tokens is not None:
        total_tokens = input_tokens + output_tokens

    return {
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "total_tokens": total_tokens,
    }


def _read_first_int(candidate: dict[str, Any], *keys: str) -> int | None:
    for key in keys:
        value = candidate.get(key)
        if isinstance(value, bool):
            continue
        if isinstance(value, int):
            return value
        if isinstance(value, float):
            return int(value)
    return None
