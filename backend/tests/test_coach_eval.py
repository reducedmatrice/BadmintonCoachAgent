"""Tests for offline badminton coach evaluation."""

from deerflow.evaluation.coach_eval import evaluate_cases, format_markdown_report


def test_evaluate_cases_outputs_dimension_scores_and_failures():
    report = evaluate_cases(
        [
            {
                "id": "prematch-1",
                "expected_route": "prematch",
                "message": "今晚打双打注意什么，我最近后场回位还是慢。",
                "coach_profile": {
                    "tech_profile": {
                        "weaknesses": [{"name": "后场步法回位慢", "severity": 0.9}]
                    }
                },
            },
            {
                "id": "route-miss",
                "expected_route": "postmatch",
                "message": "今晚打球注意什么",
            },
        ]
    )

    assert report["summary"]["case_count"] == 2
    assert "route" in report["summary"]["dimension_scores"]
    assert any(sample["case_id"] == "route-miss" for sample in report["failed_samples"])

    rendered = format_markdown_report(report)
    assert "Coach Offline Evaluation Report" in rendered
    assert "Failed Samples" in rendered


def test_evaluate_cases_supports_mixed_persona_and_writeback_dimensions():
    report = evaluate_cases(
        [
            {
                "id": "mixed-intent",
                "expected_route": "prematch",
                "expected_primary_intent": "prematch",
                "expected_secondary_intents": ["health"],
                "expected_execution_order": ["health", "prematch"],
                "message": "今晚打球前怎么热身？昨天肩膀有点酸。",
            },
            {
                "id": "persona-consistency",
                "expected_route": "prematch",
                "message": "今天打球前提醒我一下。",
                "persona": {
                    "tone": "supportive",
                    "verbosity": "balanced",
                    "questioning_style": "guided",
                    "encouragement_style": "calm",
                },
                "persona_expectations": {
                    "required_markers": ["你今天上来先别铺太开", "你再补我一句"],
                    "forbidden_markers": ["你先直接回我一句", "今天重点"],
                },
            },
            {
                "id": "writeback-correctness",
                "expected_route": "postmatch",
                "message": "今天打完感觉后场回位还是慢，不过反手更敢发力了。下次重点继续盯后场启动和反手稳定性。",
                "writeback_expectations": {
                    "expected_weakness_contains": ["后场"],
                    "expected_strength_contains": ["反手"],
                    "expected_focus_contains": ["后场", "反手"],
                    "expect_review_log": True,
                },
            },
        ]
    )

    dimensions = report["summary"]["dimension_scores"]
    assert "mixed_intent_ordering" in dimensions
    assert "persona_consistency" in dimensions
    assert "writeback_correctness" in dimensions

    rendered = format_markdown_report(report)
    assert "mixed_intent_ordering" in rendered
    assert "persona_consistency" in rendered
    assert "writeback_correctness" in rendered
