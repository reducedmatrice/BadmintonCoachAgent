#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
LOG_FILE="${LOG_FILE:-$ROOT_DIR/logs/gateway.log}"
DB_PATH="${DB_PATH:-}"

if [[ -n "$DB_PATH" ]]; then
  exec python3 "$ROOT_DIR/scripts/import_structured_logs.py" --log-file "$LOG_FILE" --db-path "$DB_PATH"
fi

exec python3 "$ROOT_DIR/scripts/import_structured_logs.py" --log-file "$LOG_FILE"
