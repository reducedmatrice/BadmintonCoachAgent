"""Single-intent routing for coach runtime."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from .health_image import analyze_health_image_text, build_health_recovery_advice
from .intent import CoachIntent, CoachIntentClassifier, CoachIntentName, detect_coach_intent
from .postmatch import extract_postmatch_review
from .prematch import build_prematch_advice
from .profile_store import persist_health_observation, persist_prematch_signal, process_postmatch_message
from .response_renderer import render_coach_route_payload

_HEALTH_OVERRIDE_HINTS = ("剧烈疼", "刺痛", "拉伤", "扭伤", "头晕", "膝盖", "肩痛", "腰痛")


@dataclass
class CoachSingleIntentRouteResult:
    """Result of single-intent routing."""

    route: CoachIntentName
    intent: CoachIntent
    payload: dict[str, Any]


@dataclass
class CoachComposableRouteResult:
    """Result of composable mixed-intent routing."""

    intent: CoachIntent
    ordered_routes: list[CoachIntentName]
    steps: list[CoachSingleIntentRouteResult]
    safety_gate: dict[str, Any] | None = None


@dataclass
class CoachSafetyGateDecision:
    """Safety gate decision for composable routing.

    This is intentionally lightweight for B4. It only controls route allow-list
    and optional blocking, without embedding domain-heavy medical logic.
    """

    allowed_routes: list[CoachIntentName] | None = None
    blocked: bool = False
    reason: str | None = None
    metadata: dict[str, Any] | None = None


CoachSafetyGateHook = Callable[[CoachIntent, list[CoachIntentName], str], CoachSafetyGateDecision | None]


def route_single_intent(
    message: str,
    *,
    intent: CoachIntent | None = None,
    agent_name: str = "badminton-coach",
    memory_data: dict[str, Any] | None = None,
    weather: dict[str, Any] | None = None,
    recall_context: dict[str, Any] | None = None,
    persist_postmatch: bool = False,
    persona: dict[str, Any] | None = None,
    llm_classifier: CoachIntentClassifier | None = None,
) -> CoachSingleIntentRouteResult:
    """Route one message into a single coach chain based on structured intent."""
    resolved_intent = intent or detect_coach_intent(message, llm_classifier=llm_classifier)
    route = _resolve_route_by_strong_rules(message=message, intent=resolved_intent)
    payload = _run_route_chain(
        route,
        message=message,
        agent_name=agent_name,
        memory_data=memory_data,
        weather=weather,
        recall_context=recall_context,
        persist_postmatch=persist_postmatch,
        persona=persona,
    )
    return CoachSingleIntentRouteResult(route=route, intent=resolved_intent, payload=payload)


def route_composable_intent(
    message: str,
    *,
    intent: CoachIntent | None = None,
    agent_name: str = "badminton-coach",
    memory_data: dict[str, Any] | None = None,
    weather: dict[str, Any] | None = None,
    recall_context: dict[str, Any] | None = None,
    persist_postmatch: bool = False,
    persona: dict[str, Any] | None = None,
    safety_gate: CoachSafetyGateHook | None = None,
    llm_classifier: CoachIntentClassifier | None = None,
) -> CoachComposableRouteResult:
    """Route mixed intents with deterministic chain ordering."""
    resolved_intent = intent or detect_coach_intent(message, llm_classifier=llm_classifier)
    ordered_routes = _resolve_composed_order(resolved_intent)
    effective_routes, gate_payload = _apply_safety_gate(
        resolved_intent,
        ordered_routes=ordered_routes,
        message=message,
        safety_gate=safety_gate,
    )

    steps: list[CoachSingleIntentRouteResult] = []
    for route in effective_routes:
        payload = _run_route_chain(
            route,
            message=message,
            agent_name=agent_name,
            memory_data=memory_data,
            weather=weather,
            recall_context=recall_context,
            persist_postmatch=persist_postmatch,
            persona=persona,
        )
        steps.append(
            CoachSingleIntentRouteResult(
                route=route,
                intent=resolved_intent,
                payload=payload,
            )
        )

    return CoachComposableRouteResult(
        intent=resolved_intent,
        ordered_routes=effective_routes,
        steps=steps,
        safety_gate=gate_payload,
    )


def _run_route_chain(
    route: CoachIntentName,
    *,
    message: str,
    agent_name: str,
    memory_data: dict[str, Any] | None,
    weather: dict[str, Any] | None,
    recall_context: dict[str, Any] | None,
    persist_postmatch: bool,
    persona: dict[str, Any] | None,
) -> dict[str, Any]:
    if route == "prematch":
        advice = build_prematch_advice(
            message,
            agent_name=agent_name,
            memory_data=memory_data,
            weather=weather,
        )
        if persist_postmatch:
            persisted = persist_prematch_signal(message, agent_name=agent_name)
            payload = {
                "chain": "prematch",
                "focus_points": advice.focus_points,
                "warmup": advice.warmup,
                "risk_reminders": advice.risk_reminders,
                "cited_context": advice.cited_context,
                "follow_up_questions": advice.follow_up_questions,
                "recall_context": recall_context,
                "persisted": persisted.persisted,
                "profile_path": str(persisted.profile_path),
                "writeback": persisted.extracted,
            }
            payload["response_text"] = render_coach_route_payload(route, payload, persona=persona)
            return payload
        payload = {
            "chain": "prematch",
            "focus_points": advice.focus_points,
            "warmup": advice.warmup,
            "risk_reminders": advice.risk_reminders,
            "cited_context": advice.cited_context,
            "follow_up_questions": advice.follow_up_questions,
            "recall_context": recall_context,
            "persisted": False,
        }
        payload["response_text"] = render_coach_route_payload(route, payload, persona=persona)
        return payload

    if route == "postmatch":
        if persist_postmatch:
            persisted = process_postmatch_message(message, agent_name=agent_name)
            payload = {
                "chain": "postmatch",
                "summary": persisted.review.summary,
                "technical_observations": [item.__dict__ for item in persisted.review.technical_observations],
                "improvements": [item.__dict__ for item in persisted.review.improvements],
                "next_focus": persisted.review.next_focus,
                "review_log_path": str(persisted.review_log_path),
                "persisted": True,
            }
            payload["response_text"] = render_coach_route_payload(route, payload, persona=persona)
            return payload
        review = extract_postmatch_review(message)
        payload = {
            "chain": "postmatch",
            "summary": review.summary,
            "technical_observations": [item.__dict__ for item in review.technical_observations],
            "improvements": [item.__dict__ for item in review.improvements],
            "next_focus": review.next_focus,
            "persisted": False,
        }
        payload["response_text"] = render_coach_route_payload(route, payload, persona=persona)
        return payload

    if route == "health":
        observation = analyze_health_image_text(message)
        advice = build_health_recovery_advice(observation)
        if persist_postmatch:
            persisted = persist_health_observation(observation, advice, agent_name=agent_name)
            payload = {
                "chain": "health",
                "risk_level": advice.risk_level,
                "structured_observations": advice.structured_observations,
                "recovery_actions": advice.recovery_actions,
                "next_session_intensity": advice.next_session_intensity,
                "follow_up_question": advice.follow_up_question,
                "missing_data": observation.missing_data,
                "recall_context": recall_context,
                "profile_path": str(persisted.profile_path),
                "persisted": True,
            }
            payload["response_text"] = render_coach_route_payload(route, payload, persona=persona)
            return payload
        payload = {
            "chain": "health",
            "risk_level": advice.risk_level,
            "structured_observations": advice.structured_observations,
            "recovery_actions": advice.recovery_actions,
            "next_session_intensity": advice.next_session_intensity,
            "follow_up_question": advice.follow_up_question,
            "missing_data": observation.missing_data,
            "recall_context": recall_context,
            "persisted": False,
        }
        payload["response_text"] = render_coach_route_payload(route, payload, persona=persona)
        return payload

    payload = {
        "chain": "fallback",
        "guidance": "请先说清你现在是赛前准备、赛后复盘，还是身体恢复问题，我再给你对应方案。",
        "follow_up_question": "你现在更希望我先帮你做赛前计划、赛后复盘，还是恢复建议？",
    }
    payload["response_text"] = render_coach_route_payload(route, payload, persona=persona)
    return payload


def _resolve_route_by_strong_rules(*, message: str, intent: CoachIntent) -> CoachIntentName:
    """Apply code-level strong rules before using the primary intent."""
    text = (message or "").strip()
    if any(keyword in text for keyword in _HEALTH_OVERRIDE_HINTS):
        return "health"
    return intent.primary_intent


def _resolve_composed_order(intent: CoachIntent) -> list[CoachIntentName]:
    routes = [intent.primary_intent, *intent.secondary_intents]
    filtered: list[CoachIntentName] = []
    for route in routes:
        if route == "fallback":
            continue
        if route not in filtered:
            filtered.append(route)
    if not filtered:
        return ["fallback"]

    route_set = set(filtered)
    # B3 explicit combinations with deterministic order.
    if route_set == {"health", "prematch"}:
        return ["health", "prematch"]
    if route_set == {"postmatch", "health"}:
        return ["postmatch", "health"]
    if route_set == {"prematch", "postmatch"}:
        return ["prematch", "postmatch"]

    return filtered


def default_coach_safety_gate(intent: CoachIntent, ordered_routes: list[CoachIntentName], message: str) -> CoachSafetyGateDecision:
    """Default safety gate hook placeholder for B4.

    It currently records lightweight risk metadata only.
    """
    return CoachSafetyGateDecision(
        allowed_routes=list(ordered_routes),
        metadata={"risk_level": intent.risk_level},
    )


def _apply_safety_gate(
    intent: CoachIntent,
    *,
    ordered_routes: list[CoachIntentName],
    message: str,
    safety_gate: CoachSafetyGateHook | None,
) -> tuple[list[CoachIntentName], dict[str, Any] | None]:
    hook = safety_gate or default_coach_safety_gate
    decision = hook(intent, list(ordered_routes), message)

    if decision is None:
        return ordered_routes, None

    metadata = dict(decision.metadata or {})
    metadata.setdefault("blocked", decision.blocked)
    if decision.reason:
        metadata["reason"] = decision.reason

    if decision.blocked:
        return ["fallback"], metadata

    if decision.allowed_routes is None:
        return ordered_routes, metadata

    filtered: list[CoachIntentName] = []
    for route in decision.allowed_routes:
        if route not in {"prematch", "postmatch", "health", "fallback"}:
            continue
        if route not in filtered:
            filtered.append(route)
    if not filtered:
        filtered = ["fallback"]
    return filtered, metadata
