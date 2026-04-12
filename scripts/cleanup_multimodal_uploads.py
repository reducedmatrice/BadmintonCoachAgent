#!/usr/bin/env python3
"""Cleanup stale multimodal upload cache with writeback verification."""

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

from deerflow.domain.coach.upload_cache import cleanup_multimodal_upload_cache


def main() -> int:
    parser = argparse.ArgumentParser(description="Cleanup stale multimodal uploads.")
    parser.add_argument("--retention-days", type=int, default=30, help="Retention period in days before deletion eligibility.")
    args = parser.parse_args()

    result = cleanup_multimodal_upload_cache(retention_days=args.retention_days)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

