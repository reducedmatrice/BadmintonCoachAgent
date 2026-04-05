#!/usr/bin/env python3
"""Run offline coach evaluation cases and emit markdown/json reports."""

from __future__ import annotations

import argparse
import json
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
    parser = argparse.ArgumentParser(description="Run offline badminton coach evaluation.")
    parser.add_argument("--cases", required=True, help="Path to evaluation case JSON.")
    parser.add_argument("--output", default="", help="Optional markdown output path.")
    parser.add_argument("--json-output", default="", help="Optional JSON output path.")
    args = parser.parse_args()

    cases = load_eval_cases(args.cases)
    report = evaluate_cases(cases)
    rendered = format_markdown_report(report)
    print(rendered, end="")

    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(rendered, encoding="utf-8")

    if args.json_output:
        json_output_path = Path(args.json_output)
        json_output_path.parent.mkdir(parents=True, exist_ok=True)
        json_output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
