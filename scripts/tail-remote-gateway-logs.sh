#!/usr/bin/env bash
set -euo pipefail

TARGET="${1:-note-agent-server}"
MODE="${2:-tail}"  # tail | history | grep

# Log file path inside the container / on the host (volume-mounted)
LOG_FILE="/home/ubuntu/data/deer-flow/logs/gateway.log"

case "$MODE" in
  tail)
    # Live follow: file first (persists across rebuilds), fall back to docker logs
    echo "[remote-logs] tailing gateway log file (Ctrl+C to stop)..."
    exec ssh "$TARGET" "tail -f $LOG_FILE 2>/dev/null || docker logs -f --tail 200 deer-flow-gateway 2>&1"
    ;;
  history)
    # Show last N lines from the persisted log file
    LINES="${3:-200}"
    echo "[remote-logs] last $LINES lines from persisted log file:"
    exec ssh "$TARGET" "tail -n $LINES $LOG_FILE 2>/dev/null || docker logs --tail $LINES deer-flow-gateway 2>&1"
    ;;
  grep)
    # Search persisted log file
    PATTERN="${3:-ManagerStructured}"
    echo "[remote-logs] searching logs for: $PATTERN"
    exec ssh "$TARGET" "grep '$PATTERN' $LOG_FILE 2>/dev/null || docker logs deer-flow-gateway 2>&1 | grep '$PATTERN'"
    ;;
  *)
    echo "Usage: $0 [server] [tail|history|grep] [lines|pattern]"
    exit 1
    ;;
esac
