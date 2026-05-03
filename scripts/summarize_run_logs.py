#!/usr/bin/env python3
"""Summarize structured manager logs into a compact markdown report."""

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

from deerflow.evaluation.run_log_report import (
    extract_manager_structured_records,
    format_run_log_markdown,
    summarize_run_logs,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Summarize structured run logs.")
    parser.add_argument("--log-file", required=True, help="Path to the log file to summarize.")
    parser.add_argument("--output", default="", help="Optional path to write the markdown summary.")
    parser.add_argument("--json-output", default="", help="Optional path to write the JSON summary.")
    args = parser.parse_args()

    text = Path(args.log_file).read_text(encoding="utf-8")
    summary = summarize_run_logs(extract_manager_structured_records(text))
    rendered = format_run_log_markdown(summary)
    print(rendered, end="")

    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(rendered, encoding="utf-8")
    if args.json_output:
        json_output_path = Path(args.json_output)
        json_output_path.parent.mkdir(parents=True, exist_ok=True)
        json_output_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
