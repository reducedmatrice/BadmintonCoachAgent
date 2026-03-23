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
