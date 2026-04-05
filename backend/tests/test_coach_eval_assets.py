"""Validation for D3 offline evaluation assets and sample coverage."""

from __future__ import annotations

from pathlib import Path

from deerflow.evaluation.coach_eval import evaluate_cases, format_markdown_report, load_eval_cases


ROOT_DIR = Path(__file__).resolve().parents[2]


def test_docs_eval_cases_cover_required_routes_and_mixed_intent():
    cases = load_eval_cases(ROOT_DIR / "docs" / "eval" / "coach_eval_cases.json")

    expected_routes = {str(case.get("expected_route", "")) for case in cases}
    assert {"prematch", "postmatch", "health"}.issubset(expected_routes)
    assert any(case.get("expected_secondary_intents") for case in cases)


def test_docs_eval_cases_render_markdown_report():
    cases = load_eval_cases(ROOT_DIR / "docs" / "eval" / "coach_eval_cases.json")

    report = evaluate_cases(cases)
    rendered = format_markdown_report(report)

    assert report["summary"]["case_count"] >= 4
    assert "mixed_intent_ordering" in report["summary"]["dimension_scores"]
    assert "persona_consistency" in report["summary"]["dimension_scores"]
    assert "writeback_correctness" in report["summary"]["dimension_scores"]
    assert "Coach Offline Evaluation Report" in rendered


def test_llm_judge_prompt_is_kept_as_extension_entry():
    prompt = (ROOT_DIR / "docs" / "eval" / "coach_eval_judge_prompt.md").read_text(encoding="utf-8")

    assert "输出 JSON" in prompt
    assert "route" in prompt
    assert "structure" in prompt
    assert "actionability" in prompt
    assert "grounding" in prompt
    assert "safety" in prompt
