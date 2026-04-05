#!/usr/bin/env python3
"""Import structured manager logs into the analytics SQLite database."""

from __future__ import annotations

import argparse
import json
import os
import site
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
BACKEND_DIR = ROOT_DIR / "backend"
VENV_PYTHON = BACKEND_DIR / ".venv" / "bin" / "python"
if VENV_PYTHON.exists() and Path(sys.executable).resolve() != VENV_PYTHON.resolve():
    os.execv(str(VENV_PYTHON), [str(VENV_PYTHON), __file__, *sys.argv[1:]])
for site_packages_dir in sorted((BACKEND_DIR / ".venv" / "lib").glob("python*/site-packages")):
    site.addsitedir(str(site_packages_dir))
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.analytics.importer import import_manager_structured_log_file


def main() -> int:
    parser = argparse.ArgumentParser(description="Import structured manager logs into SQLite.")
    parser.add_argument("--log-file", required=True, help="Path to the gateway log file.")
    parser.add_argument("--db-path", default="", help="Optional analytics database path.")
    args = parser.parse_args()

    result = import_manager_structured_log_file(args.log_file, db_path=args.db_path or None)
    print(json.dumps(result.model_dump(), ensure_ascii=False, sort_keys=True))
    return 0 if result.status == "success" else 1


if __name__ == "__main__":
    raise SystemExit(main())
