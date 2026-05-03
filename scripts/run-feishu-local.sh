#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="${ROOT_DIR}/.env.feishu.local"
WATCH_LOGS=false

for arg in "$@"; do
  case "$arg" in
    --watch-logs)
      WATCH_LOGS=true
      ;;
    *)
      echo "Unknown argument: $arg"
      echo "Usage: $0 [--watch-logs]"
      exit 1
      ;;
  esac
done

if [[ ! -f "${ENV_FILE}" ]]; then
  cat <<'EOF'
Missing local env file: .env.feishu.local

Setup:
  1. cp .env.feishu.local.example .env.feishu.local
  2. fill in your Feishu app credentials and model gateway settings
  3. rerun this script
EOF
  exit 1
fi

set -a
# shellcheck disable=SC1090
source "${ENV_FILE}"
set +a

# Feishu WebSocket is sensitive to inherited shell proxy settings.
# Force-disable proxies for this local debugging entrypoint so the SDK
# connects directly instead of trying to use a SOCKS proxy.
for proxy_var in ALL_PROXY all_proxy HTTP_PROXY HTTPS_PROXY http_proxy https_proxy; do
  unset "${proxy_var}" 2>/dev/null || true
done
export NO_PROXY='*'
export no_proxy='*'

required_vars=(
  FEISHU_APP_ID
  FEISHU_APP_SECRET
  DEERFLOW_OPENAI_BASE_URL
  DEERFLOW_OPENAI_API_KEY
  DEERFLOW_OPENAI_MODEL
)

missing=()
for var_name in "${required_vars[@]}"; do
  if [[ -z "${!var_name:-}" ]]; then
    missing+=("${var_name}")
  fi
done

if (( ${#missing[@]} > 0 )); then
  printf 'Missing required environment variables in .env.feishu.local:\n' >&2
  printf '  - %s\n' "${missing[@]}" >&2
  exit 1
fi

echo "Starting BadmintonCoachAgent with Feishu channel enabled..."
echo "Config file: ${ROOT_DIR}/config.yaml"
echo "Model: ${DEERFLOW_OPENAI_MODEL}"
echo "Mode: backend only (LangGraph + Gateway + Feishu channel)"
echo "Proxy: disabled for Feishu local debugging"

cd "${ROOT_DIR}"

mkdir -p "${ROOT_DIR}/logs"

echo "Stopping existing backend services if any..."
pkill -f "langgraph dev" 2>/dev/null || true
pkill -f "uvicorn app.gateway.app:app" 2>/dev/null || true
sleep 1

echo "Starting LangGraph server..."
./scripts/archive-log.sh "${ROOT_DIR}/logs/langgraph.log"
nohup sh -c 'cd backend && NO_COLOR=1 uv run langgraph dev --no-browser --allow-blocking --no-reload > ../logs/langgraph.log 2>&1' &
"${ROOT_DIR}/scripts/wait-for-port.sh" 2024 60 "LangGraph" || {
  echo "✗ LangGraph failed to start. Last log output:"
  tail -60 "${ROOT_DIR}/logs/langgraph.log"
  exit 1
}
echo "✓ LangGraph server started on localhost:2024"

echo "Starting Gateway API..."
./scripts/archive-log.sh "${ROOT_DIR}/logs/gateway.log"
nohup sh -c 'cd backend && PYTHONPATH=. uv run uvicorn app.gateway.app:app --host 0.0.0.0 --port 8001 > ../logs/gateway.log 2>&1' &
"${ROOT_DIR}/scripts/wait-for-port.sh" 8001 30 "Gateway API" || {
  echo "✗ Gateway API failed to start. Last log output:"
  tail -60 "${ROOT_DIR}/logs/gateway.log"
  exit 1
}
echo "✓ Gateway API started on localhost:8001"

echo ""
echo "Backend services are running."
echo " - LangGraph: http://localhost:2024"
echo " - Gateway: http://localhost:8001"
echo " - Gateway log: logs/gateway.log"
echo " - LangGraph log: logs/langgraph.log"
echo ""

if [[ "${WATCH_LOGS}" == "true" ]]; then
  echo "Watching logs/gateway.log"
  echo "Press Ctrl+C to stop watching logs. Services will keep running in background."
  echo ""
  exec tail -n 80 -f "${ROOT_DIR}/logs/gateway.log"
fi

echo "Tip: run './scripts/run-feishu-local.sh --watch-logs' to follow Feishu/Gateway logs."
