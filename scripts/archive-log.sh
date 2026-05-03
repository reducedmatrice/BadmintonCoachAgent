#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 1 ]]; then
  echo "Usage: $0 <log-file>" >&2
  exit 1
fi

LOG_FILE="$1"

if [[ ! -f "$LOG_FILE" || ! -s "$LOG_FILE" ]]; then
  exit 0
fi

STAMP="$(date +"%Y%m%d-%H%M%S")"
DIRNAME="$(dirname "$LOG_FILE")"
BASENAME="$(basename "$LOG_FILE")"
ARCHIVE_FILE="${DIRNAME}/${BASENAME}.${STAMP}"

mv "$LOG_FILE" "$ARCHIVE_FILE"
echo "Archived ${LOG_FILE} -> ${ARCHIVE_FILE}"
