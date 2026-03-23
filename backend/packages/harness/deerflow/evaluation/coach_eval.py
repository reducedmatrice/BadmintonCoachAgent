"""Offline evaluation helpers for badminton coach flows."""

from __future__ import annotations

import json
from pathlib import Path
from statistics import mean
from typing import Any

from deerflow.domain.coach import (
    analyze_health_image_text,
    build_health_recovery_advice,
    build_prematch_advice,
    extract_postmatch_review,
)


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

    dimension_names = ("route", "structure", "actionability", "grounding", "safety")
    dimension_scores = {
        name: round(mean(result["scores"][name] for result in results), 2) for name in dimension_names
    }
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
    predicted_route = _detect_route(case)
    output = _run_case(case, predicted_route)

    scores = {
        "route": 5.0 if predicted_route == expected_route else 0.0,
        "structure": _score_structure(predicted_route, output),
        "actionability": _score_actionability(predicted_route, output),
        "grounding": _score_grounding(predicted_route, output),
        "safety": _score_safety(predicted_route, output),
    }
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
        "scores": scores,
        "overall_score": overall_score,
        "failures": failures,
    }


def _detect_route(case: dict[str, Any]) -> str:
    message = str(case.get("message", ""))
    image_summary = str(case.get("image_summary", ""))
    combined = f"{message}\n{image_summary}"
    if image_summary.strip():
        return "health"
    if any(keyword in combined for keyword in ("心率", "HRV", "睡眠", "训练负荷", "恢复", "酸痛", "疼")):
        return "health"
    if any(keyword in combined for keyword in ("复盘", "今天打完", "赛后", "刚打完", "问题出在")):
        return "postmatch"
    if any(keyword in combined for keyword in ("今晚", "等会", "赛前", "上场前", "注意什么")):
        return "prematch"
    return "fallback"


def _run_case(case: dict[str, Any], route: str) -> Any:
    if route == "prematch":
        review_logs = [
            (Path(f"sample-{index}.md"), content)
            for index, content in enumerate(case.get("review_logs", []), start=1)
            if isinstance(content, str)
        ]
        return build_prematch_advice(
            str(case.get("message", "")),
            memory_data=case.get("memory_data", {"facts": []}),
            coach_profile=case.get("coach_profile"),
            review_logs=review_logs,
            weather=case.get("weather"),
        )
    if route == "postmatch":
        return extract_postmatch_review(str(case.get("message", "")))
    if route == "health":
        observation = analyze_health_image_text(str(case.get("image_summary") or case.get("message", "")))
        return build_health_recovery_advice(observation)
    return {"message": str(case.get("message", ""))}


def _score_structure(route: str, output: Any) -> float:
    if route == "prematch":
        return 5.0 if output.focus_points and output.warmup and output.risk_reminders else 2.0
    if route == "postmatch":
        return 5.0 if output.summary and output.next_focus else 2.0
    if route == "health":
        return 5.0 if output.structured_observations and output.recovery_actions else 2.0
    return 1.0


def _score_actionability(route: str, output: Any) -> float:
    if route == "prematch":
        return 5.0 if len(output.focus_points) >= 2 and output.risk_reminders else 3.0
    if route == "postmatch":
        return 5.0 if output.next_focus else 2.0
    if route == "health":
        return 5.0 if output.next_session_intensity and output.follow_up_question else 3.0
    return 1.0


def _score_grounding(route: str, output: Any) -> float:
    if route == "prematch":
        return 5.0 if output.cited_context else 2.0
    if route == "postmatch":
        return 5.0 if output.technical_observations or output.improvements else 2.0
    if route == "health":
        return 5.0 if output.structured_observations else 2.0
    return 1.0


def _score_safety(route: str, output: Any) -> float:
    if route == "prematch":
        return 5.0 if output.risk_reminders else 2.0
    if route == "postmatch":
        return 4.0 if output.next_focus else 2.0
    if route == "health":
        text = f"{output.next_session_intensity} {' '.join(output.recovery_actions)}"
        return 5.0 if any(keyword in text for keyword in ("恢复", "低强度", "中低强度")) else 2.0
    return 1.0
