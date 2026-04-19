import argparse
import json
import re
from collections import Counter
from pathlib import Path


TARGET_KEYS = {
    "primary_intent",
    "secondary_intents",
    "slots",
    "missing_slots",
    "risk_level",
    "confidence",
    "needs_clarification",
    "clarification_reason",
}

ENUM_PRIMARY = {"prematch", "postmatch", "health", "fallback"}
ENUM_RISK = {"low", "medium", "high"}
ALLOWED_SLOT_KEYS = {
    "session_goal",
    "technical_focus",
    "match_format",
    "review_text",
    "health_signal",
    "time_context",
}


def strip_code_fence(text: str) -> str:
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\s*```$", "", text)
    return text.strip()


def extract_json_object(text: str) -> str | None:
    cleaned = strip_code_fence(text)
    if cleaned.startswith("{") and cleaned.endswith("}"):
        return cleaned

    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start != -1 and end != -1 and end > start:
        return cleaned[start : end + 1]
    return None


def parse_json(text: str):
    raw = extract_json_object(text)
    if raw is None:
        return None, "no_json_object"

    try:
        return json.loads(raw), None
    except Exception:
        return None, "invalid_json"


def normalize_secondary(value) -> list[str]:
    if not isinstance(value, list):
        return []
    out = []
    for item in value:
        if isinstance(item, str) and item not in out:
            out.append(item)
    return sorted(out)


def normalize_bool(value):
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered == "true":
            return True
        if lowered == "false":
            return False
    return value


def evaluate(pred_path: Path):
    lines = pred_path.read_text(encoding="utf-8").splitlines()
    total = len(lines)
    parsed_ok = 0
    schema_ok = 0
    primary_ok = 0
    secondary_ok = 0
    risk_ok = 0
    clarify_ok = 0
    all_core_ok = 0
    high_risk_total = 0
    high_risk_recall_hits = 0
    slot_key_ok = 0
    enum_primary_ok = 0
    enum_risk_ok = 0
    confidence_type_ok = 0
    primary_counter = Counter()
    parse_errors = Counter()

    for line in lines:
        row = json.loads(line)
        pred_obj, pred_err = parse_json(row["predict"])
        label_obj, label_err = parse_json(row["label"])

        if label_obj is None:
            raise ValueError(f"Invalid label JSON in predictions file: {label_err}")

        if pred_obj is None:
            parse_errors[pred_err] += 1
            continue

        parsed_ok += 1

        keys = set(pred_obj.keys())
        if keys == TARGET_KEYS:
            schema_ok += 1

        slots = pred_obj.get("slots", {})
        if isinstance(slots, dict) and set(slots.keys()).issubset(ALLOWED_SLOT_KEYS):
            slot_key_ok += 1

        pred_primary = pred_obj.get("primary_intent")
        label_primary = label_obj.get("primary_intent")
        if pred_primary in ENUM_PRIMARY:
            enum_primary_ok += 1
        if pred_primary == label_primary:
            primary_ok += 1
        primary_counter[(label_primary, pred_primary)] += 1

        pred_secondary = normalize_secondary(pred_obj.get("secondary_intents"))
        label_secondary = normalize_secondary(label_obj.get("secondary_intents"))
        if pred_secondary == label_secondary:
            secondary_ok += 1

        pred_risk = pred_obj.get("risk_level")
        if pred_risk in ENUM_RISK:
            enum_risk_ok += 1
        if pred_risk == label_obj.get("risk_level"):
            risk_ok += 1

        if isinstance(pred_obj.get("confidence"), (int, float)):
            confidence_type_ok += 1

        if normalize_bool(pred_obj.get("needs_clarification")) == normalize_bool(label_obj.get("needs_clarification")):
            clarify_ok += 1

        if (
            pred_primary == label_primary
            and pred_secondary == label_secondary
            and pred_obj.get("risk_level") == label_obj.get("risk_level")
            and normalize_bool(pred_obj.get("needs_clarification")) == normalize_bool(label_obj.get("needs_clarification"))
        ):
            all_core_ok += 1

        if label_obj.get("risk_level") == "high":
            high_risk_total += 1
            if pred_obj.get("risk_level") == "high":
                high_risk_recall_hits += 1

    def pct(value: int) -> float:
        return round((value / total) * 100, 2) if total else 0.0

    metrics = {
        "total_samples": total,
        "json_valid_rate": pct(parsed_ok),
        "schema_exact_match_rate": pct(schema_ok),
        "slot_key_allowed_rate": pct(slot_key_ok),
        "primary_intent_enum_rate": pct(enum_primary_ok),
        "risk_level_enum_rate": pct(enum_risk_ok),
        "confidence_numeric_rate": pct(confidence_type_ok),
        "primary_intent_accuracy": pct(primary_ok),
        "secondary_intents_accuracy": pct(secondary_ok),
        "risk_level_accuracy": pct(risk_ok),
        "needs_clarification_accuracy": pct(clarify_ok),
        "all_core_fields_accuracy": pct(all_core_ok),
        "high_risk_recall": round((high_risk_recall_hits / high_risk_total) * 100, 2) if high_risk_total else None,
        "parse_errors": dict(parse_errors),
        "top_primary_confusions": [
            {"label": label, "predict": pred, "count": count}
            for (label, pred), count in primary_counter.most_common(10)
            if label != pred
        ],
    }
    return metrics


def main():
    parser = argparse.ArgumentParser(description="Evaluate router intent predictions from LLaMA-Factory generated_predictions.jsonl")
    parser.add_argument("predictions", help="Path to generated_predictions.jsonl")
    parser.add_argument("--output", help="Optional path to save evaluation json")
    args = parser.parse_args()

    metrics = evaluate(Path(args.predictions))
    text = json.dumps(metrics, ensure_ascii=False, indent=2)
    print(text)

    if args.output:
        Path(args.output).write_text(text + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
