"""Intent schema and layered detection utilities for coach runtime."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal, Mapping, Protocol

CoachIntentName = Literal["prematch", "postmatch", "health", "fallback"]
CoachRiskLevel = Literal["low", "medium", "high"]

_INTENT_ORDER: tuple[CoachIntentName, ...] = ("prematch", "postmatch", "health", "fallback")
_RISK_ORDER: tuple[CoachRiskLevel, ...] = ("low", "medium", "high")

_PREMATCH_HINTS = ("赛前", "上场前", "今晚打", "打球注意", "热身", "怎么打", "策略", "双打", "单打")
_POSTMATCH_HINTS = ("复盘", "赛后", "刚打完", "今天打完", "总结", "下次重点", "失误", "回顾")
_HEALTH_HINTS = ("膝盖", "疼", "拉伤", "疲劳", "恢复", "睡眠", "心率", "hrv", "酸痛", "伤")
_HIGH_RISK_HINTS = ("剧烈疼", "刺痛", "拉伤", "扭伤", "崩", "头晕", "高烧", "180", "184", "185")
_PRE_RULE_HEALTH_OVERRIDE_HINTS = ("剧烈疼", "刺痛", "拉伤", "扭伤", "头晕")
_CLARIFICATION_HINTS = ("怎么办", "怎么弄", "看看", "帮我看", "你好", "在吗")


@dataclass
class CoachIntent:
    """Structured coach intent result."""

    primary_intent: CoachIntentName
    secondary_intents: list[CoachIntentName]
    slots: dict[str, Any]
    missing_slots: list[str]
    risk_level: CoachRiskLevel
    confidence: float = 0.0
    source: str = "rule_fallback"
    needs_clarification: bool = False
    clarification_reason: str | None = None


class CoachIntentClassifier(Protocol):
    """LLM-backed structured intent classifier protocol."""

    def __call__(self, message: str) -> Mapping[str, Any] | CoachIntent | None:
        ...


def detect_coach_intent(
    message: str,
    *,
    llm_classifier: CoachIntentClassifier | None = None,
) -> CoachIntent:
    """Detect intent using a 4-layer pipeline.

    1. Pre-rules: strong deterministic overrides and seed signals
    2. LLM classifier: structured output when available
    3. Normalize/guard: validate payload, fill defaults, protect schema
    4. Clarification decision: low-confidence or underspecified requests ask back
    """
    text = (message or "").strip()
    pre_rule = _pre_rule_detect(text)

    if llm_classifier is not None:
        raw = llm_classifier(text)
        llm_intent = _normalize_classifier_result(raw)
        if llm_intent is not None:
            guarded = _apply_guardrails(llm_intent, pre_rule=pre_rule, message=text)
            return _finalize_intent(guarded, message=text)

    fallback = classify_coach_intent(text)
    guarded = _apply_guardrails(fallback, pre_rule=pre_rule, message=text)
    return _finalize_intent(guarded, message=text)


def classify_coach_intent(message: str) -> CoachIntent:
    """Rule-based fallback classifier for coach intent schema."""
    text = (message or "").strip()
    lowered = text.lower()

    matched: list[CoachIntentName] = []
    if _contains_any(text, lowered, _PREMATCH_HINTS):
        matched.append("prematch")
    if _contains_any(text, lowered, _POSTMATCH_HINTS):
        matched.append("postmatch")
    if _contains_any(text, lowered, _HEALTH_HINTS):
        matched.append("health")
    if not matched:
        matched.append("fallback")

    primary, secondary = _split_primary_secondary(matched)
    slots = _extract_slots(text, primary=primary, secondary=secondary)
    missing_slots = _infer_missing_slots(slots, primary=primary)
    risk_level = _infer_risk_level(text, lowered, intents=[primary, *secondary], missing_slots=missing_slots)
    confidence = _estimate_rule_confidence(primary, secondary, missing_slots, text=text, lowered=lowered)

    return CoachIntent(
        primary_intent=primary,
        secondary_intents=secondary,
        slots=slots,
        missing_slots=missing_slots,
        risk_level=risk_level,
        confidence=confidence,
        source="rule_fallback",
    )


def normalize_intent_payload(payload: Mapping[str, Any]) -> CoachIntent:
    """Normalize and validate a structured intent payload."""
    raw_primary = str(payload.get("primary_intent", "fallback")).strip().lower()
    primary = _normalize_intent_name(raw_primary)

    secondary_raw = payload.get("secondary_intents", [])
    secondary: list[CoachIntentName] = []
    if isinstance(secondary_raw, list):
        for item in secondary_raw:
            normalized = _normalize_intent_name(str(item).strip().lower())
            if normalized in {primary, "fallback"}:
                continue
            if normalized not in secondary:
                secondary.append(normalized)

    slots = payload.get("slots", {})
    if not isinstance(slots, dict):
        slots = {}

    missing_slots_raw = payload.get("missing_slots", [])
    missing_slots: list[str] = []
    if isinstance(missing_slots_raw, list):
        for item in missing_slots_raw:
            if isinstance(item, str):
                key = item.strip()
                if key and key not in missing_slots:
                    missing_slots.append(key)

    inferred_missing = _infer_missing_slots(slots, primary=primary)
    for key in inferred_missing:
        if key not in missing_slots:
            missing_slots.append(key)

    confidence = _normalize_confidence(payload.get("confidence"))
    source = str(payload.get("source", "llm_structured")).strip() or "llm_structured"
    needs_clarification = bool(payload.get("needs_clarification", False))
    clarification_reason = payload.get("clarification_reason")
    if clarification_reason is not None and not isinstance(clarification_reason, str):
        clarification_reason = str(clarification_reason)

    return CoachIntent(
        primary_intent=primary,
        secondary_intents=secondary,
        slots=slots,
        missing_slots=missing_slots,
        risk_level=_normalize_risk_level(payload.get("risk_level")),
        confidence=confidence,
        source=source,
        needs_clarification=needs_clarification,
        clarification_reason=clarification_reason,
    )


def _normalize_classifier_result(raw: Mapping[str, Any] | CoachIntent | None) -> CoachIntent | None:
    if raw is None:
        return None
    if isinstance(raw, CoachIntent):
        return raw
    if isinstance(raw, Mapping):
        return normalize_intent_payload(raw)
    return None


def _pre_rule_detect(message: str) -> dict[str, Any]:
    lowered = message.lower()
    if _contains_any(message, lowered, _PRE_RULE_HEALTH_OVERRIDE_HINTS):
        return {
            "forced_primary_intent": "health",
            "forced_risk_level": "high",
            "reason": "strong_health_risk_signal",
        }
    return {}


def _apply_guardrails(intent: CoachIntent, *, pre_rule: Mapping[str, Any], message: str) -> CoachIntent:
    primary = intent.primary_intent
    secondary = list(intent.secondary_intents)
    risk_level = intent.risk_level
    source = intent.source

    forced_primary = pre_rule.get("forced_primary_intent")
    if forced_primary in {"prematch", "postmatch", "health", "fallback"}:
        if primary != forced_primary:
            if primary != "fallback" and primary not in secondary:
                secondary.insert(0, primary)
            primary = forced_primary
            source = f"{source}+pre_rule"

    forced_risk = pre_rule.get("forced_risk_level")
    if forced_risk in _RISK_ORDER and _RISK_ORDER.index(forced_risk) > _RISK_ORDER.index(risk_level):
        risk_level = forced_risk

    missing_slots = _infer_missing_slots(intent.slots, primary=primary)
    return CoachIntent(
        primary_intent=primary,
        secondary_intents=[item for item in secondary if item != primary and item != "fallback"],
        slots=intent.slots,
        missing_slots=missing_slots,
        risk_level=risk_level,
        confidence=intent.confidence,
        source=source,
        needs_clarification=intent.needs_clarification,
        clarification_reason=intent.clarification_reason,
    )


def _finalize_intent(intent: CoachIntent, *, message: str) -> CoachIntent:
    needs_clarification, clarification_reason = _should_clarify(intent, message)
    return CoachIntent(
        primary_intent=intent.primary_intent,
        secondary_intents=intent.secondary_intents,
        slots=intent.slots,
        missing_slots=intent.missing_slots,
        risk_level=intent.risk_level,
        confidence=intent.confidence,
        source=intent.source,
        needs_clarification=needs_clarification,
        clarification_reason=clarification_reason,
    )


def _should_clarify(intent: CoachIntent, message: str) -> tuple[bool, str | None]:
    lowered = message.lower()
    if intent.needs_clarification:
        return True, intent.clarification_reason or "classifier_requested_clarification"
    if intent.primary_intent == "fallback":
        return True, "no_stable_intent_detected"
    if intent.confidence < 0.45:
        return True, "low_intent_confidence"
    if len(intent.missing_slots) >= 2:
        return True, "too_many_missing_slots"
    if intent.primary_intent == "fallback" or any(hint in message for hint in _CLARIFICATION_HINTS):
        if intent.confidence < 0.65 and not _contains_any(message, lowered, _PREMATCH_HINTS + _POSTMATCH_HINTS + _HEALTH_HINTS):
            return True, "underspecified_request"
    return False, None


def _contains_any(text: str, lowered: str, keywords: tuple[str, ...]) -> bool:
    for keyword in keywords:
        if keyword.isascii():
            if keyword in lowered:
                return True
        elif keyword in text:
            return True
    return False


def _split_primary_secondary(matched: list[CoachIntentName]) -> tuple[CoachIntentName, list[CoachIntentName]]:
    unique: list[CoachIntentName] = []
    for intent in _INTENT_ORDER:
        if intent in matched and intent not in unique:
            unique.append(intent)
    primary = unique[0] if unique else "fallback"
    secondary = [intent for intent in unique[1:] if intent != "fallback"]
    return primary, secondary


def _normalize_intent_name(raw: str) -> CoachIntentName:
    if raw in {"prematch", "postmatch", "health", "fallback"}:
        return raw  # type: ignore[return-value]
    return "fallback"


def _normalize_risk_level(raw: Any) -> CoachRiskLevel:
    candidate = str(raw or "").strip().lower()
    if candidate in _RISK_ORDER:
        return candidate  # type: ignore[return-value]
    return "medium"


def _normalize_confidence(raw: Any) -> float:
    try:
        value = float(raw)
    except (TypeError, ValueError):
        return 0.0
    if value < 0.0:
        return 0.0
    if value > 1.0:
        return 1.0
    return value


def _extract_slots(text: str, *, primary: CoachIntentName, secondary: list[CoachIntentName]) -> dict[str, Any]:
    slots: dict[str, Any] = {}
    intents = [primary, *secondary]
    if "prematch" in intents:
        slots["session_goal"] = text if text else None
        slots["match_format"] = "doubles" if "双打" in text else "singles" if "单打" in text else None
    if "postmatch" in intents:
        slots["review_text"] = text if text else None
    if "health" in intents:
        slots["health_signal"] = text if text else None
    return slots


def _infer_missing_slots(slots: Mapping[str, Any], *, primary: CoachIntentName) -> list[str]:
    required_by_primary: dict[CoachIntentName, tuple[str, ...]] = {
        "prematch": ("session_goal",),
        "postmatch": ("review_text",),
        "health": ("health_signal",),
        "fallback": tuple(),
    }
    missing: list[str] = []
    for key in required_by_primary[primary]:
        value = slots.get(key)
        if value is None:
            missing.append(key)
        elif isinstance(value, str) and not value.strip():
            missing.append(key)
    return missing


def _infer_risk_level(
    text: str,
    lowered: str,
    *,
    intents: list[CoachIntentName],
    missing_slots: list[str],
) -> CoachRiskLevel:
    if "health" in intents:
        if _contains_any(text, lowered, _HIGH_RISK_HINTS):
            return "high"
        if any(keyword in lowered for keyword in ("疼", "痛", "疲劳", "恢复")):
            return "medium"
        return "low"

    if missing_slots:
        return "medium"
    return "low"


def _estimate_rule_confidence(
    primary: CoachIntentName,
    secondary: list[CoachIntentName],
    missing_slots: list[str],
    *,
    text: str,
    lowered: str,
) -> float:
    if primary == "fallback":
        return 0.25

    score = 0.7
    if secondary:
        score += 0.1
    if missing_slots:
        score -= 0.15
    if primary == "health" and _contains_any(text, lowered, _HIGH_RISK_HINTS):
        score += 0.1
    if len(text) < 4:
        score -= 0.25
    return _normalize_confidence(score)
