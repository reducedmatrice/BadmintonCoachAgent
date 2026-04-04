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

cd "${ROOT_DIR}"

if [[ "${WATCH_LOGS}" == "true" ]]; then
  echo "Starting services in background mode and following Gateway logs..."
  make dev-daemon
  echo ""
  echo "Watching logs/gateway.log"
  echo "Press Ctrl+C to stop watching logs. Services will keep running in background."
  echo ""
  exec tail -n 80 -f "${ROOT_DIR}/logs/gateway.log"
fi

echo "Tip: run './scripts/run-feishu-local.sh --watch-logs' if you want to see Feishu logs directly in this terminal."
exec make dev
