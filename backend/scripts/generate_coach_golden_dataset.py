from __future__ import annotations

import json
from pathlib import Path

from deerflow.evaluation.golden_dataset import (
    build_golden_dataset,
    load_seed_cases,
    summarize_golden_dataset,
    validate_golden_dataset,
    write_golden_dataset,
)


def main() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    seed_path = repo_root / "docs" / "eval" / "coach_eval_cases.json"
    output_path = repo_root / "docs" / "eval" / "coach_golden_dataset.json"
    summary_path = repo_root / "docs" / "eval" / "coach_golden_dataset_summary.json"

    seed_cases = load_seed_cases(seed_path)
    golden_cases = build_golden_dataset(seed_cases)
    validate_golden_dataset(golden_cases)
    write_golden_dataset(golden_cases, output_path)
    summary = summarize_golden_dataset(golden_cases)
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(f"Generated {summary['total_cases']} cases")
    print(f"Wrote dataset to {output_path}")
    print(f"Wrote summary to {summary_path}")


if __name__ == "__main__":
    main()
