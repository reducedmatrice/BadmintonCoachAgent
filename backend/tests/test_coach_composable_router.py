"""Tests for composable mixed-intent coach routing."""

from __future__ import annotations

from deerflow.domain.coach.intent import normalize_intent_payload
from deerflow.domain.coach.router import CoachSafetyGateDecision, route_composable_intent


def test_composable_router_orders_health_then_prematch():
    intent = normalize_intent_payload(
        {
            "primary_intent": "prematch",
            "secondary_intents": ["health"],
            "slots": {"session_goal": "今晚打球", "health_signal": "肩膀酸"},
            "missing_slots": [],
            "risk_level": "medium",
        }
    )

    result = route_composable_intent("今晚打球前怎么热身？昨天肩膀也有点酸。", intent=intent, memory_data={"facts": []})

    assert result.ordered_routes == ["health", "prematch"]
    assert [step.payload["chain"] for step in result.steps] == ["health", "prematch"]


def test_composable_router_orders_postmatch_then_health():
    intent = normalize_intent_payload(
        {
            "primary_intent": "postmatch",
            "secondary_intents": ["health"],
            "slots": {"review_text": "今天打完", "health_signal": "膝盖不适"},
            "missing_slots": [],
            "risk_level": "medium",
        }
    )

    result = route_composable_intent("今天打完后场步法还是慢，另外膝盖也有点不舒服。", intent=intent)

    assert result.ordered_routes == ["postmatch", "health"]
    assert [step.payload["chain"] for step in result.steps] == ["postmatch", "health"]


def test_composable_router_orders_prematch_then_postmatch():
    intent = normalize_intent_payload(
        {
            "primary_intent": "prematch",
            "secondary_intents": ["postmatch"],
            "slots": {"session_goal": "今晚比赛", "review_text": "上次复盘"},
            "missing_slots": [],
            "risk_level": "low",
        }
    )

    result = route_composable_intent("今晚比赛前怎么准备，顺便结合上次复盘给建议。", intent=intent, memory_data={"facts": []})

    assert result.ordered_routes == ["prematch", "postmatch"]
    assert [step.payload["chain"] for step in result.steps] == ["prematch", "postmatch"]


def test_composable_router_keeps_route_boundaries_stable():
    intent = normalize_intent_payload(
        {
            "primary_intent": "prematch",
            "secondary_intents": ["health", "postmatch", "health"],
            "slots": {"session_goal": "今晚打球", "review_text": "上次复盘", "health_signal": "肩膀酸"},
            "missing_slots": [],
            "risk_level": "medium",
        }
    )

    result = route_composable_intent("组合意图测试", intent=intent, memory_data={"facts": []})

    assert result.ordered_routes == ["prematch", "health", "postmatch"]
    assert [step.route for step in result.steps] == ["prematch", "health", "postmatch"]
    assert len(result.steps) == 3


def test_composable_router_supports_safety_gate_route_filter():
    intent = normalize_intent_payload(
        {
            "primary_intent": "postmatch",
            "secondary_intents": ["health"],
            "slots": {"review_text": "今天打完", "health_signal": "膝盖不适"},
            "missing_slots": [],
            "risk_level": "medium",
        }
    )

    def _gate(_intent, ordered_routes, _message):
        assert ordered_routes == ["postmatch", "health"]
        return CoachSafetyGateDecision(
            allowed_routes=["health"],
            metadata={"policy": "health_first_only"},
        )

    result = route_composable_intent("组合路由 + gate", intent=intent, safety_gate=_gate)

    assert result.ordered_routes == ["health"]
    assert [step.route for step in result.steps] == ["health"]
    assert result.safety_gate is not None
    assert result.safety_gate["policy"] == "health_first_only"


def test_composable_router_supports_safety_gate_block():
    intent = normalize_intent_payload(
        {
            "primary_intent": "prematch",
            "secondary_intents": ["health"],
            "slots": {"session_goal": "今晚打球", "health_signal": "肩膀酸"},
            "missing_slots": [],
            "risk_level": "high",
        }
    )

    def _gate(_intent, _ordered_routes, _message):
        return CoachSafetyGateDecision(blocked=True, reason="manual_safety_review")

    result = route_composable_intent("需要人工审核", intent=intent, safety_gate=_gate)

    assert result.ordered_routes == ["fallback"]
    assert [step.route for step in result.steps] == ["fallback"]
    assert result.safety_gate is not None
    assert result.safety_gate["blocked"] is True
    assert result.safety_gate["reason"] == "manual_safety_review"
