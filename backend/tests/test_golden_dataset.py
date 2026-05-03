"""Tests for coach golden dataset generation."""

from __future__ import annotations

from pathlib import Path

from deerflow.evaluation.golden_dataset import (
    TARGET_SCENARIO_COUNTS,
    build_golden_dataset,
    load_seed_cases,
    summarize_golden_dataset,
    validate_golden_dataset,
)


ROOT_DIR = Path(__file__).resolve().parents[2]


def test_build_golden_dataset_generates_500_labeled_cases():
    seed_cases = load_seed_cases(ROOT_DIR / "docs" / "eval" / "coach_eval_cases.json")

    dataset = build_golden_dataset(seed_cases)
    validate_golden_dataset(dataset)
    summary = summarize_golden_dataset(dataset)

    assert len(dataset) == 500
    assert summary["total_cases"] == 500
    assert summary["scenario_counts"] == TARGET_SCENARIO_COUNTS
    assert set(summary["source_counts"]) >= {"eval_case", "gateway_log", "memory_log", "synthetic_boundary"}
    assert all(case["case_id"] for case in dataset)
    assert all("source_case_id" in case for case in dataset)


def test_validate_golden_dataset_rejects_wrong_distribution():
    seed_cases = load_seed_cases(ROOT_DIR / "docs" / "eval" / "coach_eval_cases.json")
    dataset = build_golden_dataset(seed_cases)
    broken = dataset[:-1]

    try:
        validate_golden_dataset(broken)
    except ValueError as exc:
        assert "exactly 500 cases" in str(exc)
    else:
        raise AssertionError("Expected validation to fail for incorrect size")
