#!/usr/bin/env python3
"""Run offline badminton coach evaluation from sample cases."""

from __future__ import annotations

import argparse
import os
import site
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
HARNESS_DIR = ROOT_DIR / "backend" / "packages" / "harness"
VENV_PYTHON = ROOT_DIR / "backend" / ".venv" / "bin" / "python"
if VENV_PYTHON.exists() and Path(sys.executable).resolve() != VENV_PYTHON.resolve():
    os.execv(str(VENV_PYTHON), [str(VENV_PYTHON), __file__, *sys.argv[1:]])
for site_packages_dir in sorted((ROOT_DIR / "backend" / ".venv" / "lib").glob("python*/site-packages")):
    site.addsitedir(str(site_packages_dir))
if str(HARNESS_DIR) not in sys.path:
    sys.path.insert(0, str(HARNESS_DIR))

from deerflow.evaluation.coach_eval import evaluate_cases, format_markdown_report, load_eval_cases


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate badminton coach sample cases.")
    parser.add_argument(
        "--cases",
        default=str(ROOT_DIR / "docs" / "eval" / "coach_eval_cases.json"),
        help="Path to the evaluation case JSON file.",
    )
    parser.add_argument(
        "--output",
        default="",
        help="Optional path to write the markdown report.",
    )
    args = parser.parse_args()

    report = evaluate_cases(load_eval_cases(args.cases))
    rendered = format_markdown_report(report)
    print(rendered, end="")

    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(rendered, encoding="utf-8")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
