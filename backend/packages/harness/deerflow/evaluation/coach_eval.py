"""Offline evaluation helpers for badminton coach flows."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from statistics import mean
from tempfile import TemporaryDirectory
from typing import Any
from unittest.mock import patch

from deerflow.config.paths import Paths
from deerflow.domain.coach import (
    analyze_health_image_text,
    build_health_recovery_advice,
    build_prematch_advice,
    extract_postmatch_review,
    render_coach_route_payload,
)
from deerflow.domain.coach.profile_store import process_postmatch_message


def load_eval_cases(path: str | Path) -> list[dict[str, Any]]:
    """Load evaluation cases from a JSON file."""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError("Evaluation cases must be a JSON array")
    return [case for case in data if isinstance(case, dict)]


def evaluate_cases(cases: list[dict[str, Any]]) -> dict[str, Any]:
    """Evaluate offline coach cases and return an aggregate report."""
    results = [_evaluate_case(case) for case in cases]
    if not results:
        return {
            "summary": {"case_count": 0, "average_score": 0.0, "dimension_scores": {}},
            "failed_samples": [],
            "results": [],
        }

    dimension_names = _collect_dimension_names(results)
    dimension_scores = {}
    for name in dimension_names:
        values = [result["scores"][name] for result in results if name in result["scores"]]
        dimension_scores[name] = round(mean(values), 2) if values else 0.0
    average_score = round(mean(result["overall_score"] for result in results), 2)
    failed_samples = [
        {
            "case_id": result["case_id"],
            "expected_route": result["expected_route"],
            "predicted_route": result["predicted_route"],
            "overall_score": result["overall_score"],
            "failures": result["failures"],
        }
        for result in results
        if result["overall_score"] < 4.0 or result["predicted_route"] != result["expected_route"]
    ]
    return {
        "summary": {
            "case_count": len(results),
            "average_score": average_score,
            "dimension_scores": dimension_scores,
        },
        "failed_samples": failed_samples,
        "results": results,
    }


def format_markdown_report(report: dict[str, Any]) -> str:
    """Render a compact markdown report for offline coach evaluation."""
    summary = report["summary"]
    lines = [
        "# Coach Offline Evaluation Report",
        "",
        f"- Cases: {summary['case_count']}",
        f"- Average score: {summary['average_score']:.2f}/5",
        "",
        "## Dimension Scores",
        "",
    ]
    for name, value in summary["dimension_scores"].items():
        lines.append(f"- {name}: {value:.2f}/5")

    lines.extend(["", "## Failed Samples", ""])
    if not report["failed_samples"]:
        lines.append("- None")
    else:
        for sample in report["failed_samples"]:
            lines.append(
                f"- {sample['case_id']}: expected `{sample['expected_route']}`, got `{sample['predicted_route']}`, "
                f"score={sample['overall_score']:.2f}, failures={'; '.join(sample['failures'])}"
            )

    return "\n".join(lines) + "\n"


def _evaluate_case(case: dict[str, Any]) -> dict[str, Any]:
    case_id = str(case.get("id", "unknown"))
    expected_route = str(case.get("expected_route", "fallback"))
    predicted_intents = _detect_intents(case)
    predicted_route = predicted_intents[0]
    predicted_secondary_intents = predicted_intents[1:]
    predicted_execution_order = _resolve_execution_order(predicted_intents)
    output = _run_case(case, predicted_route)

    scores = {
        "route": 5.0 if predicted_route == expected_route else 0.0,
        "structure": _score_structure(predicted_route, output),
        "actionability": _score_actionability(predicted_route, output),
        "grounding": _score_grounding(predicted_route, output),
        "safety": _score_safety(predicted_route, output),
    }
    mixed_intent_score = _score_mixed_intent_ordering(
        case,
        predicted_route=predicted_route,
        predicted_secondary_intents=predicted_secondary_intents,
        predicted_execution_order=predicted_execution_order,
    )
    if mixed_intent_score is not None:
        scores["mixed_intent_ordering"] = mixed_intent_score

    persona_score = _score_persona_consistency(case, output)
    if persona_score is not None:
        scores["persona_consistency"] = persona_score

    writeback_score = _score_writeback_correctness(case)
    if writeback_score is not None:
        scores["writeback_correctness"] = writeback_score

    overall_score = round(mean(scores.values()), 2)

    failures: list[str] = []
    if predicted_route != expected_route:
        failures.append("route mismatch")
    for name, value in scores.items():
        if value < 4.0:
            failures.append(f"{name}<{value:.1f}")

    return {
        "case_id": case_id,
        "expected_route": expected_route,
        "predicted_route": predicted_route,
        "predicted_secondary_intents": predicted_secondary_intents,
        "predicted_execution_order": predicted_execution_order,
        "scores": scores,
        "overall_score": overall_score,
        "failures": failures,
    }


def _detect_intents(case: dict[str, Any]) -> list[str]:
    message = str(case.get("message", ""))
    image_summary = str(case.get("image_summary", ""))
    combined = f"{message}\n{image_summary}"
    if image_summary.strip():
        return ["health"]

    positions: list[tuple[int, str]] = []
    for intent, keywords in (
        ("prematch", ("今晚", "等会", "赛前", "上场前", "注意什么", "热身", "打球前")),
        ("postmatch", ("复盘", "今天打完", "赛后", "刚打完", "问题出在", "下次重点")),
        ("health", ("心率", "HRV", "睡眠", "训练负荷", "恢复", "酸痛", "肩膀", "膝盖", "疼", "痛")),
    ):
        hits = [combined.find(keyword) for keyword in keywords if keyword in combined]
        if hits:
            positions.append((min(hits), intent))

    positions.sort(key=lambda item: item[0])
    intents = [intent for _, intent in positions]
    return intents or ["fallback"]


def _resolve_execution_order(intents: list[str]) -> list[str]:
    if "health" in intents and "prematch" in intents:
        return ["health", "prematch"]
    if "postmatch" in intents and "health" in intents:
        return ["postmatch", "health"]
    if "postmatch" in intents and "prematch" in intents:
        return intents
    return intents


def _run_case(case: dict[str, Any], route: str) -> Any:
    persona = case.get("persona")
    if route == "prematch":
        review_logs = [
            (Path(f"sample-{index}.md"), content)
            for index, content in enumerate(case.get("review_logs", []), start=1)
            if isinstance(content, str)
        ]
        advice = build_prematch_advice(
            str(case.get("message", "")),
            memory_data=case.get("memory_data", {"facts": []}),
            coach_profile=case.get("coach_profile"),
            review_logs=review_logs,
            weather=case.get("weather"),
        )
        return {
            "focus_points": advice.focus_points,
            "warmup": advice.warmup,
            "risk_reminders": advice.risk_reminders,
            "cited_context": advice.cited_context,
            "follow_up_questions": advice.follow_up_questions,
            "response_text": render_coach_route_payload(
                route,
                {
                    "focus_points": advice.focus_points,
                    "warmup": advice.warmup,
                    "risk_reminders": advice.risk_reminders,
                    "follow_up_questions": advice.follow_up_questions,
                },
                persona=persona,
            ),
        }
    if route == "postmatch":
        review = extract_postmatch_review(str(case.get("message", "")))
        return {
            "summary": review.summary,
            "technical_observations": review.technical_observations,
            "improvements": review.improvements,
            "next_focus": review.next_focus,
            "response_text": render_coach_route_payload(
                route,
                {
                    "summary": review.summary,
                    "next_focus": review.next_focus,
                },
                persona=persona,
            ),
        }
    if route == "health":
        observation = analyze_health_image_text(str(case.get("image_summary") or case.get("message", "")))
        advice = build_health_recovery_advice(observation)
        return {
            "risk_level": advice.risk_level,
            "structured_observations": advice.structured_observations,
            "recovery_actions": advice.recovery_actions,
            "next_session_intensity": advice.next_session_intensity,
            "follow_up_question": advice.follow_up_question,
            "response_text": render_coach_route_payload(
                route,
                {
                    "structured_observations": advice.structured_observations,
                    "recovery_actions": advice.recovery_actions,
                    "next_session_intensity": advice.next_session_intensity,
                    "follow_up_question": advice.follow_up_question,
                },
                persona=persona,
            ),
        }
    return {"message": str(case.get("message", ""))}


def _score_structure(route: str, output: Any) -> float:
    if route == "prematch":
        return 5.0 if output["focus_points"] and output["warmup"] and output["risk_reminders"] else 2.0
    if route == "postmatch":
        return 5.0 if output["summary"] and output["next_focus"] else 2.0
    if route == "health":
        return 5.0 if output["structured_observations"] and output["recovery_actions"] else 2.0
    return 1.0


def _score_actionability(route: str, output: Any) -> float:
    if route == "prematch":
        return 5.0 if len(output["focus_points"]) >= 2 and output["risk_reminders"] else 3.0
    if route == "postmatch":
        return 5.0 if output["next_focus"] else 2.0
    if route == "health":
        return 5.0 if output["next_session_intensity"] and output["follow_up_question"] else 3.0
    return 1.0


def _score_grounding(route: str, output: Any) -> float:
    if route == "prematch":
        return 5.0 if output["cited_context"] else 2.0
    if route == "postmatch":
        return 5.0 if output["technical_observations"] or output["improvements"] else 2.0
    if route == "health":
        return 5.0 if output["structured_observations"] else 2.0
    return 1.0


def _score_safety(route: str, output: Any) -> float:
    if route == "prematch":
        return 5.0 if output["risk_reminders"] else 2.0
    if route == "postmatch":
        return 4.0 if output["next_focus"] else 2.0
    if route == "health":
        text = f"{output['next_session_intensity']} {' '.join(output['recovery_actions'])}"
        return 5.0 if any(keyword in text for keyword in ("恢复", "低强度", "中低强度")) else 2.0
    return 1.0


def _score_mixed_intent_ordering(
    case: dict[str, Any],
    *,
    predicted_route: str,
    predicted_secondary_intents: list[str],
    predicted_execution_order: list[str],
) -> float | None:
    expected_primary = case.get("expected_primary_intent")
    expected_secondary = case.get("expected_secondary_intents")
    expected_order = case.get("expected_execution_order")

    checks = 0
    matched = 0

    if isinstance(expected_primary, str) and expected_primary:
        checks += 1
        if predicted_route == expected_primary:
            matched += 1

    if isinstance(expected_secondary, list):
        normalized_secondary = [item for item in expected_secondary if isinstance(item, str)]
        if normalized_secondary:
            checks += 1
            if predicted_secondary_intents == normalized_secondary:
                matched += 1

    if isinstance(expected_order, list):
        normalized_order = [item for item in expected_order if isinstance(item, str)]
        if normalized_order:
            checks += 1
            if predicted_execution_order == normalized_order:
                matched += 1

    if checks == 0:
        return None

    return round(5.0 * matched / checks, 2)


def _score_persona_consistency(case: dict[str, Any], output: Any) -> float | None:
    expectations = case.get("persona_expectations")
    if not isinstance(expectations, dict):
        return None

    response_text = str(case.get("candidate_response") or output.get("response_text") or _stringify_output(output))
    required_markers = [item for item in expectations.get("required_markers", []) if isinstance(item, str) and item]
    forbidden_markers = [item for item in expectations.get("forbidden_markers", []) if isinstance(item, str) and item]

    checks = len(required_markers) + len(forbidden_markers)
    if checks == 0:
        return None

    matched = sum(1 for marker in required_markers if marker in response_text)
    matched += sum(1 for marker in forbidden_markers if marker not in response_text)
    return round(5.0 * matched / checks, 2)


def _score_writeback_correctness(case: dict[str, Any]) -> float | None:
    expectations = case.get("writeback_expectations")
    if not isinstance(expectations, dict):
        return None

    message = str(case.get("message", "")).strip()
    if not message:
        return 0.0

    with TemporaryDirectory() as tmp_dir:
        paths = Paths(base_dir=tmp_dir)
        with patch("deerflow.domain.coach.profile_store.get_paths", return_value=paths):
            persisted = process_postmatch_message(
                message,
                occurred_at=datetime(2026, 4, 5, 12, 0, tzinfo=UTC),
            )

    profile = persisted.profile
    tech_profile = profile.get("tech_profile", {}) if isinstance(profile, dict) else {}
    weaknesses = tech_profile.get("weaknesses", []) if isinstance(tech_profile, dict) else []
    strengths = tech_profile.get("strengths", []) if isinstance(tech_profile, dict) else []
    focus_topics = tech_profile.get("focus_topics", []) if isinstance(tech_profile, dict) else []

    checks = 0
    matched = 0

    for keyword in expectations.get("expected_weakness_contains", []):
        if not isinstance(keyword, str) or not keyword:
            continue
        checks += 1
        if any(isinstance(item, dict) and keyword in str(item.get("name", "")) for item in weaknesses):
            matched += 1

    for keyword in expectations.get("expected_strength_contains", []):
        if not isinstance(keyword, str) or not keyword:
            continue
        checks += 1
        if any(isinstance(item, dict) and keyword in str(item.get("name", "")) for item in strengths):
            matched += 1

    for keyword in expectations.get("expected_focus_contains", []):
        if not isinstance(keyword, str) or not keyword:
            continue
        checks += 1
        if any(isinstance(item, str) and keyword in item for item in focus_topics):
            matched += 1

    expect_review_log = expectations.get("expect_review_log")
    if isinstance(expect_review_log, bool):
        checks += 1
        if persisted.review_log_path.exists() is expect_review_log:
            matched += 1

    if checks == 0:
        return None

    return round(5.0 * matched / checks, 2)


def _stringify_output(output: Any) -> str:
    if isinstance(output, dict):
        return json.dumps(output, ensure_ascii=False, sort_keys=True)
    if hasattr(output, "__dict__"):
        return json.dumps(output.__dict__, ensure_ascii=False, sort_keys=True, default=str)
    return str(output)


def _collect_dimension_names(results: list[dict[str, Any]]) -> tuple[str, ...]:
    ordered = (
        "route",
        "structure",
        "actionability",
        "grounding",
        "safety",
        "mixed_intent_ordering",
        "persona_consistency",
        "writeback_correctness",
    )
    return tuple(name for name in ordered if any(name in result["scores"] for result in results))
