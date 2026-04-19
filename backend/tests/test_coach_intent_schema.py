"""Tests for coach intent schema and layered detection."""

from deerflow.domain.coach.intent import classify_coach_intent, detect_coach_intent, normalize_intent_payload


def test_classify_single_intent_prematch():
    intent = classify_coach_intent("今晚打双打，帮我安排赛前热身和策略")

    assert intent.primary_intent == "prematch"
    assert intent.secondary_intents == []
    assert intent.slots["match_format"] == "doubles"
    assert intent.missing_slots == []
    assert intent.risk_level == "low"
    assert intent.source == "rule_fallback"
    assert intent.confidence > 0.6


def test_classify_mixed_intent_postmatch_with_health():
    intent = classify_coach_intent("今天打完后膝盖刺痛，帮我复盘并说下恢复建议")

    assert intent.primary_intent == "postmatch"
    assert "health" in intent.secondary_intents
    assert intent.slots["review_text"] is not None
    assert intent.slots["health_signal"] is not None
    assert intent.risk_level == "high"


def test_normalize_payload_enforces_schema_and_missing_slots():
    normalized = normalize_intent_payload(
        {
            "primary_intent": "prematch",
            "secondary_intents": ["health", "unknown", "health"],
            "slots": {"session_goal": "  "},
            "missing_slots": ["custom_missing"],
            "risk_level": "invalid",
            "confidence": 2,
        }
    )

    assert normalized.primary_intent == "prematch"
    assert normalized.secondary_intents == ["health"]
    assert "session_goal" in normalized.missing_slots
    assert "custom_missing" in normalized.missing_slots
    assert normalized.risk_level == "medium"
    assert normalized.confidence == 1.0


def test_detect_coach_intent_prefers_llm_structured_result_when_available():
    def _classifier(_message: str):
        return {
            "primary_intent": "prematch",
            "secondary_intents": ["health"],
            "slots": {"session_goal": "今晚打球", "health_signal": "肩膀酸"},
            "missing_slots": [],
            "risk_level": "medium",
            "confidence": 0.88,
            "source": "llm_structured",
        }

    intent = detect_coach_intent("今晚打球前怎么热身？昨天肩膀也有点酸。", llm_classifier=_classifier)

    assert intent.primary_intent == "prematch"
    assert intent.secondary_intents == ["health"]
    assert intent.source == "llm_structured"
    assert intent.confidence == 0.88
    assert intent.needs_clarification is False


def test_detect_coach_intent_applies_pre_rule_health_override_to_llm_result():
    def _classifier(_message: str):
        return {
            "primary_intent": "prematch",
            "secondary_intents": [],
            "slots": {"session_goal": "今晚打球"},
            "missing_slots": [],
            "risk_level": "low",
            "confidence": 0.91,
            "source": "llm_structured",
        }

    intent = detect_coach_intent("赛前计划先不说了，我现在膝盖刺痛。", llm_classifier=_classifier)

    assert intent.primary_intent == "health"
    assert intent.risk_level == "high"
    assert intent.source.endswith("+pre_rule")


def test_detect_coach_intent_marks_low_confidence_query_for_clarification():
    def _classifier(_message: str):
        return {
            "primary_intent": "fallback",
            "secondary_intents": [],
            "slots": {},
            "missing_slots": [],
            "risk_level": "medium",
            "confidence": 0.2,
            "source": "llm_structured",
        }

    intent = detect_coach_intent("你好", llm_classifier=_classifier)

    assert intent.needs_clarification is True
    assert intent.clarification_reason in {"low_intent_confidence", "no_stable_intent_detected"}


def test_classify_natural_prematch_training_goal_without_clarification():
    intent = detect_coach_intent("a 今晚去打球，我准备好好练练我的步伐，因为上次练步伐的时候我绊了一下，然后教练教了我如何去启动")

    assert intent.primary_intent == "prematch"
    assert intent.slots["session_goal"] is not None
    assert "步伐" in intent.slots["session_goal"]
    assert intent.needs_clarification is False


def test_classify_natural_postmatch_summary_without_clarification():
    intent = detect_coach_intent("刚打完球，今天启动还是慢了，帮我复盘一下下次重点")

    assert intent.primary_intent == "postmatch"
    assert intent.slots["review_text"] is not None
    assert intent.needs_clarification is False
